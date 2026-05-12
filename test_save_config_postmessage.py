#!/usr/bin/env python3
"""Lightweight text-level checks for the Save Configuration iframe request."""


def test_save_configuration_uses_null_proto_payload():
    with open('ckanext/terria_view/templates/terria.html', 'r', encoding='utf-8') as f:
        content = f.read()

    assert "new URL(terriaInstanceUrl, window.location.href)" in content
    assert "var payload = Object.create(null);" in content
    assert "payload.type = 'requestShareData';" in content
    assert "payload.requestId = String(requestId);" in content
    assert "payload.allowOrigin = String(window.location.origin || '');" in content
