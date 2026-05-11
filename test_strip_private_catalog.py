# encoding: utf-8
"""
Tests for stripping injected "Private Datasets (...)" branches out of saved
TerriaJS configs (see ckanext.terria_view.terria_config_builder).

These exercise only the dependency-free helpers, so they run without CKAN.
"""
import json
import urllib.parse

from ckanext.terria_view.terria_config_builder import (
    strip_private_catalog_branches,
    strip_private_catalog_from_terria_url,
)


def _share_state_with_private_catalog():
    """A ``getShareData``-style state: one real resource + an injected catalog."""
    return {
        "version": "8.0.0",
        "initSources": [{
            "stratum": "user",
            "workbench": ["HydroRIVERS - The Nile Basin"],
            "previewedItemId": "//Private Datasets (alice)/Org A/Dataset 1",
            "models": {
                "/": {
                    "type": "group",
                    "members": [
                        "HydroRIVERS - The Nile Basin",
                        "//Private Datasets (alice)",
                    ],
                },
                "HydroRIVERS - The Nile Basin": {
                    "name": "HydroRIVERS - The Nile Basin",
                    "type": "shp",
                    "url": "https://example.org/resource/abc/content/x.zip?token=t",
                    "knownContainerUniqueIds": ["/"],
                },
                "//Private Datasets (alice)": {
                    "name": "Private Datasets (alice)",
                    "type": "group",
                    "isOpen": True,
                    "members": ["//Private Datasets (alice)/Org A"],
                    "knownContainerUniqueIds": ["/"],
                },
                "//Private Datasets (alice)/Org A": {
                    "name": "Org A",
                    "type": "group",
                    "members": ["//Private Datasets (alice)/Org A/Dataset 1"],
                    "knownContainerUniqueIds": ["//Private Datasets (alice)"],
                },
                "//Private Datasets (alice)/Org A/Dataset 1": {
                    "name": "Dataset 1",
                    "type": "group",
                    "members": ["res-uuid-1"],
                    "knownContainerUniqueIds": ["//Private Datasets (alice)/Org A"],
                },
                "res-uuid-1": {
                    "name": "Some private layer",
                    "type": "csv",
                    "url": "https://example.org/resource/res-uuid-1/content/y.csv?token=secret",
                    "knownContainerUniqueIds": ["//Private Datasets (alice)/Org A/Dataset 1"],
                },
            },
        }],
    }


def test_strip_removes_private_branches_only():
    state = _share_state_with_private_catalog()
    strip_private_catalog_branches(state)

    models = state["initSources"][0]["models"]
    assert set(models) == {"/", "HydroRIVERS - The Nile Basin"}
    assert models["/"]["members"] == ["HydroRIVERS - The Nile Basin"]
    assert state["initSources"][0]["workbench"] == ["HydroRIVERS - The Nile Basin"]
    assert "previewedItemId" not in state["initSources"][0]

    # No private-dataset signed token survives.
    assert "secret" not in json.dumps(state)


def test_strip_handles_plus_for_space_encoding():
    state = {
        "initSources": [{
            "workbench": ["HydroRIVERS+-+The+Nile+Basin"],
            "models": {
                "/": {"type": "group", "members": [
                    "HydroRIVERS+-+The+Nile+Basin", "//Private+Datasets+(alice)"]},
                "HydroRIVERS+-+The+Nile+Basin": {
                    "type": "shp", "url": "u", "knownContainerUniqueIds": ["/"]},
                "//Private+Datasets+(alice)": {
                    "type": "group", "members": ["//Private+Datasets+(alice)/Org+A"],
                    "knownContainerUniqueIds": ["/"]},
                "//Private+Datasets+(alice)/Org+A": {
                    "type": "group", "members": [],
                    "knownContainerUniqueIds": ["//Private+Datasets+(alice)"]},
            },
        }],
    }
    strip_private_catalog_branches(state)
    models = state["initSources"][0]["models"]
    assert set(models) == {"/", "HydroRIVERS+-+The+Nile+Basin"}
    assert models["/"]["members"] == ["HydroRIVERS+-+The+Nile+Basin"]


def test_strip_is_noop_without_private_catalog():
    state = {
        "initSources": [{
            "workbench": ["My Layer"],
            "models": {
                "/": {"type": "group", "members": ["My Layer"]},
                "My Layer": {"type": "csv", "url": "u", "knownContainerUniqueIds": ["/"]},
            },
        }],
    }
    before = json.loads(json.dumps(state))
    strip_private_catalog_branches(state)
    assert state == before


def test_strip_catalog_array_form():
    state = {"initSources": [{"catalog": [
        {"name": "Some Layer", "type": "csv", "url": "u"},
        {"name": "Private Datasets (alice)", "type": "group", "members": []},
    ]}]}
    strip_private_catalog_branches(state)
    assert state["initSources"][0]["catalog"] == [
        {"name": "Some Layer", "type": "csv", "url": "u"}]


def test_strip_from_terria_url_roundtrip():
    state = _share_state_with_private_catalog()
    url = ("https://ihp-wins.unesco.org/terria/#start="
           + urllib.parse.quote(json.dumps(state)))
    cleaned = strip_private_catalog_from_terria_url(url)

    assert cleaned.startswith("https://ihp-wins.unesco.org/terria/#start=")
    assert len(cleaned) < len(url)
    payload = json.loads(urllib.parse.unquote(cleaned.split("#start=", 1)[1]))
    assert set(payload["initSources"][0]["models"]) == {"/", "HydroRIVERS - The Nile Basin"}


def test_strip_from_terria_url_passthrough():
    assert strip_private_catalog_from_terria_url(None) is None
    assert strip_private_catalog_from_terria_url("NA") == "NA"
    share = "https://ihp-wins.unesco.org/terria/#share=g-abc123"
    assert strip_private_catalog_from_terria_url(share) == share
    plain = "https://ihp-wins.unesco.org/terria/"
    assert strip_private_catalog_from_terria_url(plain) == plain
    bad = "https://ihp-wins.unesco.org/terria/#start=not-json"
    assert strip_private_catalog_from_terria_url(bad) == bad
