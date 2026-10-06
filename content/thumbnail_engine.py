"""
sorl-thumbnail engine for content (THUMBNAIL_ENGINE in settings).

The stock PIL engine decodes the whole image before scaling it down. The
archive holds scans of old photos up to ~260 megapixels (18000 x 14000 at
2400 DPI): a full decode of one costs ~780 MB of memory, just to make a
160px avatar. JPEG supports decoding at 1/2, 1/4 or 1/8 of its size
("draft mode", Pillow Image.draft), which is far cheaper - so this engine
asks for the smallest draft that is still at least as large as the
thumbnail, before any processing happens.

Option `rotate` (degrees clockwise, a portrait's rotation): the finished
thumbnail is turned last.

Not with a cropbox: draft mode shrinks the decoded image, so cropbox pixel
coordinates would no longer match. (Portrait crops, when applied, go
through sorl's own `cropbox` option - see docs/issues.md.)
"""

from sorl.thumbnail.engines.pil_engine import Engine as PILEngine


class Engine(PILEngine):
  def create(self, image, geometry, options):
    width, height = geometry
    if not options.get('cropbox') and (width or height):
      # draft() only affects formats that support it (JPEG); a no-op for
      # others. The result is never smaller than the requested size.
      image.draft('RGB', (width or height, height or width))
    image = super().create(image, geometry, options)
    # A portrait turned clockwise (Portrait.rotation, content/crop.py): the
    # cropped, upright result is turned last - a square stays square.
    rotate = int(options.get('rotate') or 0)
    if rotate:
      image = image.rotate(-rotate, expand=True)
    return image
