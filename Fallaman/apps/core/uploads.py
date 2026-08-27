"""Validation des fichiers envoyés par les utilisateurs.

L'attribut HTML ``accept`` filtre côté navigateur uniquement : il ne protège de
rien. Sans contrôle serveur, un fichier ``.html`` ou ``.svg`` déposé en guise de
CV est ensuite servi depuis notre propre domaine — donc exécuté avec nos cookies.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile

#: Extensions d'images acceptées (avatars, photos d'annonce).
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif"})
IMAGE_CONTENT_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/webp", "image/gif"}
)

#: Un CV peut aussi être une photo du document.
DOCUMENT_EXTENSIONS = IMAGE_EXTENSIONS | {".pdf", ".doc", ".docx"}
DOCUMENT_CONTENT_TYPES = IMAGE_CONTENT_TYPES | {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def max_upload_size() -> int:
    return int(getattr(settings, "MAX_UPLOAD_SIZE", 5 * 1024 * 1024))


def max_listing_images() -> int:
    return int(getattr(settings, "MAX_LISTING_IMAGES", 5))


def _human_size(num_bytes: int) -> str:
    return f"{num_bytes / (1024 * 1024):.0f} Mo"


def validate_upload(uploaded, *, extensions, content_types, label="fichier"):
    """Valide taille, extension et type MIME déclaré. Renvoie le fichier."""
    if not uploaded:
        return uploaded
    # Champ inchangé : `cleaned_data` contient le FieldFile déjà stocké, qui a
    # été validé à son propre envoi. Le revalider ferait échouer la sauvegarde
    # d'un profil dont l'ancien fichier porte un nom inattendu.
    if not isinstance(uploaded, UploadedFile):
        return uploaded

    size = getattr(uploaded, "size", 0) or 0
    limit = max_upload_size()
    if size > limit:
        raise ValidationError(
            f"Ce {label} dépasse {_human_size(limit)}. Choisissez un fichier plus léger."
        )

    suffix = Path(getattr(uploaded, "name", "") or "").suffix.lower()
    if suffix not in extensions:
        allowed = ", ".join(sorted(e.lstrip(".") for e in extensions))
        raise ValidationError(f"Format de {label} non accepté. Formats autorisés : {allowed}.")

    declared = (getattr(uploaded, "content_type", "") or "").split(";")[0].strip().lower()
    if declared and declared not in content_types:
        raise ValidationError(f"Format de {label} non accepté ({declared}).")

    return uploaded


def validate_image(uploaded, label="image"):
    return validate_upload(
        uploaded,
        extensions=IMAGE_EXTENSIONS,
        content_types=IMAGE_CONTENT_TYPES,
        label=label,
    )


def validate_document(uploaded, label="document"):
    return validate_upload(
        uploaded,
        extensions=DOCUMENT_EXTENSIONS,
        content_types=DOCUMENT_CONTENT_TYPES,
        label=label,
    )
