from pathlib import Path

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


MAX_IMAGE_UPLOAD_SIZE = 8 * 1024 * 1024
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def validate_uploaded_image(uploaded_file):
    if not uploaded_file or not hasattr(uploaded_file, "size"):
        return

    try:
        file_size = uploaded_file.size
    except (OSError, ValueError):
        return

    if file_size > MAX_IMAGE_UPLOAD_SIZE:
        raise ValidationError(_("L'immagine non puo superare 8 MB."))

    extension = Path(uploaded_file.name).suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(_("Formato immagine non supportato. Usa JPG, PNG o WebP."))

    content_type = getattr(uploaded_file, "content_type", "")
    if content_type and content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise ValidationError(_("Il tipo di file caricato non e un'immagine valida."))
