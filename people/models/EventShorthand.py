from django.db import models

from events.models import Event


class EventShorthand(models.Model):
  """
  Event access shortcuts for Person - kept separate from Person.py and from
  FamilyShorthand for the same reason: each shorthand group is its own file
  so a growing list of "what can a Person answer" doesn't turn into one
  unmanageable model file.

  Not stored on Person - always derived from Event, so there's no birth/
  death date to keep in sync. For a single person this costs one query per
  property access; for listing many people, use Person.objects.with_lifespan()
  instead (a queryset-level annotation), not these.
  """

  class Meta:
    abstract = True

  @property
  def birth(self):
    """The Event for this person's birth, or None. Multiple birth events
    are possible in theory (nothing here prevents it) but should be
    discouraged where they're created - e.g. a form/view can check
    `if person.birth` to hide an "add birth" option once one exists,
    rather than enforcing it as a hard DB constraint.

    Checks for a batch-prefetched value first (see
    FamilyShorthand._attach_lifespan()) - set on every instance a
    relationship-list method returns, so a page rendering many people's
    lifespans (e.g. _person_row.html) doesn't cost one query per person."""
    if hasattr(self, '_prefetched_birth'):
      return self._prefetched_birth
    return self.events.current().filter(kind=Event.Kind.BIRTH).first()

  @property
  def death(self):
    """Mirror of birth - the Event for this person's death, or None."""
    if hasattr(self, '_prefetched_death'):
      return self._prefetched_death
    return self.events.current().filter(kind=Event.Kind.DEATH).first()
