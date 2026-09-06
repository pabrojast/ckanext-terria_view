#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test private dataset functionality for ckanext-terria_view.

These tests use mocking to avoid requiring a full CKAN installation.
"""

import contextlib
import json
import re
import sys
import types
import urllib.parse
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from requests.structures import CaseInsensitiveDict

# Mock CKAN modules before importing our code
ckan_mock = types.ModuleType('ckan')
ckan_plugins_mock = types.ModuleType('ckan.plugins')
ckan_plugins_toolkit_mock = MagicMock()
ckan_common_mock = MagicMock()
ckan_logic_mock = types.ModuleType('ckan.logic')
ckan_logic_action_mock = types.ModuleType('ckan.logic.action')
ckan_logic_action_get_mock = MagicMock()
ckan_model_mock = MagicMock()
ckan_lib_mock = types.ModuleType('ckan.lib')
ckan_lib_uploader_mock = MagicMock()

sys.modules['ckan'] = ckan_mock
sys.modules['ckan.plugins'] = ckan_plugins_mock
sys.modules['ckan.plugins.toolkit'] = ckan_plugins_toolkit_mock
sys.modules['ckan.common'] = ckan_common_mock
sys.modules['ckan.logic'] = ckan_logic_mock
sys.modules['ckan.logic.action'] = ckan_logic_action_mock
sys.modules['ckan.logic.action.get'] = ckan_logic_action_get_mock
sys.modules['ckan.model'] = ckan_model_mock
sys.modules['ckan.lib'] = ckan_lib_mock
sys.modules['ckan.lib.uploader'] = ckan_lib_uploader_mock

# Mock flask
flask_mock = MagicMock()
sys.modules.setdefault('flask', flask_mock)

# Setup toolkit mock
ckan_plugins_toolkit_mock.config = {'ckan.site_url': 'https://test.example.org'}
ckan_plugins_toolkit_mock.get_action = MagicMock()
# Real exception classes so ``except toolkit.NotAuthorized`` clauses work.
ckan_plugins_toolkit_mock.NotAuthorized = type('NotAuthorized', (Exception,), {})
ckan_plugins_toolkit_mock.ObjectNotFound = type('ObjectNotFound', (Exception,), {})
# ``url_for`` is not a real router here: ``_ckan_path`` must use its fallbacks.
ckan_plugins_toolkit_mock.url_for = MagicMock(return_value=MagicMock())
ckan_plugins_toolkit_mock.check_access = MagicMock()

# Now import our modules
from ckanext.terria_view.cache_manager import CacheManager
from ckanext.terria_view.file_cache_manager import FileCacheManager


# --- Fakes for the Flask/CKAN objects that api_endpoints touches -------------

class FakeUser:
    """Minimal stand-in for CKAN 2.10's ``toolkit.current_user`` when logged in."""
    is_anonymous = False

    def __init__(self, name='alice', fullname='Alice Example', sysadmin=False):
        self.name = name
        self.fullname = fullname
        self.sysadmin = sysadmin

    @property
    def display_name(self):
        return self.fullname or self.name


class FakeAnonymousUser:
    """CKAN 2.10 ``AnonymousUser``: a *truthy* object with an empty name."""
    is_anonymous = True
    name = ''
    sysadmin = False

    @property
    def id(self):
        raise AttributeError('anonymous users have no id')


class FakeResponse:
    """Stand-in for ``flask.Response`` (flask is mocked in this harness)."""

    def __init__(self, response=b'', status=200, headers=None, mimetype=None,
                 content_type=None, direct_passthrough=False):
        self.body = response
        self.status_code = status
        self.mimetype = mimetype
        self.content_type = content_type or mimetype
        self.direct_passthrough = direct_passthrough
        self.headers = dict(headers or {})

    def get_data(self, as_text=False):
        body = self.body
        if not isinstance(body, (bytes, str)):
            body = b''.join(body)
        if as_text and isinstance(body, bytes):
            body = body.decode('utf-8')
        return body

    def json(self):
        return json.loads(self.get_data(as_text=True))


class FakeUpstream:
    """Stand-in for a streamed ``requests.Response`` from blob storage."""

    def __init__(self, status_code=200, headers=None, chunks=(), text=''):
        self.status_code = status_code
        self.headers = CaseInsensitiveDict(headers or {})
        self.text = text
        self.close_calls = 0
        self.raw = MagicMock()
        self.raw.stream = MagicMock(return_value=iter(list(chunks)))

    def close(self):
        self.close_calls += 1


def _flask_request(args=None, headers=None, method='GET', environ=None):
    """Build a fake ``flask.request`` to patch over ``api_endpoints.request``."""
    return SimpleNamespace(
        args=dict(args or {}),
        headers=CaseInsensitiveDict(headers or {}),
        method=method,
        environ={} if environ is None else environ,
    )


def _make_controller():
    """A ``TerriaAPIController`` with a mocked generator (no CKAN, no file caches)."""
    from ckanext.terria_view.api_endpoints import TerriaAPIController

    controller = TerriaAPIController.__new__(TerriaAPIController)
    controller.generator = MagicMock()
    controller.private_catalog_builder = MagicMock()
    return controller


def _registered_routes():
    """``{rule: methods}`` as registered on ``terria_api``.

    ``flask`` is a MagicMock in this harness, so ``@terria_api.route(rule)`` is
    recorded on the mock instead of a real url map.
    """
    from ckanext.terria_view.api_endpoints import terria_api

    return {
        call.args[0]: call.kwargs.get('methods')
        for call in terria_api.route.call_args_list
    }


def _route_function(name):
    """The undecorated view function ``name`` as it was handed to ``terria_api.route``."""
    from ckanext.terria_view.api_endpoints import terria_api

    for call in terria_api.route.return_value.call_args_list:
        func = call.args[0] if call.args else None
        if getattr(func, '__name__', None) == name:
            return func
    raise AssertionError(f'{name} is not registered on terria_api')


def _import_plugin_class():
    """Import ``Terria_ViewPlugin`` under the mocked ``ckan.plugins`` namespace."""
    class _StubBase:
        pass
    import ckan.plugins as _ckp
    for attr in ('SingletonPlugin', 'implements'):
        if not hasattr(_ckp, attr) or getattr(_ckp, attr) is None:
            setattr(_ckp, attr, _StubBase if attr == 'SingletonPlugin' else (lambda *a, **k: None))
    for iface in ('IConfigurer', 'IBlueprint', 'ITemplateHelpers', 'IConfigurable',
                  'IResourceView', 'IActions'):
        if not hasattr(_ckp, iface):
            setattr(_ckp, iface, _StubBase)
    from ckanext.terria_view.plugin import Terria_ViewPlugin
    return Terria_ViewPlugin


def test_format_dataset_item_accepts_package_and_user_context():
    """Test that format_dataset_item accepts optional package and user_context params."""
    from ckanext.terria_view.terria_json_generator import TerriaJSONGenerator

    gen = TerriaJSONGenerator()

    # Mock get_action for resource_view_list
    ckan_plugins_toolkit_mock.get_action.return_value = MagicMock(return_value=[])

    resource = {
        'id': 'test-resource-id',
        'format': 'shp',
        'url': 'https://test.example.org/resource/test.zip',
        'name': 'Test Resource',
        'description': 'A test resource'
    }
    org_info = {
        'display_name': 'Test Org',
        'description': 'Org description',
        'image_display_url': ''
    }

    # Without package/user_context (backward compat)
    result, views = gen.format_dataset_item(resource, 'pkg-123', 'Notes', org_info, 0)
    assert result['name'] == 'Test Resource'
    assert result['type'] == 'shp'
    assert result['id'] == 'test-resource-id'

    # With package and user_context
    package = {'id': 'pkg-123', 'private': True}
    user_ctx = {'user': 'testuser', 'auth_user_obj': MagicMock()}

    result2, views2 = gen.format_dataset_item(
        resource, 'pkg-123', 'Notes', org_info, 0,
        package=package, user_context=user_ctx
    )
    assert result2['name'] == 'Test Resource'
    assert result2['type'] == 'shp'
    print("  PASS: format_dataset_item accepts package and user_context")


def test_format_dataset_item_uses_resource_utils_for_url():
    """Test that format_dataset_item delegates URL resolution to resource_utils."""
    from ckanext.terria_view.terria_json_generator import TerriaJSONGenerator

    gen = TerriaJSONGenerator()

    # Mock get_action
    ckan_plugins_toolkit_mock.get_action.return_value = MagicMock(return_value=[])

    # Mock resource_utils to track calls
    gen.resource_utils.get_resource_url = MagicMock(return_value='https://resolved-url.org/file.zip')

    resource = {
        'id': 'res-1',
        'format': 'cog',
        'url': 'https://original-url.org/file.tif',
        'name': 'Test COG'
    }
    org_info = {'display_name': 'Org', 'description': '', 'image_display_url': ''}
    package = {'id': 'pkg-1', 'private': True}
    user_ctx = {'user': 'admin'}

    result, _ = gen.format_dataset_item(
        resource, 'pkg-1', '', org_info, 0,
        package=package, user_context=user_ctx
    )

    # Verify resource_utils was called with correct args (absolute URLs by default)
    gen.resource_utils.get_resource_url.assert_called_once_with(
        resource, package, user_ctx, relative_urls=False
    )
    assert result['url'] == 'https://resolved-url.org/file.zip'
    print("  PASS: format_dataset_item delegates to resource_utils.get_resource_url")


def test_cache_manager_docstring_mentions_public_only():
    """Verify cache manager documents public-only policy."""
    assert 'public' in CacheManager.__module__ or 'ONLY public' in open(
        'ckanext/terria_view/cache_manager.py').read()
    print("  PASS: CacheManager documents public-only cache policy")


def test_file_cache_manager_docstring_mentions_public_only():
    """Verify file cache manager documents public-only policy."""
    content = open('ckanext/terria_view/file_cache_manager.py').read()
    assert 'ONLY public' in content
    print("  PASS: FileCacheManager documents public-only cache policy")


def test_template_has_iframe_with_hash_start():
    """Template must always load the resource via #start= so TerriaJS populates workbench."""
    with open('ckanext/terria_view/templates/terria.html', 'r') as f:
        content = f.read()

    assert 'src="{{ terria_instance_url }}#start={{ encoded_config }}"' in content, (
        "Template must load the resource via #start= in the iframe src for both public "
        "and private views. Private catalog is merged server-side into encoded_config."
    )
    # The legacy postMessage private-catalog dance should no longer be in the template —
    # server-side merge replaces it.
    assert 'postConfigToIframe' not in content
    assert 'postPrivateCatalogToIframe' not in content
    assert 'terria-iframe' in content
    print("  PASS: template uses #start= consistently (no postMessage private-catalog path)")


def test_plugin_merges_private_catalog_into_encoded_config():
    """setup_template_variables must merge private catalog entries into the resource initSource."""
    with open('ckanext/terria_view/plugin.py', 'r') as f:
        content = f.read()

    assert '_merge_private_catalog_into_encoded_config' in content, (
        "plugin.py should define _merge_private_catalog_into_encoded_config"
    )
    # Entries are now merged into the resource's existing initSource catalog to
    # avoid TerriaJS re-initializing the workbench when it processes a second
    # init source.
    assert 'catalog.extend(private_entries)' in content, (
        "merge helper must extend the primary initSource catalog with private entries"
    )
    print("  PASS: plugin merges private catalog into encoded_config server-side")


def test_merge_helper_preserves_workbench_and_catalog_structure():
    """Live roundtrip: merging must keep initSources[0] workbench intact and add catalog entries."""
    # Call the unbound method directly so we don't need to instantiate the full
    # CKAN SingletonPlugin (which pulls in more mocks than we set up here).
    Terria_ViewPlugin = _import_plugin_class()
    merge_fn = Terria_ViewPlugin.__dict__['_merge_private_catalog_into_encoded_config']

    class _Dummy:
        def _debug_print(self, msg):
            pass

    base_config = {
        'version': '8.0.0',
        'initSources': [{
            'stratum': 'user',
            'catalog': [{'name': 'R1', 'type': 'csv', 'id': 'r1', 'url': 'https://u/1.csv'}],
            'workbench': ['r1'],
            'viewerMode': '3D'
        }]
    }
    encoded = urllib.parse.quote(json.dumps(base_config))
    private = {
        'catalog': [{
            'name': 'Private Datasets (alice)',
            'type': 'group',
            'members': [{'name': 'P1', 'type': 'csv', 'id': 'p1', 'url': 'https://u/p1.csv'}]
        }]
    }

    merged_encoded = merge_fn(_Dummy(), encoded, private)
    merged = json.loads(urllib.parse.unquote(merged_encoded))

    # There must still be exactly one initSource (merged inside, not appended).
    assert len(merged['initSources']) == 1, (
        f'Expected exactly 1 initSource after merge, got {len(merged["initSources"])}'
    )
    primary = merged['initSources'][0]
    # Workbench must survive untouched.
    assert primary['workbench'] == ['r1']
    # Catalog now contains original resource + private group.
    assert len(primary['catalog']) == 2
    assert primary['catalog'][0]['id'] == 'r1'
    assert primary['catalog'][1]['name'].startswith('Private Datasets')
    print("  PASS: merge preserves workbench and extends catalog in place")


def test_template_private_only_for_logged_in():
    """Private catalog generation must require login and the configured view scope."""
    # Since the template now only sees a pre-merged encoded_config, the
    # conditional lives in plugin.py: we only generate/merge private_catalog_data
    # when both user_context.user is set and the package is private.
    with open('ckanext/terria_view/plugin.py', 'r') as f:
        content = f.read()

    assert "include_private_catalog = bool(user_context.get('user')) and (" in content
    assert "bool(package.get('private')) or inject_on_public_views" in content
    assert "build_private_catalog_reference(" in content
    assert 'and private_catalog_data' in content
    print("  PASS: Private catalog generation is guarded by user+private conditions")


def test_setup_template_variables_returns_private_fields():
    """Verify setup_template_variables returns user_logged_in and private_catalog_data."""
    # Check the source code for the return dict
    with open('ckanext/terria_view/plugin.py', 'r') as f:
        content = f.read()

    assert "'user_logged_in'" in content, "plugin.py should return user_logged_in"
    assert "'private_catalog_data'" in content, "plugin.py should return private_catalog_data"
    assert '_get_private_datasets_catalog' in content, "plugin.py should have _get_private_datasets_catalog method"
    print("  PASS: setup_template_variables returns user_logged_in and private_catalog_data")


def test_private_uploaded_resource_returns_proxy_url():
    """Private uploaded resources should return the CKAN proxy URL with a signed token."""
    from ckanext.terria_view.config_manager import ConfigManager
    from ckanext.terria_view.resource_utils import ResourceUtils

    ckan_plugins_toolkit_mock.config = {
        'ckan.site_url': 'https://test.example.org',
        'beaker.session.secret': 'test-secret'
    }
    # Reset uploader call tracking to avoid pollution from earlier tests
    ckan_lib_uploader_mock.reset_mock()

    config = ConfigManager(site_url='https://test.example.org')
    utils = ResourceUtils(config)

    resource = {
        'id': 'res',
        'format': 'csv',
        'url': '/dataset/pkg/resource/res/download/member-states.csv',
        'url_type': 'upload'
    }
    package = {'id': 'pkg', 'private': True}
    user_ctx = {'user': 'tester'}

    resolved = utils.get_resource_url(resource, package, user_ctx)

    # Proxy route is preferred so Terria's cross-origin iframe can fetch without
    # depending on Azure Storage CORS configuration for the Terria origin.
    # Filename is included in the path so TerriaJS URL-extension validations don't reject it.
    assert resolved.startswith(
        'https://test.example.org/api/terria/resource/res/content/member-states.csv?token='
    )
    assert 'token=' in resolved
    # Uploader should NOT be invoked in this path — the endpoint resolves the SAS itself.
    ckan_lib_uploader_mock.get_resource_uploader.assert_not_called()
    print("  PASS: private uploaded resource returns CKAN proxy URL with filename and token")


def test_private_shapefile_proxy_url_preserves_zip_extension():
    """Shapefiles must expose a .zip URL even through the proxy (Terria client check)."""
    from ckanext.terria_view.config_manager import ConfigManager
    from ckanext.terria_view.resource_utils import ResourceUtils

    ckan_plugins_toolkit_mock.config = {
        'ckan.site_url': 'https://test.example.org',
        'beaker.session.secret': 'shp-secret'
    }
    ckan_lib_uploader_mock.reset_mock()

    utils = ResourceUtils(ConfigManager(site_url='https://test.example.org'))
    resource = {
        'id': 'shp-1',
        'format': 'shp',
        'url': '/dataset/pkg/resource/shp-1/download/member-states.zip',
        'url_type': 'upload'
    }
    package = {'id': 'pkg', 'private': True}
    user_ctx = {'user': 'tester'}

    resolved = utils.get_resource_url(resource, package, user_ctx)

    # Strip the token query string before inspecting path to avoid false-positive matches.
    url_without_query = resolved.split('?', 1)[0]
    assert url_without_query.endswith('.zip'), (
        f'Expected proxy URL to preserve .zip extension, got: {url_without_query}'
    )
    assert '/api/terria/resource/shp-1/content/member-states.zip' in resolved
    print("  PASS: shapefile proxy URL preserves .zip extension for TerriaJS validation")


def test_proxy_url_preserves_extension_for_all_uploaded_formats():
    """Proxy URL must preserve every upload extension TerriaJS validates client-side."""
    from ckanext.terria_view.config_manager import ConfigManager
    from ckanext.terria_view.resource_utils import ResourceUtils

    ckan_plugins_toolkit_mock.config = {
        'ckan.site_url': 'https://test.example.org',
        'beaker.session.secret': 'multi-fmt-secret'
    }
    utils = ResourceUtils(ConfigManager(site_url='https://test.example.org'))
    package = {'id': 'pkg', 'private': True}
    user_ctx = {'user': 'tester'}

    # (format, filename, expected extension in proxy URL path)
    cases = [
        ('csv', 'hourly_precipitation_data.csv', '.csv'),
        ('geojson', 'country-boundaries.geojson', '.geojson'),
        ('tif', 'dem.tif', '.tif'),
        ('tiff', 'ndvi.tiff', '.tiff'),
        ('geotiff', 'elevation.tiff', '.tiff'),
        ('cog', 'landcover.tif', '.tif'),
        ('kml', 'markers.kml', '.kml'),
        ('czml', 'flight.czml', '.czml'),
    ]

    for fmt, fname, expected_ext in cases:
        resource = {
            'id': f'res-{fmt}',
            'format': fmt,
            'url': f'/dataset/pkg/resource/res-{fmt}/download/{fname}',
            'url_type': 'upload'
        }
        resolved = utils.get_resource_url(resource, package, user_ctx)
        path = resolved.split('?', 1)[0]
        assert path.endswith(expected_ext), (
            f"format={fmt!r}: expected proxy URL to end with {expected_ext}, got {path!r}"
        )
        assert f'/api/terria/resource/res-{fmt}/content/{fname}' in resolved, (
            f"format={fmt!r}: proxy URL did not include filename segment (got {resolved!r})"
        )
    print(f"  PASS: proxy URL preserves extension for {len(cases)} uploaded formats")


def test_proxy_url_without_filename_still_valid():
    """When the filename cannot be extracted, the proxy URL falls back to the bare path."""
    from ckanext.terria_view.config_manager import ConfigManager
    from ckanext.terria_view.resource_utils import ResourceUtils

    ckan_plugins_toolkit_mock.config = {'beaker.session.secret': 'bare-secret'}

    utils = ResourceUtils(ConfigManager(site_url='https://test.example.org'))
    url = utils.build_proxy_resource_url('res-bare', filename=None)
    assert '/api/terria/resource/res-bare/content?token=' in url
    assert '/api/terria/resource/res-bare/content/None' not in url
    print("  PASS: proxy URL builder works without a filename segment")


def test_generate_and_verify_resource_token_roundtrip():
    """Tokens generated by ResourceUtils should verify for the same resource_id."""
    from ckanext.terria_view.config_manager import ConfigManager
    from ckanext.terria_view.resource_utils import ResourceUtils

    ckan_plugins_toolkit_mock.config = {'beaker.session.secret': 'test-secret-roundtrip'}

    utils = ResourceUtils(ConfigManager())
    token = utils.generate_resource_token('res-xyz')

    assert utils.verify_resource_token('res-xyz', token) is True
    # Tokens should be bound to the specific resource_id, not transferable.
    assert utils.verify_resource_token('different-resource', token) is False
    print("  PASS: resource proxy token verifies for the same resource and rejects others")


def test_expired_resource_token_is_rejected():
    """Tokens past their expiry timestamp must be rejected."""
    from ckanext.terria_view.config_manager import ConfigManager
    from ckanext.terria_view.resource_utils import ResourceUtils

    ckan_plugins_toolkit_mock.config = {'beaker.session.secret': 'test-secret-expired'}

    utils = ResourceUtils(ConfigManager())
    with patch('ckanext.terria_view.resource_utils.time.time', return_value=1_000_000):
        token = utils.generate_resource_token('res-1', ttl_seconds=60)

    # Fast-forward time far beyond expiry
    with patch('ckanext.terria_view.resource_utils.time.time', return_value=1_000_000 + 10_000):
        assert utils.verify_resource_token('res-1', token) is False
    print("  PASS: expired resource proxy tokens are rejected")


def test_resource_token_tampering_is_rejected():
    """Any mutation of the signature part must invalidate the token."""
    from ckanext.terria_view.config_manager import ConfigManager
    from ckanext.terria_view.resource_utils import ResourceUtils

    ckan_plugins_toolkit_mock.config = {'beaker.session.secret': 'test-secret-tamper'}

    utils = ResourceUtils(ConfigManager())
    token = utils.generate_resource_token('res-2')
    expiry, _, signature = token.partition('.')
    flipped = signature[:-1] + ('0' if signature[-1] != '0' else '1')
    tampered = f"{expiry}.{flipped}"

    assert utils.verify_resource_token('res-2', tampered) is False
    print("  PASS: tampered resource proxy tokens are rejected")


def test_resource_content_endpoint_is_registered():
    """A GET route must exist at /api/terria/resource/<id>/content for the proxy."""
    with open('ckanext/terria_view/api_endpoints.py', 'r') as f:
        content = f.read()

    assert "/api/terria/resource/<resource_id>/content" in content
    assert 'def resource_content(self' in content
    assert "def resource_content_endpoint" in content
    assert 'verify_resource_token' in content
    print("  PASS: resource content proxy endpoint is registered")


def test_terria_friendly_content_type_overrides_octet_stream():
    """CSV/GeoJSON over octet-stream must be rewritten to TerriaJS-friendly mimetypes."""
    # Reimport with mimetypes/os mocks cleared so the helper sees the real module.
    real_mimetypes = __import__('mimetypes')
    real_os = __import__('os')
    sys.modules['mimetypes'] = real_mimetypes
    sys.modules['os'] = real_os

    from ckanext.terria_view.api_endpoints import _terria_friendly_content_type

    # Classic regression: upstream returns octet-stream for a CSV — we must fix it.
    assert _terria_friendly_content_type(
        'hourly_precipitation_data.csv', 'application/octet-stream'
    ) == 'text/csv'
    assert _terria_friendly_content_type(
        'country.geojson', 'application/octet-stream'
    ) == 'application/geo+json'
    assert _terria_friendly_content_type(
        'dem.tif', 'application/octet-stream'
    ) == 'image/tiff'
    assert _terria_friendly_content_type(
        'layer.czml', 'application/octet-stream'
    ) == 'application/json'
    # Shapefile: upstream may say zip — keep it, Terria is fine with it.
    assert _terria_friendly_content_type(
        'member-states.zip', 'application/zip'
    ) == 'application/zip'
    # Falls through when we don't know: return whatever fallback we had.
    assert _terria_friendly_content_type(None, 'text/plain') == 'text/plain'
    print("  PASS: _terria_friendly_content_type overrides octet-stream with per-extension mimetype")


def test_relative_resource_url_is_normalized_to_absolute():
    """Relative CKAN resource URLs should be normalized for cross-domain Terria iframe."""
    from ckanext.terria_view.config_manager import ConfigManager
    from ckanext.terria_view.resource_utils import ResourceUtils

    ckan_plugins_toolkit_mock.config = {'ckan.site_url': 'https://test.example.org'}

    config = ConfigManager(site_url='https://test.example.org')
    utils = ResourceUtils(config)

    resource = {
        'id': 'res2',
        'format': 'csv',
        'url': '/dataset/pkg/resource/res/download/file.csv',
        'url_type': 'link'
    }
    package = {'id': 'pkg', 'private': False}
    user_ctx = {}

    resolved = utils.get_resource_url(resource, package, user_ctx)

    assert resolved == 'https://test.example.org/dataset/pkg/resource/res/download/file.csv'
    print("  PASS: relative resource URL is normalized to absolute")


def test_api_endpoint_passes_context_to_format_dataset_item():
    """Verify API endpoint passes package and user_context to format_dataset_item."""
    with open('ckanext/terria_view/api_endpoints.py', 'r') as f:
        content = f.read()

    # Check that format_dataset_item calls include package= and user_context=
    assert 'package=dataset' in content, "API should pass package=dataset"
    assert 'user_context=context' in content, "API should pass user_context=context"
    print("  PASS: API endpoint passes package and user_context to format_dataset_item")


def test_can_view_resource_handles_missing_url_without_crashing():
    """ConfigManager.can_view_resource should return False (not raise) when url is missing."""
    from ckanext.terria_view.config_manager import ConfigManager

    manager = ConfigManager()
    assert manager.can_view_resource({'format': ''}) is False
    assert manager.can_view_resource({}) is False
    print("  PASS: can_view_resource handles missing url safely")


def test_resource_utils_extracts_filename_from_download_urls():
    """Upload filename extraction should return plain filename from CKAN download URLs."""
    from ckanext.terria_view.config_manager import ConfigManager
    from ckanext.terria_view.resource_utils import ResourceUtils

    utils = ResourceUtils(ConfigManager(site_url='https://test.example.org'))
    resource = {
        'id': 'res',
        'url': '/dataset/pkg/resource/res/download/member-states.csv',
        'url_type': 'upload'
    }
    filename = utils._extract_upload_filename(
        resource,
        'https://test.example.org/dataset/pkg/resource/res/download/member-states.csv'
    )
    assert filename == 'member-states.csv'
    print("  PASS: resource_utils extracts upload filename from download URLs")


def test_plugin_registers_resource_view_cache_invalidation_actions():
    """Ensure resource_view chained actions are registered to invalidate cache on style updates."""
    with open('ckanext/terria_view/plugin.py', 'r') as f:
        content = f.read()

    assert 'def resource_view_create(self, next_action, context, data_dict):' in content
    assert 'def resource_view_update(self, next_action, context, data_dict):' in content
    assert 'def resource_view_delete(self, next_action, context, data_dict):' in content
    assert "actions['resource_view_create']" in content
    assert "actions['resource_view_update']" in content
    assert "actions['resource_view_delete']" in content
    assert 'def _clear_sld_result_caches(self):' in content
    assert 'self._clear_sld_result_caches()' in content
    print("  PASS: Plugin registers resource_view chained actions for cache invalidation")


def test_resource_view_list_uses_resource_show_payload_for_can_view():
    """Auto-view creation should evaluate the fetched resource dict, not context['resource'] internals."""
    with open('ckanext/terria_view/plugin.py', 'r') as f:
        content = f.read()

    assert "plugin_instance.config_manager.can_view_resource(resource)" in content
    assert "context['resource'].__dict__" not in content
    assert "resource = None" in content
    print("  PASS: resource_view_list checks can_view_resource against resource_show payload")


def test_private_catalog_injection_is_limited_to_private_package_views():
    """Public-view injection remains opt-in while private views stay enabled."""
    with open('ckanext/terria_view/plugin.py', 'r') as f:
        content = f.read()

    assert "'ckanext.terria_view.inject_private_catalog_on_public_views'" in content
    assert "bool(package.get('private')) or inject_on_public_views" in content
    print("  PASS: private catalog injection scope is preserved")


def test_private_catalog_mode_auto_uses_same_origin_lazy_loading():
    from ckanext.terria_view.private_catalog import resolve_private_catalog_mode

    assert resolve_private_catalog_mode(
        'auto', 'https://data.dev-wins.com', 'https://data.dev-wins.com/terria/'
    ) == 'lazy'
    assert resolve_private_catalog_mode(
        'auto', 'https://data.dev-wins.com', 'https://maps.example.org/'
    ) == 'inline'
    assert resolve_private_catalog_mode(
        'auto', 'https://data.dev-wins.com', '/terria/'
    ) == 'lazy'
    assert resolve_private_catalog_mode(
        'inline', 'https://data.dev-wins.com', 'https://data.dev-wins.com/terria/'
    ) == 'inline'


def test_lazy_private_catalog_reference_is_small_and_authenticated_endpoint_only():
    from ckanext.terria_view.private_catalog import build_private_catalog_reference

    result = build_private_catalog_reference(
        'alice', 'https://data.dev-wins.com', 'abcdefgh'
    )
    reference = result['catalog'][0]
    assert reference['type'] == 'terria-reference'
    assert reference['isGroup'] is True
    assert reference['id'].startswith('__ckan_private_catalog__/abcdefgh/')
    assert reference['url'] == (
        'https://data.dev-wins.com/api/terria/user/private-catalog'
        '?catalog_id=abcdefgh'
    )
    assert len(json.dumps(result)) < 2048


def test_lazy_private_catalog_routes_disable_shared_caching():
    with open('ckanext/terria_view/api_endpoints.py', 'r') as stream:
        content = stream.read()

    assert "'/api/terria/user/private-catalog'" in content
    assert "'/api/terria/user/private-catalog/dataset/<dataset_id>'" in content
    assert "'Cache-Control'] = 'private, no-store, max-age=0'" in content
    assert "'CDN-Cache-Control'] = 'no-store'" in content
    assert "'Surrogate-Control'] = 'no-store'" in content
    assert "'Vary'] = 'Cookie, Authorization'" in content


def test_lazy_private_catalog_index_contains_dataset_references_not_resources():
    from ckanext.terria_view.private_catalog import NON_PUBLIC_FQ, PrivateCatalogBuilder

    package_search = MagicMock(return_value={
        'count': 2,
        'results': [
            {'id': 'd2', 'name': 'two', 'title': 'Two', 'organization': 'org-a',
             'capacity': 'private'},
            {'id': 'd1', 'name': 'one', 'title': 'One', 'organization': 'org-a',
             'capacity': 'private'},
        ],
        'search_facets': {'organization': {'items': [
            {'name': 'org-a', 'display_name': 'Organization A'}
        ]}},
    })
    access_check = MagicMock(return_value={'can_download': True})

    def get_action(name):
        return {
            'package_search': package_search,
            'datashare_access_check': access_check,
        }[name]

    generator = MagicMock()
    with patch.object(ckan_plugins_toolkit_mock, 'get_action', side_effect=get_action):
        result = PrivateCatalogBuilder(
            generator, 'https://data.dev-wins.com'
        ).build_index({'user': 'alice'}, 'abcdefgh')

    group = result['catalog'][0]
    members = group['members']
    assert group['name'] == 'Organization A'
    assert group['isOpen'] is True
    assert group['shareable'] is False
    assert [member['name'] for member in members] == ['One', 'Two']
    assert all(member['type'] == 'terria-reference' for member in members)
    # Same-origin lazy catalog: relative URLs, never through the Terria proxy.
    assert all(
        member['url'].startswith('/api/terria/user/private-catalog/dataset/')
        for member in members
    )
    assert all('catalog_id=abcdefgh' in member['url'] for member in members)
    assert 'resources' not in json.dumps(result)
    # One union query (confidential U non-public datashare levels), not one per level.
    assert package_search.call_count == 1
    search_params = package_search.call_args.args[1]
    assert search_params['fq'] == NON_PUBLIC_FQ
    assert search_params['include_private'] is True
    assert 'extras_access_level' in search_params['fl']
    assert 'capacity' in search_params['fl']
    assert access_check.call_count == 2


def test_lazy_dataset_expansion_fetches_resource_views_once_and_namespaces_items():
    from ckanext.terria_view.private_catalog import PrivateCatalogBuilder

    package = {
        'id': 'dataset-1',
        'private': True,
        'state': 'active',
        'title': 'Dataset',
        'notes': '',
        'organization': {'name': 'org', 'title': 'Org'},
        'resources': [{'id': 'resource-1', 'format': 'csv', 'name': 'Resource'}],
    }
    package_show = MagicMock(return_value=package)
    resource_view_list = MagicMock(return_value=[
        {'view_type': 'terria_view', 'title': 'A'},
        {'view_type': 'terria_view', 'title': 'B'},
    ])

    def get_action(name):
        return {
            'package_show': package_show,
            'resource_view_list': resource_view_list,
            'datashare_access_check': MagicMock(return_value={'can_download': True}),
        }[name]

    generator = MagicMock()
    generator.formatos_permitidos = ['csv']
    generator.convert_sets_to_lists.side_effect = lambda value: value
    generator.format_dataset_item.side_effect = lambda *args, **kwargs: (
        {'name': f"View {args[4]}", 'type': 'csv', 'id': 'resource-1'}, 2
    )

    with patch.object(ckan_plugins_toolkit_mock, 'get_action', side_effect=get_action):
        result = PrivateCatalogBuilder(generator).build_dataset(
            {'user': 'alice'}, 'dataset-1', 'abcdefgh'
        )

    assert resource_view_list.call_count == 1
    assert len(result['catalog']) == 2
    assert all(
        item['id'].startswith('__ckan_private_catalog__/abcdefgh/resource/resource-1/')
        for item in result['catalog']
    )
    assert all(
        call.kwargs['terria_views'] == resource_view_list.return_value
        for call in generator.format_dataset_item.call_args_list
    )
    # Lazy items are consumed same-origin: proxy URLs must be relative.
    assert all(
        call.kwargs['relative_urls'] is True
        for call in generator.format_dataset_item.call_args_list
    )


def test_process_custom_config_populates_workbench_and_sanitizes_styles():
    """Custom config processing should keep data model in workbench and normalize incomplete styles."""
    from ckanext.terria_view.terria_config_builder import TerriaConfigBuilder
    from ckanext.terria_view.config_manager import ConfigManager

    class DummySLDProcessor:
        def process_sld_for_resource(self, *_args, **_kwargs):
            return None

    builder = TerriaConfigBuilder(ConfigManager(), DummySLDProcessor())

    start_data = {
        "version": "8.0.0",
        "initSources": [{
            "stratum": "user",
            "models": {
                "/": {"type": "group", "members": ["member states"]},
                "member states": {
                    "type": "csv",
                    "url": "https://old.example.org/file.csv",
                    "knownContainerUniqueIds": ["/"],
                    "styles": [{
                        "id": "rf",
                        "color": {
                            "enumColors": [{"value": "A", "color": "#ffffff"}]
                        }
                    }],
                    "activeStyle": "rf"
                }
            },
            "workbench": []
        }]
    }

    custom_url = "https://ihp-wins.unesco.org/terria/#start=" + urllib.parse.quote(
        json.dumps(start_data)
    )

    result = builder.process_custom_config(
        custom_url,
        "https://data.dev-wins.com/dataset/x/resource/y/download/file.csv",
        "csv",
        None
    )

    processed = json.loads(result)
    source = processed["initSources"][0]
    model = source["models"]["member states"]
    style = model["styles"][0]

    assert "member states" in source["workbench"]
    assert model["url"].startswith("https://data.dev-wins.com/")
    assert model["show"] is True
    assert model["isOpenInWorkbench"] is True
    assert style["color"]["mapType"] == "enum"
    assert style["color"]["colorColumn"] == "rf"
    print("  PASS: process_custom_config keeps workbench items and sanitizes table styles")


def test_process_custom_config_sanitizes_palette_only_style():
    """Palette-only color style should infer continuous mapType and colorColumn."""
    from ckanext.terria_view.terria_config_builder import TerriaConfigBuilder
    from ckanext.terria_view.config_manager import ConfigManager

    class DummySLDProcessor:
        def process_sld_for_resource(self, *_args, **_kwargs):
            return None

    builder = TerriaConfigBuilder(ConfigManager(), DummySLDProcessor())

    start_data = {
        "version": "8.0.0",
        "initSources": [{
            "stratum": "user",
            "models": {
                "/": {"type": "group", "members": ["Hourly Data"]},
                "Hourly Data": {
                    "type": "csv",
                    "url": "https://old.example.org/file.csv",
                    "knownContainerUniqueIds": ["/"],
                    "styles": [{
                        "id": "rf",
                        "color": {
                            "binColors": [],
                            "enumColors": [],
                            "colorPalette": "Blues"
                        }
                    }],
                    "activeStyle": "rf"
                }
            },
            "workbench": []
        }]
    }

    custom_url = "https://ihp-wins.unesco.org/terria/#start=" + urllib.parse.quote(
        json.dumps(start_data)
    )

    result = builder.process_custom_config(
        custom_url,
        "https://data.dev-wins.com/dataset/x/resource/y/download/file.csv",
        "csv",
        None
    )

    processed = json.loads(result)
    model = processed["initSources"][0]["models"]["Hourly Data"]
    color = model["styles"][0]["color"]

    assert color["mapType"] == "continuous"
    assert color["colorColumn"] == "rf"
    print("  PASS: process_custom_config sanitizes palette-only styles")


def test_process_custom_config_category_palette_forces_enum_maptype():
    """Category palettes should not keep continuous mapType in CSV categorical styles."""
    from ckanext.terria_view.terria_config_builder import TerriaConfigBuilder
    from ckanext.terria_view.config_manager import ConfigManager

    class DummySLDProcessor:
        def process_sld_for_resource(self, *_args, **_kwargs):
            return None

    builder = TerriaConfigBuilder(ConfigManager(), DummySLDProcessor())

    start_data = {
        "version": "8.0.0",
        "initSources": [{
            "stratum": "user",
            "models": {
                "/": {"type": "group", "members": ["member states"]},
                "member states": {
                    "type": "csv",
                    "url": "https://old.example.org/file.csv",
                    "knownContainerUniqueIds": ["/"],
                    "styles": [{
                        "id": "Electoral Group",
                        "color": {
                            "mapType": "continuous",
                            "colorPalette": "Category10"
                        }
                    }],
                    "activeStyle": "Electoral Group"
                }
            },
            "workbench": []
        }]
    }

    custom_url = "https://ihp-wins.unesco.org/terria/#start=" + urllib.parse.quote(
        json.dumps(start_data)
    )

    result = builder.process_custom_config(
        custom_url,
        "https://data.dev-wins.com/dataset/x/resource/y/download/file.csv",
        "csv",
        None
    )

    processed = json.loads(result)
    color = processed["initSources"][0]["models"]["member states"]["styles"][0]["color"]

    assert color["mapType"] == "enum"
    assert color["colorColumn"] == "Electoral Group"
    print("  PASS: category palette styles are normalized to enum mapType")


# --- Same-origin CKAN session ("whoami") endpoint -----------------------------

def test_user_session_anonymous_returns_200_without_user():
    from ckanext.terria_view import api_endpoints

    controller = _make_controller()
    fake_request = _flask_request()
    with patch.object(api_endpoints, 'Response', FakeResponse), \
            patch.object(api_endpoints, 'request', fake_request), \
            patch.object(ckan_plugins_toolkit_mock, 'current_user', FakeAnonymousUser()):
        response = controller.user_session()

    assert response.status_code == 200
    payload = response.json()
    assert payload['authenticated'] is False
    assert payload['user'] is None
    assert payload['private_catalog_url'] is None
    assert payload['login_url'] == '/user/login'
    assert payload['logout_url'] is None
    assert payload['profile_url'] is None
    assert response.headers['Cache-Control'] == 'private, no-store, max-age=0'
    assert response.headers['Vary'] == 'Cookie, Authorization'
    assert 'Access-Control-Allow-Origin' not in response.headers
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert fake_request.environ['__no_cache__'] is True


def test_user_session_authenticated_payload_and_relative_urls():
    from ckanext.terria_view import api_endpoints

    controller = _make_controller()
    with patch.object(api_endpoints, 'Response', FakeResponse), \
            patch.object(api_endpoints, 'request', _flask_request()), \
            patch.object(ckan_plugins_toolkit_mock, 'current_user', FakeUser(sysadmin=True)):
        response = controller.user_session()

    assert response.status_code == 200
    payload = response.json()
    assert payload['authenticated'] is True
    assert payload['user'] == {
        'name': 'alice', 'display_name': 'Alice Example', 'sysadmin': True
    }
    assert re.match(
        r'^/api/terria/user/private-catalog\?catalog_id=[A-Za-z0-9_-]{8,64}$',
        payload['private_catalog_url'],
    )
    assert payload['login_url'] == '/user/login'
    assert payload['logout_url'] == '/user/_logout'
    assert payload['profile_url'] == '/user/alice'
    for key in ('private_catalog_url', 'login_url', 'logout_url', 'profile_url'):
        assert not payload[key].startswith(('http', '//')), key
    assert response.headers['Cache-Control'] == 'private, no-store, max-age=0'


def test_user_session_never_raises_returns_anonymous_on_internal_error():
    from ckanext.terria_view import api_endpoints

    class ExplodingUser:
        is_anonymous = False

        @property
        def name(self):
            raise ValueError('boom')

    controller = _make_controller()
    with patch.object(api_endpoints, 'Response', FakeResponse), \
            patch.object(api_endpoints, 'request', _flask_request()), \
            patch.object(ckan_plugins_toolkit_mock, 'current_user', ExplodingUser()):
        response = controller.user_session()

    assert response.status_code == 200
    payload = response.json()
    assert payload['authenticated'] is False
    assert payload['user'] is None
    assert payload['login_url'] == '/user/login'


def test_user_session_route_is_registered():
    from ckanext.terria_view import api_endpoints

    assert _registered_routes()['/api/terria/user/session'] == ['GET']

    controller = MagicMock()
    with patch.object(api_endpoints, 'get_controller', return_value=controller):
        response = _route_function('user_session_endpoint')()
    controller.user_session.assert_called_once_with()
    assert response is controller.user_session.return_value


def test_get_user_context_treats_truthy_anonymous_user_as_anonymous():
    from ckanext.terria_view.api_endpoints import TerriaAPIController

    anonymous = FakeAnonymousUser()
    assert bool(anonymous) is True  # CKAN 2.10's AnonymousUser is truthy
    with patch.object(ckan_plugins_toolkit_mock, 'current_user', anonymous):
        assert TerriaAPIController._get_user_context() == {'user': '', 'auth_user_obj': None}
    with patch.object(ckan_plugins_toolkit_mock, 'current_user', None):
        assert TerriaAPIController._get_user_context() == {'user': '', 'auth_user_obj': None}

    user = FakeUser()
    with patch.object(ckan_plugins_toolkit_mock, 'current_user', user):
        context = TerriaAPIController._get_user_context()
    assert context['user'] == 'alice'
    assert context['auth_user_obj'] is user


def test_private_json_response_sets_no_cache_environ_and_drops_pragma():
    from ckanext.terria_view import api_endpoints

    controller = _make_controller()
    fake_request = _flask_request()
    with patch.object(api_endpoints, 'Response', FakeResponse), \
            patch.object(api_endpoints, 'request', fake_request):
        response = controller._create_private_json_response({'ok': True})

    # CKAN's middleware would otherwise append ``public, must-revalidate``.
    assert fake_request.environ['__no_cache__'] is True
    assert 'Pragma' not in response.headers
    assert response.headers['Cache-Control'] == 'private, no-store, max-age=0'
    assert response.headers['Vary'] == 'Cookie, Authorization'
    assert 'Access-Control-Allow-Origin' not in response.headers
    assert response.json() == {'ok': True}


# --- private_catalog helpers --------------------------------------------------

def test_api_url_relative_by_default_and_absolute_on_request():
    from ckanext.terria_view.private_catalog import (
        _absolute_api_url,
        _api_url,
        build_private_catalog_reference,
    )

    assert _api_url('/api/terria/user/private-catalog', 'abcdefgh') == (
        '/api/terria/user/private-catalog?catalog_id=abcdefgh'
    )
    assert _api_url(
        '/api/terria/user/private-catalog', 'abcdefgh',
        absolute=True, site_url='https://data.dev-wins.com/',
    ) == 'https://data.dev-wins.com/api/terria/user/private-catalog?catalog_id=abcdefgh'
    # Compatibility alias stays absolute.
    assert _absolute_api_url(
        'https://data.dev-wins.com', '/api/terria/user/private-catalog', 'abcdefgh'
    ) == 'https://data.dev-wins.com/api/terria/user/private-catalog?catalog_id=abcdefgh'

    relative = build_private_catalog_reference(
        'alice', 'https://data.dev-wins.com', 'abcdefgh', absolute=False
    )
    assert relative['catalog'][0]['url'] == (
        '/api/terria/user/private-catalog?catalog_id=abcdefgh'
    )
    absolute = build_private_catalog_reference('alice', 'https://data.dev-wins.com', 'abcdefgh')
    assert absolute['catalog'][0]['url'].startswith('https://data.dev-wins.com/')


def test_is_same_origin():
    from ckanext.terria_view.private_catalog import is_same_origin

    assert is_same_origin('https://data.dev-wins.com', 'https://data.dev-wins.com/terria/') is True
    assert is_same_origin('https://data.dev-wins.com', '/terria/') is True
    assert is_same_origin('https://data.dev-wins.com', 'https://ihp-wins.unesco.org/terria/') is False
    assert is_same_origin('https://data.dev-wins.com', 'http://data.dev-wins.com/terria/') is False
    assert is_same_origin('https://data.dev-wins.com', '') is False


def test_lazy_private_catalog_index_keeps_only_downloadable_datasets():
    from ckanext.terria_view.private_catalog import PrivateCatalogBuilder

    package_search = MagicMock(return_value={
        'count': 3,
        'results': [
            {'id': 'd-findable', 'title': 'Findable', 'organization': 'org-a',
             'access_level': 'findable'},
            {'id': 'd-restricted', 'title': 'Restricted', 'organization': 'org-a',
             'access_level': 'restricted'},
            {'id': 'd-error', 'title': 'Error', 'organization': 'org-a',
             'capacity': 'private'},
        ],
        'search_facets': {'organization': {'items': [
            {'name': 'org-a', 'display_name': 'Organization A'}
        ]}},
    })
    verdicts = {
        'd-findable': {'can_view_resources': False, 'can_download': False},
        'd-restricted': {'can_view_resources': True, 'can_download': True},
    }

    def access_check(context, data_dict):
        if data_dict['id'] == 'd-error':
            raise ckan_plugins_toolkit_mock.NotAuthorized('nope')
        return verdicts[data_dict['id']]

    def get_action(name):
        return {
            'package_search': package_search,
            'datashare_access_check': MagicMock(side_effect=access_check),
        }[name]

    with patch.object(ckan_plugins_toolkit_mock, 'get_action', side_effect=get_action):
        result = PrivateCatalogBuilder(MagicMock()).build_index({'user': 'alice'}, 'abcdefgh')

    names = [member['name'] for group in result['catalog'] for member in group['members']]
    assert names == ['Restricted']  # findable: no download; error: fail closed
    assert result['catalog'][0]['members'][0]['description'] == 'Access level: restricted'
    assert package_search.call_count == 1


def test_lazy_private_catalog_index_falls_back_to_private_only_without_datashare():
    from ckanext.terria_view.private_catalog import PrivateCatalogBuilder

    package_search = MagicMock(return_value={
        'count': 3,
        'results': [
            {'id': 'd-private', 'title': 'Private', 'organization': 'org-a',
             'capacity': 'private'},
            {'id': 'd-level-only', 'title': 'Level Only', 'organization': 'org-a',
             'access_level': 'restricted'},
            {'id': 'd-legacy', 'title': 'Legacy', 'organization': 'org-a',
             'capacity': 'private', 'access_level': 'confidential'},
        ],
        'search_facets': {},
    })

    def get_action(name):
        if name == 'datashare_access_check':
            raise KeyError(name)  # action not registered: datashare absent
        return package_search

    with patch.object(ckan_plugins_toolkit_mock, 'get_action', side_effect=get_action):
        result = PrivateCatalogBuilder(MagicMock()).build_index({'user': 'alice'}, 'abcdefgh')

    members = [member for group in result['catalog'] for member in group['members']]
    assert [member['name'] for member in members] == ['Legacy', 'Private']
    assert all(member['description'] == 'Access level: confidential' for member in members)
    assert package_search.call_count == 1


def _package(**overrides):
    package = {
        'id': 'dataset-1',
        'private': False,
        'state': 'active',
        'title': 'Dataset',
        'notes': '',
        'organization': {'name': 'org', 'title': 'Org'},
        'resources': [{'id': 'resource-1', 'format': 'csv', 'name': 'Resource'}],
    }
    package.update(overrides)
    return package


def _expand_dataset(package, access_verdict=None, datashare_installed=True):
    """Run ``PrivateCatalogBuilder.build_dataset`` against one mocked package."""
    from ckanext.terria_view.private_catalog import PrivateCatalogBuilder

    def get_action(name):
        if name == 'datashare_access_check':
            if not datashare_installed:
                raise KeyError(name)
            return MagicMock(return_value=access_verdict)
        return {
            'package_show': MagicMock(return_value=package),
            'resource_view_list': MagicMock(return_value=[]),
        }[name]

    generator = MagicMock()
    generator.formatos_permitidos = ['csv']
    generator.convert_sets_to_lists.side_effect = lambda value: value
    generator.format_dataset_item.side_effect = lambda *args, **kwargs: (
        {'name': 'Item', 'type': 'csv', 'id': args[0]['id']}, 1
    )
    with patch.object(ckan_plugins_toolkit_mock, 'get_action', side_effect=get_action):
        return PrivateCatalogBuilder(generator).build_dataset(
            {'user': 'alice'}, package['id'], 'abcdefgh'
        )


def test_lazy_dataset_expansion_rejects_public_level_dataset():
    with pytest.raises(ckan_plugins_toolkit_mock.ObjectNotFound):
        _expand_dataset(_package(private=False), access_verdict={'can_download': True})


def test_lazy_dataset_expansion_accepts_legacy_private_without_access_level():
    result = _expand_dataset(_package(private=True), access_verdict={'can_download': True})

    assert len(result['catalog']) == 1
    assert result['catalog'][0]['id'] == (
        '__ckan_private_catalog__/abcdefgh/resource/resource-1/view/0'
    )


def test_lazy_dataset_expansion_rejects_viewable_level_without_download():
    with pytest.raises(ckan_plugins_toolkit_mock.ObjectNotFound):
        _expand_dataset(
            _package(access_level='viewable'),
            access_verdict={'can_view_resources': True, 'can_download': False},
        )


def test_lazy_dataset_expansion_reads_access_level_from_extras():
    result = _expand_dataset(
        _package(extras=[{'key': 'access_level', 'value': 'restricted'}]),
        access_verdict={'can_download': True},
    )

    assert len(result['catalog']) == 1


def test_lazy_dataset_expansion_without_datashare_requires_private_flag():
    with pytest.raises(ckan_plugins_toolkit_mock.ObjectNotFound):
        _expand_dataset(
            _package(private=False, access_level='restricted'), datashare_installed=False
        )
    result = _expand_dataset(_package(private=True), datashare_installed=False)
    assert len(result['catalog']) == 1


# --- resource_utils / generator / token helpers -------------------------------

def test_get_resource_url_mints_token_for_access_level_dataset():
    from ckanext.terria_view.config_manager import ConfigManager
    from ckanext.terria_view.resource_utils import ResourceUtils

    ckan_plugins_toolkit_mock.config = {
        'ckan.site_url': 'https://test.example.org',
        'beaker.session.secret': 'level-secret',
    }
    utils = ResourceUtils(ConfigManager(site_url='https://test.example.org'))
    resource = {
        'id': 'res-level',
        'format': 'csv',
        'url': '/dataset/pkg/resource/res-level/download/data.csv',
        'url_type': 'upload',
    }
    logged = {'user': 'alice'}

    restricted = {'id': 'pkg', 'private': False, 'access_level': 'restricted'}
    url = utils.get_resource_url(resource, restricted, logged)
    assert url.startswith(
        'https://test.example.org/api/terria/resource/res-level/content/data.csv?token='
    )

    anonymous_url = utils.get_resource_url(resource, restricted, {})
    assert anonymous_url == (
        'https://test.example.org/dataset/pkg/resource/res-level/download/data.csv'
    )
    assert 'token=' not in anonymous_url

    via_extras = {
        'id': 'pkg', 'private': False,
        'extras': [{'key': 'access_level', 'value': 'findable'}],
    }
    assert '?token=' in utils.get_resource_url(resource, via_extras, logged)

    public = {'id': 'pkg', 'private': False}
    assert 'token=' not in utils.get_resource_url(resource, public, logged)

    relative = utils.get_resource_url(resource, restricted, logged, relative_urls=True)
    assert relative.startswith('/api/terria/resource/res-level/content/data.csv?token=')


def test_get_resource_url_requires_download_rights_before_minting_token():
    """A login is not enough: datashare's ``viewable`` lets anyone open the view
    page, but only ``can_download`` holders may get a proxy token (or the SAS)."""
    from ckanext.terria_view.config_manager import ConfigManager
    from ckanext.terria_view.resource_utils import ResourceUtils

    ckan_plugins_toolkit_mock.config = {
        'ckan.site_url': 'https://test.example.org',
        'beaker.session.secret': 'gate-secret',
    }
    ckan_lib_uploader_mock.reset_mock()
    utils = ResourceUtils(ConfigManager(site_url='https://test.example.org'))
    resource = {
        'id': 'res-gate',
        'format': 'csv',
        'url': '/dataset/pkg/resource/res-gate/download/data.csv',
        'url_type': 'upload',
    }
    viewable = {'id': 'pkg', 'private': False, 'access_level': 'viewable'}
    user_obj = object()
    logged = {'user': 'bob', 'auth_user_obj': user_obj}

    with patch.object(ResourceUtils, 'user_may_download', MagicMock(return_value=False)) as gate:
        url = utils.get_resource_url(resource, viewable, logged)
        relative = utils.get_resource_url(resource, viewable, logged, relative_urls=True)
    assert url == 'https://test.example.org/dataset/pkg/resource/res-gate/download/data.csv'
    assert relative == url
    assert 'token=' not in url
    assert gate.call_count == 2
    assert all(c.args == (logged, 'res-gate') for c in gate.call_args_list)
    # No SAS either: the uploader is never asked to sign a URL for this viewer.
    ckan_lib_uploader_mock.get_resource_uploader.assert_not_called()

    with patch.object(ResourceUtils, 'user_may_download', MagicMock(return_value=True)) as gate:
        assert '?token=' in utils.get_resource_url(resource, viewable, logged)
    gate.assert_called_once_with(logged, 'res-gate')

    # Public datasets and anonymous viewers never pay for the auth check.
    with patch.object(ResourceUtils, 'user_may_download', MagicMock(return_value=True)) as gate:
        public_url = utils.get_resource_url(resource, {'id': 'pkg', 'private': False}, logged)
        anonymous_url = utils.get_resource_url(resource, viewable, {})
    assert 'token=' not in public_url and 'token=' not in anonymous_url
    gate.assert_not_called()


def test_build_proxy_resource_url_relative_option():
    from ckanext.terria_view.config_manager import ConfigManager
    from ckanext.terria_view.resource_utils import ResourceUtils

    ckan_plugins_toolkit_mock.config = {
        'ckan.site_url': 'https://test.example.org',
        'beaker.session.secret': 'rel-secret',
    }
    utils = ResourceUtils(ConfigManager(site_url='https://test.example.org'))

    relative = utils.build_proxy_resource_url('res-1', filename='x.zip', absolute=False)
    assert relative.startswith('/api/terria/resource/res-1/content/x.zip?token=')
    assert utils.verify_resource_token('res-1', relative.split('token=', 1)[1]) is True

    absolute = utils.build_proxy_resource_url('res-1', filename='x.zip')
    assert absolute.startswith(
        'https://test.example.org/api/terria/resource/res-1/content/x.zip?token='
    )


def test_format_dataset_item_forwards_relative_urls_to_resource_utils():
    from ckanext.terria_view.terria_json_generator import TerriaJSONGenerator

    gen = TerriaJSONGenerator()
    ckan_plugins_toolkit_mock.get_action.return_value = MagicMock(return_value=[])
    resource = {
        'id': 'res-1', 'format': 'csv', 'name': 'CSV',
        'url': '/dataset/p/resource/res-1/download/f.csv',
    }
    org_info = {'display_name': 'Org', 'description': '', 'image_display_url': ''}
    package = {'id': 'pkg-1', 'private': True}
    user_ctx = {'user': 'alice'}

    with patch.object(
        gen.resource_utils, 'get_resource_url',
        return_value='/api/terria/resource/res-1/content/f.csv?token=t',
    ) as get_resource_url:
        result, _ = gen.format_dataset_item(
            resource, 'pkg-1', '', org_info, 0,
            package=package, user_context=user_ctx, relative_urls=True,
        )

    get_resource_url.assert_called_once_with(resource, package, user_ctx, relative_urls=True)
    assert result['url'] == '/api/terria/resource/res-1/content/f.csv?token=t'


def test_proxy_token_helpers_accept_relative_urls():
    from ckanext.terria_view.terria_config_builder import (
        _proxy_resource_id,
        refresh_proxy_tokens,
        strip_proxy_tokens,
    )

    assert _proxy_resource_id('/api/terria/resource/r1/content/x.zip?token=abc') == 'r1'
    assert _proxy_resource_id('/api/terria/resource/r1/content?token=abc') == 'r1'
    assert _proxy_resource_id('/api/terria/other/r1') is None

    data = {'catalog': [{'url': '/api/terria/resource/r1/content/x.zip?token=abc'}]}
    strip_proxy_tokens(data)
    assert data['catalog'][0]['url'] == '/api/terria/resource/r1/content/x.zip'

    refresh_proxy_tokens(data, lambda resource_id: f'new-{resource_id}')
    assert data['catalog'][0]['url'] == '/api/terria/resource/r1/content/x.zip?token=new-r1'


def test_user_may_download_prefers_datashare_download_auth():
    from ckanext.terria_view.resource_utils import ResourceUtils

    user_obj = object()
    context = {'user': 'alice', 'auth_user_obj': user_obj, 'ignore_auth': True}

    check_access = MagicMock(return_value=None)
    with patch.object(ckan_plugins_toolkit_mock, 'check_access', check_access):
        assert ResourceUtils.user_may_download(context, 'r1') is True
    assert check_access.call_count == 1
    name, auth_context, data_dict = check_access.call_args.args
    assert name == 'datashare_resource_download'
    assert data_dict == {'id': 'r1'}
    # Only user identity is forwarded (never ignore_auth or other flags).
    assert auth_context == {'user': 'alice', 'auth_user_obj': user_obj}

    # datashare not installed -> its auth is unknown -> fall back to resource_show.
    check_access = MagicMock(side_effect=[ValueError('Authorization function not found'), None])
    with patch.object(ckan_plugins_toolkit_mock, 'check_access', check_access):
        assert ResourceUtils.user_may_download(context, 'r1') is True
    assert [call.args[0] for call in check_access.call_args_list] == [
        'datashare_resource_download', 'resource_show'
    ]

    check_access = MagicMock(side_effect=ckan_plugins_toolkit_mock.NotAuthorized('no'))
    with patch.object(ckan_plugins_toolkit_mock, 'check_access', check_access):
        assert ResourceUtils.user_may_download(context, 'r1') is False
    assert check_access.call_count == 1  # denial is final, no resource_show retry

    check_access = MagicMock(side_effect=RuntimeError('db down'))
    with patch.object(ckan_plugins_toolkit_mock, 'check_access', check_access):
        assert ResourceUtils.user_may_download(context, 'r1') is False  # fail closed

    check_access = MagicMock(side_effect=ValueError('none registered'))
    with patch.object(ckan_plugins_toolkit_mock, 'check_access', check_access):
        assert ResourceUtils.user_may_download(context, 'r1') is False
    assert check_access.call_count == 2


def test_refresh_proxy_tokens_uses_user_may_download():
    Terria_ViewPlugin = _import_plugin_class()
    refresh = Terria_ViewPlugin.__dict__['_refresh_proxy_tokens_in_encoded_config']

    class _Dummy:
        def __init__(self, allowed):
            self.resource_utils = MagicMock()
            self.resource_utils.user_may_download = MagicMock(return_value=allowed)
            self.resource_utils.generate_resource_token = MagicMock(return_value='fresh-token')

        def _debug_print(self, msg):
            pass

    payload = {'initSources': [{'catalog': [{
        'id': 'p1', 'type': 'csv',
        'url': 'https://ckan.example/api/terria/resource/r1/content/f.csv',
    }]}]}
    encoded = urllib.parse.quote(json.dumps(payload))
    user_obj = object()
    user_context = {'user': 'alice', 'auth_user_obj': user_obj, 'extra': 1}

    dummy = _Dummy(allowed=True)
    check_access = MagicMock()
    with patch.object(ckan_plugins_toolkit_mock, 'check_access', check_access):
        new_encoded, _, blocked = refresh(dummy, encoded, user_context)

    dummy.resource_utils.user_may_download.assert_called_once_with(
        {'user': 'alice', 'auth_user_obj': user_obj}, 'r1'
    )
    check_access.assert_not_called()  # no direct resource_show check any more
    decoded = json.loads(urllib.parse.unquote(new_encoded))
    assert decoded['initSources'][0]['catalog'][0]['url'].endswith('?token=fresh-token')
    assert blocked is False

    dummy = _Dummy(allowed=False)
    new_encoded, _, blocked = refresh(dummy, encoded, user_context)
    assert blocked is True
    assert 'token=' not in urllib.parse.unquote(new_encoded)
    dummy.resource_utils.generate_resource_token.assert_not_called()

    with open('ckanext/terria_view/plugin.py', 'r') as stream:
        source = stream.read()
    assert "check_access('resource_show'" not in source
    assert 'self.resource_utils.user_may_download(' in source


def _render_terria_view(package, resource_url):
    """Run the real ``setup_template_variables`` with mocked collaborators.

    Returns ``(plugin, template_vars)``; ``plugin._update_view_cached_config``
    is a MagicMock so tests can check whether the config was persisted.
    """
    Terria_ViewPlugin = _import_plugin_class()
    plugin = Terria_ViewPlugin.__new__(Terria_ViewPlugin)
    plugin.config_manager = MagicMock(
        default_title='Terria',
        default_instance_url='https://terria.example/terria/',
        site_url='https://test.example.org',
    )
    plugin.config_manager.get_safe_resource_name.return_value = 'resource'
    plugin.resource_utils = MagicMock()
    plugin.resource_utils.get_resource_url.return_value = resource_url
    plugin.resource_utils.get_resource_bounds.return_value = ('20', '-13', '-60', '-108')
    plugin.terria_config_builder = MagicMock()
    plugin.terria_config_builder.create_config_for_resource.return_value = json.dumps(
        {'initSources': [{'catalog': [{'id': 'main', 'type': 'csv', 'url': resource_url}]}]}
    )
    plugin._update_view_cached_config = MagicMock()
    plugin._private_catalog_mode_for = MagicMock(return_value='inline')
    plugin._refresh_proxy_tokens_in_encoded_config = MagicMock(
        side_effect=lambda encoded, _user_context: (encoded, False, False)
    )
    plugin._get_private_datasets_catalog = MagicMock(return_value=None)
    data_dict = {
        'package': package,
        'resource': {
            'id': 'res-1', 'name': 'Resource', 'format': 'csv',
            'url': '/dataset/pkg/resource/res-1/download/data.csv', 'url_type': 'upload',
        },
        'resource_view': {'id': 'view-1', 'title': 'Terria'},
    }
    with patch.object(ckan_plugins_toolkit_mock, 'current_user', FakeUser()), \
            patch.object(ckan_plugins_toolkit_mock, 'asbool', lambda value: value is True):
        template_vars = Terria_ViewPlugin.setup_template_variables(plugin, {}, data_dict)
    return plugin, template_vars


def test_setup_template_variables_never_persists_cached_config_for_non_public_datasets():
    """``cached_config`` is returned by ``resource_view_show`` to anyone who may
    see the view, so a per-viewer proxy token must never be written into it."""
    token_url = 'https://test.example.org/api/terria/resource/res-1/content/data.csv?token=1.abc'
    plain_url = 'https://test.example.org/dataset/pkg/resource/res-1/download/data.csv'

    # datashare levels are ``private=False``: the old ``package['private']``
    # guard would have persisted the token on every render.
    for package in (
        {'id': 'pkg', 'private': False, 'access_level': 'viewable'},
        {'id': 'pkg', 'private': False,
         'extras': [{'key': 'access_level', 'value': 'restricted'}]},
        {'id': 'pkg', 'private': True},
    ):
        plugin, template_vars = _render_terria_view(package, token_url)
        plugin._update_view_cached_config.assert_not_called()
        # The viewer still gets the freshly minted URL in the rendered config.
        assert 'token=1.abc' in urllib.parse.unquote(template_vars['encoded_config'])

    # Belt and braces: a proxy URL is never persisted even for a public-looking package.
    plugin, _ = _render_terria_view({'id': 'pkg', 'private': False}, token_url)
    plugin._update_view_cached_config.assert_not_called()

    # Public datasets with a plain URL keep the cache.
    plugin, _ = _render_terria_view({'id': 'pkg', 'private': False}, plain_url)
    plugin._update_view_cached_config.assert_called_once()
    _context, view, encoded, signature = plugin._update_view_cached_config.call_args.args
    assert view['id'] == 'view-1'
    assert encoded and signature


# --- Resource proxy: token or same-origin session, ranges, streaming ---------

def _proxy_controller(token_valid=True, may_download=True,
                      upstream_url='https://blob.example.net/c/f.tif?sig=SECRET',
                      filename='f.tif'):
    controller = _make_controller()
    utils = controller.generator.resource_utils
    utils.verify_resource_token.return_value = token_valid
    utils.user_may_download.return_value = may_download
    utils.resolve_private_resource_source.return_value = (upstream_url, 'image/tiff', filename)
    return controller


def _proxy_call(controller, args=None, headers=None, method='GET', upstream=None,
                upstream_error=None, current_user=None, resource_id='res-1'):
    """Invoke ``resource_content`` with fake flask objects and a fake upstream."""
    from ckanext.terria_view import api_endpoints

    fake_request = _flask_request(args=args, headers=headers, method=method)
    requests_request = MagicMock(return_value=upstream, side_effect=upstream_error)
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.object(api_endpoints, 'Response', FakeResponse))
        stack.enter_context(patch.object(api_endpoints, 'request', fake_request))
        stack.enter_context(patch.object(api_endpoints.requests, 'request', requests_request))
        stack.enter_context(patch.object(
            ckan_plugins_toolkit_mock, 'current_user',
            FakeAnonymousUser() if current_user is None else current_user,
        ))
        response = controller.resource_content(resource_id)
    return response, requests_request, fake_request


def test_resource_content_valid_token_forwards_range_and_passes_206():
    controller = _proxy_controller()
    upstream = FakeUpstream(206, {
        'Content-Type': 'application/octet-stream',
        'Content-Range': 'bytes 0-9/100',
        'Content-Length': '10',
        'ETag': '"e1"',
        'Accept-Ranges': 'bytes',
    }, chunks=[b'01234', b'56789'])

    response, requests_request, fake_request = _proxy_call(
        controller,
        args={'token': 'valid'},
        headers={
            'Range': 'bytes=0-9',
            'If-None-Match': '"e1"',
            'Cookie': 'ckan=session-secret',
            'Authorization': 'Bearer x',
        },
        upstream=upstream,
    )

    utils = controller.generator.resource_utils
    utils.verify_resource_token.assert_called_once_with('res-1', 'valid')
    utils.user_may_download.assert_not_called()

    method, url = requests_request.call_args.args
    assert (method, url) == ('GET', 'https://blob.example.net/c/f.tif?sig=SECRET')
    forwarded = requests_request.call_args.kwargs['headers']
    assert forwarded['Range'] == 'bytes=0-9'
    assert forwarded['If-None-Match'] == '"e1"'
    assert forwarded['Accept-Encoding'] == 'identity'
    assert 'Cookie' not in forwarded
    assert 'Authorization' not in forwarded
    assert requests_request.call_args.kwargs['stream'] is True
    assert requests_request.call_args.kwargs['timeout'] == (10, 60)

    assert response.status_code == 206
    assert response.direct_passthrough is True
    assert response.mimetype == 'image/tiff'  # extension wins over octet-stream
    assert response.headers['Content-Range'] == 'bytes 0-9/100'
    assert response.headers['Content-Length'] == '10'
    assert response.headers['ETag'] == '"e1"'
    assert 'Content-Range' in response.headers['Access-Control-Expose-Headers']
    assert response.headers['Cache-Control'] == 'private, max-age=300'
    assert response.headers['Access-Control-Allow-Origin'] == '*'
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert fake_request.environ['__no_cache__'] is True

    # Streamed lazily: the upstream is released once the body is consumed.
    assert upstream.close_calls == 0
    assert response.get_data() == b'0123456789'
    assert upstream.close_calls == 1
    upstream.raw.stream.assert_called_once_with(8192, decode_content=False)


def test_resource_content_passes_through_304_and_closes_upstream():
    controller = _proxy_controller()
    upstream = FakeUpstream(304, {
        'ETag': '"e1"', 'Last-Modified': 'Mon, 01 Jan 2024 00:00:00 GMT',
    })

    response, requests_request, _ = _proxy_call(
        controller,
        args={'token': 'valid'},
        headers={
            'If-None-Match': '"e1"',
            'If-Range': '"e1"',
            'If-Modified-Since': 'Mon, 01 Jan 2024 00:00:00 GMT',
        },
        upstream=upstream,
    )

    forwarded = requests_request.call_args.kwargs['headers']
    assert forwarded['If-Range'] == '"e1"'
    assert forwarded['If-Modified-Since'] == 'Mon, 01 Jan 2024 00:00:00 GMT'
    assert response.status_code == 304
    assert response.get_data() == b''
    assert response.headers['ETag'] == '"e1"'
    assert response.headers['Last-Modified'] == 'Mon, 01 Jan 2024 00:00:00 GMT'
    assert response.headers['Access-Control-Allow-Origin'] == '*'
    assert upstream.close_calls == 1
    upstream.raw.stream.assert_not_called()


def test_resource_content_head_closes_upstream_immediately():
    controller = _proxy_controller()
    upstream = FakeUpstream(200, {
        'Content-Type': 'image/tiff', 'Content-Length': '100', 'ETag': '"e1"',
    })

    response, requests_request, _ = _proxy_call(
        controller, args={'token': 'valid'}, method='HEAD', upstream=upstream
    )

    assert requests_request.call_args.args[0] == 'HEAD'
    assert response.status_code == 200
    assert response.headers['Content-Length'] == '100'
    assert response.headers['Accept-Ranges'] == 'bytes'  # advertised when upstream is silent
    assert response.headers['Content-Disposition'].startswith('inline; filename="f.tif"')
    assert response.get_data() == b''
    assert upstream.close_calls == 1
    upstream.raw.stream.assert_not_called()


def test_resource_content_without_token_uses_session_auth():
    controller = _proxy_controller()
    upstream = FakeUpstream(200, {'Content-Type': 'image/tiff', 'Content-Length': '3'},
                            chunks=[b'abc'])

    response, _, fake_request = _proxy_call(
        controller, args={}, upstream=upstream, current_user=FakeUser()
    )

    utils = controller.generator.resource_utils
    utils.verify_resource_token.assert_not_called()
    utils.user_may_download.assert_called_once()
    context, resource_id = utils.user_may_download.call_args.args
    assert context['user'] == 'alice'
    assert resource_id == 'res-1'
    assert response.status_code == 200
    assert 'no-store' in response.headers['Cache-Control']
    assert 'Cookie' in response.headers['Vary']
    assert fake_request.environ['__no_cache__'] is True
    assert response.get_data() == b'abc'


def test_resource_content_denies_anonymous_401_and_unauthorized_session_403():
    controller = _proxy_controller(may_download=False)

    response, requests_request, fake_request = _proxy_call(
        controller, args={}, current_user=FakeAnonymousUser()
    )
    assert response.status_code == 401
    assert response.json()['error'] is True
    assert response.headers['Access-Control-Allow-Origin'] == '*'
    # Verdicts are per caller: never cached, and CKAN must not add ``public``.
    assert 'no-store' in response.headers['Cache-Control']
    assert fake_request.environ['__no_cache__'] is True
    requests_request.assert_not_called()
    controller.generator.resource_utils.resolve_private_resource_source.assert_not_called()

    response, requests_request, fake_request = _proxy_call(
        controller, args={}, current_user=FakeUser()
    )
    assert response.status_code == 403
    assert response.json()['error'] is True
    assert response.headers['Access-Control-Allow-Origin'] == '*'
    assert 'no-store' in response.headers['Cache-Control']
    assert fake_request.environ['__no_cache__'] is True
    requests_request.assert_not_called()


def test_resource_content_expired_token_falls_back_to_session():
    controller = _proxy_controller(token_valid=False)
    upstream = FakeUpstream(200, {'Content-Type': 'image/tiff'}, chunks=[b'x'])

    response, _, _ = _proxy_call(
        controller, args={'token': 'expired'}, upstream=upstream, current_user=FakeUser()
    )

    utils = controller.generator.resource_utils
    utils.verify_resource_token.assert_called_once_with('res-1', 'expired')
    utils.user_may_download.assert_called_once()
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'private, no-store'
    assert response.get_data() == b'x'

    # Expired token and no session is still a 401.
    controller = _proxy_controller(token_valid=False)
    response, _, _ = _proxy_call(
        controller, args={'token': 'expired'}, current_user=FakeAnonymousUser()
    )
    assert response.status_code == 401


def test_resource_content_error_body_never_echoes_upstream_url():
    import requests as real_requests

    controller = _proxy_controller()
    response, _, _ = _proxy_call(
        controller,
        args={'token': 'valid'},
        upstream_error=real_requests.ConnectionError(
            'https://blob.example.net/c/f.tif?sig=SECRET: connection refused'
        ),
    )
    assert response.status_code == 502
    text = response.get_data(as_text=True)
    assert response.json()['error'] is True
    assert 'SECRET' not in text
    assert 'blob.example.net' not in text

    upstream = FakeUpstream(
        500, {'Content-Type': 'application/xml'},
        text='<Error>https://blob.example.net/c/f.tif?sig=SECRET</Error>',
    )
    response, _, _ = _proxy_call(controller, args={'token': 'valid'}, upstream=upstream)
    assert response.status_code == 502
    text = response.get_data(as_text=True)
    assert 'SECRET' not in text
    assert 'blob.example.net' not in text
    assert upstream.close_calls == 1

    controller = _proxy_controller()
    controller.generator.resource_utils.resolve_private_resource_source.side_effect = (
        RuntimeError('https://blob.example.net/?sig=SECRET')
    )
    response, _, _ = _proxy_call(controller, args={'token': 'valid'})
    assert response.status_code == 500
    assert 'SECRET' not in response.get_data(as_text=True)


def test_resource_content_sanitizes_content_disposition():
    from ckanext.terria_view.api_endpoints import _content_disposition

    header = _content_disposition('a";b\r\nX-Injected: 1.tif')
    assert '\r' not in header and '\n' not in header
    assert re.match(r'^inline; filename="([^";]*)"; filename\*=UTF-8\'\'(\S+)$', header)
    assert 'filename="abX-Injected: 1.tif"' in header
    assert "filename*=UTF-8''abX-Injected%3A%201.tif" in header

    unicode_header = _content_disposition('año.tif')
    assert 'filename="ao.tif"' in unicode_header
    assert "filename*=UTF-8''a%C3%B1o.tif" in unicode_header

    controller = _proxy_controller(filename='a";b\r\n.tif')
    upstream = FakeUpstream(200, {'Content-Type': 'image/tiff'}, chunks=[b'x'])
    response, _, _ = _proxy_call(controller, args={'token': 'valid'}, upstream=upstream)
    disposition = response.headers['Content-Disposition']
    assert '\r' not in disposition and '\n' not in disposition
    assert disposition.startswith('inline; filename="ab.tif"')


def test_resource_content_passes_through_416_with_content_range_and_closes_upstream():
    controller = _proxy_controller()
    upstream = FakeUpstream(416, {'Content-Range': 'bytes */100', 'Content-Length': '0'})

    response, requests_request, fake_request = _proxy_call(
        controller, args={'token': 'valid'}, headers={'Range': 'bytes=500-600'},
        upstream=upstream,
    )

    assert requests_request.call_args.kwargs['headers']['Range'] == 'bytes=500-600'
    assert response.status_code == 416
    assert response.get_data() == b''
    assert response.headers['Content-Range'] == 'bytes */100'
    assert 'Content-Length' not in response.headers  # only Content-Range is relayed
    assert 'Content-Range' in response.headers['Access-Control-Expose-Headers']
    assert response.headers['Cache-Control'] == 'private, max-age=300'
    assert fake_request.environ['__no_cache__'] is True
    assert upstream.close_calls == 1
    upstream.raw.stream.assert_not_called()


def test_resource_content_relays_content_encoding_and_upstream_content_length():
    controller = _proxy_controller(filename='data.csv')
    upstream = FakeUpstream(200, {
        'Content-Type': 'application/octet-stream',
        'Content-Encoding': 'gzip',
        'Content-Length': '42',  # compressed size: the bytes are relayed untouched
    }, chunks=[b'\x1f\x8b', b'rest'])

    response, _, _ = _proxy_call(controller, args={'token': 'valid'}, upstream=upstream)

    assert response.status_code == 200
    assert response.headers['Content-Encoding'] == 'gzip'
    assert response.headers['Content-Length'] == '42'
    assert response.headers['Accept-Ranges'] == 'bytes'  # defaulted on a 200 without it
    assert 'Content-Encoding' in response.headers['Access-Control-Expose-Headers']
    assert response.get_data() == b'\x1f\x8brest'
    upstream.raw.stream.assert_called_once_with(8192, decode_content=False)
    assert upstream.close_calls == 1


def test_options_preflight_allows_range_and_conditional_headers():
    from ckanext.terria_view import api_endpoints

    assert _registered_routes()['/api/terria/<path:path>'] == ['OPTIONS']
    with patch.object(api_endpoints, 'Response', FakeResponse):
        response = _route_function('handle_options')('resource/res-1/content/f.tif')

    assert response.status_code == 200
    assert response.headers['Access-Control-Allow-Origin'] == '*'
    assert response.headers['Access-Control-Allow-Methods'] == 'GET, HEAD, POST, OPTIONS'
    allowed = {h.strip() for h in response.headers['Access-Control-Allow-Headers'].split(',')}
    assert {'Content-Type', 'Range', 'If-Range', 'If-None-Match', 'If-Modified-Since'} <= allowed
    assert response.headers['Access-Control-Max-Age'] == '600'


if __name__ == '__main__':
    print("\n=== Private Dataset Tests ===\n")

    tests = [
        test_format_dataset_item_accepts_package_and_user_context,
        test_format_dataset_item_uses_resource_utils_for_url,
        test_cache_manager_docstring_mentions_public_only,
        test_file_cache_manager_docstring_mentions_public_only,
        test_template_has_iframe_with_hash_start,
        test_plugin_merges_private_catalog_into_encoded_config,
        test_merge_helper_preserves_workbench_and_catalog_structure,
        test_template_private_only_for_logged_in,
        test_setup_template_variables_returns_private_fields,
        test_private_uploaded_resource_returns_proxy_url,
        test_private_shapefile_proxy_url_preserves_zip_extension,
        test_proxy_url_preserves_extension_for_all_uploaded_formats,
        test_proxy_url_without_filename_still_valid,
        test_generate_and_verify_resource_token_roundtrip,
        test_expired_resource_token_is_rejected,
        test_resource_token_tampering_is_rejected,
        test_resource_content_endpoint_is_registered,
        test_terria_friendly_content_type_overrides_octet_stream,
        test_relative_resource_url_is_normalized_to_absolute,
        test_api_endpoint_passes_context_to_format_dataset_item,
        test_can_view_resource_handles_missing_url_without_crashing,
        test_resource_utils_extracts_filename_from_download_urls,
        test_plugin_registers_resource_view_cache_invalidation_actions,
        test_resource_view_list_uses_resource_show_payload_for_can_view,
        test_private_catalog_injection_is_limited_to_private_package_views,
        test_user_session_anonymous_returns_200_without_user,
        test_user_session_authenticated_payload_and_relative_urls,
        test_user_session_never_raises_returns_anonymous_on_internal_error,
        test_user_session_route_is_registered,
        test_get_user_context_treats_truthy_anonymous_user_as_anonymous,
        test_private_json_response_sets_no_cache_environ_and_drops_pragma,
        test_api_url_relative_by_default_and_absolute_on_request,
        test_is_same_origin,
        test_lazy_private_catalog_index_keeps_only_downloadable_datasets,
        test_lazy_private_catalog_index_falls_back_to_private_only_without_datashare,
        test_lazy_dataset_expansion_rejects_public_level_dataset,
        test_lazy_dataset_expansion_accepts_legacy_private_without_access_level,
        test_lazy_dataset_expansion_rejects_viewable_level_without_download,
        test_lazy_dataset_expansion_reads_access_level_from_extras,
        test_lazy_dataset_expansion_without_datashare_requires_private_flag,
        test_get_resource_url_mints_token_for_access_level_dataset,
        test_get_resource_url_requires_download_rights_before_minting_token,
        test_build_proxy_resource_url_relative_option,
        test_format_dataset_item_forwards_relative_urls_to_resource_utils,
        test_proxy_token_helpers_accept_relative_urls,
        test_user_may_download_prefers_datashare_download_auth,
        test_refresh_proxy_tokens_uses_user_may_download,
        test_setup_template_variables_never_persists_cached_config_for_non_public_datasets,
        test_resource_content_valid_token_forwards_range_and_passes_206,
        test_resource_content_passes_through_304_and_closes_upstream,
        test_resource_content_head_closes_upstream_immediately,
        test_resource_content_without_token_uses_session_auth,
        test_resource_content_denies_anonymous_401_and_unauthorized_session_403,
        test_resource_content_expired_token_falls_back_to_session,
        test_resource_content_error_body_never_echoes_upstream_url,
        test_resource_content_sanitizes_content_disposition,
        test_resource_content_passes_through_416_with_content_range_and_closes_upstream,
        test_resource_content_relays_content_encoding_and_upstream_content_length,
        test_options_preflight_allows_range_and_conditional_headers,
        test_process_custom_config_populates_workbench_and_sanitizes_styles,
        test_process_custom_config_sanitizes_palette_only_style,
        test_process_custom_config_category_palette_forces_enum_maptype,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  FAIL: {test.__name__}: {e}")
            failed += 1

    print(f"\n--- Results: {passed} passed, {failed} failed ---")
    if failed:
        sys.exit(1)
