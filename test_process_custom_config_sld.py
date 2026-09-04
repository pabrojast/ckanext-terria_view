#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""process_custom_config must not clobber saved viewer style edits with SLD.

When a view has both ``custom_config`` (Save Configuration) and ``style``
(an SLD URL), the SLD is only a seed for *missing* fields. Legend titles,
displayRange and table styles already present in the saved share data stay.
"""

import json
import urllib.parse

from ckanext.terria_view.config_manager import ConfigManager
from ckanext.terria_view.terria_config_builder import TerriaConfigBuilder


SLD_URL = (
    "https://example.org/dataset/x/resource/sld/download/style.sld"
)
RESOURCE_URL = (
    "https://data.dev-wins.com/dataset/x/resource/y/download/file.tif"
)
SHP_RESOURCE_URL = (
    "https://data.dev-wins.com/dataset/x/resource/y/download/file.zip"
)

SLD_COG = {
    "legends": [{
        "title": "Legend",
        "items": [
            {"title": "0.0000", "color": "rgb(247, 251, 255)"},
            {"title": "10.0000", "color": "rgb(8, 48, 107)"},
        ],
    }],
    "renderOptions": {
        "single": {
            "colors": [
                [0, "rgb(247, 251, 255)"],
                [10, "rgb(8, 48, 107)"],
            ],
            "useRealValue": True,
            "type": "continuous",
            "domain": [0, 10],
        }
    },
}

SLD_SHP = {
    "legends": [{
        "title": "Legend",
        "items": [{"title": "A", "color": "#ff0000"}],
    }],
    "styles": [{
        "id": "sld-style",
        "title": "SLD Style (code)",
        "color": {
            "mapType": "enum",
            "colorColumn": "code",
            "enumColors": [{"value": "A", "color": "#ff0000"}],
        },
    }],
    "activeStyle": "sld-style",
    "defaultStyle": {"id": "sld-style"},
}


class DummySLDProcessor:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def process_sld_for_resource(self, sld_url, resource_format):
        self.calls.append((sld_url, resource_format))
        return self.result


def _builder(sld_result):
    processor = DummySLDProcessor(sld_result)
    return TerriaConfigBuilder(ConfigManager(), processor), processor


def _custom_url(start_data):
    return "https://ihp-wins.unesco.org/terria/#start=" + urllib.parse.quote(
        json.dumps(start_data), safe=""
    )


def _cog_start(model_extra=None, model_id="flood map"):
    model = {
        "type": "cog",
        "url": "https://old.example.org/file.tif",
        "name": model_id,
        "knownContainerUniqueIds": ["/"],
        "opacity": 0.8,
    }
    if model_extra:
        model.update(model_extra)
    return {
        "version": "8.0.0",
        "initSources": [{
            "stratum": "user",
            "models": {
                "/": {"type": "group", "members": [model_id]},
                model_id: model,
            },
            "workbench": [model_id],
        }],
    }


def _shp_start(model_extra=None, model_id="rivers"):
    model = {
        "type": "shp",
        "url": "https://old.example.org/file.zip",
        "name": model_id,
        "knownContainerUniqueIds": ["/"],
        "opacity": 0.8,
    }
    if model_extra:
        model.update(model_extra)
    return {
        "version": "8.0.0",
        "initSources": [{
            "stratum": "user",
            "models": {
                "/": {"type": "group", "members": [model_id]},
                model_id: model,
            },
            "workbench": [model_id],
        }],
    }


def _process(builder, start_data, resource_url, resource_format):
    result = builder.process_custom_config(
        _custom_url(start_data),
        resource_url,
        resource_format,
        SLD_URL,
        resource_id="y",
    )
    assert result is not None
    return json.loads(result)


def _main_model(processed, model_id):
    return processed["initSources"][0]["models"][model_id]


def test_cog_keeps_edited_legend_titles():
    builder, processor = _builder(SLD_COG)
    start = _cog_start({
        "legends": [{
            "title": "Water level (m)",
            "items": [
                {"title": "0.0000 m", "color": "rgb(247, 251, 255)"},
                {"title": "10.0000 m", "color": "rgb(8, 48, 107)"},
            ],
        }],
        "renderOptions": {
            "single": {
                "colors": [[0, "rgb(247, 251, 255)"], [10, "rgb(8, 48, 107)"]],
                "useRealValue": True,
                "type": "continuous",
                "domain": [0, 10],
            }
        },
    })
    processed = _process(builder, start, RESOURCE_URL, "tif")
    model = _main_model(processed, "flood map")
    titles = [item["title"] for item in model["legends"][0]["items"]]

    assert titles == ["0.0000 m", "10.0000 m"]
    assert model["legends"][0]["title"] == "Water level (m)"
    assert processor.calls == [(SLD_URL, "tif")]
    print("  PASS: COG saved legend titles with units are not overwritten")


def test_cog_keeps_display_range():
    builder, _processor = _builder(SLD_COG)
    start = _cog_start({
        "legends": SLD_COG["legends"],
        "renderOptions": {
            "single": {
                "colors": [[0, "rgb(247, 251, 255)"], [10, "rgb(8, 48, 107)"]],
                "useRealValue": True,
                "type": "continuous",
                "domain": [0, 10],
                "displayRange": [0.05, 100],
                "applyDisplayRange": True,
            }
        },
    })
    processed = _process(builder, start, RESOURCE_URL, "tif")
    single = _main_model(processed, "flood map")["renderOptions"]["single"]

    assert single["displayRange"] == [0.05, 100]
    assert single["applyDisplayRange"] is True
    print("  PASS: COG displayRange from the viewer is preserved")


def test_cog_fills_missing_sld_fields():
    builder, _processor = _builder(SLD_COG)
    processed = _process(builder, _cog_start(), RESOURCE_URL, "tif")
    model = _main_model(processed, "flood map")

    assert model["legends"] == SLD_COG["legends"]
    assert model["renderOptions"] == SLD_COG["renderOptions"]
    assert model["url"] == RESOURCE_URL
    print("  PASS: COG without saved style fields is seeded from the SLD")


def test_uppercase_tif_does_not_clobber_saved_legends():
    builder, processor = _builder(SLD_COG)
    start = _cog_start({
        "legends": [{
            "title": "Legend",
            "items": [{"title": "0 m", "color": "rgb(247, 251, 255)"}],
        }],
        "renderOptions": SLD_COG["renderOptions"],
    })
    processed = _process(builder, start, RESOURCE_URL, "TIF")
    titles = [
        item["title"]
        for item in _main_model(processed, "flood map")["legends"][0]["items"]
    ]

    assert titles == ["0 m"]
    assert processor.calls == [(SLD_URL, "tif")]
    print("  PASS: format TIF is routed to SLD but does not clobber legends")


def test_shp_keeps_edited_styles_with_uppercase_format():
    builder, processor = _builder(SLD_SHP)
    saved_styles = [{
        "id": "sld-style",
        "title": "Edited style",
        "color": {
            "mapType": "enum",
            "colorColumn": "code",
            "enumColors": [{"value": "A", "color": "#00ff00"}],
        },
    }]
    start = _shp_start({
        "legends": [{
            "title": "Legend",
            "items": [{"title": "A (units)", "color": "#00ff00"}],
        }],
        "styles": saved_styles,
        "activeStyle": "sld-style",
    })
    processed = _process(builder, start, SHP_RESOURCE_URL, "SHP")
    model = _main_model(processed, "rivers")

    assert model["styles"] == saved_styles
    assert model["legends"][0]["items"][0]["title"] == "A (units)"
    assert processor.calls == [(SLD_URL, "shp")]
    print("  PASS: SHP saved styles/legend titles survive lowercase SLD routing")


def test_shp_fills_missing_styles_from_sld():
    builder, _processor = _builder(SLD_SHP)
    processed = _process(builder, _shp_start(), SHP_RESOURCE_URL, "SHP")
    model = _main_model(processed, "rivers")

    assert model["styles"] == SLD_SHP["styles"]
    assert model["activeStyle"] == "sld-style"
    assert model["legends"] == SLD_SHP["legends"]
    print("  PASS: SHP without saved style fields is seeded from the SLD")


if __name__ == "__main__":
    print("\n=== process_custom_config SLD no-clobber ===\n")
    test_cog_keeps_edited_legend_titles()
    test_cog_keeps_display_range()
    test_cog_fills_missing_sld_fields()
    test_uppercase_tif_does_not_clobber_saved_legends()
    test_shp_keeps_edited_styles_with_uppercase_format()
    test_shp_fills_missing_styles_from_sld()
    print("\nAll tests passed.\n")
