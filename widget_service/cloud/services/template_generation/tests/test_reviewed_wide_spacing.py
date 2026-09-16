"""Regression coverage for the reviewed Q058/Q060/Q073 layout geometry."""

import pytest

from services.template_generation.engine.cardplan.registry import CardPlanRegistry
from services.template_generation.engine.compact_dsl_a2ui_converter import (
    _COMPACT_ROOT_DIMENSIONS,
)


@pytest.mark.parametrize(
    ("template_id", "gap"),
    [
        ("ScheduleOverviewMeetingEntryHero@1", 10),
        ("BluetoothDeviceOverviewCaseConnectionHero@1", 8),
        ("BluetoothDeviceOverviewCaseSettingsHero@1", 4),
        ("BatteryOverviewChargeStatusHero@1", 8),
    ],
)
def test_reviewed_title_to_content_gap(template_id, gap):
    definition = CardPlanRegistry().require_template(template_id)
    options = definition.variants[0].root.values[-1]
    item_margin = options.properties.get("itemMargin")
    assert item_margin is not None
    assert item_margin.value == gap


@pytest.mark.parametrize("size", ["2x4", "4x2"])
def test_wide_canvas_is_300_by_150(size):
    assert _COMPACT_ROOT_DIMENSIONS.get(size) == {"width": 300, "height": 150}


def test_square_canvas_is_unchanged():
    assert _COMPACT_ROOT_DIMENSIONS.get("2x2") == {"width": 160, "height": 160}
