# encoding: utf-8
"""
Módulo para construir configuraciones de TerriaJS.
"""
import json
import re
import urllib.parse
from typing import Dict, List, Optional, Any


# --- Private-catalog stripping ------------------------------------------------
#
# ``Terria_ViewPlugin.setup_template_variables`` injects the logged-in user's
# private datasets into ``encoded_config`` so the embedded map's catalog tree
# shows them. That data must never be *persisted* into a view's
# ``custom_config``:
#   * each "Save Configuration" re-captures the full injected tree, which is
#     then re-injected on the next render -> the config grows without bound;
#   * the injected resource items embed short-lived signed proxy tokens that
#     expire, breaking the saved view;
#   * a public view's config would then leak one user's private-dataset list.
#
# These helpers strip those ``Private Datasets (...)`` branches out of a
# TerriaJS ``#start=`` / init-source payload before it is saved or re-rendered.

_PRIVATE_CATALOG_NAME_PREFIX = 'Private Datasets ('


def _looks_like_private_catalog_id(value) -> bool:
    """True if ``value`` is a Terria model id/name for the injected private catalog.

    Handles both ``//Private Datasets (user)/...`` model ids and the bare
    ``Private Datasets (user)`` group name, and tolerates the ``+``-for-space
    encoding some saved share links carry.
    """
    if not isinstance(value, str):
        return False
    normalized = value.lstrip('/').replace('+', ' ').strip()
    return normalized.startswith(_PRIVATE_CATALOG_NAME_PREFIX)


def _strip_private_from_catalog_list(catalog) -> None:
    """Drop ``Private Datasets (...)`` groups from an in-place catalog list."""
    if not isinstance(catalog, list):
        return
    catalog[:] = [
        entry for entry in catalog
        if not (isinstance(entry, dict) and _looks_like_private_catalog_id(entry.get('name')))
    ]


def _strip_private_from_init_source(init_source) -> None:
    if not isinstance(init_source, dict):
        return

    models = init_source.get('models')
    removed = set()
    if isinstance(models, dict):
        # Seed with model keys that are themselves private-catalog ids.
        for key in list(models.keys()):
            if key != '/' and _looks_like_private_catalog_id(key):
                removed.add(key)

        # Propagate to descendants: any model whose container chain leads to a
        # removed/private model, and any member referenced from a removed group.
        changed = True
        while changed:
            changed = False
            for key, value in list(models.items()):
                if key in removed or key == '/' or not isinstance(value, dict):
                    continue
                containers = value.get('knownContainerUniqueIds') or []
                if any(isinstance(c, str) and (c in removed or _looks_like_private_catalog_id(c))
                       for c in containers):
                    removed.add(key)
                    changed = True
            for key in list(removed):
                group = models.get(key)
                if isinstance(group, dict):
                    for member in group.get('members') or []:
                        if isinstance(member, str) and member in models and member not in removed:
                            removed.add(member)
                            changed = True

        for key in removed:
            models.pop(key, None)

        # Clean dangling references in surviving models' member lists.
        for value in models.values():
            if isinstance(value, dict) and isinstance(value.get('members'), list):
                value['members'] = [
                    m for m in value['members']
                    if not (isinstance(m, str) and (m in removed or _looks_like_private_catalog_id(m)))
                ]

    # Clean top-level reference lists carried on the init source.
    for list_key in ('workbench', 'timeline'):
        lst = init_source.get(list_key)
        if isinstance(lst, list):
            init_source[list_key] = [
                m for m in lst
                if not (isinstance(m, str) and (m in removed or _looks_like_private_catalog_id(m)))
            ]
    previewed = init_source.get('previewedItemId')
    if isinstance(previewed, str) and (previewed in removed or _looks_like_private_catalog_id(previewed)):
        init_source.pop('previewedItemId', None)

    # Un-loaded form: a literal ``catalog`` array on the init source.
    _strip_private_from_catalog_list(init_source.get('catalog'))


def payload_has_private_catalog(data) -> bool:
    """Cheap check: does ``data`` carry any ``Private Datasets (...)`` branch?

    Used to avoid re-serializing (and thus churning the encoding of) a saved
    state that has nothing to strip.
    """
    if not isinstance(data, dict):
        return False
    init_sources = data.get('initSources')
    sources = init_sources if isinstance(init_sources, list) else []
    for init_source in sources:
        if not isinstance(init_source, dict):
            continue
        models = init_source.get('models')
        if isinstance(models, dict):
            if any(k != '/' and _looks_like_private_catalog_id(k) for k in models):
                return True
        catalog = init_source.get('catalog')
        if isinstance(catalog, list) and any(
            isinstance(e, dict) and _looks_like_private_catalog_id(e.get('name')) for e in catalog
        ):
            return True
    catalog = data.get('catalog')
    if isinstance(catalog, list) and any(
        isinstance(e, dict) and _looks_like_private_catalog_id(e.get('name')) for e in catalog
    ):
        return True
    return False


def strip_private_catalog_branches(start_data):
    """Remove all ``Private Datasets (...)`` branches from a TerriaJS payload.

    Mutates and returns ``start_data`` (a parsed ``#start=`` state or an init
    source). Safe (a no-op) on payloads that contain no private catalog.
    """
    if not isinstance(start_data, dict):
        return start_data
    init_sources = start_data.get('initSources')
    if isinstance(init_sources, list):
        for init_source in init_sources:
            _strip_private_from_init_source(init_source)
    _strip_private_from_catalog_list(start_data.get('catalog'))
    return start_data


def strip_private_catalog_from_terria_url(url):
    """Strip private-catalog branches from a ``https://.../#start=<json>`` URL.

    Returns the rebuilt URL (compactly re-encoded, like ``JSON.stringify``), or
    the original value **unchanged** when it is not a string, has no ``#start=``
    fragment, fails to parse as JSON, or contains no private catalog.
    """
    if not isinstance(url, str) or '#start=' not in url:
        return url
    base, _, encoded = url.partition('#start=')
    try:
        data = json.loads(urllib.parse.unquote(encoded))
    except (ValueError, TypeError):
        return url
    if not payload_has_private_catalog(data):
        return url
    strip_private_catalog_branches(data)
    return base + '#start=' + urllib.parse.quote(
        json.dumps(data, separators=(',', ':'), ensure_ascii=False)
    )


# --- Pruning the saved private branch to displayed items ---------------------
#
# When a viewer with private datasets clicks "Save Configuration", TerriaJS's
# ``getShareData`` serialises not just the private items they put on the map but
# the whole injected ``Private Datasets (...)`` tree as ancestors (each group's
# full ``members`` list), which can run to ~1 MB. For a *saved view* we only
# need the items actually displayed; trim the branch down to those plus their
# ancestor groups (with ``members`` pruned to the kept descendants).


def _private_branch_model_ids(models) -> set:
    """Return the set of model ids that belong to an injected private-catalog branch.

    A model is "in the branch" if its id looks like a ``Private Datasets (...)``
    id, or it descends (via ``knownContainerUniqueIds``) from such a model, or it
    is a member of a branch group.
    """
    if not isinstance(models, dict):
        return set()
    branch = set(
        key for key in models
        if key != '/' and _looks_like_private_catalog_id(key)
    )
    changed = True
    while changed:
        changed = False
        for key, value in models.items():
            if key in branch or key == '/' or not isinstance(value, dict):
                continue
            containers = value.get('knownContainerUniqueIds') or []
            if any(isinstance(c, str) and (c in branch or _looks_like_private_catalog_id(c))
                   for c in containers):
                branch.add(key)
                changed = True
        for key in list(branch):
            group = models.get(key)
            if isinstance(group, dict):
                for member in group.get('members') or []:
                    if isinstance(member, str) and member in models and member not in branch:
                        branch.add(member)
                        changed = True
    return branch


def _prune_private_branch_in_init_source(init_source) -> None:
    if not isinstance(init_source, dict):
        return
    models = init_source.get('models')
    if not isinstance(models, dict):
        return
    branch = _private_branch_model_ids(models)
    if not branch:
        return

    # Which private items are actually displayed?
    used = set()
    for list_key in ('workbench', 'timeline'):
        for m in init_source.get(list_key) or []:
            if isinstance(m, str):
                used.add(m)
    previewed = init_source.get('previewedItemId')
    if isinstance(previewed, str):
        used.add(previewed)
    used_private = used & branch

    keep = set()
    frontier = list(used_private)
    keep.update(used_private)
    while frontier:
        cur = frontier.pop()
        model = models.get(cur)
        if not isinstance(model, dict):
            continue
        for c in model.get('knownContainerUniqueIds') or []:
            if isinstance(c, str) and c in branch and c not in keep:
                keep.add(c)
                frontier.append(c)

    drop = branch - keep
    if not drop:
        return
    for key in drop:
        models.pop(key, None)
    # Clean dangling references to dropped ids from every surviving model
    # (including the root ``/`` group).
    for value in models.values():
        if isinstance(value, dict) and isinstance(value.get('members'), list):
            value['members'] = [
                m for m in value['members']
                if not (isinstance(m, str) and m in drop)
            ]
    # Clean dangling references carried on the init source.
    for list_key in ('workbench', 'timeline'):
        lst = init_source.get(list_key)
        if isinstance(lst, list):
            init_source[list_key] = [
                m for m in lst if not (isinstance(m, str) and m in drop)
            ]
    if isinstance(init_source.get('previewedItemId'), str) and init_source['previewedItemId'] in drop:
        init_source.pop('previewedItemId', None)
    # Also trim any literal ``catalog`` array form (best-effort; rarely present
    # in a Terria-roundtripped saved state).
    catalog = init_source.get('catalog')
    if isinstance(catalog, list) and not used_private:
        _strip_private_from_catalog_list(catalog)


def prune_private_catalog_to_used(start_data):
    """Trim injected ``Private Datasets (...)`` branches down to the items actually
    displayed (workbench/timeline/preview) plus their ancestor groups. Mutates and
    returns ``start_data``; a no-op when there is no private branch."""
    if not isinstance(start_data, dict):
        return start_data
    init_sources = start_data.get('initSources')
    if isinstance(init_sources, list):
        for init_source in init_sources:
            _prune_private_branch_in_init_source(init_source)
    return start_data


# --- Private-resource proxy tokens -------------------------------------------
#
# Private datasets injected into a Terria config are referenced through CKAN's
# ``/api/terria/resource/<id>/content`` proxy with a short-lived signed
# ``?token=`` (see ``ResourceUtils.generate_resource_token``). Those tokens
# must not be *persisted* into a saved view (they expire), but — unlike the old
# behaviour, which dropped the whole private branch — we keep the branch and
# re-mint a per-viewer token at render time so a saved view can be shared with
# other users who still have access to the underlying datasets.

# Matches ``/api/terria/resource/<resource_id>/content`` with an optional
# trailing ``/<filename>`` segment (see ``build_proxy_resource_url``).
_PROXY_CONTENT_PATH_RE = re.compile(
    r'^/api/terria/resource/(?P<rid>[^/?#]+)/content(?:/[^?#]*)?$'
)


def _proxy_resource_id(url):
    """Return the resource id if ``url`` is a CKAN Terria resource-proxy URL, else ``None``."""
    if not isinstance(url, str) or '/api/terria/resource/' not in url:
        return None
    try:
        path = urllib.parse.urlsplit(url).path
    except ValueError:
        return None
    match = _PROXY_CONTENT_PATH_RE.match(path)
    return match.group('rid') if match else None


def _set_url_query_token(url, token):
    """Return ``url`` with its ``token`` query param replaced (removed when ``token`` is falsy)."""
    split = urllib.parse.urlsplit(url)
    params = [
        (k, v) for k, v in urllib.parse.parse_qsl(split.query, keep_blank_values=True)
        if k != 'token'
    ]
    if token:
        params.append(('token', token))
    return urllib.parse.urlunsplit(
        (split.scheme, split.netloc, split.path, urllib.parse.urlencode(params), split.fragment)
    )


def _walk_string_values(node, transform):
    """Recursively replace every string value in nested dicts/lists with ``transform(value)`` (in place)."""
    if isinstance(node, dict):
        for key in list(node.keys()):
            value = node[key]
            if isinstance(value, str):
                node[key] = transform(value)
            else:
                _walk_string_values(value, transform)
    elif isinstance(node, list):
        for index in range(len(node)):
            value = node[index]
            if isinstance(value, str):
                node[index] = transform(value)
            else:
                _walk_string_values(value, transform)


def strip_proxy_tokens(start_data):
    """Strip the short-lived ``token`` query param from every resource-proxy URL (in place)."""
    def transform(value):
        if 'token=' in value and _proxy_resource_id(value):
            return _set_url_query_token(value, None)
        return value
    _walk_string_values(start_data, transform)
    return start_data


def strip_proxy_tokens_from_terria_url(url):
    """Strip private-resource proxy ``token`` params from a ``https://.../#start=<json>`` URL.

    Unlike :func:`strip_private_catalog_from_terria_url`, the injected private
    catalog branches are kept — only the expired-once token is removed. Returns
    the rebuilt URL (compactly re-encoded), or the original value unchanged when
    it is not a string, has no ``#start=`` fragment, carries no token, or fails
    to parse as JSON.
    """
    if not isinstance(url, str) or '#start=' not in url:
        return url
    base, _, encoded = url.partition('#start=')
    if 'token' not in encoded:
        return url
    try:
        data = json.loads(urllib.parse.unquote(encoded))
    except (ValueError, TypeError):
        return url
    strip_proxy_tokens(data)
    return base + '#start=' + urllib.parse.quote(
        json.dumps(data, separators=(',', ':'), ensure_ascii=False)
    )


def refresh_proxy_tokens(start_data, mint_token):
    """Re-mint ``token`` query params for resource-proxy URLs in a parsed payload (in place).

    ``mint_token(resource_id) -> str | None``: return a fresh token value when
    the current viewer may read the resource, or ``None`` to leave the URL
    token-less (the proxy then answers ``401`` for that item). Called at most
    once per resource id. Returns ``start_data``.
    """
    decisions = {}

    def transform(value):
        resource_id = _proxy_resource_id(value)
        if not resource_id:
            return value
        if resource_id not in decisions:
            try:
                decisions[resource_id] = mint_token(resource_id)
            except Exception:
                decisions[resource_id] = None
        return _set_url_query_token(value, decisions[resource_id])

    _walk_string_values(start_data, transform)
    return start_data


def prepare_saved_custom_config_url(url):
    """Prepare a ``#start=<json>`` URL for persistence as a view's ``custom_config``.

    Two transforms in one parse/re-encode pass:
      * prune any injected ``Private Datasets (...)`` branch down to the items
        actually displayed (workbench/timeline/preview) plus their ancestor
        groups — keeps the saved config small while still restoring the private
        datasets the user had on the map;
      * strip the short-lived signed proxy ``?token=`` (it expires; a fresh
        per-viewer token is re-minted at render time).

    Returns the rebuilt URL (compactly re-encoded), or the original value
    unchanged when it is not a string, has no ``#start=`` fragment, or fails to
    parse as JSON.
    """
    if not isinstance(url, str) or '#start=' not in url:
        return url
    base, _, encoded = url.partition('#start=')
    try:
        data = json.loads(urllib.parse.unquote(encoded))
    except (ValueError, TypeError):
        return url
    prune_private_catalog_to_used(data)
    strip_proxy_tokens(data)
    return base + '#start=' + urllib.parse.quote(
        json.dumps(data, separators=(',', ':'), ensure_ascii=False)
    )


class TerriaConfigBuilder:
    """Constructor de configuraciones para TerriaJS."""
    
    def __init__(self, config_manager, sld_processor):
        """
        Inicializa el constructor de configuraciones.
        
        Args:
            config_manager: Instancia del gestor de configuraciones
            sld_processor: Instancia del procesador SLD
        """
        self.config_manager = config_manager
        self.sld_processor = sld_processor
    
    def _debug_print(self, message: str):
        """
        Print debug messages only when TERRIA_DEBUG environment variable is set to 'true'.
        
        Args:
            message: Debug message to print
        """
        import os
        if os.getenv("TERRIA_DEBUG", "false").lower() == "true":
            print(message)
    
    def create_base_config(self, resource_name: str, bounds: tuple) -> Dict:
        """
        Crea la configuración base para TerriaJS.
        
        Args:
            resource_name: Nombre del recurso
            bounds: Tupla con (ymax, xmax, ymin, xmin)
            
        Returns:
            Diccionario con configuración base
        """
        ymax, xmax, ymin, xmin = bounds
        
        return {
            "version": "8.0.0",
            "initSources": [{
                "homeCamera": {
                    "north": float(ymax),
                    "east": float(xmax),
                    "south": float(ymin),
                    "west": float(xmin)
                },
                "initialCamera": {
                    "north": float(ymax),
                    "east": float(xmax),
                    "south": float(ymin),
                    "west": float(xmin)
                },
                "stratum": "user",
                "workbench": [resource_name],
                "viewerMode": "3D",
                "focusWorkbenchItems": True,
                "baseMaps": {
                    "defaultBaseMapId": "basemap-positron",
                    "previewBaseMapId": "basemap-positron"
                }
            }]
        }
    
    def create_csv_config(self, resource_name: str, resource_url: str, bounds: tuple) -> str:
        """
        Crea configuración para recursos CSV.
        
        Args:
            resource_name: Nombre del recurso
            resource_url: URL del recurso
            bounds: Tupla con (ymax, xmax, ymin, xmin)
            
        Returns:
            Configuración JSON como string
        """
        catalog_item = {
            "name": resource_name,
            "type": "csv",
            "id": resource_name,
            "url": resource_url,
            "cacheDuration": "5m",
            "isOpenInWorkbench": True,
            "styles": [{
                "id": "default",
                "time": {
                    "spreadStartTime": True,
                    "spreadFinishTime": True
                }
            }],
            "activeStyle": "default"
        }
        
        config_dict = self.create_base_config(resource_name, bounds)
        config_dict["initSources"][0]["catalog"] = [catalog_item]
        
        return json.dumps(config_dict)
    
    def create_cog_config(self, resource_name: str, resource_url: str, bounds: tuple, 
                         sld_url: Optional[str] = None) -> str:
        """
        Crea configuración para recursos COG (Cloud Optimized GeoTIFF).
        
        Args:
            resource_name: Nombre del recurso
            resource_url: URL del recurso
            bounds: Tupla con (ymax, xmax, ymin, xmin)
            sld_url: URL del archivo SLD (opcional)
            
        Returns:
            Configuración JSON como string
        """
        catalog_item = {
            "name": resource_name,
            "type": "cog",
            "id": resource_name,
            "url": resource_url,
            "cacheDuration": "5m",
            "isOpenInWorkbench": True,
            "opacity": 0.8
        }
        
        # Apply SLD styles if available
        if sld_url:
            sld_styles = self.sld_processor.process_cog_sld(sld_url)
            catalog_item.update(sld_styles)
        
        config_dict = self.create_base_config(resource_name, bounds)
        config_dict["initSources"][0]["catalog"] = [catalog_item]
        
        return json.dumps(config_dict)
    
    def create_shp_config(self, resource_name: str, resource_url: str, bounds: tuple, 
                         sld_url: Optional[str] = None) -> str:
        """
        Crea configuración para recursos Shapefile.
        
        Args:
            resource_name: Nombre del recurso
            resource_url: URL del recurso
            bounds: Tupla con (ymax, xmax, ymin, xmin)
            sld_url: URL del archivo SLD (opcional)
            
        Returns:
            Configuración JSON como string
        """
        catalog_item = {
            "name": resource_name,
            "type": "shp",
            "id": resource_name,
            "url": resource_url,
            "cacheDuration": "5m",
            "isOpenInWorkbench": True,
            "opacity": 0.8,
            "clampToGround": False,
            # "forceCesiumPrimitives": True,  # Removed - causes issues with GeoJSON conversion to Cesium primitives
            "enableManualRegionMapping": False  # Ensure we use point/feature rendering
        }
        
        # Apply SLD styles if available
        if sld_url:
            self._debug_print(f"Processing SLD for shapefile: {sld_url}")
            sld_styles = self.sld_processor.process_shp_sld(sld_url)
            self._debug_print(f"SLD processing result: {sld_styles}")
            
            if sld_styles:
                # Apply all SLD style properties
                for key, value in sld_styles.items():
                    catalog_item[key] = value
                    self._debug_print(f"Applied SLD property {key}: {value}")
        
        config_dict = self.create_base_config(resource_name, bounds)
        config_dict["initSources"][0]["catalog"] = [catalog_item]
        
        return json.dumps(config_dict)
    
    def create_geojson_config(self, resource_name: str, resource_url: str, bounds: tuple,
                              sld_url: Optional[str] = None) -> str:
        """
        Crea configuración para recursos GeoJSON.
        
        Args:
            resource_name: Nombre del recurso
            resource_url: URL del recurso
            bounds: Tupla con (ymax, xmax, ymin, xmin)
            sld_url: URL del archivo SLD (opcional)
            
        Returns:
            Configuración JSON como string
        """
        catalog_item = {
            "name": resource_name,
            "type": "geojson",
            "id": resource_name,
            "url": resource_url,
            "cacheDuration": "5m",
            "isOpenInWorkbench": True,
            "opacity": 0.8,
            "clampToGround": False,
            "enableManualRegionMapping": False
        }
        
        # Apply SLD styles if available (same vector styling as SHP)
        if sld_url:
            self._debug_print(f"Processing SLD for geojson: {sld_url}")
            sld_styles = self.sld_processor.process_shp_sld(sld_url)
            self._debug_print(f"SLD processing result: {sld_styles}")
            
            if sld_styles:
                for key, value in sld_styles.items():
                    catalog_item[key] = value
                    self._debug_print(f"Applied SLD property {key}: {value}")
        
        config_dict = self.create_base_config(resource_name, bounds)
        config_dict["initSources"][0]["catalog"] = [catalog_item]
        
        return json.dumps(config_dict)
    
    def create_generic_config(self, resource_name: str, resource_url: str, 
                            resource_format: str, bounds: tuple) -> str:
        """
        Crea configuración genérica para otros tipos de recursos.
        
        Args:
            resource_name: Nombre del recurso
            resource_url: URL del recurso
            resource_format: Formato del recurso
            bounds: Tupla con (ymax, xmax, ymin, xmin)
            
        Returns:
            Configuración JSON como string
        """
        ymax, xmax, ymin, xmin = bounds
        
        config = f"""{{
            "version": "8.0.0",
            "initSources": [
                {{
                    "catalog": [
                        {{
                            "name": "{resource_name}",
                            "type": "group",
                            "isOpen": true,
                            "members": [
                                {{
                                    "id": "{resource_name}",
                                    "name": "{resource_name}",
                                    "type": "{resource_format.lower()}",
                                    "url": "{resource_url}",
                                    "cacheDuration": "5m",
                                    "isOpenInWorkbench": true
                                }}
                            ]
                        }}
                    ],
                    "homeCamera": {{
                        "north": {ymax},
                        "east": {xmax},
                        "south": {ymin},
                        "west": {xmin}
                    }},
                    "initialCamera": {{
                        "north": {ymax},
                        "east": {xmax},
                        "south": {ymin},
                        "west": {xmin}
                    }},
                    "stratum": "user",
                    "models": {{
                        "//{resource_name}": {{
                            "isOpen": true,
                            "knownContainerUniqueIds": [
                                "/"
                            ],
                            "type": "group"
                        }},
                        "{resource_name}": {{
                            "show": true,
                            "isOpenInWorkbench": true,
                            "knownContainerUniqueIds": [
                                "//{resource_name}"
                            ],
                            "type": "{resource_format.lower()}"
                        }},
                        "/": {{
                            "type": "group"
                        }}
                    }},
                    "workbench": [
                        "{resource_name}"
                    ],
                    "viewerMode": "3dSmooth",
                    "focusWorkbenchItems": true,
                    "baseMaps": {{
                        "defaultBaseMapId": "basemap-positron",
                        "previewBaseMapId": "basemap-positron"
                    }}
                }}
            ]
        }}"""
        
        return config
    
    def create_config_for_resource(self, resource: Dict, resource_name: str, 
                                  resource_url: str, bounds: tuple, 
                                  sld_url: Optional[str] = None) -> str:
        """
        Crea la configuración apropiada según el tipo de recurso.
        
        Args:
            resource: Diccionario con datos del recurso
            resource_name: Nombre del recurso
            resource_url: URL del recurso
            bounds: Tupla con (ymax, xmax, ymin, xmin)
            sld_url: URL del archivo SLD (opcional)
            
        Returns:
            Configuración JSON como string
        """
        resource_format = resource.get('format', '').lower()
        
        if self.config_manager.is_csv_resource(resource):
            return self.create_csv_config(resource_name, resource_url, bounds)
        elif self.config_manager.is_tiff_resource(resource):
            return self.create_cog_config(resource_name, resource_url, bounds, sld_url)
        elif self.config_manager.is_shp_resource(resource):
            return self.create_shp_config(resource_name, resource_url, bounds, sld_url)
        elif self.config_manager.is_geojson_resource(resource):
            return self.create_geojson_config(resource_name, resource_url, bounds, sld_url)
        else:
            return self.create_generic_config(resource_name, resource_url, resource_format, bounds)
    
    def process_custom_config(self, custom_config: str, resource_url: str,
                            resource_format: str, sld_url: Optional[str] = None,
                            resource_id: Optional[str] = None) -> Optional[str]:
        """
        Procesa una configuración personalizada y actualiza URLs y estilos.

        Args:
            custom_config: Configuración personalizada
            resource_url: URL del recurso
            resource_format: Formato del recurso
            sld_url: URL del archivo SLD (opcional)
            resource_id: ID del recurso principal de la vista. Cuando se indica,
                solo se reescribe la URL del modelo que corresponde a ese
                recurso; el resto de items (p. ej. datasets privados inyectados)
                se dejan intactos y sus tokens se renuevan en render
                (``refresh_proxy_tokens``).

        Returns:
            Configuración procesada como string JSON, None en caso de error
        """
        try:
            # Parse custom configuration
            parsed_url = urllib.parse.urlparse(custom_config)
            fragment = parsed_url.fragment
            
            if fragment.startswith('share='):
                # Caso de URL con #share
                gist_id = fragment.split('=g-')[1]
                gist_url = f'https://gist.githubusercontent.com/pabrojast/{gist_id}/raw/Terriajs-usercatalog.json'
                try:
                    with urllib.request.urlopen(gist_url) as response:
                        decoded_param = response.read().decode('utf-8')
                except Exception as e:
                    self._debug_print(f"Error fetching gist config: {e}")
                    return None
            else:
                # Caso original con #start
                start_param = fragment.split('=', 1)[1]
                decoded_param = urllib.parse.unquote(start_param)
            
            # Parsear el JSON
            start_data = json.loads(decoded_param)

            # Decode names
            start_data = self._decode_names_in_object(start_data)

            # NOTE: injected "Private Datasets (...)" branches captured into this
            # saved state are intentionally kept (so a saved view can be shared
            # with other users who still have access). Their short-lived proxy
            # ``?token=`` is stripped on save and re-minted per viewer at render
            # time — see ``strip_proxy_tokens_from_terria_url`` /
            # ``refresh_proxy_tokens`` and ``Terria_ViewPlugin``.

            # Get SLD styles if available
            sld_styles = None
            if sld_url and resource_format in ['shp', 'geojson', 'tif', 'tiff', 'geotiff', 'cog']:
                self._debug_print(f"Processing SLD for resource format: {resource_format}")
                sld_styles = self.sld_processor.process_sld_for_resource(sld_url, resource_format)
                self._debug_print(f"SLD styles result: {sld_styles}")
            
            # Strip orphaned group models (e.g. built-in catalog groups like
            # "//IHP-WINS") that were captured in the saved Terria state but
            # already exist in the Terria instance, causing duplicates.
            for init_source in start_data.get('initSources', []):
                if 'models' in init_source:
                    original_keys = set(init_source['models'].keys())
                    init_source['models'] = self._strip_orphaned_group_models(
                        init_source['models']
                    )
                    stripped_keys = original_keys - set(init_source['models'].keys())

                    # Remove previewedItemId when it references a stripped model
                    if stripped_keys and init_source.get('previewedItemId') in stripped_keys:
                        self._debug_print(
                            f"Removing previewedItemId '{init_source['previewedItemId']}' "
                            f"(references stripped model)"
                        )
                        del init_source['previewedItemId']
            
            # Update URLs and apply styles
            for init_source in start_data.get('initSources', []):
                if 'models' in init_source:
                    updated_model_ids = []
                    url_model_keys = [
                        k for k, v in init_source['models'].items()
                        if isinstance(v, dict) and 'url' in v
                    ]
                    single_data_item = len(url_model_keys) == 1
                    for model_key, model_value in init_source['models'].items():
                        if isinstance(model_value, dict) and 'url' in model_value:
                            proxied_rid = _proxy_resource_id(model_value.get('url'))
                            # Decide whether this model is the view's *main*
                            # resource (and so should have its URL/styles
                            # refreshed) or another item (e.g. an injected
                            # private dataset) we must leave untouched.
                            if proxied_rid is not None:
                                is_main_resource = (
                                    resource_id is not None and proxied_rid == resource_id
                                )
                            else:
                                # Non-proxy URL: only treat as the main resource
                                # in the legacy single-data-item case (no extra
                                # catalog items injected) — otherwise we can't
                                # tell which one it is, so leave it alone.
                                is_main_resource = single_data_item

                            # Keep style blocks well-formed for every data item.
                            self._sanitize_model_styles(model_value)

                            if not is_main_resource:
                                # Another catalog item (injected private dataset
                                # etc.) — its proxy token is re-minted per viewer
                                # at render time (see refresh_proxy_tokens).
                                continue

                            # Actualizar la URL
                            model_value['url'] = resource_url
                            model_value.setdefault('isOpenInWorkbench', True)
                            model_value.setdefault('show', True)
                            self._debug_print(f"Updated URL for model {model_key}: {resource_url}")
                            updated_model_ids.append(model_key)

                            # Apply SLD styles if available
                            if sld_styles and resource_format.lower() in ['shp', 'geojson', 'tif', 'tiff', 'geotiff', 'cog']:
                                self._debug_print(f"Applying SLD styles to model {model_key}")
                                # Always apply legends if available
                                if 'legends' in sld_styles:
                                    model_value['legends'] = sld_styles['legends']
                                    self._debug_print(f"Applied legends to model {model_key}")
                                
                                # Apply styles for SHP/GeoJSON resources
                                if resource_format.lower() in ['shp', 'geojson'] and 'styles' in sld_styles:
                                    model_value['styles'] = sld_styles['styles']
                                    if 'activeStyle' in sld_styles:
                                        model_value['activeStyle'] = sld_styles['activeStyle']
                                    # if 'forceCesiumPrimitives' in sld_styles:
                                    #     model_value['forceCesiumPrimitives'] = sld_styles['forceCesiumPrimitives']
                                    self._debug_print(f"Applied styles to model {model_key}: {sld_styles['styles']}")
                                    self._debug_print(f"Applied activeStyle: {sld_styles.get('activeStyle')}")
                                    # print(f"Applied forceCesiumPrimitives: {sld_styles.get('forceCesiumPrimitives')}")
                                    
                                # Apply renderOptions for COG resources
                                elif resource_format.lower() in ['tif', 'tiff', 'geotiff', 'cog'] and 'renderOptions' in sld_styles:
                                    model_value['renderOptions'] = sld_styles['renderOptions']
                                    self._debug_print(f"Applied renderOptions to model {model_key}")
                            self._sanitize_model_styles(model_value)

                    # Ensure data items are visible on map by default
                    # (saved share links may sometimes have an empty workbench list)
                    if updated_model_ids:
                        workbench = init_source.get('workbench')
                        if not isinstance(workbench, list):
                            workbench = []
                        for model_id in updated_model_ids:
                            if model_id not in workbench:
                                workbench.append(model_id)
                        init_source['workbench'] = workbench
            
            return json.dumps(start_data)
            
        except Exception as e:
            self._debug_print(f"Error processing custom config: {e}")
            return None

    def _sanitize_model_styles(self, model_value: Dict) -> None:
        """
        Normalize table style blocks to avoid Terria parse/runtime errors.

        Some saved custom configs contain partial style definitions
        (for example enumColors without mapType/colorColumn). This method
        fills safe defaults when they can be inferred.
        """
        styles = model_value.get('styles')
        if not isinstance(styles, list):
            return

        style_ids = []
        for style in styles:
            if not isinstance(style, dict):
                continue
            style_id = style.get('id')
            if isinstance(style_id, str):
                style_ids.append(style_id)

            color = style.get('color')
            if not isinstance(color, dict):
                continue

            enum_colors = color.get('enumColors')
            bin_colors = color.get('binColors')
            has_enum = isinstance(enum_colors, list) and len(enum_colors) > 0
            has_bin = isinstance(bin_colors, list) and len(bin_colors) > 0
            has_palette = bool(color.get('colorPalette'))
            palette_name = (color.get('colorPalette') or '').lower()
            is_category_palette = palette_name.startswith('category')

            if not color.get('mapType'):
                if has_enum:
                    color['mapType'] = 'enum'
                elif has_bin:
                    color['mapType'] = 'bin'
                elif has_palette:
                    # Category palettes are intended for discrete values.
                    color['mapType'] = 'enum' if is_category_palette else 'continuous'

            # Guardrail: some saved configs force continuous + category palette,
            # which can break categorical CSV columns.
            if color.get('mapType') == 'continuous' and is_category_palette:
                color['mapType'] = 'enum'

            # Infer colorColumn from style id when missing (common in legacy share links)
            if isinstance(color, dict) and not color.get('colorColumn'):
                inferred_column = style_id or model_value.get('activeStyle')
                if inferred_column:
                    color['colorColumn'] = inferred_column

        active_style = model_value.get('activeStyle')
        if style_ids and (not active_style or active_style not in style_ids):
            model_value['activeStyle'] = style_ids[0]
    
    def _strip_orphaned_group_models(self, models: Dict) -> Dict:
        """
        Remove group models not in the ancestry chain of any data item.
        
        Saved Terria states include model entries for built-in catalog groups
        (e.g. "//IHP-WINS") that were merely opened/browsed.  When loaded via
        #start=, these create duplicates of groups already in the instance.
        This method keeps only models reachable from data items (those with a
        ``url``) plus the root ``/``.
        """
        if not models:
            return models

        needed = {"/"}
        # Seed with data-item models (have a url) and trace their ancestry
        for key, model in models.items():
            if isinstance(model, dict) and 'url' in model:
                needed.add(key)
                to_visit = [key]
                while to_visit:
                    current = to_visit.pop()
                    current_model = models.get(current, {})
                    if isinstance(current_model, dict):
                        for cid in current_model.get('knownContainerUniqueIds', []):
                            if cid not in needed and cid in models:
                                needed.add(cid)
                                to_visit.append(cid)

        # Also follow members from already-needed groups
        changed = True
        while changed:
            changed = False
            for key in list(needed):
                model = models.get(key, {})
                if isinstance(model, dict):
                    for member in model.get('members', []):
                        if member in models and member not in needed:
                            needed.add(member)
                            changed = True

        stripped = {k: v for k, v in models.items() if k in needed}
        removed = set(models.keys()) - needed
        if removed:
            self._debug_print(
                f"Stripped orphaned group models from config: {removed}"
            )
        return stripped

    def _decode_names_in_object(self, obj: Any) -> Any:
        """
        Método auxiliar para decodificar nombres en objetos anidados.
        
        Args:
            obj: Objeto a procesar
            
        Returns:
            Objeto procesado con nombres decodificados
        """
        if isinstance(obj, dict):
            new_dict = {}
            for key, value in obj.items():
                # Decode the key if it contains '+'
                new_key = urllib.parse.unquote_plus(key) if '+' in key else key
                
                if isinstance(value, dict):
                    # If there are specific fields that contain names
                    if 'name' in value:
                        value['name'] = urllib.parse.unquote_plus(value['name'])
                    if 'title' in value:
                        value['title'] = urllib.parse.unquote_plus(value['title'])
                    if 'legend' in value and isinstance(value['legend'], dict):
                        if 'title' in value['legend']:
                            value['legend']['title'] = urllib.parse.unquote_plus(value['legend']['title'])
                    
                    value = self._decode_names_in_object(value)
                elif isinstance(value, list):
                    value = [
                        urllib.parse.unquote_plus(item) if isinstance(item, str) else self._decode_names_in_object(item) 
                        for item in value
                    ]
                elif isinstance(value, str) and '+' in value:
                    value = urllib.parse.unquote_plus(value)
                    
                new_dict[new_key] = value
            return new_dict
        elif isinstance(obj, list):
            return [self._decode_names_in_object(item) for item in obj]
        return obj 
