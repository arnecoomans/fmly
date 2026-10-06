from django.db import models

from cmnsd.api.registry import api_action


class RelativesEditing(models.Model):
  """Edit mode: a person's parents, partners and children, through two API
  actions (cmnsd object_action) - the rules are in people/relatives.py.
  data: {relation: 'parent' | 'partner' | 'child', token: <the other person>}.
  Separate from EditableRelationsMixin's link/unlink: a family link is a
  PersonRelation row with a direction, not a many-to-many field."""

  class Meta:
    abstract = True

  def relative_tokens(self):
    """{'parent': ..., 'partner': ..., 'child': ...} - per group, the tokens
    a picker shouldn't offer: who's linked already, and the person
    themselves (person/_relative_picker.html)."""
    groups = {'parent': self._get_parents_flat(), 'partner': self.get_partners(), 'child': self._get_children_flat()}
    return {kind: ','.join([self.token, *(p.token for p in people)]) for kind, people in groups.items()}

  @api_action()
  def add_relative(self, request, data):
    from ..relatives import add_relative
    return add_relative(self, data.get('relation'), data.get('token'), request)

  @api_action()
  def remove_relative(self, request, data):
    from ..relatives import remove_relative
    return remove_relative(self, data.get('relation'), data.get('token'), request)
