"""Saved SWOT viewer configuration must survive catalog generation.

Use the existing CKAN-free harness; all URLs and HTTP responses here are local
fixtures. The reach/node shapes reproduce the IHP-WINS SWOT views, including
their direct instance URL and the extra CSV model captured by a chart.
"""

import copy
import json
import urllib.parse
from unittest.mock import MagicMock

import pytest

import test_private_datasets as ckan_fakes
from ckanext.terria_view.config_manager import ConfigManager
from ckanext.terria_view.terria_json_generator import TerriaJSONGenerator


RESOURCE_ID = 'e5982971-3e89-4f81-a9e3-67333e168e17'
RESOURCE_URL = f'https://example.org/dataset/swot/resource/{RESOURCE_ID}/download/reaches.geojson'
ORG = {'display_name': 'NASA', 'description': ''}
POPUP = {
    'name': 'Reach {{reach_id}}',
    'template': "<p>Water level + width (m)</p><chart src='{{chart_url}}' "
                "downloads='{{url}}' x-column='time_utc' y-columns='wse,width'></chart>",
}


@pytest.fixture
def generator():
    # Avoid shared caches and real HTTP/SLD calls in these unit tests.
    gen = TerriaJSONGenerator.__new__(TerriaJSONGenerator)
    gen.config_manager = ConfigManager(site_url='https://example.org')
    gen.resource_utils = MagicMock()
    gen.resource_utils.get_resource_url.return_value = RESOURCE_URL
    gen.sld_processor = MagicMock()
    gen.cache_manager = MagicMock()
    gen.cache_manager.get_cached_config.return_value = None
    gen.http = MagicMock()
    gen.TIMEOUT_SECONDS = 1
    gen.formatos_permitidos = ['geojson']
    return gen


def resource(format_='GeoJSON'):
    return {'id': RESOURCE_ID, 'name': 'SWOT Reaches', 'format': format_, 'url': RESOURCE_URL}


def custom_url(models, encoder=urllib.parse.quote):
    start = {
        'version': '8.0.0',
        'initSources': [{
            'stratum': 'user', 'models': models, 'workbench': list(models),
            'initialCamera': {'west': 10, 'east': 20, 'south': 0, 'north': 10},
        }],
    }
    return 'https://example.org/terria/#start=' + encoder(json.dumps(start), safe='')


def view(url, field='terria_instance_url'):
    result = {
        'title': 'SWOT Explorer', 'view_type': 'terria_view',
        'custom_config': 'NA', 'style': 'NA',
        'terria_instance_url': 'https://example.org/terria/',
    }
    result[field] = url
    return result


def item(generator, views, format_='GeoJSON', view_index=0):
    result, total = generator.format_dataset_item(
        resource(format_), 'swot', '', ORG, view_index, terria_views=views
    )
    assert total == len(views)
    return result


@pytest.mark.parametrize('encoder', [urllib.parse.quote, urllib.parse.quote_plus])
@pytest.mark.parametrize('geometry', ['reach', 'node'])
def test_swot_direct_url_exports_styles_and_popup_without_chart_contamination(generator, encoder, geometry):
    style = {'stroke-width': 5} if geometry == 'reach' else {'marker-size': '7', 'stroke-width': 0}
    rules = [
        {'properties': {'has_data': True}, 'style': {'stroke': '#1e6091'}},
        {'properties': {'has_data': False}, 'style': {'stroke': '#a67c52'}},
    ]
    saved = {
        'type': 'geojson', 'url': RESOURCE_URL, 'name': 'Saved SWOT name',
        'style': style, 'perPropertyStyles': rules, 'featureInfoTemplate': POPUP,
        'styles': [{'id': 'availability', 'color': {'colorColumn': 'has_data'}}],
        'activeStyle': 'availability', 'opacity': 1,
    }
    models = {
        '/': {'type': 'group', 'members': ['swot']},
        'swot': saved,
        'chart': {
            'type': 'csv', 'url': 'https://example.org/series.csv',
            'styles': [{'id': 'chart', 'chart': {'xAxisColumn': 'time_utc'}}],
            'activeStyle': 'chart', 'opacity': 0.2,
        },
    }
    result = item(generator, [view(custom_url(models, encoder))])

    for key in ('style', 'perPropertyStyles', 'featureInfoTemplate', 'styles', 'activeStyle', 'opacity'):
        assert result[key] == saved[key]
    assert (result['id'], result['url'], result['name']) == (RESOURCE_ID, RESOURCE_URL, 'SWOT Reaches')
    assert 'initialCamera' not in result
    assert 'workbench' not in result
    assert 'models' not in result
    generator.http.get.assert_not_called()


def test_direct_url_has_same_precedence_as_embedded_ckan_view(generator):
    direct = custom_url({'swot': {'type': 'geojson', 'style': {'stroke': '#123456'}}})
    other = custom_url({'swot': {'type': 'geojson', 'style': {'stroke': '#abcdef'}}})
    selected = view(direct)
    selected['custom_config'] = other
    assert item(generator, [selected])['style'] == {'stroke': '#123456'}


def test_custom_config_and_explicit_empty_style_values_are_preserved(generator):
    saved = {
        'type': 'geojson', 'url': RESOURCE_URL,
        'defaultStyle': {'color': {'nullColor': '#123456'}},
        'activeStyle': 'default', 'perPropertyStyles': [], 'legends': [],
        'opacity': 0, 'clampToGround': False, 'forceCesiumPrimitives': False,
        'featureInfoTemplate': POPUP,
    }
    result = item(generator, [view(custom_url({'swot': saved}), 'custom_config')])
    for key, value in saved.items():
        assert result[key] == value


@pytest.mark.parametrize('identity', ['model_key', 'id', 'url', 'download_path', 'proxy_path'])
def test_selects_resource_among_multiple_geojson_models(generator, identity):
    target = {'type': 'geojson', 'style': {'stroke': '#123456'}}
    key = 'swot'
    if identity == 'model_key':
        key = RESOURCE_ID
        target.pop('type')  # Share data can contain only user overrides.
    elif identity == 'id':
        target['id'] = RESOURCE_ID
    elif identity == 'url':
        target['url'] = RESOURCE_URL
    elif identity == 'download_path':
        target['url'] = f'https://old.example.org/dataset/old/resource/{RESOURCE_ID}/download/old.geojson'
    else:
        target['url'] = f'/api/terria/resource/{RESOURCE_ID}/content/old.geojson?token=expired'
    models = {
        key: target,
        'unrelated': {'type': 'geojson', 'url': 'https://example.org/other.geojson', 'style': {'stroke': '#abcdef'}},
    }
    assert item(generator, [view(custom_url(models))])['style'] == {'stroke': '#123456'}


def test_ambiguous_models_do_not_contribute_styles(generator):
    models = {key: {'type': 'geojson', 'style': {'stroke': color}}
              for key, color in [('one', '#123456'), ('two', '#abcdef')]}
    result = item(generator, [view(custom_url(models), 'custom_config')])
    assert 'style' not in result
    assert result['url'] == RESOURCE_URL


def test_model_overrides_in_later_init_source_keep_the_resource_identity(generator):
    start = {'initSources': [
        {'models': {'swot': {'type': 'geojson', 'url': RESOURCE_URL, 'style': {'stroke': '#123456'}}}},
        {'stratum': 'user', 'models': {'swot': {'style': {'stroke': '#abcdef'}, 'featureInfoTemplate': POPUP}}},
    ]}
    url = 'https://example.org/terria/#start=' + urllib.parse.quote(json.dumps(start))
    result = item(generator, [view(url)])
    assert result['style'] == {'stroke': '#abcdef'}
    assert result['featureInfoTemplate'] == POPUP


@pytest.mark.parametrize('fragment', [
    '', 'start=', 'start=not-json', 'start=%5B%5D', 'start=null',
    'start=%7B%22initSources%22%3Anull%7D',
    'start=%7B%22initSources%22%3A%5Bnull%2C%22remote.json%22%2C%7B%22models%22%3A%5B%5D%7D%5D%7D',
    'share=unsupported',
])
def test_malformed_configuration_keeps_base_item(generator, fragment):
    result = item(generator, [view('https://example.org/terria/#' + fragment)])
    assert result['id'] == RESOURCE_ID
    assert result['url'] == RESOURCE_URL
    assert 'style' not in result
    generator.http.get.assert_not_called()


@pytest.mark.parametrize('format_,type_', [('SHP', 'shp'), ('shape', 'shp'), ('TIF', 'cog'), ('COG', 'cog')])
def test_shp_and_cog_keep_saved_styles_over_sld_defaults(generator, format_, type_):
    seed = {'legends': [{'title': 'From SLD'}], 'styles': [{'id': 'sld'}],
            'activeStyle': 'sld', 'renderOptions': {'single': {'domain': [0, 100]}}}
    generator.sld_processor.process_shp_sld.return_value = seed
    generator.sld_processor.process_cog_sld.return_value = seed
    saved = {'type': type_, 'url': RESOURCE_URL, 'legends': [], 'opacity': 0.4}
    if type_ == 'shp':
        saved.update(styles=[{'id': 'saved'}], activeStyle='saved')
    else:
        saved['renderOptions'] = {'single': {'displayRange': [10, 20]}}
    selected = view(custom_url({'swot': saved}), 'custom_config')
    selected['style'] = 'https://example.org/style.sld'
    result = item(generator, [selected], format_)
    for key, value in saved.items():
        assert result[key] == value
    assert (generator.sld_processor.process_shp_sld.call_count,
            generator.sld_processor.process_cog_sld.call_count) == ((1, 0) if type_ == 'shp' else (0, 1))


def test_existing_gist_custom_config_still_loads(generator):
    generator.http.get.return_value = MagicMock(status_code=200, text=json.dumps({
        'initSources': [{'models': {'swot': {'type': 'geojson', 'url': RESOURCE_URL, 'style': {'stroke': '#123456'}}}}],
    }))
    result = item(generator, [view('https://example.org/terria/#share=g-test', 'custom_config')])
    assert result['style'] == {'stroke': '#123456'}
    generator.http.get.assert_called_once_with(
        'https://gist.githubusercontent.com/pabrojast/test/raw/Terriajs-usercatalog.json', timeout=1
    )


def test_dataset_catalog_preserves_multiple_view_ids_and_saved_config(generator, monkeypatch):
    views = [view(custom_url({'swot': {'type': 'geojson', 'url': RESOURCE_URL, 'style': {'stroke': color}}}))
             for color in ('#123456', '#abcdef')]
    original_views = copy.deepcopy(views)
    dataset = {'id': 'swot', 'title': 'SWOT', 'state': 'active', 'resources': [resource()]}
    actions = {'package_show': MagicMock(return_value=dataset), 'resource_view_list': MagicMock(return_value=views)}
    monkeypatch.setattr(ckan_fakes.ckan_plugins_toolkit_mock, 'get_action', actions.__getitem__)

    result = generator.generate_dataset_json('swot')['catalog'][0]['members']

    assert [entry['style']['stroke'] for entry in result] == ['#123456', '#abcdef']
    assert [entry['id'] for entry in result] == [RESOURCE_ID, RESOURCE_ID + '-1']
    assert result[0]['shareKeys'] == [RESOURCE_ID + '-0']
    assert all(entry['url'] == RESOURCE_URL for entry in result)
    assert views == original_views
