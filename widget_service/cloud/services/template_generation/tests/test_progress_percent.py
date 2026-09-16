"""Percent conversion is an explicit host function, not an arbitrary function escape."""

import json

import pytest

from services.template_generation.engine.compact_dsl_a2ui_converter import (
    CompactDslConversionError,
    convert_compact_dsl_to_a2ui,
)


def convert_progress(value: object, total: object = 100) -> str:
    rows = [
        ["root", "Column", {"width": 160, "height": 160}, ["rain"]],
        ["rain", "Progress", {"value": value, "total": total}],
        ["/data/weather/rain", "65%"],
    ]
    return convert_compact_dsl_to_a2ui(
        "\n".join(json.dumps(row) for row in rows),
        protocol_profile={
            "version": "v0.9",
            "catalogId": "ohos.a2ui.extended.catalog.form",
            "sizes": {"2x2": {"width": 160, "height": 160}},
        },
        surface_id="rain_test",
        size="2x2",
    )


@pytest.mark.parametrize("binding", [{"path": "/data/weather/rain"}, "{{ ${/data/weather/rain} }}"])
def test_progress_percent_preserves_dynamic_binding(binding: object) -> None:
    value = {"call": "toProgressPercent", "args": {"value": binding}}
    output = convert_progress(value)
    assert '"toProgressPercent"' in output
    assert "/data/weather/rain" in output


@pytest.mark.parametrize(
    "value",
    [
        {"call": "unknown", "args": {"value": {"path": "/data/weather/rain"}}},
        {"call": "toProgressPercent", "args": {}},
        {"call": "toProgressPercent", "args": {"value": True}},
        {"call": "toProgressPercent", "args": {"value": "65%"}},
        {
            "call": "toProgressPercent",
            "args": {"value": {"path": "/data/weather/rain"}, "extra": 1},
        },
        {"call": "toProgressPercent", "args": {"value": {"call": "unknown"}}},
    ],
)
def test_progress_percent_rejects_unapproved_call_shape(value: object) -> None:
    with pytest.raises(CompactDslConversionError):
        convert_progress(value)


def test_progress_total_does_not_accept_percent_function() -> None:
    with pytest.raises(CompactDslConversionError):
        convert_progress(
            65,
            {"call": "toProgressPercent", "args": {"value": {"path": "/data/weather/rain"}}},
        )
