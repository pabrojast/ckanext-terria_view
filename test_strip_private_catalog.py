# encoding: utf-8
"""
Tests for stripping injected "Private Datasets (...)" branches out of saved
TerriaJS configs (see ckanext.terria_view.terria_config_builder) and for the
``scripts/strip_private_catalog_from_views.py`` cleanup helper.

These exercise only the dependency-free helpers, so they run without CKAN.
"""
import importlib.util
import json
import os
import urllib.parse

from ckanext.terria_view.terria_config_builder import (
    collapse_private_catalog_to_saved_layers,
    payload_has_private_catalog,
    prepare_saved_custom_config_url,
    strip_private_catalog_branches,
    strip_private_catalog_from_terria_url,
)

# Load the standalone cleanup script as a module (no CKAN / psycopg2 needed for
# its strip + clean_config helpers).
_CLEANUP_PATH = os.path.join(os.path.dirname(__file__), 'scripts',
                             'strip_private_catalog_from_views.py')
_spec = importlib.util.spec_from_file_location('strip_private_catalog_from_views', _CLEANUP_PATH)
cleanup_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cleanup_script)


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


def test_strip_from_terria_url_no_churn_without_private_catalog():
    # A valid #start= URL with no private catalog must come back byte-for-byte
    # identical (don't re-encode / churn the stored value for nothing).
    state = {"initSources": [{
        "workbench": ["My Layer"],
        "models": {
            "/": {"type": "group", "members": ["My Layer"]},
            "My Layer": {"type": "csv", "url": "u", "knownContainerUniqueIds": ["/"]},
        },
    }]}
    url = ("https://ihp-wins.unesco.org/terria/#start="
           + urllib.parse.quote(json.dumps(state)))
    assert strip_private_catalog_from_terria_url(url) == url


def test_payload_has_private_catalog():
    assert payload_has_private_catalog(_share_state_with_private_catalog()) is True
    assert payload_has_private_catalog({"initSources": [{"models": {
        "/": {"type": "group", "members": []}}}]}) is False
    assert payload_has_private_catalog({"initSources": [{"catalog": [
        {"name": "Private Datasets (x)", "type": "group"}]}]}) is True
    assert payload_has_private_catalog("nope") is False


def test_lazy_catalog_save_collapses_browser_to_one_saved_layers_group():
    state = {
        'initSources': [{
            'workbench': ['__ckan_private_catalog__/session1/resource/r1/view/0'],
            'models': {
                '/': {'type': 'group', 'members': [
                    '__ckan_private_catalog__/session1/browser'
                ]},
                '__ckan_private_catalog__/session1/browser': {
                    'type': 'group',
                    'members': ['__ckan_private_catalog__/session1/dataset/d1'],
                    'knownContainerUniqueIds': ['/'],
                },
                '__ckan_private_catalog__/session1/dataset/d1': {
                    'type': 'group',
                    'members': [
                        '__ckan_private_catalog__/session1/resource/r1/view/0',
                        '__ckan_private_catalog__/session1/resource/r2/view/0',
                    ],
                    'knownContainerUniqueIds': [
                        '__ckan_private_catalog__/session1/browser'
                    ],
                },
                '__ckan_private_catalog__/session1/resource/r1/view/0': {
                    'type': 'csv',
                    'url': 'https://example.org/api/terria/resource/r1/content/x.csv?token=secret',
                    'knownContainerUniqueIds': [
                        '__ckan_private_catalog__/session1/dataset/d1'
                    ],
                },
                '__ckan_private_catalog__/session1/resource/r2/view/0': {
                    'type': 'csv',
                    'url': 'https://example.org/api/terria/resource/r2/content/y.csv?token=unused',
                    'knownContainerUniqueIds': [
                        '__ckan_private_catalog__/session1/dataset/d1'
                    ],
                },
            },
        }],
    }

    collapse_private_catalog_to_saved_layers(state)
    source = state['initSources'][0]
    models = source['models']
    saved_id = '__ckan_saved_private_layers__'
    used_id = '__ckan_private_catalog__/session1/resource/r1/view/0'
    assert set(models) == {'/', saved_id, used_id}
    assert models['/']['members'] == [saved_id]
    assert models[saved_id]['members'] == [used_id]
    assert models[used_id]['knownContainerUniqueIds'] == [saved_id]
    assert source['workbench'] == [used_id]


def test_prepare_lazy_saved_config_is_small_tokenless_and_idempotent():
    state = _share_state_with_private_catalog()
    private_id = 'res-uuid-1'
    state['initSources'][0]['workbench'] = [private_id]
    url = _terria_url(state)

    prepared = prepare_saved_custom_config_url(url, lazy_private_catalog=True)
    prepared_again = prepare_saved_custom_config_url(
        prepared, lazy_private_catalog=True
    )
    payload = json.loads(urllib.parse.unquote(prepared.split('#start=', 1)[1]))
    models = payload['initSources'][0]['models']

    assert prepared_again == prepared
    assert set(models) == {
        '/', 'HydroRIVERS - The Nile Basin',
        '__ckan_saved_private_layers__', private_id,
    }
    assert 'token=' not in prepared
    assert len(prepared) < len(url)


# --- cleanup script (scripts/strip_private_catalog_from_views.py) -------------

def _terria_url(state):
    return "https://ihp-wins.unesco.org/terria/#start=" + urllib.parse.quote(json.dumps(state))


def test_cleanup_clean_config_strips_both_fields():
    url = _terria_url(_share_state_with_private_catalog())
    config = {
        "custom_config": url,
        "style": "NA",
        "terria_instance_url": "https://ihp-wins.unesco.org/terria/",
        "filterable": True,
        "__extras": {"custom_config_option": "custom", "custom_config_url": url},
    }
    new_config, changed = cleanup_script.clean_config(config, drop_extras_url=False)
    assert changed is True
    assert len(json.dumps(new_config)) < len(json.dumps(config))
    for field in (new_config["custom_config"], new_config["__extras"]["custom_config_url"]):
        payload = json.loads(urllib.parse.unquote(field.split("#start=", 1)[1]))
        assert set(payload["initSources"][0]["models"]) == {"/", "HydroRIVERS - The Nile Basin"}
    assert "secret" not in json.dumps(new_config)
    # __extras kept (only the private branches were stripped, key not removed)
    assert "custom_config_url" in new_config["__extras"]
    # idempotent
    assert cleanup_script.clean_config(new_config, drop_extras_url=False)[1] is False


def test_cleanup_clean_config_drop_extras_url():
    url = _terria_url(_share_state_with_private_catalog())
    config = {"custom_config": url, "__extras": {"custom_config_url": url, "x": 1}}
    new_config, changed = cleanup_script.clean_config(config, drop_extras_url=True)
    assert changed is True
    assert "custom_config_url" not in new_config["__extras"]
    assert new_config["__extras"] == {"x": 1}


def test_cleanup_clean_config_noop_on_plain_config():
    plain = {"custom_config": "NA", "style": "NA",
             "terria_instance_url": "x", "filterable": True}
    assert cleanup_script.clean_config(dict(plain)) == (None, False)
    # a small non-private custom_config + leftover form field: not touched in
    # the default mode (no private branch to strip).
    small = _terria_url({"initSources": [{"models": {
        "/": {"type": "group", "members": ["L"]},
        "L": {"type": "csv", "url": "u", "knownContainerUniqueIds": ["/"]}}}]})
    cfg = {"custom_config": small, "__extras": {"custom_config_url": small}}
    assert cleanup_script.clean_config(cfg, drop_extras_url=False) == (None, False)
