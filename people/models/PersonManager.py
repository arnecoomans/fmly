from django.db import models


class PersonQuerySet(models.QuerySet):
  """Custom queryset for Person - adds chainable optimization methods."""

  def with_relations(self):
    """Prefetch relations_from/relations_to with the other Person, so a
    view rendering many people's families doesn't call .get_children() /
    .get_parents() / etc. once per person."""
    from .PersonRelations import PersonRelation
    return self.prefetch_related(
      models.Prefetch('relations_from', queryset=PersonRelation.objects.select_related('person_to')),
      models.Prefetch('relations_to', queryset=PersonRelation.objects.select_related('person_from')),
    )

  def with_lifespan(self):
    """Annotate birth_year/death_year via a correlated subquery against
    Event - not stored on Person, so there's nothing to keep in sync, but
    still one query for however many people are in this queryset (not one
    per person, unlike calling get_birth_event()/get_death_event() per
    row)."""
    from events.models import Event
    birth_qs = Event.objects.current().filter(
      people=models.OuterRef('pk'), kind=Event.Kind.BIRTH
    ).order_by('year', 'month', 'day').values('year')[:1]
    death_qs = Event.objects.current().filter(
      people=models.OuterRef('pk'), kind=Event.Kind.DEATH
    ).order_by('year', 'month', 'day').values('year')[:1]
    return self.annotate(
      birth_year=models.Subquery(birth_qs, output_field=models.IntegerField()),
      death_year=models.Subquery(death_qs, output_field=models.IntegerField()),
    )

  def optimized(self):
    """Full optimization for a single-person detail view."""
    return self.with_relations()

  def for_list(self):
    """Hook called by cmnsd.api.filtering.build_list() after filtering:
    evaluates the queryset and batch-attaches birth/death events (one
    query total, see FamilyShorthand._attach_lifespan()), since every row
    in a list renders a lifespan - and portraits, for the avatars (see
    FamilyShorthand._attach_portraits()). Returns a list, not a queryset."""
    return self.model._attach_portraits(self.model._attach_lifespan(self))


class PersonManager(models.Manager):
  """Default manager for Person. Returns PersonQuerySet instances."""

  def get_queryset(self):
    return PersonQuerySet(self.model, using=self._db)

  def with_relations(self):
    return self.get_queryset().with_relations()

  def with_lifespan(self):
    return self.get_queryset().with_lifespan()

  def optimized(self):
    return self.get_queryset().optimized()
