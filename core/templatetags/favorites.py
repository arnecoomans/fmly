from django import template

register = template.Library()


@register.filter
def heart(obj, request):
  """{% include 'favorite/heart.html' with heart=obj|heart:request %} - the
  count, whether it's yours and who (core.favorites.heart)."""
  from core.favorites import heart as get_heart
  return get_heart(obj, request)
