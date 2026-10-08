"""
Tags with how many content items each holds for this viewer - shown on
every tag chip: the tags overview (/tags/), a tag page's child tags, and
the tags on an item's or a person's page.

The count is what the tag's own page shows (TagDetailView): content the
viewer may see, wholes only, an item counted once - also when it's there
because one of its parts carries the tag. Two queries for any number of
tags, not one per tag.
"""

from collections import defaultdict

from cmnsd.models.access import filter_accessible

from .models import Tag


def attach_content_counts(tags, request):
  """Set tag.content_count on each of `tags` (a list); returns the list."""
  from content.models import Content
  tags = list(tags)
  ids = [tag.pk for tag in tags]
  wholes = Content.objects.visible_to(request).listable()
  items = defaultdict(set)
  for tag_id, content_id in wholes.filter(tags__in=ids).values_list('tags', 'pk'):
    items[tag_id].add(content_id)
  for tag_id, content_id in wholes.filter(parts__tags__in=ids).values_list('parts__tags', 'pk'):
    items[tag_id].add(content_id)
  for tag in tags:
    tag.content_count = len(items[tag.pk])
  return tags


def by_count(tags):
  """Most content first, then by name - for a short row of chips (an
  item's, a person's, a tag's children): the important tags lead. Not in
  Tag.Meta.ordering: the count depends on the viewer. The tags overview
  stays alphabetical - it's long, you scan it for a name."""
  return sorted(tags, key=lambda tag: (-tag.content_count, tag.name.casefold()))


def _by_name(tag):
  return tag.name.casefold()


def tag_overview(request):
  """The tags this viewer may see that hold content, for /tags/:
  (groups, loose). groups: root tags with children - e.g. "Collection" -
  each with .listed_children (the non-empty ones); loose: the other root
  tags. A tag with nothing in it for this viewer is left out, and a
  group with no non-empty children unless it holds content itself. One
  level of children; deeper levels are on the tag's own page."""
  tags = attach_content_counts(filter_accessible(Tag.objects.all(), request), request)
  children = defaultdict(list)
  for tag in tags:
    if tag.parent_id and tag.content_count:
      children[tag.parent_id].append(tag)
  groups, loose = [], []
  for tag in tags:
    if tag.parent_id:
      continue
    if children[tag.pk]:
      tag.listed_children = sorted(children[tag.pk], key=_by_name)
      groups.append(tag)
    elif tag.content_count:
      loose.append(tag)
  return sorted(groups, key=_by_name), sorted(loose, key=_by_name)


# The tag that marks something to come back to (made by manage.py
# prepare_release) - the
# dashboard lists what carries it under loose ends.
LOOSE_END_SLUG = 'loose-end'


def loose_end_tag():
  return Tag.objects.filter(slug=LOOSE_END_SLUG, parent=None).first()


def descendant_tokens(tag):
  """The tokens of every tag below `tag`, any depth - one query per level
  (a tag's parent picker doesn't offer them: that would make a loop)."""
  tokens, level = [], [tag.pk]
  while level:
    rows = list(Tag.objects.filter(parent__in=level).values_list('pk', 'token'))
    tokens += [token for _pk, token in rows]
    level = [pk for pk, _token in rows]
  return tokens
