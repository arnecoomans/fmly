from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from django.template.defaultfilters import slugify
from cmnsd.models.cmnsd_basemodel import BaseModel
from .BaseIcon import BaseIcon

class Location(BaseModel, BaseIcon):
  slug                = models.SlugField(max_length=255, unique=True)
  name                = models.CharField(max_length=255)
  description         = models.TextField(blank=True)
  parent              = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='sublocations')
  alternatives        = models.ManyToManyField('self', blank=True, symmetrical=False, related_name='alternative_to')

  coord_lat           = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-90.0), MaxValueValidator(90.0)])
  coord_lon           = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-180.0), MaxValueValidator(180.0)])

  def __str__(self):
    return self.get_display_name()
  
  def save(self, *args, **kwargs):
    if not self.slug:
      self.slug = slugify(self.name)
    super().save(*args, **kwargs)
  
  class Meta:
    ordering = ['parent__parent__name', 'parent__name', 'name']
    unique_together = ('parent', 'name')
  
  def get_display_name(self):
    name = self.name
    if self.parent:
      name += f", { self.parent.name }"
    if self.parent and self.parent.parent:
      name += f", { self.parent.parent.name }"
    return name
  
  def get_alternatives(self):
    alternatives = self.alternatives.all() | self.alternative_to.all()
    return alternatives.distinct()
  
  def get_event_people(self):
    people = set()
    for event in self.events.all():
      for person in event.people.all():
        people.add(person)
    return people
  def people(self):
    return self.get_event_people()
  
  def country(self):
    if self.parent and self.parent.parent:
      return self.parent.parent
    elif self.parent:
      return self.parent
    else:
      return None
  def region(self):
    if self.parent and self.parent.parent:
      return self.parent
    else:
      return None