"""
Favorites (core.models.Favorite, issue #453): public and social - what
stands out in the archive. Counted for every card in a list in one query,
named on an item's page for who's signed in, and two lists: the family's
favorites (the dashboard) and your own (content/favorites/). Each only
what this viewer may see - a favorite on an item that's since been hidden
or deleted drops out with it.
"""

from collections import Counter

from django.contrib.contenttypes.models import ContentType

from .models import Favorite


def counts(objects):
  """{pk: number of favorites} for `objects` (one model), in one query."""
  objects = list(objects)
  if not objects:
    return {}
  rows = Favorite.objects.filter(
    target_content_type=ContentType.objects.get_for_model(objects[0]),
    target_id__in=[obj.pk for obj in objects],
  ).order_by().values_list('target_id', flat=True)
  return Counter(rows)


def attach(items, request):
  """Set item.favorite_count and item.is_favorite (this viewer's) on each of
  `items` (a list, one model) - the heart on a card. One query."""
  items = list(items)
  if not items:
    return items
  user = getattr(request, 'user', None)
  rows = Favorite.objects.filter(
    target_content_type=ContentType.objects.get_for_model(items[0]),
    target_id__in=[item.pk for item in items],
  ).order_by().values_list('target_id', 'user_id')
  number, mine = Counter(), set()
  for target_id, user_id in rows:
    number[target_id] += 1
    if user is not None and user_id == user.pk:
      mine.add(target_id)
  for item in items:
    item.favorite_count = number[item.pk]
    item.is_favorite = item.pk in mine
  return items


def heart(obj, request):
  """What the heart on an object's page shows: {count, mine, names} - the
  names (by account, oldest favorite first) only for who's signed in."""
  user = getattr(request, 'user', None)
  signed_in = bool(user and user.is_authenticated)
  favorites = list(obj.favorites.select_related('user__person').order_by('date_created'))
  from .preferences import account_name
  return {
    'count': len(favorites),
    'mine': signed_in and any(f.user_id == user.pk for f in favorites),
    'names': [account_name(f.user) for f in favorites] if signed_in else [],
  }


def family_favorites(request, count=10):
  """The published items (wholes) this viewer may see with the most
  favorites - at least one; ties: the most recently favorited first."""
  from django.db.models import Count, Max
  from content.models import Content
  return list(
    Content.objects.visible_to(request).listable().filter(status=Content.Status.PUBLISHED)
    .annotate(favorite_count=Count('favorites', distinct=True), last_favorite=Max('favorites__date_created'))
    .filter(favorite_count__gt=0)
    .select_related('photo_detail', 'document_detail')
    .order_by('-favorite_count', '-last_favorite')[:count]
  )


def my_favorites(request):
  """The items (wholes) this viewer favorited and may still see, the most
  recently favorited first."""
  from django.db.models import Max
  from content.models import Content
  return list(
    Content.objects.visible_to(request).listable().filter(favorites__user=request.user)
    .annotate(favorited=Max('favorites__date_created'))
    .select_related('photo_detail', 'document_detail', 'book_detail')
    .order_by('-favorited')
  )
