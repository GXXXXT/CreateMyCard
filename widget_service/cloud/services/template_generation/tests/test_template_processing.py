"""模板生成、来源分流、布局预算及最终语义校验的串联回归。"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from models.capability import DataCapability
from models.generation import CandidateDataBinding, EventAction, TaskSpec
from services.card_validation import ValidationOptions, validate_card
from services.card_validation.compact_dsl_validator import (
    CompactDslValidationError,
    validate_compact_dsl_height,
)
from services.generation_pipeline import (
    DslProcessingContext,
    DslProcessorKind,
    get_dsl_processor,
)
from services.protocol_registry import A2UIProtocolRegistry
from services.task_spec_builder import TaskSpecBuilder
from services.template_generation.engine.cardplan.compiler import _generic_metric_display_value
from services.template_generation.engine.cardplan.preview_dataset import _template_parameters
from services.template_generation.engine.cardplan.prompt import action_bindings
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.cardplan.template_retrieval import TemplateSearchIntent
from services.template_generation.engine.pipeline import generate_template_a2ui
from services.template_generation.engine.tersel_converter import TerselConversionError
from services.template_generation.source_adapter import prepare_template_source_dsl
from services.template_generation.tests.test_template_generation import (
    _WEATHER_TEMPLATE_FIELDS,
    WeatherTemplateModel,
    _weather_card_spec,
    _weather_task_spec,
)
from services.template_generation.tests.test_template_retrieval import (
    _WEATHER_BATTERY_BINDINGS,
    _weather_battery_card_spec,
    _weather_battery_task,
)
from services.template_generation.tests.test_wide_template_planner import _health_case, _PlanModel

_CAPABILITIES = Path(__file__).resolve().parents[3] / "data/capabilities/app-11.7.7.300_rom-7.0"


def _data_capabilities():
    values = json.loads((_CAPABILITIES / "data_capabilities.json").read_text(encoding="utf-8"))
    return [DataCapability.model_validate(value) for value in values]


def _complete_card(card):
    result = dict(card)
    result.setdefault("description", "查看当前数据")
    bindings = []
    for binding in card.get("dataBindings", []):
        value = dict(binding)
        value.setdefault("arguments", {})
        bindings.append(value)
    result["dataBindings"] = bindings
    return result


def _process_and_validate(output, card, kind):
    task = output.projected_task_spec
    card = _complete_card(card)
    profile = A2UIProtocolRegistry().get_profile()
    source = prepare_template_source_dsl(
        output.a2ui,
        processor_kind=kind,
        size=task.size,
        protocol_profile=profile,
    )
    context = DslProcessingContext(
        size=task.size,
        task_spec=task.model_dump(mode="json"),
        card_spec=card,
        protocol_profile=profile,
        data_capabilities=_data_capabilities(),
        source_kind="template",
    )
    result = get_dsl_processor(kind).process(source, context)
    assert not result.errors, result.errors
    effective_data = []
    for binding in card.get("dataBindings", []):
        effective_data.append(binding.get("capabilityId"))
    report = validate_card(
        artifact={
            "genui": result.standard_dsl,
            "cardSpec": card,
            "taskSpec": context.task_spec,
            "effectiveCapabilities": {
                "data": effective_data,
                "event": context.task_spec.get("eventCandidates", []),
                "asset": task.assetCandidates,
            },
        },
        options=ValidationOptions(capabilities_dir=_CAPABILITIES),
    )
    assert not report.has_error(), report.render_text()
    return source, context


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", tuple(DslProcessorKind))
@pytest.mark.parametrize("with_actions", (False, True))
async def test_wide_weather_battery_preserves_template_design_and_validates(kind, with_actions):
    task = _weather_battery_task(with_actions)
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={
            "ViewWeather": ("/current/condition",),
            "GetPhoneBatteryInfo": ("/batterySOC", "/chargingStatusDesc"),
        },
        action=tuple(event.id for event in task.eventCandidates),
    )
    output = await generate_template_a2ui(
        task,
        _weather_battery_card_spec(),
        _WEATHER_BATTERY_BINDINGS,
        _PlanModel(intent, actions=action_bindings(task)),
    )
    source, context = _process_and_validate(output, _weather_battery_card_spec(), kind)
    if kind == DslProcessorKind.DESIGN_COMPACT:
        model_result = get_dsl_processor(kind).process(
            source, replace(context, source_kind="model")
        )
        messages = "\n".join(item.message for item in model_result.errors)
        assert "fontSize 20" in messages
        assert "must use W9" in messages
    if with_actions:
        assert "BatteryOverviewChargingRingHero@1" in output.template_ids
        assert output.a2ui.count('"call":"clickToDeeplink"') == 2


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("single_metrics", "include_countdown"), ((False, False), (True, False), (False, True)),
)
async def test_real_schema_generic_metrics_keep_units_through_artifact_validation(
    single_metrics,
    include_countdown,
):
    original, bindings, card, intent = _health_case(include_countdown)
    task = TaskSpecBuilder().build(
        original.userQuery,
        "2x4",
        list(bindings),
        _data_capabilities(),
        [],
        [],
    )
    task.assetCandidates = original.assetCandidates
    options = {}
    if single_metrics and not include_countdown:
        options["trusted_template_candidate_ids"] = (
            "SleepOverviewFull@1",
            "GenericMetricOverviewCompact@1",
        )
    output = await generate_template_a2ui(task, card, bindings, _PlanModel(intent), **options)
    _process_and_validate(output, card, DslProcessorKind.DESIGN_COMPACT)
    assert "步'" in output.a2ui
    assert "次/分钟'" in output.a2ui
    assert "displayUnits" not in output.a2ui
    assert "unitIncluded" not in output.a2ui
    if single_metrics and not include_countdown:
        assert "GenericMetricOverviewCompact@1" in output.template_ids
    else:
        assert "GenericMetricOverviewDualCompact@1" in output.template_ids


class _ActivityModel(_PlanModel):
    def __init__(self, intent, body):
        super().__init__(intent)
        self.fixed_body = body

    async def generate(self, *_args, **_kwargs):
        return self.fixed_body


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ("WideHero", "WideFull"))
async def test_activity_wide_with_all_icons_fits_and_has_no_duplicate_units(role):
    template_id = f"ActivityOverview{role}@1"
    definition = get_cardplan_registry().require_template(template_id)
    bindings = (
        CandidateDataBinding(
            capabilityId="GetHealthAndSportSummary",
            writeResultTo="/data/healthSport",
            candidateOutputFields=[
                "/dailySteps",
                "/dailyTotalCaloriesText",
                "/dailyDistanceText",
                "/targetDateText",
            ],
        ),
    )
    events = []
    if role == "WideHero":
        events.append(
            EventAction(
                id="event.open.settings.bluetooth",
                call="clickToDeeplink",
                args={"uri": "example://settings/bluetooth"},
            )
        )
    task = TaskSpecBuilder().build(
        "活动数据", "2x4", list(bindings), _data_capabilities(), events, []
    )
    parameters = _template_parameters(definition)
    assets = json.loads((_CAPABILITIES / "asset_capabilities.json").read_text(encoding="utf-8"))
    sources = set(parameters.values())
    task.assetCandidates = [asset for asset in assets if asset.get("src") in sources]
    card = {
        "title": "活动数据",
        "suggestSize": "2x4",
        "dataBindings": [
            {"capabilityId": "GetHealthAndSportSummary", "writeResultTo": "/data/healthSport"}
        ],
    }
    intent = TemplateSearchIntent(
        requiredOutputFieldsByCapability={
            "GetHealthAndSportSummary": definition.primary_data + definition.secondary_data,
        },
        action=tuple(event.id for event in events),
    )
    content = f'Template("{template_id}",{json.dumps(parameters)})'
    if events:
        action = action_bindings(task)[0]
        action_props = json.dumps({"actionId": action.action_id, "label": action.display_label})
        body = (
            f'Template("WideSingleFocusLayout@1",{{}},{content},'
            f'Template("PillAction@1",{action_props}));'
        )
    else:
        body = f'Template("WideFullOnlyLayout@1",{{}},{content});'
    output = await generate_template_a2ui(task, card, bindings, _ActivityModel(intent, body))
    _process_and_validate(output, card, DslProcessorKind.DESIGN_COMPACT)
    assert template_id in output.template_ids
    assert '"content":"千卡"' not in output.a2ui
    assert '"content":"千里"' not in output.a2ui


def _height_source(height, wrapper, depth):
    rows = [["root", wrapper, {"width": 300, "height": 150}, ["template_root"]]]
    parent = "template_root"
    for index in range(depth):
        child = f"wrapper_{index}"
        props = {"height": "matchParent"}
        if index == 0:
            props["padding"] = 12
        rows.append([parent, "Stack", props, [child]])
        parent = child
    rows.extend(
        [
            [parent, "Column", {"height": "matchParent", "itemMargin": 8}, ["one", "two"]],
            ["one", "Text", {"content": "A", "height": height}],
            ["two", "Text", {"content": "B", "height": height}],
            ["/", {"data": {}}],
        ]
    )
    return "\n".join(json.dumps(row) for row in rows)


@pytest.mark.parametrize("wrapper", ("Column", "Stack", "Row"))
@pytest.mark.parametrize("depth", (1, 3))
@pytest.mark.parametrize("height", (59, 60, 70))
def test_height_budget_survives_template_and_stack_wrappers(wrapper, depth, height):
    source = _height_source(height, wrapper, depth)
    options = {"task_spec": {"size": "2x4"}, "card_spec": {"suggestSize": "2x4"}}
    if height == 59:
        validate_compact_dsl_height(source, **options)
    else:
        with pytest.raises(CompactDslValidationError, match="overflows by"):
            validate_compact_dsl_height(source, **options)


@pytest.mark.parametrize("defect", ("event", "asset", "type", "binding", "tree", "extra_data"))
def test_template_processor_still_rejects_unapproved_or_malformed_content(defect):
    root = {"width": 300, "height": 150, "padding": 12}
    text = {"content": "{{ ${/data/health/value} }}", "fontSize": 20}
    children = ["value"]
    rows = [["root", "Column", root, children], ["value", "Text", text]]
    value: int | str = 60
    if defect == "event":
        root["onClick"] = [{"call": "clickToDeeplink", "args": {"uri": "unapproved"}}]
    elif defect == "asset":
        children.append("image")
        rows.append(["image", "Image", {"src": "resources/base/media/unapproved.svg"}])
    elif defect == "type":
        value = "not a number"
    elif defect == "binding":
        text["content"] = "{{ ${/data/health/undeclared} }}"
    elif defect == "tree":
        children.append("missing")
    rows.append(["/", {"data": {"health": {"value": value}}}])
    if defect == "extra_data":
        rows.append(["/data/health/undeclared", 1])
    task = TaskSpec(
        userQuery="校验边界",
        size="2x4",
        dataModelSchema={"data": {"health": {"value": {"type": "integer", "sampleValue": 60}}}},
    )
    context = DslProcessingContext(
        size="2x4",
        task_spec=task.model_dump(mode="json"),
        card_spec={"dataBindings": [{"capabilityId": "Health", "writeResultTo": "/data/health"}]},
        protocol_profile=A2UIProtocolRegistry().get_profile(),
        source_kind="template",
    )
    source = "\n".join(json.dumps(row) for row in rows)
    result = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT).process(source, context)
    assert not result.standard_dsl
    assert result.errors
    assert all(issue.code == "TEMPLATE_DSL_VALIDATION_FAILED" for issue in result.errors)


@pytest.mark.parametrize("sample", (None, 0, 12, "12"))
@pytest.mark.parametrize("included", (False, True))
def test_explicit_unit_metadata_overrides_description_and_sample_type(sample, included):
    leaf = {
        "type": "integer",
        "description": "旧说明，单位为公里",
        "sampleValue": sample,
        "displayUnits": ["步"],
        "unitIncluded": included,
    }
    placeholder = "${data.health.value}"
    value = _generic_metric_display_value(leaf, "/data/health/value", placeholder)
    if included:
        assert value == placeholder
    else:
        assert value == "{{ ${/data/health/value} + '步' }}"
    assert "公里" not in value


@pytest.mark.parametrize(
    "metadata",
    (
        {"displayUnits": ["步"]},
        {"unitIncluded": False},
        {"displayUnits": [], "unitIncluded": False},
        {"displayUnits": [""], "unitIncluded": False},
        {"displayUnits": [1], "unitIncluded": False},
        {"displayUnits": ["步"], "unitIncluded": "false"},
    ),
)
def test_malformed_unit_metadata_is_rejected(metadata):
    with pytest.raises(TerselConversionError, match="display unit"):
        _generic_metric_display_value(metadata, "/data/health/value", "${data.health.value}")


def test_template_root_marker_does_not_change_model_validation_rules():
    source = '\n'.join(
        json.dumps(row)
        for row in (
            ["root", "Stack", {"width": 300, "height": 150}, ["template_root"]],
            ["template_root", "Column", {}, ["title"]],
            ["title", "Text", {"content": "天气概览", "fontSize": 20}],
            ["/", {}],
        )
    )
    context = DslProcessingContext(
        size="2x4",
        task_spec={"size": "2x4", "dataModelSchema": {}},
        card_spec={"suggestSize": "2x4", "dataBindings": []},
        protocol_profile=A2UIProtocolRegistry().get_profile(),
    )
    processor = get_dsl_processor(DslProcessorKind.DESIGN_COMPACT)
    model_result = processor.process(source, context)
    assert any("fontSize 20" in issue.message for issue in model_result.errors)
    template_result = processor.process(source, replace(context, source_kind="template"))
    assert not template_result.errors


@pytest.mark.asyncio
@pytest.mark.parametrize("fusion", (False, True))
async def test_2x2_template_processing_preserves_plain_and_fusion_backgrounds(fusion):
    task = _weather_task_spec()
    card = _weather_card_spec()
    binding = CandidateDataBinding(
        capabilityId="ViewWeather",
        writeResultTo="/data/weather",
        candidateOutputFields=list(_WEATHER_TEMPLATE_FIELDS),
    )
    model = WeatherTemplateModel(
        theme_id="fusion-weather-blue" if fusion else "family-weather-care-blue",
        body='Template("SingleFocusLayout@1",{},Template("WeatherOverviewFull@1",{}));',
    )
    output = await generate_template_a2ui(task, card, (binding,), model, enable_fusion_ball=fusion)
    source, _context = _process_and_validate(output, card, DslProcessorKind.DESIGN_COMPACT)
    assert '"template_root"' in source
    assert ('"fusionBallBackground"' in source) is fusion
