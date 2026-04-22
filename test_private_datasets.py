#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test private dataset functionality for ckanext-terria_view.

These tests use mocking to avoid requiring a full CKAN installation.
"""

import json
import sys
import types
import urllib.parse
from unittest.mock import MagicMock, patch, PropertyMock

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
ckan_plugins_toolkit_mock.ObjectNotFound = Exception

# Now import our modules
from ckanext.terria_view.cache_manager import CacheManager
from ckanext.terria_view.file_cache_manager import FileCacheManager


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

    # Verify resource_utils was called with correct args
    gen.resource_utils.get_resource_url.assert_called_once_with(resource, package, user_ctx)
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


def test_template_has_private_catalog_injection():
    """Test that template contains private catalog injection logic."""
    with open('ckanext/terria_view/templates/terria.html', 'r') as f:
        content = f.read()

    assert 'private_catalog_data' in content, "Template should reference private_catalog_data"
    assert 'user_logged_in' in content, "Template should check user_logged_in"
    assert 'terriaPrivateCatalog' in content, "Template should have JS var terriaPrivateCatalog"
    assert 'postConfigToIframe' in content, "Template should have postConfigToIframe function"
    assert 'terria-iframe' in content, "Template should have id=terria-iframe on iframes"
    print("  PASS: Template has private catalog injection logic")


def test_template_private_only_for_logged_in():
    """Test that private injection is conditional on user being logged in."""
    with open('ckanext/terria_view/templates/terria.html', 'r') as f:
        content = f.read()

    # Check that private catalog injection is guarded by user_logged_in
    assert '{% if user_logged_in and private_catalog_data' in content
    print("  PASS: Private catalog injection is conditional on user_logged_in")


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
    """Private catalog should only be injected for private package views."""
    with open('ckanext/terria_view/plugin.py', 'r') as f:
        content = f.read()

    assert "include_private_catalog = bool(user_context.get('user')) and bool(package.get('private'))" in content
    print("  PASS: private catalog injection is limited to private package views")


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


if __name__ == '__main__':
    print("\n=== Private Dataset Tests ===\n")

    tests = [
        test_format_dataset_item_accepts_package_and_user_context,
        test_format_dataset_item_uses_resource_utils_for_url,
        test_cache_manager_docstring_mentions_public_only,
        test_file_cache_manager_docstring_mentions_public_only,
        test_template_has_private_catalog_injection,
        test_template_private_only_for_logged_in,
        test_setup_template_variables_returns_private_fields,
        test_private_uploaded_resource_returns_proxy_url,
        test_private_shapefile_proxy_url_preserves_zip_extension,
        test_proxy_url_without_filename_still_valid,
        test_generate_and_verify_resource_token_roundtrip,
        test_expired_resource_token_is_rejected,
        test_resource_token_tampering_is_rejected,
        test_resource_content_endpoint_is_registered,
        test_relative_resource_url_is_normalized_to_absolute,
        test_api_endpoint_passes_context_to_format_dataset_item,
        test_can_view_resource_handles_missing_url_without_crashing,
        test_resource_utils_extracts_filename_from_download_urls,
        test_plugin_registers_resource_view_cache_invalidation_actions,
        test_resource_view_list_uses_resource_show_payload_for_can_view,
        test_private_catalog_injection_is_limited_to_private_package_views,
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
