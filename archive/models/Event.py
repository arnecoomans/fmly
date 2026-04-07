from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MaxValueValidator, MinValueValidator

import datetime


from cmnsd.models import BaseModel
from .BaseIcon import BaseIcon
MONTHS = [
  (1, _('january')),
  (2, _('february')),
  (3, _('march')),
  (4, _('april')),
  (5, _('may')),
  (6, _('june')),
  (7, _('july')),
  (8, _('august')),
  (9, _('september')),
  (10, _('october')),
  (11, _('november')),
  (12, _('december')),]

TYPE_CHOICES = [
  ('birth', _('birth')),
  ('death', _('death')),
  ('marriage', _('marriage')),
  ('general', _('general')),
  ('other', _('other')),
]

class EventQuerySet(models.QuerySet):
  """Custom queryset for Event — adds chainable optimisation methods."""

  def with_relations(self):
    """Prefetch people, locations and images to avoid per-event queries."""
    return self.prefetch_related('people', 'locations', 'images')

  def optimized(self):
    return self.with_relations()


class EventManager(models.Manager):
  """Default manager for Event. Returns EventQuerySet instances."""

  def get_queryset(self):
    return EventQuerySet(self.model, using=self._db)

  def optimized(self):
    return self.get_queryset().optimized()


class Event(BaseModel):
  type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='other', verbose_name=_('type'))
  title = models.CharField(max_length=200, blank=True, null=True, verbose_name=_('title'))
  description = models.TextField(blank=True, null=True, verbose_name=_('description'))

  year = models.PositiveIntegerField(
    validators=[MinValueValidator(1), MaxValueValidator(9999)],
    blank=True,
    null=True,
    verbose_name=_('year'),
  )
  month = models.PositiveIntegerField(
    choices=MONTHS,
    blank=True,
    null=True,
    verbose_name=_('month'),
  )
  day = models.PositiveIntegerField(
    validators=[MinValueValidator(1), MaxValueValidator(31)],
    blank=True,
    null=True,
    verbose_name=_('day'),
  )

  people = models.ManyToManyField('Person', blank=True, related_name='events', verbose_name=_('people'))
  locations = models.ManyToManyField('Location', blank=True, related_name='events', verbose_name=_('locations'))
  images = models.ManyToManyField('Image', blank=True, related_name='events', verbose_name=_('images'))

  # ajax_template_name = 'function/person_event'

  objects = EventManager()

  class Meta:
    ordering = ['-year', '-month', '-day', 'title', 'type']
    indexes = [
      models.Index(fields=["type", "year"])
    ]

  def __str__(self):
    try:
      return self.get_title()
    except:
      return f"{ self.type} - { self.title }"
  
  def get_title(self):
    if not hasattr(self, '_title'):
      title = []
      people = list(self.people.all())
      locations = list(self.locations.all())
      if self.type in ['birth', 'death', 'marriage']:
        title.append(str(_(self.get_type_display())))
        if people:
          title.append(f"{ _('of') }")
      if people:
        people_names = ', '.join([str(person.short_name()) for person in people])
        title.append(f" { people_names }")
      if locations:
        location_names = ', '.join([str(location) for location in locations])
        title.append(f"{ _('at') } { location_names }")
      self._title = " ".join(title)
    return self._title
  
  @property
  def months(self):
    return MONTHS
  
  @property
  def weekday(self):
    if not self.month or not self.day:
      return None
    date = datetime.date(year=self.year, month=self.month, day=self.day)
    return date.strftime('%A')

  def date(self):
    if not self.year:
      return None
    return datetime.date(year=self.year, month=self.month or 1, day=self.day or 1)
  
  def image_count(self):
    return len(self.images.all())
  
  def editable(self):
    if self.type in ['birth', 'death']:
      return False
    return True
  
  def show_type(self):
    if self.type in ['birth', 'death', 'marriage']:
      return True
    return False
  