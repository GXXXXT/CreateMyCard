"""按服务确认的模板来源检查产物，保留数据边界和布局预算。"""

from services.card_validation.compact_dsl_validator import (
    CompactDslValidationError,
    validate_compact_dsl_baseline,
)
from services.card_validation.display_unit_rules import repair_repeated_display_units
from services.generation_pipeline import DslProcessingContext, DslProcessingResult, QualityIssue
from services.template_generation.engine.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    convert_a2ui_to_compact_dsl,
    convert_compact_dsl_to_a2ui,
    validate_compact_dsl_context,
)


def process_template_source(
    source_dsl: str,
    context: DslProcessingContext,
    *,
    compact: bool,
) -> DslProcessingResult:
    """模板不使用自由设计规则；错误仍阻止转换并交给原失败处理链路。"""
    try:
        archived = source_dsl
        if not compact:
            archived = convert_a2ui_to_compact_dsl(source_dsl, size=context.size)
        checked = validate_compact_dsl_context(
            archived,
            task_spec=context.task_spec,
            card_spec=context.card_spec,
        )
        validate_compact_dsl_baseline(
            archived,
            task_spec=context.task_spec,
            card_spec=context.card_spec,
        )
    except (CompactDslConversionError, CompactDslValidationError) as exc:
        messages = exc.errors if isinstance(exc, CompactDslValidationError) else (str(exc),)
        issues = tuple(
            QualityIssue(
                stage="validation",
                code="TEMPLATE_DSL_VALIDATION_FAILED",
                message=message,
            )
            for message in messages
        )
        return DslProcessingResult(source_dsl=source_dsl, issues=issues)

    try:
        standard_dsl = source_dsl
        if compact:
            standard_dsl = convert_compact_dsl_to_a2ui(
                archived,
                size=context.size,
                protocol_profile=context.protocol_profile,
            )
    except CompactDslConversionError as exc:
        issue = QualityIssue(
            stage="conversion",
            code="TEMPLATE_DSL_CONVERSION_FAILED",
            message=str(exc),
        )
        return DslProcessingResult(source_dsl=source_dsl, issues=(issue,))

    standard_dsl = repair_repeated_display_units(
        standard_dsl,
        context.card_spec,
        context.data_capabilities,
    )
    warnings = tuple(
        QualityIssue(
            stage="validation",
            code="TEMPLATE_DSL_VALIDATION_WARNING",
            message=message,
            severity="warning",
        )
        for message in checked.warnings
    )
    return DslProcessingResult(
        source_dsl=source_dsl,
        standard_dsl=standard_dsl,
        issues=warnings,
    )
