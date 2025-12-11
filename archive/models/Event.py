from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MaxValueValidator, MinValueValidator

import datetime


from cmnsd.models.cmnsd_basemodel import BaseModel
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

  class Meta:
    ordering = ['-year', '-month', '-day', 'title', 'type']
  
  def __str__(self):
    try:
      return self.get_title()
    except:
      return f"{ self.type} - { self.title }"
  
  def get_title(self):
    title = []
    if self.type in ['birth', 'death', 'marriage']:
      title.append(self.get_type_display())
      if self.people.exists():
        title.append(f"{ _('of') }")
    if self.people.exists():
      people_names = ', '.join([str(person.short_name()) for person in self.people.all()])
      title.append(f" { people_names }")
    if self.locations.exists():
      location_names = ', '.join([str(location) for location in self.locations.all()])
      title.append(f"{ _('at') } { location_names }")
    title.append(f"{ _('on') }")
    if self.day:
      title.append(f"{ self.day }")
    if self.month:
      title.append(f"{ self.get_month_display() }")
    title.append(f"{ self.year }")
    if self.title:
      title.append(f": { self.title }")
    return " ".join(title)
  
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
    return self.images.count()