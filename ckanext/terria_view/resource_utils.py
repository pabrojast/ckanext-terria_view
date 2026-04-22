# encoding: utf-8
"""
Módulo con utilidades para manejo de recursos.
"""
import hashlib
import hmac
import json
import os.path
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple
from ckan.lib import uploader
from ckan.plugins import toolkit


# Shared token TTL for private resource proxy URLs (in seconds).
RESOURCE_PROXY_TOKEN_TTL = 3600


class ResourceUtils:
    """Utilidades para manejo de recursos."""

    def __init__(self, config_manager):
        """
        Inicializa las utilidades de recursos.

        Args:
            config_manager: Instancia del gestor de configuraciones
        """
        self.config_manager = config_manager

    def _get_token_secret(self) -> bytes:
        """
        Retrieve the HMAC secret used to sign resource proxy tokens.

        Falls back across common CKAN secret keys so tokens stay valid across
        environments. Returning bytes for HMAC compatibility.
        """
        for key in ('beaker.session.secret', 'SECRET_KEY', 'flask.secret_key'):
            value = toolkit.config.get(key) if toolkit.config else None
            if value:
                return str(value).encode('utf-8')
        # Last-resort fallback; CKAN deployments should always set a secret.
        return b'ckanext-terria-view-proxy-fallback'

    def generate_resource_token(self, resource_id: str,
                                ttl_seconds: int = RESOURCE_PROXY_TOKEN_TTL) -> str:
        """
        Generate a signed access token for the resource proxy endpoint.

        Token format: ``<expiry_unix>.<hex_hmac_sha256>``. Anyone holding the
        token can fetch the resource until expiry, similar in spirit to a SAS
        token but served by CKAN with open CORS.
        """
        if not resource_id:
            raise ValueError('resource_id is required to generate a token')

        expiry = int(time.time()) + max(60, int(ttl_seconds))
        payload = f"{resource_id}|{expiry}".encode('utf-8')
        signature = hmac.new(
            self._get_token_secret(), payload, hashlib.sha256
        ).hexdigest()
        return f"{expiry}.{signature}"

    def verify_resource_token(self, resource_id: str, token: str) -> bool:
        """
        Validate a signed proxy token for a specific resource.

        Uses constant-time comparison to resist timing attacks.
        """
        if not resource_id or not token or '.' not in token:
            return False
        expiry_str, _, signature = token.partition('.')
        if not signature:
            return False
        try:
            expiry = int(expiry_str)
        except (TypeError, ValueError):
            return False
        if expiry < int(time.time()):
            return False

        payload = f"{resource_id}|{expiry}".encode('utf-8')
        expected = hmac.new(
            self._get_token_secret(), payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(signature, expected)

    def build_proxy_resource_url(self, resource_id: str,
                                 ttl_seconds: int = RESOURCE_PROXY_TOKEN_TTL,
                                 filename: Optional[str] = None) -> str:
        """
        Build the CKAN-hosted proxy URL for a private resource.

        The proxy streams the file server-side (using the CKAN uploader to
        resolve the Azure SAS) and returns it with open CORS headers, so the
        cross-domain Terria iframe can load it without depending on the
        Storage Account's CORS configuration.

        The ``filename`` segment is appended to the path so that TerriaJS
        client-side validations that inspect the URL extension (e.g. the
        shapefile catalog item requires a ``.zip`` URL, GeoJSON expects
        ``.geojson``) don't reject the proxy URL. The filename is not used
        for authorization — the signed token alone gates access.
        """
        site_url = (self.config_manager.site_url
                    or toolkit.config.get('ckan.site_url', '') or '').rstrip('/')
        token = self.generate_resource_token(resource_id, ttl_seconds=ttl_seconds)

        path = f"/api/terria/resource/{resource_id}/content"
        if filename:
            # Preserve extension (important for Terria validations) while making
            # the segment URL-safe. quote() leaves ``.`` unchanged so ``file.zip``
            # stays ``file.zip``.
            safe_filename = urllib.parse.quote(filename, safe='.-_')
            if safe_filename:
                path = f"{path}/{safe_filename}"

        return f"{site_url}{path}?token={token}"

    def _to_absolute_url(self, url: str) -> str:
        """
        Convierte una URL relativa en absoluta usando ckan.site_url.

        Args:
            url: URL a normalizar

        Returns:
            URL absoluta si se puede resolver, si no la original
        """
        if not url:
            return url

        parsed = urllib.parse.urlparse(url)
        if parsed.scheme and parsed.netloc:
            return url

        site_url = self.config_manager.site_url or toolkit.config.get('ckan.site_url', '')
        if not site_url:
            return url

        site_url = site_url.rstrip('/') + '/'

        if url.startswith('//'):
            scheme = urllib.parse.urlparse(site_url).scheme or 'https'
            return f"{scheme}:{url}"

        return urllib.parse.urljoin(site_url, url.lstrip('/'))

    def _extract_upload_filename(self, resource: Dict, resource_url: str) -> str:
        """
        Extrae el nombre de archivo para uploads privados.

        ckanext-cloudstorage espera un ``filename`` (ej. ``data.csv``) en
        ``get_url_from_filename``, no la URL completa del endpoint download.
        """
        candidates = []
        raw_resource_url = resource.get('url')
        if isinstance(raw_resource_url, str) and raw_resource_url:
            candidates.append(raw_resource_url)
        if isinstance(resource_url, str) and resource_url:
            candidates.append(resource_url)

        for candidate in candidates:
            parsed = urllib.parse.urlparse(candidate)
            path = parsed.path or candidate
            if '/download/' in path:
                filename = path.rsplit('/download/', 1)[-1]
            else:
                filename = os.path.basename(path.rstrip('/'))
            filename = urllib.parse.unquote(filename or '')
            if filename:
                return filename

        return ''
    
    def get_sld_files_from_dataset(self, package_id: str) -> List[Dict]:
        """
        Obtiene archivos SLD de un dataset usando la API interna de CKAN.
        
        Args:
            package_id: ID del paquete/dataset
            
        Returns:
            Lista de diccionarios con información de archivos SLD
        """
        try:
            context = {'ignore_auth': True}
            package_data = toolkit.get_action('package_show')(
                context, {'id': package_id}
            )

            sld_files = []
            resources = package_data.get('resources', [])

            for resource in resources:
                resource_format = resource.get('format', '').lower()

                if resource_format == 'sld':
                    sld_file = {
                        'id': resource.get('id'),
                        'name': resource.get('name', 'Archivo SLD sin nombre'),
                        'url': resource.get('url'),
                        'description': resource.get('description', '')
                    }
                    sld_files.append(sld_file)

            return sld_files
        except Exception as e:
            print(f"Error obteniendo archivos SLD desde la API: {e}")
            return []
    
    def extract_bounds_from_spatial(self, spatial: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        Extrae coordenadas de un campo spatial en formato GeoJSON.
        
        Args:
            spatial: String con datos espaciales en formato GeoJSON
            
        Returns:
            Tupla con (ymax, xmax, ymin, xmin) como strings, None si no se pueden extraer
        """
        try:
            spatial_data = json.loads(spatial)
            if spatial_data.get("type") == "Polygon":
                coordinates = spatial_data["coordinates"][0]
                lats = [coord[1] for coord in coordinates]
                lons = [coord[0] for coord in coordinates]
                ymax = max(lats)
                ymin = min(lats)
                xmax = max(lons)
                xmin = min(lons)
                return str(ymax), str(xmax), str(ymin), str(xmin)
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
        return None, None, None, None
    
    def get_resource_bounds(self, package: Dict) -> Tuple[str, str, str, str]:
        """
        Obtiene las coordenadas de un paquete/dataset.
        
        Args:
            package: Diccionario con datos del paquete
            
        Returns:
            Tupla con (ymax, xmax, ymin, xmin) como strings
        """
        # Intentar extraer las coordenadas desde 'spatial'
        ymax_spatial, xmax_spatial, ymin_spatial, xmin_spatial = self.extract_bounds_from_spatial(
            package.get("spatial", "")
        )
        
        # Si no se pudo extraer desde 'spatial', usar valores por defecto
        ymax = self.config_manager.clean_coordinate(
            ymax_spatial if ymax_spatial else package.get("ymax"), "20"
        )
        xmax = self.config_manager.clean_coordinate(
            xmax_spatial if xmax_spatial else package.get("xmax"), "-13"
        )
        ymin = self.config_manager.clean_coordinate(
            ymin_spatial if ymin_spatial else package.get("ymin"), "-60"
        )
        xmin = self.config_manager.clean_coordinate(
            xmin_spatial if xmin_spatial else package.get("xmin"), "-108"
        )
        
        return ymax, xmax, ymin, xmin
    
    def get_resource_url(self, resource: Dict, package: Dict, user_context: Dict) -> str:
        """
        Obtiene la URL apropiada para un recurso considerando permisos y ubicación.

        Args:
            resource: Diccionario con datos del recurso
            package: Diccionario con datos del paquete
            user_context: Contexto del usuario

        Returns:
            URL del recurso
        """
        resource_url = resource.get("url") or ""

        is_private_dataset = package.get("private") is True
        is_logged_user = bool(user_context.get('user'))
        is_uploaded_resource = resource.get('url_type') == 'upload' or resource_url.startswith('/')

        # Recursos privados subidos: servirlos vía el proxy CKAN con token firmado.
        # Exponer la URL SAS de Azure directamente falla cross-origin si el Storage
        # Account no tiene CORS configurado para el dominio de Terria; el proxy
        # devuelve el archivo con CORS abierto y sin depender de esa configuración.
        if is_private_dataset and is_logged_user and is_uploaded_resource and resource.get('id'):
            try:
                # Preserve the original filename in the URL path so TerriaJS
                # client-side extension checks (e.g. shp requires .zip, geojson
                # requires .geojson) don't reject the proxy URL.
                proxy_filename = self._extract_upload_filename(resource, resource_url)
                return self.build_proxy_resource_url(
                    resource['id'], filename=proxy_filename or None
                )
            except Exception:
                # Proxy URL couldn't be built (e.g. missing site_url). Fall through
                # to the uploader-resolved SAS so we at least return something usable
                # even if it will hit the CORS limitation.
                pass

        if is_private_dataset and is_logged_user and is_uploaded_resource:
            try:
                upload = uploader.get_resource_uploader(resource)
                filename = self._extract_upload_filename(resource, resource_url)
                uploaded_url = upload.get_url_from_filename(
                    resource['id'],
                    filename or resource_url,
                    content_type=resource.get('mimetype')
                ) or resource_url
            except Exception:
                uploaded_url = resource_url
        else:
            uploaded_url = resource_url

        # Terria suele correr en otro dominio; las rutas relativas deben salir absolutas.
        return self._to_absolute_url(uploaded_url)

    def resolve_private_resource_source(self, resource_id: str) -> Optional[Tuple[str, Optional[str], Optional[str]]]:
        """
        Resolve the upstream SAS (or equivalent) URL for streaming a private resource.

        Runs with ``ignore_auth`` because the caller (the proxy endpoint) must
        already have validated the signed token before calling this.

        Returns:
            Tuple ``(url, content_type, filename)`` or None when the resource
            can't be resolved.
        """
        if not resource_id:
            return None

        # Build a self-sufficient sysadmin-equivalent context: ``resource_show``
        # may be invoked outside a request (auth already validated by token).
        try:
            import ckan.model as _model
            lookup_context = {
                'model': _model,
                'session': _model.Session,
                'user': 'ckan.system',
                'ignore_auth': True,
            }
        except Exception:
            lookup_context = {'ignore_auth': True}

        try:
            resource = toolkit.get_action('resource_show')(
                lookup_context, {'id': resource_id}
            )
        except Exception:
            return None

        raw_url = resource.get('url') or ''
        filename = self._extract_upload_filename(resource, raw_url)
        if not filename and raw_url:
            # Last-ditch basename in case upload URL is neither ``/download/`` nor
            # a clean path (e.g. already-SAS-style URL in ``resource.url``).
            filename = os.path.basename(urllib.parse.urlparse(raw_url).path or '')

        content_type = resource.get('mimetype')

        if resource.get('url_type') == 'upload' or raw_url.startswith('/'):
            # cloudstorage.get_url_from_filename expects a plain basename
            # (``foo.csv``) — passing a full URL here builds a broken SAS path.
            if not filename:
                return None
            try:
                upload = uploader.get_resource_uploader(resource)
                resolved = upload.get_url_from_filename(
                    resource['id'], filename, content_type=content_type
                )
                if resolved:
                    return resolved, content_type, filename
            except Exception:
                pass

        if raw_url:
            return self._to_absolute_url(raw_url), content_type, filename or None
        return None
    
    def decode_names_in_object(self, obj: Any) -> Any:
        """
        Decodifica nombres con caracteres especiales en objetos anidados.
        
        Args:
            obj: Objeto a procesar (dict, list, str, etc.)
            
        Returns:
            Objeto procesado con nombres decodificados
        """
        if isinstance(obj, dict):
            new_dict = {}
            for key, value in obj.items():
                # Decodificar el key si contiene '+'
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
                    
                    value = self.decode_names_in_object(value)
                elif isinstance(value, list):
                    value = [
                        urllib.parse.unquote_plus(item) if isinstance(item, str) else self.decode_names_in_object(item) 
                        for item in value
                    ]
                elif isinstance(value, str) and '+' in value:
                    value = urllib.parse.unquote_plus(value)
                    
                new_dict[new_key] = value
            return new_dict
        elif isinstance(obj, list):
            return [self.decode_names_in_object(item) for item in obj]
        return obj
    
    def process_custom_config_url(self, custom_config_url: str) -> Optional[Dict]:
        """
        Procesa una URL de configuración personalizada para extraer datos.
        
        Args:
            custom_config_url: URL con configuración personalizada
            
        Returns:
            Diccionario con datos de configuración parseados, None en caso de error
        """
        try:
            # Extract the 'start' or 'share' parameter from the URL
            parsed_url = urllib.parse.urlparse(custom_config_url)
            fragment = parsed_url.fragment
            
            if fragment.startswith('share='):
                # Caso de URL con #share
                gist_id = fragment.split('=g-')[1]
                gist_url = f'https://gist.githubusercontent.com/pabrojast/{gist_id}/raw/Terriajs-usercatalog.json'
                try:
                    with urllib.request.urlopen(gist_url) as response:
                        decoded_param = response.read().decode('utf-8')
                except Exception as e:
                    print(f"Error fetching gist config: {e}")
                    return None
            else:
                # Caso original con #start
                start_param = fragment.split('=', 1)[1]
                decoded_param = urllib.parse.unquote(start_param)
            
            # Parsear el JSON
            start_data = json.loads(decoded_param)
            
            # Decodificar nombres
            start_data = self.decode_names_in_object(start_data)
            
            return start_data
            
        except Exception as e:
            print(f"Error processing custom config: {e}")
            return None 
