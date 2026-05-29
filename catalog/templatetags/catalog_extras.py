from functools import lru_cache

from django import template
from django.contrib.staticfiles import finders
from PIL import Image


register = template.Library()


@register.filter
def split_lines(value):
    return [line.strip() for line in str(value).splitlines() if line.strip()]


@register.simple_tag
def image_size(image):
    if not image:
        return None
    try:
        return (image.width, image.height)
    except (OSError, ValueError):
        return None


@lru_cache(maxsize=128)
def _static_image_size(path):
    resolved_path = finders.find(path)
    if not resolved_path:
        return None
    try:
        with Image.open(resolved_path) as image:
            return image.size
    except (OSError, ValueError):
        return None


@register.simple_tag
def static_image_size(path):
    return _static_image_size(path)
