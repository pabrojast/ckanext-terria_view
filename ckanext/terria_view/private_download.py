# encoding: utf-8
"""
Helpers for generating and validating short-lived tokens for private resource downloads.
"""
from typing import Optional, Tuple

from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from ckan.common import config


DEFAULT_TTL_SECONDS = 3600
TOKEN_SALT = "terria-view-private-download"


def _get_secret() -> Optional[str]:
    secret = (
        config.get("ckanext.terria_view.private_download_secret")
        or config.get("beaker.session.secret")
        or config.get("app_instance_uuid")
        or config.get("SECRET_KEY")
    )
    return secret


def _get_ttl_seconds() -> int:
    value = config.get("ckanext.terria_view.private_download_token_ttl", DEFAULT_TTL_SECONDS)
    try:
        return int(value)
    except (TypeError, ValueError):
        return DEFAULT_TTL_SECONDS


def _get_serializer() -> Optional[URLSafeTimedSerializer]:
    secret = _get_secret()
    if not secret:
        return None
    return URLSafeTimedSerializer(secret, salt=TOKEN_SALT)


def generate_token(resource_id: str, user: Optional[str] = None) -> Optional[str]:
    serializer = _get_serializer()
    if not serializer:
        return None
    payload = {"resource_id": resource_id}
    if user:
        payload["user"] = user
    return serializer.dumps(payload)


def validate_token(token: str, resource_id: str) -> Tuple[bool, Optional[str]]:
    serializer = _get_serializer()
    if not serializer:
        return False, "Private download token is not configured."

    ttl_seconds = _get_ttl_seconds()
    try:
        payload = serializer.loads(token, max_age=ttl_seconds)
    except SignatureExpired:
        return False, "Private download token expired."
    except BadSignature:
        return False, "Invalid private download token."

    if payload.get("resource_id") != resource_id:
        return False, "Private download token does not match resource."

    return True, None
