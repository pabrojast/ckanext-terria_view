# encoding: utf-8
"""
Action wrappers to reduce oversized resource extras in API responses.
"""
import os
from typing import Dict, Iterable, List, Optional

import ckan.logic.action.get as get
import ckan.plugins.toolkit as toolkit

# Keep a reference to the original actions
_original_package_show = get.package_show
_original_resource_show = get.resource_show

# Default keys to strip from resource extras/output to avoid massive payloads
DEFAULT_STRIP_RESOURCE_EXTRAS_KEYS = [
    "text_content_info",
    "spreadsheet_sheets",
    "format_version",
    "file_size_bytes",
    "file_integrity",
    "document_pages",
    "content_type_detected",
    "compression_info",
    "data_statistics",
    "data_domains",
    "data_fields",
]


def _debug_print(message: str) -> None:
    if os.getenv("TERRIA_DEBUG", "false").lower() == "true":
        print(message)


def _get_strip_keys() -> List[str]:
    config = toolkit.config
    enabled = toolkit.asbool(
        config.get("ckanext.terria_view.strip_resource_extras_enabled", True)
    )
    if not enabled:
        return []

    raw_keys = config.get("ckanext.terria_view.strip_resource_extras_keys", "")
    if raw_keys:
        keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
        return keys

    return list(DEFAULT_STRIP_RESOURCE_EXTRAS_KEYS)


def _pop_bool(data_dict: Optional[Dict], key: str) -> Optional[bool]:
    if not data_dict or key not in data_dict:
        return None
    value = data_dict.pop(key)
    return toolkit.asbool(value)


def _strip_resource_extras(resource: Dict, keys: Iterable[str]) -> None:
    if not resource or not keys:
        return

    key_set = set(keys)

    # Remove top-level merged extra keys
    for key in key_set:
        if key in resource:
            resource.pop(key, None)

    # Clean nested extras, if present
    extras = resource.get("extras")
    if isinstance(extras, dict):
        for key in key_set:
            extras.pop(key, None)
    elif isinstance(extras, list):
        resource["extras"] = [item for item in extras if item.get("key") not in key_set]


def package_show(context, data_dict):
    """
    Wrap package_show to strip heavy resource extras from the response.

    Optional request override:
      - strip_resource_extras=false to keep all keys for this call.
    """
    data_dict = dict(data_dict or {})
    strip_override = _pop_bool(data_dict, "strip_resource_extras")

    result = _original_package_show(context, data_dict)

    keys = _get_strip_keys()
    if strip_override is False or not keys:
        return result

    resources = result.get("resources")
    if isinstance(resources, list):
        for resource in resources:
            _strip_resource_extras(resource, keys)

    _debug_print(
        f"package_show: stripped keys from {len(resources) if resources else 0} resources"
    )
    return result


def resource_show(context, data_dict):
    """
    Wrap resource_show to strip heavy extras from the response.

    Optional request override:
      - strip_resource_extras=false to keep all keys for this call.
    """
    data_dict = dict(data_dict or {})
    strip_override = _pop_bool(data_dict, "strip_resource_extras")

    result = _original_resource_show(context, data_dict)

    keys = _get_strip_keys()
    if strip_override is False or not keys:
        return result

    _strip_resource_extras(result, keys)

    _debug_print("resource_show: stripped keys from response")
    return result
