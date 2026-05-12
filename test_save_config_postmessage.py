#!/usr/bin/env python3
"""Lightweight text-level checks for the Save Configuration iframe protocol."""


def test_save_configuration_uses_object_payload_candidates():
    with open('ckanext/terria_view/templates/terria.html', 'r', encoding='utf-8') as f:
        content = f.read()

    assert "new URL(terriaInstanceUrl, window.location.href)" in content
    assert "var payloadFactories = [" in content
    assert "Object.create(null)" in content
    assert "JSON.parse(JSON.stringify({" in content
    assert "payload.type = 'requestShareData';" in content
    assert "Browser blocked postMessage to TerriaJS iframe" in content
