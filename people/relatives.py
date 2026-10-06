"""
Editing a person's family on their page (edit mode): parents, partners and
children - the logic behind Person's add_relative / remove_relative
actions (people/models/RelativesEditing.py). Siblings aren't edited: they
follow from shared parents.

Stored as PersonRelation rows: "A parent of B" is (person_from=A,
person_to=B, parent); a partnership is one row, A-B in pk order
(PersonRelation.save). A child of X is stored as X parent of the child.

Rules: the other person must be one the editor may see; not the person
themselves; no link twice; at most two parents; nobody becomes their own
ancestor. Needs the change permission on the person (require_can_edit);
each change goes to both people's admin history.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.translation import gettext as _

from cmnsd.edit.log import log_change
from cmnsd.edit.mode import require_can_edit
from cmnsd.models.access import filter_accessible

from .models.PersonRelations import PersonRelation

PARENT, PARTNER, CHILD = 'parent', 'partner', 'child'
KINDS = (PARENT, PARTNER, CHILD)
MAX_PARENTS = 2


def _other(person, request, token):
  other = filter_accessible(type(person).objects.all(), request).filter(token=token or '').first()
  if other is None:
    raise ValidationError(_("That person wasn't found."))
  if other.pk == person.pk:
    raise ValidationError(_("Someone can't be related to themselves."))
  return other


def _kind(kind):
  if kind not in KINDS:
    raise ValidationError(_("That can't be changed here."))
  return kind


def _relation(person, kind, other):
  """The PersonRelation row for "other is <kind> of person" - a queryset,
  empty when there's none."""
  R = PersonRelation.RelationType
  if kind == PARENT:
    return PersonRelation.objects.filter(person_from=other, person_to=person, relation_type=R.PARENT)
  if kind == CHILD:
    return PersonRelation.objects.filter(person_from=person, person_to=other, relation_type=R.PARENT)
  return PersonRelation.objects.filter(
    Q(person_from=person, person_to=other) | Q(person_from=other, person_to=person), relation_type=R.PARTNER,
  )


def ancestor_ids(person):
  """The pks of everyone above `person` (parents, their parents, ...) - one
  query per generation."""
  found, level = set(), {person.pk}
  while level:
    level = set(PersonRelation.objects.filter(
      person_to__in=level, relation_type=PersonRelation.RelationType.PARENT,
    ).values_list('person_from', flat=True)) - found
    found |= level
  return found


def _name(person, request):
  display = getattr(person, 'api_display', None)
  return display(request) if display else str(person)


def add_relative(person, kind, token, request):
  """Link another person as parent, partner or child of `person`."""
  require_can_edit(person, request)
  kind = _kind(kind)
  other = _other(person, request, token)
  if _relation(person, kind, other).exists():
    raise ValidationError(_("%(name)s is already linked.") % {'name': _name(other, request)})
  R = PersonRelation.RelationType
  if kind in (PARENT, CHILD):
    parent, child = (other, person) if kind == PARENT else (person, other)
    if PersonRelation.objects.filter(person_to=child, relation_type=R.PARENT).count() >= MAX_PARENTS:
      raise ValidationError(_("%(name)s already has two parents.") % {'name': _name(child, request)})
    if child.pk in ancestor_ids(parent) or _relation(person, PARTNER, other).exists():
      raise ValidationError(_("That would make someone their own ancestor."))
    PersonRelation.objects.create(person_from=parent, person_to=child, relation_type=R.PARENT)
  else:
    if other.pk in ancestor_ids(person) or person.pk in ancestor_ids(other):
      raise ValidationError(_("A parent or child can't also be a partner."))
    PersonRelation.objects.create(person_from=person, person_to=other, relation_type=R.PARTNER)
  label = {PARENT: _("parent"), PARTNER: _("partner"), CHILD: _("child")}[kind]
  log_change(request, person, f"Added {kind}: {other}")
  log_change(request, other, f"Added as {kind} of {person}")
  messages.success(request, _("%(name)s added as %(label)s.") % {'name': _name(other, request), 'label': label})
  return {'relation': kind, 'object': other}


def remove_relative(person, kind, token, request):
  """Remove the link; both people stay."""
  require_can_edit(person, request)
  kind = _kind(kind)
  other = _other(person, request, token)
  rows = _relation(person, kind, other)
  if not rows.exists():
    raise ValidationError(_("That isn't linked."))
  rows.delete()
  log_change(request, person, f"Removed {kind}: {other}")
  log_change(request, other, f"Removed as {kind} of {person}")
  messages.success(request, _("%(name)s is no longer linked.") % {'name': _name(other, request)})
  return {'relation': kind, 'object': other}


def suggested_parents(person, request):
  """When `person` has exactly one parent: the likely other parent, before
  any typing - first that parent's partners, then the other parents of
  that parent's other children (a co-parent with no partnership recorded).
  Only people this viewer may see; never someone already a parent, the
  person themselves, or their own descendant. [(person, 'partner' |
  'co-parent')], at most a handful."""
  from .models import Person
  parents = person._get_parents_flat()
  if len(parents) != 1:
    return []
  parent = parents[0]
  partners = [p.pk for p in parent.get_partners()]
  co_parents = list(PersonRelation.objects.filter(
    relation_type=PersonRelation.RelationType.PARENT,
    person_to__in=PersonRelation.objects.filter(
      person_from=parent, relation_type=PersonRelation.RelationType.PARENT,
    ).exclude(person_to=person).values('person_to'),
  ).exclude(person_from=parent).values_list('person_from', flat=True))
  descendants = _descendant_ids(person)
  ordered, seen = [], {person.pk, parent.pk, *descendants}
  for pk, reason in [*((pk, 'partner') for pk in partners), *((pk, 'co-parent') for pk in co_parents)]:
    if pk not in seen:
      seen.add(pk)
      ordered.append((pk, reason))
  visible = {p.pk: p for p in filter_accessible(Person.objects.filter(pk__in=[pk for pk, _r in ordered]), request)}
  return [(visible[pk], reason) for pk, reason in ordered if pk in visible][:5]


def _descendant_ids(person):
  found, level = set(), {person.pk}
  while level:
    level = set(PersonRelation.objects.filter(
      person_from__in=level, relation_type=PersonRelation.RelationType.PARENT,
    ).values_list('person_to', flat=True)) - found
    found |= level
  return found
