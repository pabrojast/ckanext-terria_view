# encoding: utf-8
"""Lazy, authenticated Terria catalog generation for private CKAN datasets."""

from collections import OrderedDict
import re
import secrets
import urllib.parse

import ckan.plugins.toolkit as toolkit


PRIVATE_CATALOG_ID_PREFIX = '__ckan_private_catalog__/'
PRIVATE_CATALOG_MODE_AUTO = 'auto'
PRIVATE_CATALOG_MODES = {'auto', 'lazy', 'inline'}
_CATALOG_ID_RE = re.compile(r'^[A-Za-z0-9_-]{8,64}$')


def new_catalog_id() -> str:
    """Return a short opaque id used only to namespace one catalog browser."""
    return secrets.token_urlsafe(12)


def normalize_catalog_id(value) -> str:
    """Accept safe client round-trips, otherwise create a fresh namespace."""
    value = str(value or '')
    return value if _CATALOG_ID_RE.match(value) else new_catalog_id()


def _origin(url: str):
    if not url:
        return None
    parsed = urllib.parse.urlsplit(url)
    if not parsed.scheme and not parsed.netloc:
        return 'relative'
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or '').lower()
    if not scheme or not host:
        return None
    port = parsed.port
    if port is None:
        port = 443 if scheme == 'https' else 80 if scheme == 'http' else None
    return scheme, host, port


def resolve_private_catalog_mode(configured_mode, site_url, terria_instance_url) -> str:
    """Resolve ``auto`` to lazy for same-origin Terria, inline otherwise."""
    mode = str(configured_mode or PRIVATE_CATALOG_MODE_AUTO).strip().lower()
    if mode not in PRIVATE_CATALOG_MODES:
        mode = PRIVATE_CATALOG_MODE_AUTO
    if mode != PRIVATE_CATALOG_MODE_AUTO:
        return mode

    terria_origin = _origin(terria_instance_url)
    if terria_origin == 'relative':
        return 'lazy'
    return 'lazy' if terria_origin and terria_origin == _origin(site_url) else 'inline'


def _absolute_api_url(site_url: str, path: str, catalog_id: str) -> str:
    base = (site_url or toolkit.config.get('ckan.site_url', '') or '').rstrip('/')
    query = urllib.parse.urlencode({'catalog_id': catalog_id})
    return f"{base}{path}?{query}"


def build_private_catalog_reference(user: str, site_url: str, catalog_id=None) -> dict:
    """Build the tiny reference injected into the initial Terria ``#start``."""
    catalog_id = normalize_catalog_id(catalog_id)
    return {
        'catalog': [{
            'id': f'{PRIVATE_CATALOG_ID_PREFIX}{catalog_id}/browser',
            'name': f'Private Datasets ({user})',
            'type': 'terria-reference',
            'url': _absolute_api_url(
                site_url, '/api/terria/user/private-catalog', catalog_id
            ),
            'isGroup': True,
            'description': f'Private datasets accessible to {user}',
        }]
    }


class PrivateCatalogBuilder:
    """Generate the index cheaply and expand a single dataset on demand."""

    def __init__(self, generator, site_url=None):
        self.generator = generator
        self.site_url = site_url or toolkit.config.get('ckan.site_url', '')

    def build_index(self, context: dict, catalog_id=None) -> dict:
        catalog_id = normalize_catalog_id(catalog_id)
        rows = 1000
        start = 0
        datasets = []
        organization_titles = {}

        while True:
            result = toolkit.get_action('package_search')(context, {
                'include_private': True,
                'q': '*:*',
                'fq': '+capacity:private',
                'rows': rows,
                'start': start,
                'fl': ['id', 'name', 'title', 'organization'],
                'facet.field': ['organization'],
                'facet.limit': -1,
            })
            page = result.get('results') or []
            datasets.extend(page)

            facets = result.get('search_facets') or {}
            for item in (facets.get('organization') or {}).get('items') or []:
                organization_titles[item.get('name')] = (
                    item.get('display_name') or item.get('name')
                )

            start += len(page)
            if not page or start >= int(result.get('count') or 0):
                break

        orgs = OrderedDict()
        for dataset in sorted(
            datasets,
            key=lambda value: (value.get('title') or value.get('name') or '').casefold(),
        ):
            dataset_id = dataset.get('id')
            if not dataset_id:
                continue
            organization = dataset.get('organization')
            if isinstance(organization, dict):
                org_key = organization.get('name') or '__no_org__'
                org_title = organization.get('title') or organization.get('name')
            elif organization:
                org_key = str(organization)
                org_title = organization_titles.get(org_key, org_key)
            else:
                org_key = '__no_org__'
                org_title = 'Unknown Organization'

            members = orgs.setdefault(org_key, {
                'name': org_title or 'Unknown Organization',
                'type': 'group',
                'id': f'{PRIVATE_CATALOG_ID_PREFIX}{catalog_id}/organization/{org_key}',
                'members': [],
            })['members']
            dataset_title = dataset.get('title') or dataset.get('name') or 'Unknown Dataset'
            encoded_dataset_id = urllib.parse.quote(str(dataset_id), safe='')
            members.append({
                'id': f'{PRIVATE_CATALOG_ID_PREFIX}{catalog_id}/dataset/{dataset_id}',
                'name': dataset_title,
                'type': 'terria-reference',
                'url': _absolute_api_url(
                    self.site_url,
                    f'/api/terria/user/private-catalog/dataset/{encoded_dataset_id}',
                    catalog_id,
                ),
                'isGroup': True,
                'description': 'Private dataset',
            })

        return {'catalog': list(orgs.values())}

    def build_dataset(self, context: dict, dataset_id: str, catalog_id=None) -> dict:
        catalog_id = normalize_catalog_id(catalog_id)
        dataset = toolkit.get_action('package_show')(context, {'id': dataset_id})
        if not dataset.get('private') or dataset.get('state') != 'active':
            raise toolkit.ObjectNotFound('Private dataset not found')

        org = dataset.get('organization') or {}
        org_info = {
            'display_name': org.get('title') or org.get('name') or 'Unknown Organization',
            'description': org.get('description', '') or '',
            'image_display_url': org.get('image_display_url', '') or '',
        }
        notes = dataset.get('notes', '') or ''
        supported = {value.lower() for value in self.generator.formatos_permitidos}
        members = []

        for resource in dataset.get('resources') or []:
            if (resource.get('format') or '').lower() not in supported:
                continue
            resource_id = resource.get('id')
            if not resource_id:
                continue
            try:
                views = toolkit.get_action('resource_view_list')(
                    context, {'id': resource_id}
                )
                terria_views = [
                    view for view in views if view.get('view_type') == 'terria_view'
                ]
                view_count = max(1, len(terria_views))
                for view_index in range(view_count):
                    item, _ = self.generator.format_dataset_item(
                        resource,
                        dataset.get('id'),
                        notes,
                        org_info,
                        view_index,
                        package=dataset,
                        user_context=context,
                        terria_views=terria_views,
                    )
                    item['id'] = (
                        f'{PRIVATE_CATALOG_ID_PREFIX}{catalog_id}/resource/'
                        f'{resource_id}/view/{view_index}'
                    )
                    item.pop('shareKeys', None)
                    members.append(item)
            except Exception:
                continue

        return {'catalog': self.generator.convert_sets_to_lists(members)}
