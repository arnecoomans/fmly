from django import template

register = template.Library()


@register.filter
def visible_tags(person, request):
  """{{ person|visible_tags:request }} - a bare {{ person.get_tags }}
  would call it with request=None (its default), same reason
  relation_to_user exists for get_relation_to_user(). With each tag's
  content count (core/tags.py), shown on the chip - most content first."""
  from core.tags import attach_content_counts, by_count
  return by_count(attach_content_counts(person.get_tags(request), request))


# Person page sections (SectionShorthand) - each needs the viewer, and a
# bare {{ person.method }} would call it without a request.

@register.filter
def visible_content(person, request):
  return person.get_visible_content(request)


@register.filter
def visible_events(person, request):
  return person.get_visible_events(request)


@register.filter
def relationship_count(person, request):
  return person.count_relationships(request)


@register.filter
def content_count(person, request):
  return person.count_visible_content(request)


@register.filter
def event_count(person, request):
  return person.count_visible_events(request)


@register.filter
def comment_count(person, request):
  return person.count_comments(request)


@register.filter
def content_sort(person, request):
  return person.content_sort(request)


@register.filter
def kind_counts(items):
  """[(kind, label, count), ...] for the kinds present in a content list,
  in Content.Kind order - the filter pills."""
  from collections import Counter
  from content.models import Content
  counts = Counter(item.kind for item in items)
  return [(kind, label, counts[kind]) for kind, label in Content.Kind.choices if counts[kind]]


@register.filter
def for_row(person):
  """{% with person=person|for_row %} - one person ready for
  people/_person_row.html on its own (lifespan + portrait attached, as a
  list's for_list() does for many) - e.g. the row an edit-mode action
  returns."""
  return person._attach_portraits(person._attach_lifespan([person]))[0]


@register.filter
def life_timeline(person, request):
  """{% for entry in person|life_timeline:request %} - the person's own
  events and their close family's, by date (people/timeline.py)."""
  from people.timeline import life_timeline as timeline
  return timeline(person, request)


@register.filter
def person_url(person, request):
  """{{ person|person_url:request }} - the person's page for this viewer,
  or '' when they may not open it: a private person, for anyone but
  themself, their parents and staff (people/privacy.py). Their name then shows
  without a link."""
  return person.page_url_for(getattr(request, 'user', None)) or ''


@register.filter
def age_at_death(person):
  """{{ person|age_at_death }} -> 'aged 72' / 'about 72' / '' - for the
  death row, by the timeline's rule (people/timeline.py age_at()): no age
  when either date is 'before'/'after' or a year is missing."""
  from people.timeline import age_at
  death = person.death
  return age_at(person.birth, death) if death else ''


@register.filter
def star_sign(person, request):
  """{% with sign=person|star_sign:request %} - Person.get_star_sign() with
  this viewer: a bare {{ person.get_star_sign }} would call it without a
  request (as relation_to_user)."""
  return person.get_star_sign(request)
