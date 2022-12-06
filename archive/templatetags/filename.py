import os

from django import template


register = template.Library()

@register.filter
def filename(value):
    return os.path.basename(value.file.name)

@register.filter
def imagedimensions(value):
    from PIL import Image
    try:
        image = Image.open(value)
        width, height = image.size
        return str(width) + 'x' + str(height)
    except:
        return None
