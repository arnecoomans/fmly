"""
Roles of people on an item (ContentPerson, issue #471): set one on the
item's page (edit mode), each person's role menu.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _, ngettext

from cmnsd.edit.log import log_change
from cmnsd.edit.mode import require_can_edit


def set_person_role(content, token, role, request):
  """That person's role on this item - '' for none. Only for a person
  linked to it, and a role the item offers (Content.person_roles)."""
  require_can_edit(content, request)
  link = content.person_links.select_related('person').filter(person__token=token or '').first()
  if link is None:
    raise ValidationError(_("That person isn't on this item."))
  role = role or ''
  if role and role not in dict(content.person_roles()):
    raise ValidationError(_("That role doesn't fit this item."))
  if link.role != role:
    link.role = role
    link.save(update_fields=['role'])
    log_change(request, content, f"Role of {link.person}: {link.get_role_display() or '-'}")
    messages.success(request, _("Role saved."))
  return {'relation': 'people', 'object': link.person}


# The role an item's kind suggests (issue #471): a posed portrait is of
# someone; a candid or group photo shows who was there; a record is of the
# person it's about. Kinds that vary - a newspaper, a personal paper, a photo
# not classified - suggest nothing. (kind, its photo or document kind) -> role.
SUGGESTED_ROLES = {
  ('photo', 'portrait'): 'subject',
  ('photo', 'group'): 'depicted',
  ('photo', 'candid'): 'depicted',
  ('photo', 'historical'): 'depicted',
  ('document', 'identity'): 'subject',
  ('document', 'civil_record'): 'subject',
  ('document', 'service_record'): 'subject',
  ('document', 'war_record'): 'subject',
}


def suggested_role(content):
  """SUGGESTED_ROLES for this item - '' when its kind says nothing."""
  from django.core.exceptions import ObjectDoesNotExist
  try:
    if content.kind == 'photo':
      sub = content.photo_detail.photo_kind
    elif content.kind == 'document':
      sub = content.document_detail.document_kind
    else:
      return ''
  except ObjectDoesNotExist:
    return ''
  return SUGGESTED_ROLES.get((content.kind, sub), '')


def apply_suggested_roles(content, request):
  """The suggested role for everyone on it without one - only people this
  viewer may see. Returns how many."""
  from cmnsd.models.access import filter_accessible
  from people.models import Person
  require_can_edit(content, request)
  role = suggested_role(content)
  if not role:
    raise ValidationError(_("This item's kind suggests no role - choose one per person."))
  links = content.person_links.filter(role='', person__in=filter_accessible(Person.objects.all(), request)).select_related('person')
  names = [str(link.person) for link in links]
  count = links.update(role=role)
  if count:
    label = dict(content.person_roles())[role]
    log_change(request, content, f"Role of {', '.join(names)}: {label}")
    messages.success(request, ngettext("%(count)s person is now %(role)s.", "%(count)s people are now %(role)s.", count) % {'count': count, 'role': label})
  return count


def attach_roles(content, people):
  """Each person's role on this item as person.content_role - one query."""
  roles = dict(content.person_links.values_list('person_id', 'role'))
  for person in people:
    person.content_role = roles.get(person.pk, '')
  return people
