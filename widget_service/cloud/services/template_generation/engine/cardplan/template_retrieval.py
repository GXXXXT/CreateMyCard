"""Search CardTpl candidates from first-layer LLM field requirements.

Search deliberately does not select a final template, layout, component composition,
card size, or theme compatibility. Those are second-layer responsibilities. The 2x2
route currently admits one business with zero to two root Actions.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.logger import json_for_log, logger
from models.generation import CandidateDataBinding, TaskSpec
from services.template_generation.engine.advanced.data_shape import extract_data_shape
from services.template_generation.engine.advanced.models import (
    AdvancedScopeBrief,
    TemplateComponentCandidate,
    TemplateRouteSelection,
)

from .provider_bundle import provider_template_layout_kind
from .registry import CardPlanRegistry
from .retrieval_index import FieldToken, TemplateVariantSearchRecord

_MAX_COMPONENT_TEMPLATE_CANDIDATES = 24
_GENERIC_SCALAR_TYPES = frozenset({"string", "integer", "number", "boolean"})


class TemplateRetrievalMiss(ValueError):
    """No provider-backed component can cover the first-layer request."""


class TemplateRetrievalQuery(BaseModel):
    """The first-layer decision: theme, display demands, and explicit Action."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    theme_id: str = Field(alias="themeId", min_length=1)
    required_output_fields_by_capability: dict[str, tuple[str, ...]] = Field(
        alias="requiredOutputFieldsByCapability",
    )
    action_ids: tuple[str, ...] = Field(default=(), alias="action", max_length=2)

    @field_validator("required_output_fields_by_capability")
    @classmethod
    def valid_fields(cls, values: dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
        pattern = re.compile(r"^/(?:[^/~]|~[01])+(?:/(?:[^/~]|~[01])+)*$")
        for capability_id, paths in values.items():
            if not capability_id.strip() or len(paths) != len(set(paths)):
                raise ValueError("capability IDs and output fields must be unique")
            if any(pattern.fullmatch(path) is None for path in paths):
                raise ValueError("required output fields must be JSON Pointers")
        return values

    @field_validator("action_ids", mode="before")
    @classmethod
    def normalized_actions(cls, value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        values = (value,) if isinstance(value, str) else tuple(value)
        normalized = tuple(item.strip() for item in values if isinstance(item, str))
        if len(normalized) != len(values) or any(not item for item in normalized):
            raise ValueError("action must contain only non-empty eventIds")
        if len(normalized) != len(set(normalized)):
            raise ValueError("action eventIds must be unique")
        return normalized


def build_template_retrieval_prompt(
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    coverage_bindings: tuple[CandidateDataBinding, ...],
) -> list[dict[str, str]]:
    """Build the first-layer marker prompt without exposing final UI choices."""
    data_shape = extract_data_shape(task_spec)
    capability_ids = tuple(binding.capabilityId for binding in coverage_bindings)
    component_ids = _component_ids_for_capabilities(registry, capability_ids)
    theme_ids = registry.first_layer_theme_ids(component_ids)
    data_roots = {binding.capabilityId: binding.writeResultTo for binding in coverage_bindings}
    payload = {
        "userQuery": task_spec.userQuery,
        "taskSpec": task_spec.model_dump(mode="json"),
        "taskSpecDataFields": [
            {
                "path": field.path,
                "name": field.name,
                "dataType": field.data_type,
                "description": field.description,
                "roles": field.roles,
            }
            for field in data_shape.fields
        ],
        "candidateDataBindings": [binding.model_dump(mode="json") for binding in coverage_bindings],
        "candidateOutputFieldsByCapability": {
            binding.capabilityId: tuple(binding.candidateOutputFields)
            for binding in coverage_bindings
        },
        "themes": theme_ids,
        "actionCandidates": [
            {"eventId": event.id, "call": event.call}
            for event in task_spec.eventCandidates
            if event.id
        ],
        "providerFirstLayerRules": registry.provider_first_layer_rules(component_ids, data_roots),
        "themeFirstLayerRules": registry.theme_first_layer_rule_documents(theme_ids),
    }
    schema = TemplateRetrievalQuery.model_json_schema(by_alias=True)
    system = (
        "你是模板生成第一层。只输出 template-retrieval-query/1 JSON。"
        "themeId 必须从 themes 选择；themes 已由服务按当前业务确定性过滤，"
        "存在融球候选时不会再包含非融球主题。"
        "requiredOutputFieldsByCapability 的 key 必须来自 "
        "candidateDataBindings。每个 value 仅保留 userQuery、title、description 或 taskSpec "
        "明确要求展示的字段，字段必须逐字来自 "
        "candidateOutputFieldsByCapability；不得按模板反推字段，"
        "也不得补全用户未要求展示的字段。"
        "不得为了迁就布局限制而省略用户明确要求的其他业务字段；"
        "2x2 模板 Search 当前只接受一个可完整覆盖的业务，"
        "多个业务由服务端确定性判定模板不适用；2x4 可按 Wide 布局容量保留多个业务。"
        "用户只要求某领域卡片、未明确字段时，该 capability 输出空数组。"
        "action 仅当用户明确要求点击、跳转或操作时才选择 actionCandidates 中"
        "语义一致的零到两个不重复 eventId；不能因候选事件存在而默认选择。"
        "不得输出组件、模板、Variant、尺寸、布局、Props 或理由。\n"
        + json.dumps(schema, ensure_ascii=False)
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def retrieve_template_variants(
    query: TemplateRetrievalQuery,
    task_spec: TaskSpec,
    registry: CardPlanRegistry,
    coverage_bindings: tuple[CandidateDataBinding, ...],
    card_spec: dict[str, Any],
    *,
    preferred_template_ids: tuple[str, ...] = (),
) -> TemplateRouteSelection:
    """Return component candidate sets; never choose a final CardTpl variant."""
    selected_theme = registry.require_theme(query.theme_id)
    if selected_theme.supported_layout_ids:
        raise TemplateRetrievalMiss("first-layer Theme must not be layout-scoped")
    _validate_selected_actions(query, task_spec)
    action_count = _selected_action_count(query, task_spec)
    preferred_layout_suffix = {1: "Hero", 2: "Compact"}.get(action_count)
    if not query.required_output_fields_by_capability:
        raise TemplateRetrievalMiss("template retrieval has no requested capability")
    candidate_ids = {binding.capabilityId for binding in coverage_bindings}
    if not set(query.required_output_fields_by_capability).issubset(candidate_ids):
        raise TemplateRetrievalMiss("requested capability is outside candidate data bindings")

    by_component: dict[str, set[str]] = {}
    required_groups: list[tuple[str, ...]] = []
    for capability_id, paths in query.required_output_fields_by_capability.items():
        candidate_paths = _candidate_paths(coverage_bindings, capability_id)
        if not set(paths).issubset(candidate_paths):
            raise TemplateRetrievalMiss("required output fields must come from candidates")
        data_root = _capability_data_root(card_spec, capability_id)
        query_tokens = frozenset(
            _task_spec_field_token(task_spec, data_root, capability_id, path) for path in paths
        )
        component_templates = _component_templates_for_capability(
            registry,
            capability_id,
            query_tokens,
            task_spec,
            card_spec,
            preferred_template_ids,
            preferred_layout_suffix,
            candidate_output_fields=candidate_paths,
        )
        if not component_templates:
            raise TemplateRetrievalMiss(
                f"no provider template covers capability {capability_id} and its requested fields"
            )
        required_groups.extend(_required_field_template_groups(query_tokens, component_templates))
        for component_id, template_paths in component_templates.items():
            by_component.setdefault(component_id, set()).update(template_paths)

    # Specialized health components can all match the same summary capability.
    # Prefer the specialized component whose single Template covers the most
    # requested fields, then use GenericMetricOverview only for the residual
    # fields.  Generic is a bounded fallback slot, never the primary business.
    repeated_generic_compact_slots = False
    primary_health: str | None = None
    primary_template_ids: set[str] = set()
    if task_spec.size == "2x4":
        health_ids = {
            "ActivityOverview", "WorkoutOverview", "HeartRateOverview",
            "SleepOverview", "GenericMetricOverview",
        }
        selected_health = health_ids.intersection(by_component)
        if len(selected_health) >= 2 and "GenericMetricOverview" in by_component:
            specialized_health = sorted(selected_health - {"GenericMetricOverview"})
            primary_coverage = 0
            for component_id in specialized_health:
                component_ids = by_component[component_id]
                coverage_by_template = {
                    template_id: sum(template_id in group for group in required_groups)
                    for template_id in component_ids
                }
                component_coverage = max(coverage_by_template.values(), default=0)
                best_ids = {
                    template_id
                    for template_id, coverage in coverage_by_template.items()
                    if coverage == component_coverage
                }
                # Stable tie-breaking keeps the richer domain view ahead of a
                # single-purpose metric view.
                priority = {
                    "SleepOverview": 0,
                    "ActivityOverview": 1,
                    "WorkoutOverview": 2,
                    "HeartRateOverview": 3,
                }.get(component_id, 9)
                current_priority = {
                    "SleepOverview": 0,
                    "ActivityOverview": 1,
                    "WorkoutOverview": 2,
                    "HeartRateOverview": 3,
                }.get(primary_health or "", 9)
                if component_coverage > primary_coverage or (
                    component_coverage == primary_coverage and priority < current_priority
                ):
                    primary_health = component_id
                    primary_template_ids = best_ids
                    primary_coverage = component_coverage

            for component_id in selected_health:
                if component_id not in {"GenericMetricOverview", primary_health}:
                    by_component.pop(component_id, None)

            if primary_health is not None:
                by_component[primary_health].intersection_update(primary_template_ids)

            generic_ids = by_component["GenericMetricOverview"]
            residual_groups: list[tuple[str, ...]] = []
            generic_field_count = 0
            for group in required_groups:
                group_ids = set(group)
                if primary_template_ids.intersection(group_ids):
                    # The specialized primary owns this field; do not also
                    # advertise it as a Generic parameter candidate.
                    residual_groups.append(
                        tuple(item for item in group if item not in generic_ids)
                    )
                    continue
                residual_groups.append(group)
                if generic_ids.intersection(group_ids):
                    generic_field_count += 1
            required_groups = residual_groups
            if generic_field_count > 2:
                logger.info(
                    "[Template Retrieval] generic_capacity_exceeded "
                    f"primary_component={primary_health} "
                    f"primary_coverage={primary_coverage} "
                    f"residual_field_count={generic_field_count} capacity=2"
                )
                raise TemplateRetrievalMiss(
                    "generic compact capacity cannot cover all residual requested fields"
                )
            if generic_field_count == 0:
                by_component.pop("GenericMetricOverview", None)
                generic_ids = set()
            preferred_generic_name = "GenericMetricOverviewCompact@1"
            if generic_ids and preferred_generic_name in generic_ids:
                # Generic Compact is repeatable. For two residual metrics, keep
                # two separate Compact slots so 2x4 can use the existing
                # WideFullTwoCompactLayout instead of a dedicated Full+Compact
                # layout. The repeated slot marker is materialized below in
                # required_groups; componentCandidates remains de-duplicated.
                by_component["GenericMetricOverview"] = {preferred_generic_name}
                repeated_generic_compact_slots = generic_field_count >= 2
            logger.info(
                "[Template Retrieval] specialized_primary_selected "
                f"component_id={primary_health} coverage={primary_coverage} "
                f"template_ids={sorted(primary_template_ids)} "
                f"generic_residual_count={generic_field_count}"
            )

            # Current 2x4 layouts provide three visible slots in total.  With
            # an explicit Action, only two slots remain for business content.
            # Do not silently discard the specialized primary or pretend that
            # a bounded Generic Compact covers an arbitrary number of fields.
            required_slot_count = len(by_component) + action_count
            if action_count and len(by_component) > 2:
                requested_fields = {
                    capability_id: list(paths)
                    for capability_id, paths in query.required_output_fields_by_capability.items()
                }
                logger.info(
                    "[Template Retrieval] layout_capacity_exceeded "
                    f"card_size=2x4 available_slot_count=3 "
                    f"required_slot_count={required_slot_count} "
                    f"business_components={sorted(by_component)} "
                    f"action_count={action_count} "
                    f"requested_fields={json_for_log(requested_fields)}"
                )
                raise TemplateRetrievalMiss(
                    "2x4 layout capacity is insufficient for the specialized primary, "
                    "generic residual metrics, and selected Action"
                )

    candidates = tuple(
        TemplateComponentCandidate(
            componentId=component_id,
            availableTemplateIds=tuple(sorted(template_ids)),
        )
        for component_id, template_ids in sorted(
            by_component.items(), key=_component_candidate_order_key
        )
    )
    resolved_theme_id = query.theme_id
    if task_spec.size == "2x2":
        candidates, required_groups = _apply_2x2_combination_policy(
            candidates,
            action_count,
            required_groups,
        )
    else:
        candidates = tuple(
            _candidate_with_complete_field_coverage(candidate, required_groups)
            for candidate in candidates
        )
        required_groups = [candidate.available_template_ids for candidate in candidates]
        if repeated_generic_compact_slots and primary_health is not None:
            primary_group = next(
                (
                    candidate.available_template_ids
                    for candidate in candidates
                    if candidate.component_id == primary_health
                ),
                (),
            )
            generic_group = next(
                (
                    candidate.available_template_ids
                    for candidate in candidates
                    if candidate.component_id == "GenericMetricOverview"
                ),
                (),
            )
            if primary_group and generic_group:
                required_groups = [primary_group, generic_group, generic_group]
    logger.info(
        "[Template Retrieval] candidate_groups_resolved "
        f"group_count={len(required_groups)} "
        f"groups={json_for_log([list(group) for group in required_groups])} "
        f"repeated_generic_compact_slots={repeated_generic_compact_slots}"
    )
    scope = AdvancedScopeBrief(
        themeId=resolved_theme_id,
        advancedComponentIds=tuple(candidate.component_id for candidate in candidates),
    )
    return TemplateRouteSelection(
        scope=scope,
        componentCandidates=candidates,
        actionIds=query.action_ids,
        requiredTemplateGroups=tuple(required_groups),
        requiredOutputFieldsByCapability=query.required_output_fields_by_capability,
    )


def _component_candidate_order_key(
    item: tuple[str, set[str]],
) -> tuple[int, str]:
    """Place the visually larger business before Compact-only support slots."""
    component_id, template_ids = item
    compact_only = all(
        provider_template_layout_kind(template_id) == "Compact"
        for template_id in template_ids
    )
    return (1 if compact_only else 0, component_id)


def restrict_query_to_preferred_templates(
    query: TemplateRetrievalQuery,
    registry: CardPlanRegistry,
    preferred_template_ids: tuple[str, ...],
) -> TemplateRetrievalQuery:
    """Keep gallery-only field demand within its explicitly trusted templates."""
    if not preferred_template_ids:
        return query
    preferred_ids = set(preferred_template_ids)
    available_paths_by_capability: dict[str, set[str]] = {}
    matched_ids: set[str] = set()
    for record in registry.template_variant_search_records:
        if record.template_id not in preferred_ids:
            continue
        matched_ids.add(record.template_id)
        available_paths_by_capability.setdefault(record.capability_id, set()).update(
            record.available_paths
        )
    if matched_ids != preferred_ids:
        raise TemplateRetrievalMiss("trusted template candidate is outside Search records")
    required_fields = {
        capability_id: tuple(
            path
            for path in paths
            if path in available_paths_by_capability.get(capability_id, set())
        )
        for capability_id, paths in query.required_output_fields_by_capability.items()
    }
    return query.model_copy(
        update={"required_output_fields_by_capability": required_fields}
    )


def _apply_2x2_combination_policy(
    candidates: tuple[TemplateComponentCandidate, ...],
    action_count: int,
    required_groups: list[tuple[str, ...]],
) -> tuple[tuple[TemplateComponentCandidate, ...], list[tuple[str, ...]]]:
    """Restrict 2x2 candidates to the business and Action capacity contract."""
    component_count = len(candidates)
    if component_count > 1:
        raise TemplateRetrievalMiss(
            "2x2 template Search does not support multiple data businesses"
        )
    if action_count >= 3:
        raise TemplateRetrievalMiss("2x2 template Search supports at most two Actions")
    if component_count == 1:
        layout_suffixes = {
            0: ("Full",),
            1: ("Hero", "Full"),
            2: ("Compact",),
        }[action_count]
    else:
        raise TemplateRetrievalMiss("template Search found no business component")

    business_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        business_candidates.append(
            {
                "businessId": candidate.component_id,
                "availableTemplateIds": list(candidate.available_template_ids),
            }
        )
    layout_label = "/".join(layout_suffixes)
    layout_diagnostics = {
        "businessCount": component_count,
        "actionCount": action_count,
        "requiredLayoutSuffixes": list(layout_suffixes),
        "requiredLayoutLabel": layout_label,
        "businessCandidates": business_candidates,
    }
    logger.info(
        "[Template Retrieval] layout_policy_selected "
        f"diagnostics={json_for_log(layout_diagnostics)}"
    )

    filtered_candidates = tuple(
        _candidate_with_layout_suffixes(candidate, layout_suffixes) for candidate in candidates
    )
    allowed_template_ids = {
        template_id
        for candidate in filtered_candidates
        for template_id in candidate.available_template_ids
    }
    filtered_groups = [
        tuple(template_id for template_id in group if template_id in allowed_template_ids)
        for group in required_groups
    ]
    if any(not group for group in filtered_groups):
        diagnostics = {
            "requiredLayoutSuffixes": list(layout_suffixes),
            "requiredTemplateGroupsBeforeLayout": [list(group) for group in required_groups],
            "requiredTemplateGroupsAfterLayout": [list(group) for group in filtered_groups],
            "layoutCompatibleTemplateIds": sorted(allowed_template_ids),
        }
        logger.info(
            "[Template Retrieval] layout_field_coverage_mismatch "
            f"diagnostics={json_for_log(diagnostics)}"
        )
        raise TemplateRetrievalMiss(
            f"2x2 {layout_label} templates cannot cover all requested fields"
        )
    for candidate in filtered_candidates:
        _require_single_template_coverage(candidate, filtered_groups, layout_label)
    return filtered_candidates, filtered_groups


def _selected_action_count(query: TemplateRetrievalQuery, task_spec: TaskSpec) -> int:
    selected_action_ids = set(query.action_ids)
    count = 0
    for event in task_spec.eventCandidates:
        if event.id in selected_action_ids:
            count += 1
    return count


def _candidate_with_layout_suffixes(
    candidate: TemplateComponentCandidate,
    layout_suffixes: tuple[str, ...],
) -> TemplateComponentCandidate:
    matching_template_ids: list[str] = []
    for template_id in candidate.available_template_ids:
        has_layout_suffix = False
        for suffix in layout_suffixes:
            if _template_has_layout_suffix(template_id, suffix):
                has_layout_suffix = True
                break
        if has_layout_suffix:
            matching_template_ids.append(template_id)
    template_ids = tuple(matching_template_ids)
    if not template_ids:
        layout_label = "/".join(layout_suffixes)
        diagnostics = {
            "businessId": candidate.component_id,
            "requiredLayoutSuffixes": list(layout_suffixes),
            "requiredLayoutLabel": layout_label,
            "availableTemplateIds": list(candidate.available_template_ids),
        }
        logger.info(
            "[Template Retrieval] layout_suffix_mismatch "
            f"diagnostics={json_for_log(diagnostics)}"
        )
        raise TemplateRetrievalMiss(
            f"2x2 business {candidate.component_id} has no {layout_label} template"
        )
    return candidate.model_copy(update={"available_template_ids": template_ids})


def _require_single_template_coverage(
    candidate: TemplateComponentCandidate,
    required_groups: list[tuple[str, ...]],
    layout_suffix: str,
) -> None:
    """A 2x2 business slot must use one layout-compatible business template."""
    candidate_ids = set(candidate.available_template_ids)
    component_groups = [
        set(group).intersection(candidate_ids)
        for group in required_groups
        if set(group).intersection(candidate_ids)
    ]
    if component_groups and not set.intersection(*component_groups):
        diagnostics = {
            "businessId": candidate.component_id,
            "requiredLayoutLabel": layout_suffix,
            "availableTemplateIds": list(candidate.available_template_ids),
            "requiredTemplateGroups": [sorted(group) for group in component_groups],
        }
        logger.info(
            "[Template Retrieval] single_template_coverage_mismatch "
            f"diagnostics={json_for_log(diagnostics)}"
        )
        raise TemplateRetrievalMiss(
            f"2x2 {layout_suffix} templates cannot cover one {candidate.component_id} slot"
        )


def _template_has_layout_suffix(template_id: str, layout_suffix: str) -> bool:
    """Match the declared business-template layout before its version suffix."""
    template_name, separator, version = template_id.rpartition("@")
    return bool(separator and version and template_name.endswith(layout_suffix))


def _candidate_with_complete_field_coverage(
    candidate: TemplateComponentCandidate,
    required_groups: list[tuple[str, ...]],
) -> TemplateComponentCandidate:
    """Keep only candidates that independently cover the first-layer display demand."""
    candidate_ids = set(candidate.available_template_ids)
    component_groups = [
        set(group).intersection(candidate_ids)
        for group in required_groups
        if set(group).intersection(candidate_ids)
    ]
    complete_ids = set.intersection(*component_groups) if component_groups else candidate_ids
    if not complete_ids:
        raise TemplateRetrievalMiss(
            f"template candidates cannot cover one {candidate.component_id} slot"
        )
    template_ids = tuple(
        template_id
        for template_id in candidate.available_template_ids
        if template_id in complete_ids
    )
    return candidate.model_copy(update={"available_template_ids": template_ids})


def _component_templates_for_capability(
    registry: CardPlanRegistry,
    capability_id: str,
    query_tokens: frozenset[FieldToken],
    task_spec: TaskSpec,
    card_spec: dict[str, Any],
    preferred_template_ids: tuple[str, ...] = (),
    preferred_layout_suffix: str | None = None,
    candidate_output_fields: set[str] | None = None,
) -> dict[str, dict[str, frozenset[str]]]:
    result: dict[str, dict[str, frozenset[str]]] = {}
    data_root = _capability_data_root(card_spec, capability_id)
    provided_output_fields = candidate_output_fields or set()
    task_spec_available_fields = _task_spec_field_entries(task_spec, data_root)
    business_ids = {
        record.business_id
        for record in registry.template_variant_search_records
        if record.capability_id == capability_id
    }
    for business_id in sorted(business_ids):
        group = registry.ux_business_components[business_id]
        template_ids = set(registry.enabled_template_ids(group.local_template_ids))
        matches: dict[str, frozenset[str]] = {}
        evaluations: list[dict[str, Any]] = []
        for record in registry.template_variant_search_records:
            if record.capability_id != capability_id or record.business_id != business_id:
                continue
            evaluations.append(
                _template_record_evaluation(
                    record,
                    task_spec,
                    data_root,
                    query_tokens,
                    template_ids,
                )
            )
            if record.template_id not in template_ids:
                continue
            size_is_supported = _template_can_participate_in_size(record, task_spec.size)
            if not size_is_supported:
                continue
            if not _template_required_fields_are_available(record, task_spec, card_spec):
                continue
            if business_id == "GenericMetricOverview" and task_spec.size == "2x4":
                # Generic Compact templates deliberately have no fixed field
                # allowlist in the 2x4 residual-composition route. Their path
                # props are constrained by the current candidate output fields
                # and the token type check above. Generic is deliberately not
                # admitted as a second business in 2x2, where the existing
                # single-business layout contract must remain unchanged.
                matches[record.template_id] = frozenset(
                    token.path
                    for token in query_tokens
                    if token.path in provided_output_fields
                    and token.data_type in _GENERIC_SCALAR_TYPES
                )
            else:
                matches[record.template_id] = _record_available_query_paths(
                    record, query_tokens
                )
        if query_tokens:
            matches = {template_id: paths for template_id, paths in matches.items() if paths}
        limited_matches: dict[str, frozenset[str]] = {}
        if matches:
            limited_matches = _limit_component_templates(
                matches,
                registry.enabled_template_ids(group.local_template_ids),
                query_tokens,
                preferred_template_ids,
                preferred_layout_suffix,
            )
            result[business_id] = limited_matches
        _log_template_candidate_evaluation(
            capability_id=capability_id,
            business_id=business_id,
            data_root=data_root,
            card_size=task_spec.size,
            user_required_fields=_field_entries_for_tokens(query_tokens),
            candidate_output_fields=provided_output_fields,
            task_spec_available_fields=task_spec_available_fields,
            disabled_provider_ids=set(getattr(registry, "disabled_provider_ids", ())),
            disabled_template_ids=set(getattr(registry, "disabled_template_ids", ())),
            evaluations=evaluations,
            matches=matches,
            limited_matches=limited_matches,
        )
    covered_paths: set[str] = set()
    for templates in result.values():
        for paths in templates.values():
            covered_paths.update(paths)
    if not {token.path for token in query_tokens}.issubset(covered_paths):
        return {}
    return result


def _limit_component_templates(
    matches: dict[str, frozenset[str]],
    declared_template_ids: tuple[str, ...],
    query_tokens: frozenset[FieldToken],
    preferred_template_ids: tuple[str, ...] = (),
    preferred_layout_suffix: str | None = None,
) -> dict[str, frozenset[str]]:
    """Keep the upstream candidate bound without dropping field coverage."""
    selected = [
        template_id
        for template_id in preferred_template_ids
        if template_id in matches
    ]
    layout_matches: list[str] = []
    if preferred_layout_suffix is not None:
        for template_id in declared_template_ids:
            if template_id not in matches:
                continue
            if not _template_has_layout_suffix(template_id, preferred_layout_suffix):
                continue
            layout_matches.append(template_id)
    for token in sorted(query_tokens):
        template_id = next(
            (item for item in layout_matches if token.path in matches[item]),
            None,
        )
        if template_id is not None and template_id not in selected:
            selected.append(template_id)
    if not query_tokens and layout_matches:
        selected.append(layout_matches[0])
    for token in sorted(query_tokens):
        template_id = next(
            (
                item
                for item in declared_template_ids
                if item in matches and token.path in matches[item]
            ),
            None,
        )
        if template_id is not None and template_id not in selected:
            selected.append(template_id)
    selected.extend(
        template_id
        for template_id in declared_template_ids
        if template_id in matches and template_id not in selected
    )
    selected = selected[:_MAX_COMPONENT_TEMPLATE_CANDIDATES]
    return {template_id: matches[template_id] for template_id in selected}


def _template_record_evaluation(
    record: TemplateVariantSearchRecord,
    task_spec: TaskSpec,
    data_root: str,
    query_tokens: frozenset[FieldToken],
    enabled_template_ids: set[str],
) -> dict[str, Any]:
    """构造单模板的字段覆盖诊断，不记录用户数据值。"""
    missing_required_fields: list[str] = []
    required_type_mismatches: list[dict[str, str]] = []
    required_types = {token.path: token.data_type for token in record.required_field_tokens}
    for path in sorted(record.required_paths):
        pointer = f"{data_root.rstrip('/')}{path}"
        leaf = _task_spec_schema_leaf(task_spec.dataModelSchema, pointer)
        if leaf is None:
            missing_required_fields.append(path)
            continue
        expected_type = required_types.get(path)
        actual_type = leaf.get("type")
        if expected_type is None or actual_type == expected_type:
            continue
        required_type_mismatches.append(
            {
                "path": path,
                "expectedType": expected_type,
                "actualType": actual_type if isinstance(actual_type, str) else "",
            }
        )

    if record.business_id == "GenericMetricOverview" and task_spec.size == "2x4":
        # GenericMetricOverview has no fixed provider field list on the wide
        # residual route. Its candidate fields are validated before this
        # diagnostic is built, so report the requested scalar paths as covered
        # instead of using the empty metadata allowlist.
        matched_user_fields = frozenset(token.path for token in query_tokens)
    else:
        matched_user_fields = _record_available_query_paths(record, query_tokens)
    unmatched_user_fields = sorted(token.path for token in query_tokens)
    unmatched_user_fields = [
        path for path in unmatched_user_fields if path not in matched_user_fields
    ]
    user_type_mismatches = _user_required_type_mismatches(record, query_tokens)
    rejection_reasons: list[str] = []
    if record.template_id not in enabled_template_ids:
        rejection_reasons.append("template_disabled")
    size_is_supported = _template_can_participate_in_size(record, task_spec.size)
    if not size_is_supported:
        rejection_reasons.append("card_size_not_supported")
    if missing_required_fields:
        rejection_reasons.append("user_provided_data_missing_template_required_fields")
    if required_type_mismatches:
        rejection_reasons.append("user_provided_data_type_mismatch")
    if query_tokens and not matched_user_fields:
        rejection_reasons.append("user_required_data_not_covered")

    return {
        "templateId": record.template_id,
        "templateEnabled": record.template_id in enabled_template_ids,
        "supportedCardSizes": sorted(record.supported_card_sizes),
        "matchedUserRequiredFields": sorted(matched_user_fields),
        "unmatchedUserRequiredFields": unmatched_user_fields,
        "missingTemplateRequiredFields": missing_required_fields,
        "templateRequiredFieldTypeMismatches": required_type_mismatches,
        "userRequiredFieldTypeMismatches": user_type_mismatches,
        "userRequiredDataFullyCovered": not unmatched_user_fields,
        "userProvidedDataSatisfiesTemplateRequirements": (
            not missing_required_fields and not required_type_mismatches
        ),
        "rejectionReasons": rejection_reasons,
    }


def _template_can_participate_in_size(
    record: TemplateVariantSearchRecord,
    card_size: str,
) -> bool:
    """Allow standard business shapes inside a 2x4 composition layout."""
    if not record.supported_card_sizes or card_size in record.supported_card_sizes:
        return True
    if card_size != "2x4":
        return False
    return provider_template_layout_kind(record.template_id) in {
        "Full",
        "Hero",
        "Compact",
    }


def _user_required_type_mismatches(
    record: TemplateVariantSearchRecord,
    query_tokens: frozenset[FieldToken],
) -> list[dict[str, str]]:
    template_types = {token.path: token.data_type for token in record.field_tokens}
    mismatches: list[dict[str, str]] = []
    for token in sorted(query_tokens):
        expected_type = template_types.get(token.path)
        if expected_type is None or expected_type == token.data_type:
            continue
        mismatches.append(
            {
                "path": token.path,
                "templateType": expected_type,
                "userDataType": token.data_type,
            }
        )
    return mismatches


def _field_entries_for_tokens(tokens: frozenset[FieldToken]) -> list[dict[str, str]]:
    return [{"path": token.path, "type": token.data_type} for token in sorted(tokens)]


def _task_spec_field_entries(task_spec: TaskSpec, data_root: str) -> list[dict[str, str]]:
    prefix = f"{data_root.rstrip('/')}/"
    entries: list[dict[str, str]] = []
    for field in extract_data_shape(task_spec).fields:
        if not field.path.startswith(prefix):
            continue
        relative_path = f"/{field.path.removeprefix(prefix)}"
        entries.append({"path": relative_path, "type": field.data_type})
    return sorted(entries, key=lambda item: item.get("path", ""))


def _log_template_candidate_evaluation(
    *,
    capability_id: str,
    business_id: str,
    data_root: str,
    card_size: str,
    user_required_fields: list[dict[str, str]],
    candidate_output_fields: set[str],
    task_spec_available_fields: list[dict[str, str]],
    disabled_provider_ids: set[str],
    disabled_template_ids: set[str],
    evaluations: list[dict[str, Any]],
    matches: dict[str, frozenset[str]],
    limited_matches: dict[str, frozenset[str]],
) -> None:
    eligible_ids = list(matches)
    selected_ids = list(limited_matches)
    selected_set = set(selected_ids)
    dropped_ids = [template_id for template_id in eligible_ids if template_id not in selected_set]
    for evaluation in evaluations:
        template_id = evaluation.get("templateId")
        is_eligible = isinstance(template_id, str) and template_id in matches
        is_selected = isinstance(template_id, str) and template_id in limited_matches
        evaluation.update(
            {
                "eligibleBeforeCandidateLimit": is_eligible,
                "selectedAfterCandidateLimit": is_selected,
            }
        )
        if not is_eligible or is_selected:
            continue
        reasons = evaluation.get("rejectionReasons")
        if isinstance(reasons, list):
            reasons.append("candidate_limit_exceeded")

    diagnostics = {
        "capabilityId": capability_id,
        "businessId": business_id,
        "dataRoot": data_root,
        "cardSize": card_size,
        "userRequiredFields": user_required_fields,
        "candidateOutputFields": sorted(candidate_output_fields),
        "taskSpecAvailableFields": task_spec_available_fields,
        "disabledProviderIds": sorted(disabled_provider_ids),
        "disabledTemplateIds": sorted(disabled_template_ids),
        "eligibleTemplateIdsBeforeLimit": eligible_ids,
        "selectedTemplateIdsAfterLimit": selected_ids,
        "droppedByCandidateLimit": dropped_ids,
        "templates": evaluations,
    }
    logger.info(
        "[Template Retrieval] candidate_evaluation "
        f"diagnostics={json_for_log(diagnostics)}"
    )


def _required_field_template_groups(
    query_tokens: frozenset[FieldToken],
    component_templates: dict[str, dict[str, frozenset[str]]],
) -> tuple[tuple[str, ...], ...]:
    if not query_tokens:
        template_ids: set[str] = set()
        for templates in component_templates.values():
            template_ids.update(templates)
        return (tuple(sorted(template_ids)),)
    groups: list[tuple[str, ...]] = []
    for token in sorted(query_tokens):
        matching_template_ids: list[str] = []
        for templates in component_templates.values():
            for template_id, paths in templates.items():
                if token.path in paths:
                    matching_template_ids.append(template_id)
        groups.append(tuple(sorted(matching_template_ids)))
    return tuple(groups)


def _component_ids_for_capabilities(
    registry: CardPlanRegistry,
    capability_ids: tuple[str, ...],
) -> tuple[str, ...]:
    wanted = set(capability_ids)
    return tuple(
        business_id
        for business_id, component in registry.ux_business_components.items()
        if wanted.intersection(component.data_capability_ids)
    )


def _candidate_paths(
    coverage_bindings: tuple[CandidateDataBinding, ...], capability_id: str
) -> set[str]:
    matching = [item for item in coverage_bindings if item.capabilityId == capability_id]
    if len(matching) != 1:
        raise TemplateRetrievalMiss("template retrieval requires one binding per capability")
    return set(matching[0].candidateOutputFields)


def _capability_data_root(card_spec: dict[str, Any], capability_id: str) -> str:
    bindings = card_spec.get("dataBindings")
    if not isinstance(bindings, list):
        raise TemplateRetrievalMiss("CardSpec data bindings are unavailable")
    roots = {
        item.get("writeResultTo")
        for item in bindings
        if isinstance(item, dict) and item.get("capabilityId") == capability_id
    }
    valid = {root for root in roots if isinstance(root, str) and root.startswith("/data")}
    if len(valid) != 1:
        raise TemplateRetrievalMiss("capability data root is unavailable or ambiguous")
    return next(iter(valid))


def _task_spec_field_token(
    task_spec: TaskSpec, data_root: str, capability_id: str, relative_path: str
) -> FieldToken:
    pointer = f"{data_root.rstrip('/')}{relative_path}"
    leaf = _task_spec_schema_leaf(task_spec.dataModelSchema, pointer)
    if leaf is None or not isinstance(leaf.get("type"), str):
        raise TemplateRetrievalMiss(
            f"required output field is absent or untyped in TaskSpec: {relative_path}"
        )
    return FieldToken(capability_id, relative_path, str(leaf["type"]))


def _task_spec_schema_leaf(schema: dict[str, Any], pointer: str) -> dict[str, Any] | None:
    current: Any = schema
    for raw_part in pointer.removeprefix("/").split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part == "0" and current:
            current = current[0]
        else:
            return None
    return current if isinstance(current, dict) else None


def _record_available_query_paths(
    record: TemplateVariantSearchRecord,
    query_tokens: frozenset[FieldToken],
) -> frozenset[str]:
    typed_by_path = {token.path: token.data_type for token in record.field_tokens}
    available_paths: set[str] = set()
    for token in query_tokens:
        if token.path not in record.available_paths:
            continue
        expected_type = typed_by_path.get(token.path, token.data_type)
        if expected_type == token.data_type:
            available_paths.add(token.path)
    return frozenset(available_paths)


def _validate_selected_actions(query: TemplateRetrievalQuery, task_spec: TaskSpec) -> None:
    if not query.action_ids:
        return
    action_ids = {event.id for event in task_spec.eventCandidates if event.id}
    if not set(query.action_ids).issubset(action_ids):
        raise TemplateRetrievalMiss("selected Action is outside TaskSpec.eventCandidates")


def _template_required_fields_are_available(
    record: TemplateVariantSearchRecord,
    task_spec: TaskSpec,
    card_spec: dict[str, Any],
) -> bool:
    data_root = _capability_data_root(card_spec, record.capability_id)
    for path in record.required_paths:
        pointer = f"{data_root.rstrip('/')}{path}"
        if _task_spec_schema_leaf(task_spec.dataModelSchema, pointer) is None:
            return False
    for token in record.required_field_tokens:
        pointer = f"{data_root.rstrip('/')}{token.path}"
        leaf = _task_spec_schema_leaf(task_spec.dataModelSchema, pointer)
        if leaf is None or leaf.get("type") != token.data_type:
            return False
    return True
