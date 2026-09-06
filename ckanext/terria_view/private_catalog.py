# encoding: utf-8
"""Lazy, authenticated Terria catalog generation for non-public CKAN datasets."""

from collections import OrderedDict
import re
import secrets
import urllib.parse

import ckan.plugins.toolkit as toolkit


PRIVATE_CATALOG_ID_PREFIX = '__ckan_private_catalog__/'
PRIVATE_CATALOG_MODE_AUTO = 'auto'
PRIVATE_CATALOG_MODES = {'auto', 'lazy', 'inline'}
_CATALOG_ID_RE = re.compile(r'^[A-Za-z0-9_-]{8,64}$')

# ckanext-datashare stores its level in the ``access_level`` extra
# (``public | confidential | findable | viewable | restricted``); CKAN core's
# ``private=True`` corresponds to ``confidential``.
ACCESS_LEVEL_FIELD = 'access_level'
# One paginated Solr query: confidential datasets (``capacity:private``) plus
# any datashare level other than ``public``.
NON_PUBLIC_FQ = (
    f'+(capacity:private OR ({ACCESS_LEVEL_FIELD}:* AND NOT {ACCESS_LEVEL_FIELD}:public))'
)
# ``access_level`` is indexed but not stored as a top-level Solr field; asking
# for ``extras_access_level`` works because CKAN folds ``extras_*`` back into
# ``row['access_level']`` in ``package_search`` results.
INDEX_FL = ['id', 'name', 'title', 'organization', 'capacity', 'extras_access_level']


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


def is_same_origin(site_url: str, terria_instance_url: str) -> bool:
    """True when Terria runs on the CKAN origin (or on a relative path)."""
    origin = _origin(terria_instance_url)
    if origin == 'relative':
        return True
    return origin is not None and origin == _origin(site_url)


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


def dataset_access_level(dataset) -> str:
    """Return the datashare access level of a dataset dict (``public`` when unset).

    Looks at the top-level key first (``package_show`` with datashare, or a Solr
    row where ``extras_access_level`` was folded back) and then at the raw
    ``extras`` list.
    """
    if not isinstance(dataset, dict):
        return 'public'
    level = dataset.get(ACCESS_LEVEL_FIELD)
    if not level:
        for extra in dataset.get('extras') or []:
            if isinstance(extra, dict) and extra.get('key') == ACCESS_LEVEL_FIELD:
                level = extra.get('value')
                break
    level = str(level or '').strip().lower()
    return level or 'public'


def is_non_public_dataset(dataset) -> bool:
    """True for CKAN-private datasets and for any datashare level other than public."""
    if not isinstance(dataset, dict):
        return False
    return (
        dataset.get('private') is True
        or dataset.get('capacity') == 'private'
        or dataset_access_level(dataset) != 'public'
    )


def _api_url(path: str, catalog_id: str, absolute: bool = False, site_url: str = '') -> str:
    """Build a private-catalog API URL; relative by default (same-origin Terria)."""
    query = urllib.parse.urlencode({'catalog_id': catalog_id})
    if not absolute:
        return f"{path}?{query}"
    base = (site_url or toolkit.config.get('ckan.site_url', '') or '').rstrip('/')
    return f"{base}{path}?{query}"


def _absolute_api_url(site_url: str, path: str, catalog_id: str) -> str:
    """Compatibility alias for :func:`_api_url` with ``absolute=True``."""
    return _api_url(path, catalog_id, absolute=True, site_url=site_url)


def build_private_catalog_reference(user: str, site_url: str, catalog_id=None,
                                    absolute: bool = True) -> dict:
    """Build the tiny reference injected into the initial Terria ``#start``.

    ``absolute=False`` emits a relative URL for a same-origin Terria so the
    request never goes through the terriajs-server proxy (which drops cookies).
    """
    catalog_id = normalize_catalog_id(catalog_id)
    return {
        'catalog': [{
            'id': f'{PRIVATE_CATALOG_ID_PREFIX}{catalog_id}/browser',
            'name': f'Private Datasets ({user})',
            'type': 'terria-reference',
            'url': _api_url(
                '/api/terria/user/private-catalog', catalog_id,
                absolute=absolute, site_url=site_url,
            ),
            'isGroup': True,
            'description': f'Private datasets accessible to {user}',
        }]
    }


class PrivateCatalogBuilder:
    """Generate the index cheaply and expand a single dataset on demand."""

    def __init__(self, generator, site_url=None, relative_urls=True):
        self.generator = generator
        self.site_url = site_url or toolkit.config.get('ckan.site_url', '')
        # The lazy endpoints are consumed same-origin (cookie auth), so member
        # and resource URLs are relative unless a caller asks otherwise.
        self.relative_urls = bool(relative_urls)

    @staticmethod
    def _access(context: dict, dataset_id):
        """Run ``datashare_access_check`` for one dataset.

        Returns the access dict, ``None`` when ckanext-datashare is not
        installed (action not registered) and ``False`` on any other failure
        so callers fail closed.
        """
        try:
            access_check = toolkit.get_action('datashare_access_check')
        except (KeyError, ImportError):
            return None
        try:
            result = access_check(dict(context), {'id': dataset_id})
        except Exception:
            return False
        return result if isinstance(result, dict) else False

    def _can_load(self, context: dict, dataset: dict) -> bool:
        """Gate on ``can_download``: Terria fetches the raw file, so viewing is not enough.

        Without datashare, fall back to the historical private-only behaviour
        (``private=True`` from ``package_show`` or ``capacity=private`` from Solr).
        """
        access = self._access(context, dataset.get('id'))
        if access is None:
            return dataset.get('private') is True or dataset.get('capacity') == 'private'
        if not access:
            return False
        return bool(access.get('can_download'))

    def build_index(self, context: dict, catalog_id=None) -> dict:
        catalog_id = normalize_catalog_id(catalog_id)
        rows = 1000
        start = 0
        datasets = []
        organization_titles = {}

        # ``include_private`` with the user's context makes Solr apply the
        # permission labels; findable/restricted rows are discoverable by any
        # logged-in user and are narrowed below by ``can_download``.
        while True:
            result = toolkit.get_action('package_search')(context, {
                'include_private': True,
                'q': '*:*',
                'fq': NON_PUBLIC_FQ,
                'rows': rows,
                'start': start,
                'fl': list(INDEX_FL),
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
            # Defensive: the fq already excludes public rows.
            if not is_non_public_dataset(dataset):
                continue
            if not self._can_load(context, dataset):
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
                'isOpen': True,
                'shareable': False,
                'members': [],
            })['members']
            dataset_title = dataset.get('title') or dataset.get('name') or 'Unknown Dataset'
            encoded_dataset_id = urllib.parse.quote(str(dataset_id), safe='')
            level = dataset_access_level(dataset)
            if level == 'public':
                # Non-public row without a datashare level: legacy CKAN
                # ``private=True``, which datashare calls ``confidential``.
                level = 'confidential'
            members.append({
                'id': f'{PRIVATE_CATALOG_ID_PREFIX}{catalog_id}/dataset/{dataset_id}',
                'name': dataset_title,
                'type': 'terria-reference',
                'url': _api_url(
                    f'/api/terria/user/private-catalog/dataset/{encoded_dataset_id}',
                    catalog_id,
                    absolute=not self.relative_urls,
                    site_url=self.site_url,
                ),
                'isGroup': True,
                'description': f'Access level: {level}',
            })

        return {'catalog': list(orgs.values())}

    def build_dataset(self, context: dict, dataset_id: str, catalog_id=None) -> dict:
        catalog_id = normalize_catalog_id(catalog_id)
        dataset = toolkit.get_action('package_show')(context, {'id': dataset_id})
        if (
            dataset.get('state') != 'active'
            or not is_non_public_dataset(dataset)
            or not self._can_load(context, dataset)
        ):
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
                        relative_urls=self.relative_urls,
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
