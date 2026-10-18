from django import template

register = template.Library()


@register.filter
def mentioned_in(obj, request):
  """{% with rows=person|mentioned_in:request %} - the texts mentioning it
  that this viewer may see (cmnsd.models.Mention.mentioned_in, issue #470):
  [{'source', 'fields', 'kind'}]."""
  from cmnsd.models.Mention import mentioned_in as rows
  return rows(obj, request)


@register.filter
def mention_kind(obj):
  """{{ person|mention_kind }} -> 'person': the API name a mention of it uses."""
  from cmnsd.api.registry import API_REGISTRY
  return API_REGISTRY.get(type(obj), {}).get('name', obj._meta.model_name)


@register.filter
def content_type_id(obj):
  from django.contrib.contenttypes.models import ContentType
  return ContentType.objects.get_for_model(obj).pk


@register.filter
def may_unlink(source, request):
  """{% if source|may_unlink:request %} - may change that text's words."""
  from cmnsd.models.Mention import may_change_mentions
  return may_change_mentions(source, getattr(request, 'user', None))


@register.filter
def source_url(source):
  """Where a text is read: a person's page, a transcript's item, else its own page."""
  if hasattr(source, 'page_url'):
    return source.page_url()
  if hasattr(source, 'get_absolute_url'):
    return source.get_absolute_url()
  item = getattr(source, 'content', None)
  return item.get_absolute_url() if item is not None and hasattr(item, 'get_absolute_url') else ''


@register.filter
def verbose_kind(obj):
  """{{ source|verbose_kind }} -> 'comment', 'person': what kind of thing it is."""
  return obj._meta.verbose_name


@register.filter
def reach_label(obj):
  """'' for what everyone signed in may see, else a word for who may:
  "family only", "private", "draft" (cmnsd mention_reach) - a picker's
  pill: choosing it links something not every reader sees."""
  from cmnsd.models.Mention import mention_reach
  return mention_reach(obj)[2]
