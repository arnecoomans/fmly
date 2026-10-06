"""
Private people (Person.private): part of the tree - their name shows in
family lists, events, on photos - but their page opens only for the person
themself (their linked account), their parents' accounts and staff. For
everyone else the name is not a link, and the address answers "not found".

Person.get_absolute_url() stays empty for a private person - the safe
default wherever nobody asks who's looking (the admin's "view on site");
Person.page_url_for(user) and the person_url filter decide per viewer.
"""

ATTRIBUTE = '_private_pages_open'


def private_pages_open_to(user):
  """{person pk} - the private people whose page this user may open: their
  own person and that person's children. Once per user object (a request)."""
  if not (user and user.is_authenticated):
    return set()
  cached = getattr(user, ATTRIBUTE, None)
  if cached is None:
    from .models import PersonRelation
    person = getattr(user, 'person', None)
    cached = set()
    if person is not None:
      cached.add(person.pk)
      cached.update(PersonRelation.objects.filter(
        person_from=person, relation_type=PersonRelation.RelationType.PARENT,
      ).values_list('person_to', flat=True))
    setattr(user, ATTRIBUTE, cached)
  return cached


def opens_every_private_page(user):
  """Staff: every private person's page."""
  return bool(user and user.is_authenticated and user.is_staff)


def may_open_page(person, user):
  """Whether this user may open the person's page as far as `private` goes
  (status and visibility are checked as for anyone else)."""
  return not person.private or opens_every_private_page(user) or person.pk in private_pages_open_to(user)
