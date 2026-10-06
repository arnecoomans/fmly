"""
Tag names and places decided after the first import - applied by the
importers, so a re-import keeps them (import_content_tags for archive_tag
rows, import_content.Command.tag() for tags made from groups, attachment
links and book collections).

Collections - a curated set of items (an archive series, a bookshelf) -
are children of one root tag, "Collection". Colorization groups - a
legacy group of an original photo and its colorized version, marked with
the legacy tag "ingekleurd" - are children of "Colorization". Legacy tags
are matched by their legacy slug, which a rename keeps: the tag is still
found on the next run.
"""

from django.utils.text import slugify

from core.models import Tag

COLLECTION_TAG_NAME = 'Collection'
COLORIZATION_TAG_NAME = 'Colorization'
# The legacy tag that marks a group as a colorization group.
COLORIZATION_MARKER_SLUG = 'ingekleurd'

# Every imported tag: published, for signed-in members (visibility
# community). Applied on every run, also to tags that already exist.
IMPORTED_TAG_ACCESS = {'status': 'p', 'visibility': 'c'}

# legacy slug -> name
RENAMED_TAGS = {
  'paspoort': 'Archief Paspoortaanvragen',
}

# Legacy slugs of tags that are collections. Book collections
# (archive_collection) always are - import_content passes collection=True.
COLLECTION_SLUGS = {
  'paspoort',                                       # archive_tag
  'stamboeken-ambtenaren-en-gouvernementsmarine',   # archive_tag
  'krangan-81',                                     # archive_group
}


def root_tag(name):
  """A root tag by name ("Collection", "Colorization") - created on first use."""
  tag = Tag.objects.filter(slug=slugify(name), parent__isnull=True).first()
  if tag is None:
    tag = Tag.objects.create(name=name, user_id=1, **IMPORTED_TAG_ACCESS)
  return ensure_access(tag)


def ensure_access(tag):
  """Published, visibility community (IMPORTED_TAG_ACCESS) - saved only
  when it differs."""
  if any(getattr(tag, field) != value for field, value in IMPORTED_TAG_ACCESS.items()):
    for field, value in IMPORTED_TAG_ACCESS.items():
      setattr(tag, field, value)
    tag.save()
  return tag


def collection_tag():
  return root_tag(COLLECTION_TAG_NAME)


def tag_layout(slug, name, collection=False, colorization=False, defer_parent=False):
  """(name, parent) for a legacy tag: renamed if decided; under
  "Collection" if it's a collection, under "Colorization" if it's a
  colorization group; otherwise (name, None) - root. defer_parent: the
  name only (parent None), without creating a root tag - for a caller that
  sets the parents once its own rows are in."""
  if defer_parent:
    parent = None
  elif collection or slug in COLLECTION_SLUGS:
    parent = collection_tag()
  elif colorization:
    parent = root_tag(COLORIZATION_TAG_NAME)
  else:
    parent = None
  return RENAMED_TAGS.get(slug, name), parent
