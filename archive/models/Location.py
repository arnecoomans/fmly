from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator

from cmnsd.models.cmnsd_basemodel import BaseModel
from .BaseIcon import BaseIcon

class Location(BaseModel, BaseIcon):
  slug                = models.SlugField(max_length=255, unique=True)
  name                = models.CharField(max_length=255, unique=True)
  description         = models.TextField(blank=True)
  parent              = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='sublocations')
  alternatives        = models.ManyToManyField('self', blank=True, symmetrical=False, related_name='alternative_to')

  coord_lat           = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-90.0), MaxValueValidator(90.0)])
  coord_lon           = models.FloatField(null=True, blank=True, validators=[MinValueValidator(-180.0), MaxValueValidator(180.0)])

  def __str__(self):
    return self.get_display_name()
  
  class Meta:
    ordering = ['name']
  
  def get_display_name(self):
    name = self.name
    if self.parent:
      name += f", { self.parent.name }"
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