"""Read saved Terria states without assuming every share token is a gist."""
import json
import re
from urllib.parse import urlsplit, parse_qs, urljoin

import requests
from ckan.plugins import toolkit

MAX_BYTES = 4 * 1024 * 1024


def _download(url):
    # Destinations are constructed only from administrator-configured instance
    # URLs (or the fixed legacy gist host), never from a resource-supplied host.
    with requests.get(url, timeout=(5, 15), stream=True, allow_redirects=False) as response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("Saved map service returned an unexpected response")
        payload = bytearray()
        for chunk in response.iter_content(65536):
            payload.extend(chunk)
            if len(payload) > MAX_BYTES:
                raise ValueError("Saved map exceeds the size limit")
        return payload.decode("utf-8")


def read_saved_config(value, default_instance_url=None):
    if not isinstance(value, str) or len(value) > MAX_BYTES * 3:
        raise ValueError("Invalid saved map")
    if value.lstrip().startswith("{"):
        raw = value
    else:
        parsed = urlsplit(value)
        params = parse_qs(parsed.fragment)
        if "start" in params:
            raw = params["start"][0]
        elif "share" in params:
            token = params["share"][0]
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", token):
                raise ValueError("Invalid share token")
            if token.startswith("g-"):
                raw = _download("https://gist.githubusercontent.com/pabrojast/" + token[2:] + "/raw/Terriajs-usercatalog.json")
            else:
                config = toolkit.config
                instances = [config.get("ckanext.terria_view.default_instance_url"), default_instance_url]
                if config.get("ckan.site_url"):
                    instances.append(config["ckan.site_url"].rstrip("/") + "/terria/")
                instances.extend(str(config.get("ckanext.terria_view.share_instances", "")).split())
                base = None
                for instance in filter(None, instances):
                    candidate = urlsplit(instance)
                    if candidate.scheme in ("http", "https") and not candidate.username and not candidate.password and (
                        (not parsed.netloc or (parsed.scheme, parsed.netloc) == (candidate.scheme, candidate.netloc))
                        and parsed.path.rstrip("/") == candidate.path.rstrip("/")
                    ):
                        base = instance.split("#")[0].split("?")[0].rstrip("/") + "/"
                        break
                if base is None:
                    raise ValueError("This saved map's share service is not configured")
                raw = _download(urljoin(base, "share/" + token))
        else:
            raise ValueError("Saved map has no start or share state")
    if len(raw.encode("utf-8")) > MAX_BYTES:
        raise ValueError("Saved map exceeds the size limit")
    result = json.loads(raw)
    if not isinstance(result, dict) or not isinstance(result.get("initSources"), list):
        raise ValueError("Saved map must contain initSources")
    return result
