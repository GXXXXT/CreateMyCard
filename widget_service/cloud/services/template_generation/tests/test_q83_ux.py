"""Q83 合并不能改写其它宽版布局，确定性序列化保留新版 Planner 字段。"""

import pytest

from services.template_generation.engine.cardplan.q83_ux import adapt_wide_three_mask_ux
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.pipeline import _deterministic_plan_source
from services.template_generation.engine.tersel_converter import Nested2Node
from services.template_generation.tests.test_wide_template_planner import _health_case, _plans


@pytest.mark.parametrize(
    ("size", "template_ids"),
    [
        ("2x2", ("WideFullTwoCompactLayout@1",)),
        ("2x4", ("WideFullTwoCompactLayout@1", "WeatherOverviewFull@1")),
        ("2x4", ("WideFullOnlyLayout@1",)),
    ],
)
def test_q83_adaptation_leaves_other_combinations_unchanged(size, template_ids):
    root = Nested2Node("Stack", ("card", {"padding": 12}), ())
    assert (
        adapt_wide_three_mask_ux(
            root,
            size=size,
            template_ids=template_ids,
            app_version="11.7.5.208",
            enable_background=True,
        )
        is root
    )


def test_deterministic_serialization_preserves_planner_metric_fields():
    task, bindings, card, intent = _health_case()
    plan = _plans(task, bindings, card, intent)[0]
    output = _deterministic_plan_source(plan, task, card, get_cardplan_registry())
    matched = False
    for slot in plan.business_slots:
        for parameter, path in slot.field_bindings.items():
            matched = True
            assert f'"{parameter}": "{path}"' in output
    assert matched
