import json
from unittest.mock import Mock

import pytest
import test_private_datasets as ckan_fakes
from ckanext.terria_view import saved_config


def test_shortlink_resolves_configured_service_and_preserves_literal_plus(monkeypatch):
    monkeypatch.setattr(saved_config.toolkit, 'config', {'ckan.site_url': 'https://data.dev-wins.com'})
    payload = {'initSources': [{'models': {'water': {'name': 'A+B', 'opacity': 0}}}]}
    download = Mock(return_value=json.dumps(payload))
    monkeypatch.setattr(saved_config, '_download', download)
    assert saved_config.read_saved_config('https://data.dev-wins.com/terria/#share=ABC-123') == payload
    download.assert_called_once_with('https://data.dev-wins.com/terria/share/ABC-123')


@pytest.mark.parametrize('url', [
    'https://unconfigured.example/terria/#share=abc',
    'https://data.dev-wins.com/other/#share=abc',
    'http://127.0.0.1/terria/#share=abc',
    'https://data.dev-wins.com/terria/#share=../../secret',
])
def test_unconfigured_share_sources_are_not_fetched(monkeypatch, url):
    monkeypatch.setattr(saved_config.toolkit, 'config', {'ckan.site_url': 'https://data.dev-wins.com'})
    download = Mock(side_effect=AssertionError('Must not fetch'))
    monkeypatch.setattr(saved_config, '_download', download)
    with pytest.raises(ValueError):
        saved_config.read_saved_config(url)
    download.assert_not_called()


def test_oversized_and_invalid_state_is_rejected(monkeypatch):
    monkeypatch.setattr(saved_config, 'MAX_BYTES', 100)
    with pytest.raises(ValueError):
        saved_config.read_saved_config(json.dumps({'initSources': [], 'oversized': 'x' * 110}))
    with pytest.raises(ValueError):
        saved_config.read_saved_config('{"initSources": null}')


def test_share_download_rejects_redirects_and_caps_stream(monkeypatch):
    response = Mock(status_code=302)
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    get = Mock(return_value=response)
    monkeypatch.setattr(saved_config.requests, 'get', get)
    with pytest.raises(ValueError):
        saved_config._download('https://configured.example/share/id')
    assert get.call_args.kwargs['allow_redirects'] is False
    response.status_code = 200
    response.iter_content.return_value = [b'x' * 60, b'y' * 60]
    monkeypatch.setattr(saved_config, 'MAX_BYTES', 100)
    with pytest.raises(ValueError):
        saved_config._download('https://configured.example/share/id')
