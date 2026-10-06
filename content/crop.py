"""
Turning a stored crop (fractions 0-1 of the image as displayed) into
sorl's `cropbox` option (pixels of the file as stored).

Two things differ between those: size (fractions vs pixels) and
orientation. A portrait may also be turned (Portrait.rotation): its crop is
taken on the turned photo, so it's first mapped back to the upright one. A photo stored sideways with an EXIF "rotate" tag is shown
upright, and a crop is chosen on the upright image - but sorl applies
`cropbox` BEFORE it applies the EXIF orientation (EngineBase.create), so
the rectangle is mapped back to the stored orientation here first.
"""

from PIL import Image

EXIF_ORIENTATION = 0x0112

# Displayed (u, v) -> stored (a, b), per EXIF orientation, all as
# fractions. The inverse of how each orientation turns the stored image
# into the displayed one (2/4 mirror, 3 rotate 180, 5/7 transpose/
# transverse, 6/8 rotate 90 clockwise / counter-clockwise).
_TO_STORED = {
  1: lambda u, v: (u, v),
  2: lambda u, v: (1 - u, v),
  3: lambda u, v: (1 - u, 1 - v),
  4: lambda u, v: (u, 1 - v),
  5: lambda u, v: (v, u),
  6: lambda u, v: (v, 1 - u),
  7: lambda u, v: (1 - v, 1 - u),
  8: lambda u, v: (1 - v, u),
}


# Turned (clockwise by `rotation`) (u, v) -> upright (x, y), all fractions:
# the inverse of turning the upright image for a portrait (Portrait.rotation).
_FROM_TURNED = {
  0: lambda u, v: (u, v),
  90: lambda u, v: (v, 1 - u),
  180: lambda u, v: (1 - u, 1 - v),
  270: lambda u, v: (1 - v, u),
}


def upright_box(crop_box, rotation):
  """A crop chosen on the photo turned by `rotation` (clockwise) -> the
  same region on the upright photo, (x, y, w, h) fractions."""
  if not rotation:
    return crop_box
  x, y, w, h = crop_box
  to_upright = _FROM_TURNED[rotation]
  corners = [to_upright(x, y), to_upright(x + w, y + h)]
  xs, ys = [c[0] for c in corners], [c[1] for c in corners]
  return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)


def stored_rectangle(crop_box, orientation):
  """(x, y, w, h) displayed fractions -> (x1, y1, x2, y2) stored fractions."""
  x, y, w, h = crop_box
  to_stored = _TO_STORED.get(orientation, _TO_STORED[1])
  corners = [to_stored(x, y), to_stored(x + w, y + h)]
  xs, ys = [c[0] for c in corners], [c[1] for c in corners]
  return min(xs), min(ys), max(xs), max(ys)


def image_geometry(path):
  """(width, height, orientation) of the stored file - header only, no
  pixel decode, so this is cheap even for a 250 MP scan."""
  with Image.open(path) as image:
    orientation = image.getexif().get(EXIF_ORIENTATION, 1)
    return image.size[0], image.size[1], orientation


def displayed_size(path):
  """(width, height) as the image is shown: the stored size, swapped for
  an EXIF orientation that turns it a quarter (5-8)."""
  width, height, orientation = image_geometry(path)
  return (height, width) if orientation in (5, 6, 7, 8) else (width, height)


def sorl_cropbox(crop_box, path, rotation=0):
  """sorl's cropbox string ("x1,y1,x2,y2" in stored pixels) for a crop
  chosen on the displayed image - turned by `rotation` first, for a
  portrait - or None for no crop. The cut region is upright; the thumbnail
  engine turns it (option `rotate`)."""
  if crop_box is None:
    return None
  width, height, orientation = image_geometry(path)
  x1, y1, x2, y2 = stored_rectangle(upright_box(crop_box, rotation), orientation)
  return f"{round(x1 * width)},{round(y1 * height)},{round(x2 * width)},{round(y2 * height)}"
