"""Q83 仅使用已发布的既有图标，不增加素材注册或 SVG。"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from services.capability_registry import CapabilityRegistry


@pytest.mark.parametrize("version", ["app-11.7.5.205_rom-6.0", "app-11.7.7.300_rom-7.0"])
def test_q83_uses_only_published_assets(version: str) -> None:
    registry = CapabilityRegistry(version=version)
    published = json.loads((registry.version_dir / "asset_capabilities.json").read_text("utf-8"))
    assets = registry.list_asset_capabilities()
    by_id = {asset.id: asset for asset in assets}
    assert len(assets) == len(published)
    assert len(by_id) == len(assets)
    assert "asset.ux_q83_drop" not in by_id
    assert "asset.ux_q83_earphone_case" not in by_id
    for item in published:
        original = by_id.get(item.get("id"))
        assert original is not None
        assert original.src == item.get("src")
        assert original.description == item.get("description")
    repo = Path(__file__).resolve().parents[2]
    for asset_id in ("asset.drop_1", "asset.earphone_case_16644", "asset.music_fill"):
        asset = by_id.get(asset_id)
        assert asset is not None
        svg = ET.parse(repo / asset.src).getroot()
        assert svg.tag == "{http://www.w3.org/2000/svg}svg"
        assert svg.get("width") == svg.get("height") == "24"
