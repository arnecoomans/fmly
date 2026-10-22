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


def set_person_region(content, data, request):
  """Where a person linked to this image is on it - a box or a point, as
  fractions of the image as shown (cmnsd RegionMixin) - or none ('clear').
  Only on an image, only for someone on it, only for who may change it."""
  require_can_edit(content, request)
  if not (content.file and content.media_type == 'image'):
    raise ValidationError(_("Only a photo or a scan has places to point out."))
  link = content.person_links.select_related('person').filter(person__token=data.get('person') or '').first()
  if link is None:
    raise ValidationError(_("That person isn't on this item."))
  if not data.get('clear') and link.role not in link.FRAME_ROLES:
    raise ValidationError(_("%(name)s is %(role)s here - to point them out, make them depicted.") % {'name': link.person, 'role': link.get_role_display()})
  if data.get('clear'):
    link.set_region(None)
    log_change(request, content, f"Frame of {link.person}: removed")
    messages.success(request, _("Frame removed."))
  else:
    try:
      box = tuple(float(data.get(key)) for key in ('region_x', 'region_y', 'region_w', 'region_h'))
    except (TypeError, ValueError):
      raise ValidationError(_("Point out where they are on the photo."))
    link.set_region(box)
    link.full_clean(exclude=['content', 'person', 'role'])
    log_change(request, content, f"Frame of {link.person}: {', '.join(f'{v:.4f}' for v in link.region)}")
    messages.success(request, _("%(name)s is pointed out.") % {'name': link.person})
  link.save(update_fields=['region_x', 'region_y', 'region_w', 'region_h'])
  return {'relation': 'people', 'object': link.person}


def attach_roles(content, people):
  """Each person's role on this item as person.content_role, and whether
  they're pointed out on it (person.has_frame) - one query."""
  from .models import ContentPerson
  links = {person_id: (role, x is not None) for person_id, role, x in content.person_links.values_list('person_id', 'role', 'region_x')}
  for person in people:
    person.content_role, framed = links.get(person.pk, ('', False))
    person.can_frame = person.content_role in ContentPerson.FRAME_ROLES   # in the picture, or not known yet
    person.has_frame = framed and person.can_frame
  return people
