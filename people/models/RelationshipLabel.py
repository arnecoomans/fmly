from django.db import models
from django.utils.text import format_lazy
from django.utils.translation import gettext_lazy as _

from cmnsd.api.registry import api_field

from .PersonRelations import PersonRelation

# How many parent-edges to walk up from either side before giving up.
# Confirmed against the real dataset (not just estimated) that this stays
# cheap even at depth 5+: the deepest actual ancestor chain in this data
# is 10 generations, and walking to depth 5 on it costs 13 queries, not
# the theoretical worst case (2+4+8+16+32 per side) - real genealogical
# records are sparse, branches run out of recorded parents quickly. Still
# deliberately bounded rather than unbounded: collateral relations beyond
# first cousin (second cousin, "N times removed") are NOT in _LABELS even
# though depth 5 would technically reach some of them - those still aren't
# intuitively understood by most people, so they silently return no label
# (see relationship_to()) rather than guessing wording for them.
MAX_GENERATIONS = 5

# (distance from `person` to the common ancestor, distance from `viewer`
# to the common ancestor) -> (male, female, gender-neutral-or-None).
# Gender-neutral is None where neither English nor Dutch has a standard
# single word for it (sibling in Dutch; aunt/uncle and niece/nephew in
# both) - relationship_to() suppresses the label entirely in that case
# rather than guessing a gendered word or forcing an awkward compound.
# Dutch terms for 4/5 generations (beto-/oud-beto- prefixes) are entered
# as best-known genealogical convention - worth confirming with a native
# speaker when the .po translations actually get filled in, not just
# trusted as-is from a code comment.
_LABELS = {
  (0, 1): (_("father"), _("mother"), _("parent")),
  (0, 2): (_("grandfather"), _("grandmother"), _("grandparent")),
  (0, 3): (_("great-grandfather"), _("great-grandmother"), _("great-grandparent")),
  (0, 4): (_("great-great-grandfather"), _("great-great-grandmother"), _("great-great-grandparent")),
  (0, 5): (_("great-great-great-grandfather"), _("great-great-great-grandmother"), _("great-great-great-grandparent")),
  (1, 0): (_("son"), _("daughter"), _("child")),
  (2, 0): (_("grandson"), _("granddaughter"), _("grandchild")),
  (3, 0): (_("great-grandson"), _("great-granddaughter"), _("great-grandchild")),
  (4, 0): (_("great-great-grandson"), _("great-great-granddaughter"), _("great-great-grandchild")),
  (5, 0): (_("great-great-great-grandson"), _("great-great-great-granddaughter"), _("great-great-great-grandchild")),
  (1, 1): (_("brother"), _("sister"), None),
  (1, 2): (_("uncle"), _("aunt"), None),
  (2, 1): (_("nephew"), _("niece"), None),
  (2, 2): (_("cousin"), _("cousin"), _("cousin")),
}


def _ancestors_with_distance(person, max_depth):
  """{ancestor_pk: distance} via parent edges, including `person` itself
  at distance 0, up to max_depth generations up."""
  distances = {person.pk: 0}
  frontier = [person]
  depth = 0
  while frontier and depth < max_depth:
    depth += 1
    next_frontier = []
    for p in frontier:
      for parent in p._get_parents_flat():
        if parent.pk not in distances:
          distances[parent.pk] = depth
          next_frontier.append(parent)
    frontier = next_frontier
  return distances


class RelationshipLabel(models.Model):
  """
  "What is this person to the current viewer" - e.g. person.relationship_to(
  request.user.person) might return "father". Deliberately bounded (see
  MAX_GENERATIONS/_LABELS): direct line to great-great-great-grandparent/
  -child, siblings, aunt/uncle, niece/nephew, first cousins, and a direct
  partner check - not second cousins, "removed" degrees, half-vs-full
  sibling distinction, step-relations, or in-laws. Shown once per page
  (the profile card), not per relationship-row - the ancestor walk costs
  a handful of queries, which is fine once per page load and wasteful
  repeated for every row in every relationship list.
  """

  class Meta:
    abstract = True

  def _is_partner_of(self, other):
    if not other:
      return False
    lo, hi = sorted((self.pk, other.pk))
    return PersonRelation.objects.filter(
      person_from_id=lo, person_to_id=hi,
      relation_type=PersonRelation.RelationType.PARTNER,
    ).exists()

  def relationship_to(self, viewer):
    """Full display phrase describing what `self` is to `viewer` - e.g.
    "Your father", or "You" when self IS the viewer (a real, mapped case,
    not just excluded as a non-relation - it's the one relationship that
    needs its own phrasing instead of the "Your X" pattern, so that's
    handled here rather than left for the template to bolt a prefix onto).
    None if there's no viewer, they're unrelated within MAX_GENERATIONS,
    or no gender-appropriate label exists (see _LABELS)."""
    if not viewer:
      return None
    if viewer.pk == self.pk:
      return _("You")
    if self._is_partner_of(viewer):
      return _("Your partner")

    my_ancestors = _ancestors_with_distance(self, MAX_GENERATIONS)
    viewer_ancestors = _ancestors_with_distance(viewer, MAX_GENERATIONS)
    common = set(my_ancestors) & set(viewer_ancestors)
    if not common:
      return None
    # Closest shared ancestor wins if multiple exist - always the shortest
    # path, never trying to merge/display multiple simultaneous relations
    # (e.g. a double-cousin scenario).
    closest = min(common, key=lambda pk: my_ancestors[pk] + viewer_ancestors[pk])
    d_person = my_ancestors[closest]
    d_viewer = viewer_ancestors[closest]

    entry = _LABELS.get((d_person, d_viewer))
    if not entry:
      return None
    male, female, neutral = entry
    if self.gender == 'm':
      label = male
    elif self.gender == 'f':
      label = female
    else:
      label = neutral
    if not label:
      return None
    # format_lazy, not an f-string or % - both would force eager
    # evaluation of the still-lazy gettext_lazy() label/prefix, breaking
    # per-request i18n (same gotcha as .capitalize() on a lazy string).
    return format_lazy(_("Your {label}"), label=label)

  @api_field(readonly=True)
  def get_relation_to_user(self, request=None):
    """API/template-callable form of relationship_to() - resolves the
    viewer from request.user.person instead of taking a Person directly.
    Matches the old cmnsd @ajax_function(request=None) signature (see
    cmnsd/docs/claude.md, "Make a model method callable via AJAX") that
    the future dispatch is expected to call methods with, so this is
    ready for that without changes once it exists. Safe for anonymous
    users, no request, or a user with no linked Person - all resolve to
    no viewer, so relationship_to() returns None rather than raising.
    @api_field, not @api_action: this has no side effect, it's a pure
    computed read - @api_action is reserved for things that mutate state."""
    user = getattr(request, 'user', None)
    if not user or not getattr(user, 'is_authenticated', False):
      return None
    viewer = getattr(user, 'person', None)
    return self.relationship_to(viewer)
