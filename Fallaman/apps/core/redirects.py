"""Validation des cibles de redirection fournies par l'utilisateur.

Un simple ``url.startswith("/")`` ne suffit pas : ``//evil.tld`` commence par
« / » et le navigateur y voit une URL protocole-relative vers un autre domaine.
"""

from __future__ import annotations

from django.utils.http import url_has_allowed_host_and_scheme


def is_safe_target(url: str, request=None) -> bool:
    """Vrai si ``url`` pointe vers ce site (chemin relatif ou hôte autorisé)."""
    if not url:
        return False
    allowed_hosts = {request.get_host()} if request is not None else set()
    return url_has_allowed_host_and_scheme(
        url=url,
        allowed_hosts=allowed_hosts,
        require_https=bool(request and request.is_secure()),
    )


def safe_redirect_target(url: str, fallback: str, request=None) -> str:
    """Renvoie ``url`` si elle est sûre, sinon ``fallback``."""
    return url if is_safe_target(url, request=request) else fallback
