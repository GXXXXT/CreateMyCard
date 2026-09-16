"""Adapt the user-confirmed 300x150 three-mask UX to the 320x160 Form canvas."""

from __future__ import annotations

from typing import Any

from services.fusion_ball_expander import fusion_ball_enabled
from services.template_generation.engine.tersel_converter import Nested2Node

_SCALE = 16 / 15
_LENGTH_KEYS = frozenset(
    {
        "width",
        "height",
        "padding",
        "margin",
        "borderRadius",
        "fontSize",
        "itemMargin",
        "strokeWidth",
        "constraintSize",
    }
)
_Q83_TEMPLATES = frozenset(
    {
        "WeatherOverviewCyclingRainFull@1",
        "BluetoothDeviceOverviewConnectionBatteryCompact@1",
        "CompactAction@1",
        "WideFullTwoCompactLayout@1",
    }
)


def _scale_length(value: Any) -> Any:
    result: Any = value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        result = round(value * _SCALE, 6)
    elif isinstance(value, dict):
        result = {key: _scale_length(item) for key, item in value.items()}
    return result


def _scaled(node: Nested2Node) -> Nested2Node:
    values: list[Any] = []
    for value in node.values:
        if isinstance(value, dict):
            options: dict[str, Any] = {}
            for key, item in value.items():
                options[key] = _scale_length(item) if key in _LENGTH_KEYS else item
            value = options
        values.append(value)
    children = tuple(_scaled(child) for child in node.children)
    return Nested2Node(node.component_type, tuple(values), children)


def _q83_colors(node: Nested2Node) -> Nested2Node:
    values: list[Any] = []
    for value in node.values:
        if isinstance(value, dict):
            value = dict(value)
            if "backgroundColor" in value:
                value["backgroundColor"] = "#19CCDDFF"
            if node.component_type == "Text":
                value["fontColor"] = "#FFCCDDFF" if value.get("fontWeight") == 700 else "#99CCDDFF"
            if node.component_type == "Image":
                value["fillColor"] = "#99CCDDFF"
            if node.component_type == "Progress":
                value.update({"color": "#FFCCDDFF", "backgroundColor": "#19CCDDFF"})
        elif node.component_type == "Text" and isinstance(value, str):
            if value.endswith("市天气"):
                value = value.removesuffix("市天气") + "天气"
            elif value == "心动歌单":
                value = "打开歌单"
        values.append(value)
    children = tuple(_q83_colors(child) for child in node.children)
    return Nested2Node(node.component_type, tuple(values), children)


def _circle_slot(name: str, width: int, height: int, diameter: int, color: str) -> Nested2Node:
    circle = Nested2Node(
        "Divider",
        (
            {
                "_id": name,
                "width": diameter,
                "height": diameter,
                "borderRadius": diameter / 2,
                "strokeWidth": 0,
                "color": "#00000000",
                "backgroundColor": color,
            },
        ),
        (),
    )
    return Nested2Node(
        "Stack",
        (
            "overlay",
            {
                "_id": name + "Slot",
                "width": width,
                "height": height,
                "alignContent": "bottomEnd",
            },
        ),
        (circle,),
    )


def _with_options(node: Nested2Node, overrides: dict[str, Any]) -> Nested2Node:
    values = list(node.values)
    if not values or not isinstance(values[-1], dict):
        raise ValueError("Q83 layout node requires static options")
    options = dict(values[-1])
    options.pop("layoutWeight", None)
    options.update(overrides)
    values[-1] = options
    return Nested2Node(node.component_type, tuple(values), node.children)


def _three_mask_content(content: Nested2Node) -> Nested2Node:
    """Override only the confirmed Q83 combination, retaining other wide layouts."""
    if content.component_type != "Row" or len(content.children) != 2:
        raise ValueError("Q83 requires a two-column layout")
    left, right = content.children
    if len(right.children) != 2:
        raise ValueError("Q83 requires two right-hand compact slots")
    mask = {"borderRadius": 12, "backgroundColor": "#19CCDDFF", "clip": True}
    left = _with_options(left, {"width": 132, "height": 126, "padding": 8, **mask})
    top = _with_options(
        right.children[0],
        {
            "width": "matchParent",
            "height": 57,
            "padding": {"left": 8, "top": 6, "right": 8, "bottom": 7},
            **mask,
        },
    )
    bottom = _with_options(right.children[1], {"width": "matchParent", "height": 57})
    actions: list[Nested2Node] = []
    for action in bottom.children:
        action = _with_options(action, mask)
        rows: list[Nested2Node] = []
        for row in action.children:
            if row.component_type == "Row":
                row = _with_options(
                    row,
                    {
                        "padding": {"left": 8, "top": 6, "right": 8, "bottom": 7},
                    },
                )
            rows.append(row)
        actions.append(Nested2Node(action.component_type, action.values, tuple(rows)))
    bottom = Nested2Node(bottom.component_type, bottom.values, tuple(actions))
    right = _with_options(right, {"width": 132, "height": 126, "itemMargin": 12})
    right = Nested2Node(right.component_type, right.values, (top, bottom))
    content = _with_options(
        content, {"width": "matchParent", "height": "matchParent", "itemMargin": 12}
    )
    return Nested2Node(content.component_type, content.values, (left, right))


def adapt_wide_three_mask_ux(
    root: Nested2Node,
    *,
    size: str,
    template_ids: tuple[str, ...],
    app_version: str | None,
    enable_background: bool,
) -> Nested2Node:
    if size != "2x4" or not _Q83_TEMPLATES.issubset(template_ids):
        return root
    original_content = _q83_colors(_three_mask_content(root.children[0]))
    content = _scaled(original_content)
    # The old content root already owns template_root; retain one canonical marker.
    content_values: list[Any] = []
    for value in content.values:
        if isinstance(value, dict):
            value = {**value, "_id": "q83MaskLayout"}
        content_values.append(value)
    foreground = Nested2Node(
        "Stack",
        (
            "overlay",
            {
                "_id": "template_root",
                "width": "matchParent",
                "height": "matchParent",
                "padding": _scale_length(12),
                "alignContent": "topStart",
            },
        ),
        (Nested2Node(content.component_type, tuple(content_values), content.children),),
    )
    options = dict(root.values[-1])
    options.update({"padding": 0, "borderRadius": 18, "clip": True, "alignContent": "topStart"})
    options.pop("itemMargin", None)
    options.pop("alignItems", None)
    backgrounds: tuple[Nested2Node, ...] = ()
    if enable_background and fusion_ball_enabled(app_version):
        glass = Nested2Node(
            "Divider",
            (
                {
                    "_id": "q83Glass",
                    "width": "matchParent",
                    "height": "matchParent",
                    "strokeWidth": 0,
                    "color": "#00000000",
                    "backgroundColor": "#0DFFFFFF",
                    "backdropBlur": {"radius": _scale_length(110)},
                },
            ),
            (),
        )
        background = Nested2Node(
            "Stack",
            (
                "overlay",
                {
                    "_id": "fusionBallBackground",
                    "width": "matchParent",
                    "height": "matchParent",
                    "alignContent": "topStart",
                    "clip": True,
                },
            ),
            (
                _scaled(_circle_slot("q83NavyBall", 360, 220, 370, "#FF121259")),
                _scaled(_circle_slot("q83CyanBall", 220, 370, 310, "#FF1698D9")),
                _scaled(_circle_slot("q83BlueBall", 356, 246, 156, "#FF2B65D9")),
                glass,
            ),
        )
        backgrounds = (background,)
        options.pop("linearGradient", None)
        options["backgroundColor"] = "#FF121259"
    return Nested2Node("Stack", ("card", options), (*backgrounds, foreground))
