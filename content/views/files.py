from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET
from django_sendfile import sendfile
from sorl.thumbnail import get_thumbnail

from cmnsd.models.access import filter_accessible
from people.models import Person

from ..crop import sorl_cropbox
from ..models import Content, Portrait

# Named sizes, so a URL can't make the server render arbitrary variants.
# Values are sorl get_thumbnail() arguments: geometry plus options.
DEFAULT_THUMBNAIL_PRESETS = {
  'card': {'geometry': '480x360', 'crop': 'center'},
  'avatar': {'geometry': '160x160', 'crop': 'center'},
  # The detail page's view of an image: fit within the box, never upscaled.
  'large': {'geometry': '1600x1600', 'upscale': False},
  # Zooming in on a scan too large for a browser to hold whole (the
  # lightbox, Content.zoom_url): fine detail, bounded memory.
  'xlarge': {'geometry': '6000x6000', 'upscale': False},
}
# The presets an item's own thumbnail crop applies to (Content.thumb_crop_*):
# the lists' thumbnails, not the large view of the item itself.
CROPPED_PRESETS = {'card', 'avatar'}


def thumbnail_presets():
  return getattr(settings, 'CONTENT_THUMBNAIL_PRESETS', DEFAULT_THUMBNAIL_PRESETS)


def _visible_content(request, token):
  """The content, if this viewer may open it - status and visibility first
  (Content.objects.viewable_by: for staff also a deleted item, whose page
  they may open). Hidden and nonexistent both 404, so a response says
  nothing about whether a token exists."""
  return get_object_or_404(Content.objects.viewable_by(request), token=token)


def _stored_path(file):
  if not file or not file.storage.exists(file.name):
    raise Http404("No file.")
  return file.storage.path(file.name)


@require_GET
def content_file(request, token):
  """content/<token>/file/ - the original, served inline via sendfile.
  Files live in private/content/<year>/ (MEDIA_ROOT = SENDFILE_ROOT =
  private/), which the web server never serves directly - see
  docs/FMLY-3.0-PLAN.md, Content, "Storage and serving"."""
  content = _visible_content(request, token)
  return sendfile(request, _stored_path(content.file), attachment=False)


@require_GET
def content_thumbnail(request, token, preset):
  """content/<token>/thumb/<preset>/ - a sorl thumbnail of an image, in a
  named size. sorl writes its cache to the default storage, i.e.
  private/cache/, so thumbnails are as protected as originals.
  Non-images have no thumbnail (yet) and 404. 'card' and 'avatar' use the
  item's own crop and turn when it has one (Content.thumb_crop_*,
  content/crop.py); ?v= in the URL (content_tags.thumb_url) changes with it."""
  options = thumbnail_presets().get(preset)
  if options is None:
    raise Http404("Unknown thumbnail size.")
  content = _visible_content(request, token)
  if content.media_type != 'image':
    raise Http404("No thumbnail for this kind of file.")
  path = _stored_path(content.file)
  options = dict(options)
  if preset in CROPPED_PRESETS:
    cropbox = sorl_cropbox(content.thumb_crop_box, path, content.thumb_rotation)
    if cropbox:
      options['cropbox'] = cropbox
    if content.thumb_rotation:
      options['rotate'] = content.thumb_rotation   # turned last (content/thumbnail_engine.py)
      if content.thumb_rotation in (90, 270):
        # Cut and sized upright, then turned: a 4:3 card is 3:4 before the turn.
        width, height = options['geometry'].split('x')
        options['geometry'] = f'{height}x{width}'
  thumbnail = get_thumbnail(content.file, options.pop('geometry'), **options)
  # sorl swallows generation errors (THUMBNAIL_DEBUG off) and returns a
  # thumbnail it never wrote - 404 rather than a sendfile error.
  return sendfile(request, _stored_path(thumbnail), attachment=False)


@require_GET
def portrait_thumbnail(request, token, person_token):
  """content/<token>/portrait/<person token>/ - a person's avatar: this
  photo, cropped to that person's stored crop (content.Portrait), in the
  'avatar' preset size. Per person, not per photo: one group photo can be
  the portrait of several people, each cropped differently. Requires that
  the viewer may see both the photo and the person. No stored crop = the
  preset's center crop."""
  content = _visible_content(request, token)
  person = get_object_or_404(filter_accessible(Person.objects.all(), request), token=person_token)
  link = get_object_or_404(Portrait, person=person, content=content)
  if content.media_type != 'image':
    raise Http404("No thumbnail for this kind of file.")
  path = _stored_path(content.file)
  options = dict(thumbnail_presets()['avatar'])
  cropbox = sorl_cropbox(link.crop_box, path, link.rotation)
  if cropbox:
    options['cropbox'] = cropbox
  if link.rotation:
    options['rotate'] = link.rotation   # turned last (content/thumbnail_engine.py)
  thumbnail = get_thumbnail(content.file, options.pop('geometry'), **options)
  return sendfile(request, _stored_path(thumbnail), attachment=False)
