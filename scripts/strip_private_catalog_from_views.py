#!/usr/bin/env python3
# encoding: utf-8
"""
One-off maintenance script: shrink Terria ``resource_view`` configs that got
bloated by an injected private-dataset catalog.

Background
----------
``Terria_ViewPlugin.setup_template_variables`` injects the logged-in user's
private datasets into the rendered ``encoded_config`` so the embedded map shows
them in its catalog tree. If the user then clicks "Save Configuration" (or
re-saves the view from the CKAN form with the iframe URL still in the field),
that whole tree gets baked into the view's ``custom_config`` — and re-injected
on the next render, so it grows without bound. Symptoms: multi-MB
``resource_view.config`` rows, 30-60s renders of the view edit form, broken
``#start=`` URLs once the embedded signed proxy tokens expire.

The plugin fix (``strip_private_catalog_*`` in ``terria_config_builder.py``)
stops new bloat. This script cleans up rows that are already bloated.

What it does, per ``terria_view`` row:
  * strips ``Private Datasets (...)`` branches from ``config.custom_config``
    (the ``https://.../#start=<json>`` URL);
  * drops the stale ``config.__extras.custom_config_url`` form-field copy;
  * leaves everything else untouched.

Usage
-----
    # dry run (default) — prints what would change, writes nothing
    python3 strip_private_catalog_from_views.py

    # actually apply
    python3 strip_private_catalog_from_views.py --apply

    # explicit DB URL (otherwise CKAN_SQLALCHEMY_URL / SQLALCHEMY_URL env is used)
    python3 strip_private_catalog_from_views.py --db-url postgresql://user:pass@host/db --apply

    # only touch rows whose config is larger than N bytes (default 0 = all)
    python3 strip_private_catalog_from_views.py --min-bytes 100000 --apply

Run it from anywhere that can reach the CKAN database, e.g. inside a CKAN pod:
    kubectl -n ckan cp scripts/strip_private_catalog_from_views.py <pod>:/tmp/
    kubectl -n ckan exec <pod> -- python3 /tmp/strip_private_catalog_from_views.py --apply

Requires: psycopg2 (already present in CKAN images).
"""
import argparse
import json
import os
import sys
import urllib.parse

try:
    import psycopg2
except ImportError:  # pragma: no cover
    sys.stderr.write("psycopg2 is required (it ships with CKAN images)\n")
    raise


# --- private-catalog stripping (self-contained copy of the plugin helpers) ---

_PRIVATE_CATALOG_NAME_PREFIX = 'Private Datasets ('


def _looks_like_private_catalog_id(value):
    if not isinstance(value, str):
        return False
    normalized = value.lstrip('/').replace('+', ' ').strip()
    return normalized.startswith(_PRIVATE_CATALOG_NAME_PREFIX)


def _strip_private_from_catalog_list(catalog):
    if not isinstance(catalog, list):
        return
    catalog[:] = [
        entry for entry in catalog
        if not (isinstance(entry, dict) and _looks_like_private_catalog_id(entry.get('name')))
    ]


def _strip_private_from_init_source(init_source):
    if not isinstance(init_source, dict):
        return
    models = init_source.get('models')
    removed = set()
    if isinstance(models, dict):
        for key in list(models.keys()):
            if key != '/' and _looks_like_private_catalog_id(key):
                removed.add(key)
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
        for value in models.values():
            if isinstance(value, dict) and isinstance(value.get('members'), list):
                value['members'] = [
                    m for m in value['members']
                    if not (isinstance(m, str) and (m in removed or _looks_like_private_catalog_id(m)))
                ]
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
    _strip_private_from_catalog_list(init_source.get('catalog'))


def strip_private_catalog_branches(start_data):
    if not isinstance(start_data, dict):
        return start_data
    init_sources = start_data.get('initSources')
    if isinstance(init_sources, list):
        for init_source in init_sources:
            _strip_private_from_init_source(init_source)
    _strip_private_from_catalog_list(start_data.get('catalog'))
    return start_data


def strip_private_catalog_from_terria_url(url):
    if not isinstance(url, str) or '#start=' not in url:
        return url
    base, _, encoded = url.partition('#start=')
    try:
        data = json.loads(urllib.parse.unquote(encoded))
    except (ValueError, TypeError):
        return url
    strip_private_catalog_branches(data)
    return base + '#start=' + urllib.parse.quote(json.dumps(data))


# --- the cleanup itself -------------------------------------------------------

def clean_config(config):
    """Return (new_config_dict_or_None, changed_bool). ``config`` is a dict."""
    if not isinstance(config, dict):
        return None, False
    changed = False
    new_config = json.loads(json.dumps(config))  # deep copy

    cc = new_config.get('custom_config')
    if isinstance(cc, str) and cc not in ('', 'NA') and '#start=' in cc:
        stripped = strip_private_catalog_from_terria_url(cc)
        if stripped != cc:
            new_config['custom_config'] = stripped
            changed = True

    extras = new_config.get('__extras')
    if isinstance(extras, dict) and 'custom_config_url' in extras:
        # Stale form-field copy of custom_config; nothing reads it.
        del extras['custom_config_url']
        changed = True
        if not extras:
            del new_config['__extras']

    return (new_config if changed else None), changed


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--db-url', default=os.environ.get('CKAN_SQLALCHEMY_URL')
                        or os.environ.get('SQLALCHEMY_URL'),
                        help='PostgreSQL URL (default: $CKAN_SQLALCHEMY_URL / $SQLALCHEMY_URL)')
    parser.add_argument('--apply', action='store_true',
                        help='actually write changes (default: dry run)')
    parser.add_argument('--min-bytes', type=int, default=0,
                        help='only consider rows whose config is larger than this many bytes')
    args = parser.parse_args()

    if not args.db_url:
        parser.error('no database URL: pass --db-url or set CKAN_SQLALCHEMY_URL')

    conn = psycopg2.connect(args.db_url)
    conn.autocommit = False
    total = scanned = changed = 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, resource_id, length(config) AS clen, config "
                "FROM resource_view WHERE view_type = 'terria_view' "
                "AND length(config) > %s ORDER BY length(config) DESC",
                (args.min_bytes,),
            )
            rows = cur.fetchall()

        for view_id, resource_id, clen, config_text in rows:
            total += 1
            try:
                config = json.loads(config_text)
            except (ValueError, TypeError):
                print("! %s (resource %s): config is not valid JSON, skipping" % (view_id, resource_id))
                continue
            scanned += 1
            new_config, did_change = clean_config(config)
            if not did_change:
                continue
            changed += 1
            new_text = json.dumps(new_config)
            print("%s  resource=%s  %d -> %d bytes (%s)" % (
                view_id, resource_id, clen, len(new_text),
                'APPLIED' if args.apply else 'dry-run',
            ))
            if args.apply:
                with conn.cursor() as cur:
                    cur.execute("UPDATE resource_view SET config = %s WHERE id = %s",
                                (new_text, view_id))
        if args.apply:
            conn.commit()
        else:
            conn.rollback()
    finally:
        conn.close()

    print("\n%d terria views examined, %d would change%s." % (
        total, changed, ' and were updated' if args.apply else ' (run with --apply to write)',
    ))


if __name__ == '__main__':
    main()
