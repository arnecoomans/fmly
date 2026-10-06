"""
Helpers for the preferences page (core.views.PreferencesView): how an
account is named, and which accounts belong to your relatives in the tree.
"""


def account_name(user):
  """An account by its person's name when linked, else its full name or username."""
  person = getattr(user, 'person', None)
  if person is not None:
    return person.get_full_name()
  return user.get_full_name() or user.username


def accounts_in_tree(user):
  """{user pk} - accounts linked to your parents, children, siblings and
  partners in the family tree (your own person's close family) - partners
  also when only implied: your children's other parent."""
  person = getattr(user, 'person', None) if user and user.is_authenticated else None
  if person is None:
    return set()
  siblings = [row['person'] for row in person.get_siblings()]   # rows: {person, is_half, shared_parent}
  children = person._get_children_flat()
  co_parents = [parent for child in children for parent in child._get_parents_flat() if parent.pk != person.pk]
  relatives = [*person._get_parents_flat(), *children, *siblings, *person.get_partners(), *co_parents]
  return {relative.related_user_id for relative in relatives if relative.related_user_id and relative.related_user_id != user.pk}
