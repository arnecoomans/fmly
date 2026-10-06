"""
Editing an item's parts on the site (edit mode, docs/EDIT-MODE-PLAN.md):
the logic behind Content's parts actions (add_part, move_part,
toggle_variant, join_previous, separate_part, detach_part).

Numbering, as everywhere (Content.make_parts_of): parts are 1, 2, ... in
order; 0 = a variant of the whole itself; the same number twice =
variants of each other. Moving a part moves its number group - the
variants go with it. After every change the parts are renumbered 1..n
without gaps (renumber), groups and 0 kept.

Every action needs the change permission on the items involved
(cmnsd.edit.mode.require_can_edit) and is logged to the admin history of
both the whole and the part (cmnsd.edit.log). Positions are written with
queryset updates: a part's file and slug don't change.
"""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import F, Max
from django.utils.translation import gettext as _

from cmnsd.edit.log import log_change
from cmnsd.edit.mode import require_can_edit


def _ordered(whole):
  return list(whole.parts.order_by('position', 'pk'))


def _set(part, **fields):
  type(part).objects.filter(pk=part.pk).update(**fields)
  for name, value in fields.items():
    setattr(part, name, value)


def renumber(whole):
  """Number the parts 1..n in their current order, without gaps: a group
  (same number) stays one number, 0 stays 0."""
  number, last = 0, None
  for part in _ordered(whole):
    if part.position == 0:
      continue
    if part.position != last:
      number += 1
      last = part.position
    if part.position != number:
      _set(part, position=number)


def _numbers(whole):
  """The distinct part numbers in use, ascending, without 0."""
  return sorted({part.position for part in _ordered(whole) if part.position})


def _next_number(whole):
  return (whole.parts.aggregate(top=Max('position'))['top'] or 0) + 1


def _whole_of(part, request):
  if not part.parent_id:
    raise ValidationError(_("This item isn't a part of anything."))
  whole = part.parent
  require_can_edit(whole, request)
  require_can_edit(part, request)
  return whole


def add_part(whole, part, request):
  """Make `part` the last part of `whole` (the next number)."""
  require_can_edit(whole, request)
  require_can_edit(part, request)
  if part.pk == whole.pk:
    raise ValidationError(_("An item can't be a part of itself."))
  if whole.parent_id:
    raise ValidationError(_("%(item)s is itself a part - add to its whole instead.") % {'item': whole})
  if part.parent_id == whole.pk:
    raise ValidationError(_("%(item)s is already a part of this item.") % {'item': part})
  if part.parent_id:
    raise ValidationError(_("%(item)s is already a part of %(whole)s - remove it there first.") % {'item': part, 'whole': part.parent})
  if part.parts.exists():
    raise ValidationError(_("%(item)s has parts of its own, so it can't become a part.") % {'item': part})
  number = _next_number(whole)
  _set(part, parent=whole, position=number)
  log_change(request, whole, f"Added part {number}: {part}")
  log_change(request, part, f"Became part {number} of {whole}")
  messages.success(request, _("“%(item)s” is now part %(number)s.") % {'item': part, 'number': number})


def move_part(part, direction, request):
  """Swap the part's number group with the previous ('earlier') or next
  ('later') group - variants move together. A variant of the whole (0)
  doesn't move: make it a part first."""
  whole = _whole_of(part, request)
  if direction not in ('earlier', 'later'):
    raise ValidationError(_("Unknown direction."))
  if part.position == 0:
    raise ValidationError(_("A variant of the whole has no place in the order - make it a part first."))
  numbers = _numbers(whole)
  index = numbers.index(part.position)
  other_index = index - 1 if direction == 'earlier' else index + 1
  if not 0 <= other_index < len(numbers):
    return
  mine, other = numbers[index], numbers[other_index]
  parts = whole.parts.all()
  moving = list(parts.filter(position=mine).values_list('pk', flat=True))
  parts.filter(position=other).update(position=mine)
  parts.filter(pk__in=moving).update(position=other)
  renumber(whole)
  log_change(request, whole, f"Moved part {mine} ({part}) {direction}: now {other}")
  messages.success(request, _("Part %(old)s moved to %(new)s.") % {'old': mine, 'new': other})


def toggle_variant(part, request):
  """A part becomes a variant of the whole (0), or a variant becomes the
  last part again."""
  whole = _whole_of(part, request)
  if part.position == 0:
    _set(part, position=_next_number(whole))
    message = f"{part}: no longer a variant of the whole, now part {part.position}"
  else:
    _set(part, position=0)
    message = f"{part}: now a variant of the whole"
  renumber(whole)
  log_change(request, whole, message)
  if part.position == 0:
    messages.success(request, _("“%(item)s” is now a variant of the whole.") % {'item': part})
  else:
    messages.success(request, _("“%(item)s” is a part again.") % {'item': part})


def join_previous(part, request):
  """Give the part the previous part's number: variants of each other."""
  whole = _whole_of(part, request)
  numbers = _numbers(whole)
  if part.position == 0 or numbers.index(part.position) == 0:
    raise ValidationError(_("There is no previous part to join."))
  previous = numbers[numbers.index(part.position) - 1]
  _set(part, position=previous)
  renumber(whole)
  log_change(request, whole, f"{part}: now a variant of part {previous}")
  messages.success(request, _("“%(item)s” now shares number %(number)s.") % {'item': part, 'number': previous})


def separate_part(part, request):
  """Undo join_previous: the part gets its own number, right after the
  group it shared a number with."""
  whole = _whole_of(part, request)
  if part.position == 0 or whole.parts.filter(position=part.position).count() < 2:
    raise ValidationError(_("This part doesn't share its number."))
  whole.parts.filter(position__gt=part.position).update(position=F('position') + 1)
  _set(part, position=part.position + 1)
  renumber(whole)
  log_change(request, whole, f"{part}: own number again, part {part.position}")
  messages.success(request, _("“%(item)s” has its own number again.") % {'item': part})


def detach_part(part, request):
  """The part becomes a separate item again - nothing is deleted."""
  whole = _whole_of(part, request)
  _set(part, parent=None, position=0)
  renumber(whole)
  log_change(request, whole, f"Removed part: {part}")
  log_change(request, part, f"No longer a part of {whole}")
  messages.success(request, _("“%(item)s” is a separate item again.") % {'item': part})
