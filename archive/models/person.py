import datetime
from django.db import models
from django.db.models import F
from django.db.models.functions import Coalesce
from django.contrib.auth.models import User
from django.template.defaultfilters import slugify
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.urls import reverse_lazy, reverse
from math import floor
from django.utils.translation import gettext_lazy as _
from django.db.models import Value, CharField
from functools import reduce
from operator import or_
from django.db.models import (
    Exists, OuterRef, Case, When, Value, CharField,
    Subquery, IntegerField, F, BooleanField
)
from django.db.models import Q

from .Event import Event

from cmnsd.models.cmnsd_basemodel import BaseModel, VisibilityModel
from cmnsd.models.cmnsd_basemethod import ajax_function, searchable_function

def annotate_relation(qs, label):
  return qs.annotate(
    relation=Value(label, output_field=CharField())
  )


class Person(BaseModel):
  ''' Model: Person
      People are:
      - tagged on an image
      - related to another person
  '''
  first_names         = models.CharField(max_length=255, blank=True, verbose_name='Voornamen', help_text='Alle voornamen, inclusief roepnaam')
  given_name          = models.CharField(max_length=255, blank=True, verbose_name='Roepnaam', help_text='Indien afwijkend van eerste voornaam')
  last_name           = models.CharField(max_length=255, blank=True, verbose_name='Achternaam', help_text='Achternaam bij geboorte')
  married_name        = models.CharField(max_length=255, blank=True, verbose_name='Getrouwde Achternaam', help_text='Achternaam van echtgeno(o)t(e)')

  nickname            = models.CharField(max_length=255, blank=True, verbose_name='Bijnaam')
  email               = models.EmailField(blank=True, help_text='Dit veld is alleen zichtbaar voor jou en voor de site-beheerder(s). Vul je e-mailadres in zodat we je een wachtwoord-reset email kunnen sturen als je niet langer kan inloggen.')
  slug                = models.CharField(max_length=255, unique=True)
  
  # Gender (required for family tree)
  GENDERS             = [('m', _('male')), ('f', _('female')), ('x', _('not stored'))]
  gender              = models.CharField(max_length=1, choices=GENDERS, default='x')
  
  # Information
  # Dating
  MONTHS = [(1, 'januari'), (2, 'februari'), (3, 'maart'), (4, 'april'), (5, 'mei'), (6, 'juni'), (7, 'juli'), (8, 'augustus'), (9, 'september'), (10, 'oktober'), (11, 'november'), (12, 'december')]
  
  moment_of_death_unconfirmed = models.BooleanField(default=False, help_text='Set True if moment of death is unknown but person has deceased.')

  # Bio
  bio                 = models.TextField(blank=True, help_text='Markdown supported')
  # Meta
  private             = models.BooleanField(default=False, help_text="Private Mode limits the information being shared")
  related_user        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='related_person')
  user                = models.ForeignKey(User, on_delete=models.CASCADE)
  date_modified       = models.DateTimeField(auto_now=True)
  date_created        = models.DateTimeField(auto_now_add=True)
  
  # Portrait settings
  portrait_x = models.IntegerField(null=True, blank=True)
  portrait_y = models.IntegerField(null=True, blank=True)
  portrait_w = models.IntegerField(null=True, blank=True)
  portrait_h = models.IntegerField(null=True, blank=True)

  
  class Meta:
    ordering = ('first_names', 'last_name')
    verbose_name = 'person'
    verbose_name_plural = 'people'

  def __str__(self):
    ''' Return the name of the person with year of birth and death '''
    name = self.full_name()
    # Remove LifeSpan from __str__ because it requires a search in Events
    # and slows down admin views and edit views. When lifespan is needed,
    # Autosuggest or full_name() can be used.
    return name

  ''' PROPERTIES '''
  @property
  def months(self):
    """ Return the months choices, usable in forms and filters """
    return self.MONTHS
  @property
  def genders(self):
    """ Return the gender choices, usable in forms and filters """
    return self.GENDERS
  
  ''' AJAX FUNCTIONS FOR BUILDING DETAIL PAGE '''
  @ajax_function
  def names(self):
    return {
      'first_names': self.first_names,
      'given_name': self.given_name,
      'last_name': self.last_name,
      'married_name': self.married_name,
      'nickname': self.nickname,
    }
  
  @ajax_function
  def dates(self):
    return {
      'date_of_birth': self.get_date_of_birth(),
      'date_of_death': self.get_date_of_death(),
      'moment_of_death_unconfirmed': self.moment_of_death_unconfirmed,
    }
  
  ''' SEARCHABLE FUNCTIONS '''
  ''' Decade and Century shorthand available for searching people
      alive in a certain period
  '''
  @searchable_function
  def century(self):
    if self.birth() and self.birth().year:
      return floor(self.birth().year/100)*100
  @searchable_function
  def decade(self):
    decades = []
    if self.birth() and self.birth().year:
      decade = floor(self.birth().year/10)*10
      if decade not in decades:
        decades.append(decade)
      if self.death() and self.death().year:
        max = 0
        while decade <= floor(self.death().year/10)*10:
          decade +=10
          max +=1
          if decade not in decades and decade <= floor(self.death().year/10)*10:
            decades.append(decade)
          if max > 8:
            break
    decades.sort()
    return decades
  
  ''' NAME Displaying '''
  @searchable_function
  def last_names(self):
    last_names = []
    if self.last_name and self.last_name not in last_names:
      last_names.append(self.last_name)
    if self.married_name and self.married_name not in last_names:
      last_names.append(self.married_name)
    return last_names

  @searchable_function
  def familycollection(self):
    families = []
    for name in getattr(settings, 'FAMILIES', []):
      if name.lower() in self.last_name.lower() \
        or (self.married_name and name.lower() in self.married_name.lower()):
        if name not in families:
          families.append(name)
    return families
  

  def name(self):
    return ' '.join([self.first_names, self.last_name])

  def full_name(self):
    if self.private:
      return ' '.join([self.first_names, self.last_name]).strip()
    else:
      name = []
      name.append(self.first_names)
      if self.given_name:
        name.append(f"({ self.given_name})")
      if self.married_name:
        name.append(self.married_name)
        if self.last_name:
          name.append(f"- { self.last_name }")
      else:
        name.append(self.last_name)
      return ' '.join(name).strip()
  
  def short_name(self):
    if self.given_name:
      return f"{ self.given_name } { self.last_name }"
    return f"{ self.first_names.split(' ')[0] } { self.last_name }"
  
  
  
  ''' EVENTS '''
  @ajax_function
  def get_date_of_birth(self):
    if self.events.filter(type='birth').exists():
      event = self.events.filter(type='birth').first()
      if not event.year:
        return None
      return datetime.date(year=event.year, month=event.month or 1, day=event.day or 1)
  
  @ajax_function
  def get_date_of_death(self):
    if self.events.filter(type='death').exists():
      event = self.events.filter(type='death').first()
      if not event.year:
        return None
      return datetime.date(year=event.year, month=event.month or 1, day=event.day or 1)
  
  def birth(self):
    return self.events.filter(type='birth').last()
    
  def death(self):
    return self.events.filter(type='death').last()
  
  ''' Timeline functions'''  
  def has_timeline(self):
    return True if self.events.exists() else False
  
  @ajax_function
  def timeline(self):
    events = self.events.all()
    # Include Parent events
    for parent in self.get_parents().all() or []:
      events = events | parent.events.filter(type__in=['birth', 'death', 'marriage'])
    # Include Children events
    for child in self.get_children().all() or []:
      events = events | child.events.filter(type__in=['birth', 'death', 'marriage'])
    # Include Partner events
    for partner in self.get_partners().all() or []:
      events = events | partner.events.filter(type__in=['birth', 'death',])
    # Include General events
    events = events | Event.objects.filter(type='general')
    # Crop events between birth and death
    if self.birth():
      events = events.filter(
        models.Q(year__gt=self.birth().year) |
        models.Q(year=self.birth().year, month__gte=Coalesce(self.birth().month, 1)) |
        models.Q(year=self.birth().year, month=Coalesce(self.birth().month, 1), day__gte=Coalesce(self.birth().day, 1))
      )
    if self.death():
      events = events.filter(
        models.Q(year__lt=self.death().year) |
        models.Q(year=self.death().year, month__lte=Coalesce(self.death().month, 12)) |
        models.Q(year=self.death().year, month=Coalesce(self.death().month, 12), day__lte=Coalesce(self.death().day, 31))
      )
    return events.order_by('year', 'month', 'day').distinct()
  

  def get_lifespan_data(self):
    data = {
      'birth_year': None,
      'death_year': None,
      'moment_of_death_unconfirmed': self.moment_of_death_unconfirmed,
    }
    if self.birth() and self.birth().year:
      data['birth_year'] = self.birth().year
    if self.death() and self.death().year:
      data['death_year'] = self.death().year
    return data

  def get_lifespan(self):
    lifespan = ''
    if self.get_lifespan_data()['birth_year']:
      lifespan += str(self.get_lifespan_data()['birth_year'])
    else:
      lifespan += '*'
    if self.get_lifespan_data()['death_year']:
      lifespan += ' - ' + str(self.get_lifespan_data()['death_year'])
    elif self.get_lifespan_data()['moment_of_death_unconfirmed']:
      lifespan += ' - &dagger;'
    return lifespan

  def get_lifespan_display(self):
    lifespan = ''
    if self.get_lifespan_data()['birth_year']:
      lifespan += str(self.birth().date().strftime('%d-%m-%Y'))
    if self.birth():
      locations = []
      for location in self.birth().locations.all():
        if location not in locations:
          locations.append(location.name)
      if locations:
        lifespan += f" ({', '.join(locations)})"
    if self.get_lifespan_data()['death_year'] or self.get_lifespan_data()['moment_of_death_unconfirmed']:
      lifespan += ' - '
      if self.get_lifespan_data()['death_year']:
        lifespan += str(self.death().date().strftime('%d-%m-%Y'))
      if self.death():
        locations = []
        for location in self.death().locations.all():
          if location not in locations:
            locations.append(location.name)
        if locations:
          lifespan += f" ({', '.join(locations)})"
      else:
        if self.get_lifespan_data()['moment_of_death_unconfirmed']:
          lifespan += '&dagger;'
    return lifespan
    
  ''' Family Relations
      There are two family relations stored:
      * A (up) is parent of B (down)
      * C is partner of D
      Brothers and sisters are calculated by havind a shared parent.
  '''

  ''' get_parents()
      Parents have a simple relation
      up is parent of down.
  '''

  @ajax_function
  def parents(self):
    return self.get_parents()
  def siblings(self):
    return self.get_siblings()
  def partners(self):
    return self.get_partners()
  def children(self):
    return self.get_children()
  
  @ajax_function
  def family(self):
    return self.get_family()
    return {
      'parents': [parent.id for parent in self.get_parents()] if self.get_parents() else [],
      'children': [child.id for child in self.get_children()] if self.get_children() else [],
      'partners': [partner.id for partner in self.get_partners()] if self.get_partners() else [],
      'siblings': [sibling.id for sibling in self.get_siblings()] if self.get_siblings() else [],
    }
  
  @ajax_function
  @searchable_function
  def all_family(self):
    family = []
    for parent in self.get_parents() or []:
      family.append(parent)
    for child in self.get_children() or []:
      family.append(child)
    for partner in self.get_partners() or []:
      family.append(partner)
    for sibling in self.get_siblings() or []:
      family.append(sibling)
    return family
  
  @ajax_function
  def all_last_names(self):
    last_names = []
    for person in Person.objects.all():
      if person.last_name not in last_names:
        last_names.append(person.last_name)
      if person.married_name and person.married_name not in last_names:
        last_names.append(person.married_name)
    return last_names
  
  def all_places(self):
    places = []
    for person in Person.objects.all():
      if person.place_of_birth and person.place_of_birth.lower() not in [p.lower() for p in places]:
        places.append(person.place_of_birth)
      if person.place_of_death and person.place_of_death.lower() not in [p.lower() for p in places]:
        places.append(person.place_of_death)
    return places

  def get_related_people(self):
    relations = (
      FamilyRelations.objects
      .filter(Q(up=self) | Q(down=self))
      .annotate(
        person_id=Case(
          When(up=self, then=F("down_id")),
          When(down=self, then=F("up_id")),
          output_field=IntegerField(),
        )
      )
    )

    return (
      Person.objects
      .filter(id__in=relations.values("person_id"))
      .annotate(
        relation_id=Subquery(
          relations
          .filter(person_id=OuterRef("pk"))
          .values("id")[:1]
        ),
        relation_type=Subquery(
          relations
          .filter(person_id=OuterRef("pk"))
          .values("type")[:1]
        ),
      )
    )

  ''' FAMILY RELATIONS METHODS '''
  def get_family(self):
    """
    Returns a queryset of all family members:
    parents, children, siblings, partners.

    Annotates:
      - relation_type: parent | child | sibling | partner
      - birth_year / month / day
    """

    PersonModel = self.__class__

    # --------------------------------------------------
    # Parent: someone who is parent of self
    # --------------------------------------------------
    is_parent = FamilyRelations.objects.filter(
      down_id=self.pk,
      type="parent",
      up_id=OuterRef("pk"),
    )

    # --------------------------------------------------
    # Child: someone who is child of self
    # --------------------------------------------------
    is_child = FamilyRelations.objects.filter(
      up_id=self.pk,
      type="parent",
      down_id=OuterRef("pk"),
    )

    # --------------------------------------------------
    # Partner: explicit partner relation
    # --------------------------------------------------
    explicit_partner = FamilyRelations.objects.filter(
      type="partner",
    ).filter(
      Q(up_id=self.pk, down_id=OuterRef("pk")) |
      Q(down_id=self.pk, up_id=OuterRef("pk"))
    )

    # --------------------------------------------------
    # Partner via shared child
    # --------------------------------------------------
    shared_child_partner = FamilyRelations.objects.filter(
        type="parent",
      ).filter(
        # I am parent of a child
        Q(
          up_id=self.pk,
          down__relation_up__type="parent",
          down__relation_up__up_id=OuterRef("pk"),
        )
      )

    # --------------------------------------------------
    # Siblings (FIXED: direct siblings only)
    # --------------------------------------------------
    self_parents = FamilyRelations.objects.filter(
      down_id=self.pk,
      type="parent",
    ).values("up_id")

    is_sibling = FamilyRelations.objects.filter(
      type="parent",
      up_id__in=Subquery(self_parents),
      down_id=OuterRef("pk"),
    ).exclude(
      down_id=self.pk
    )

    # --------------------------------------------------
    # Birth subquery (ordering)
    # --------------------------------------------------
    birth_qs = (
      Event.objects
      .filter(people=OuterRef("pk"), type="birth")
      .order_by("-year", "-month", "-day")
    )

    qs = (
      PersonModel.objects
      .exclude(pk=self.pk)

      # --- relationship existence checks ---
      .annotate(
        _is_parent=Exists(is_parent),
        _is_child=Exists(is_child),
        _is_sibling=Exists(is_sibling),
        _is_partner_explicit=Exists(explicit_partner),
        _is_partner_shared=Exists(shared_child_partner),
      )

      # --- combine partner logic ---
      .annotate(
        _is_partner=Case(
          When(
            Q(_is_partner_explicit=True) | Q(_is_partner_shared=True),
            then=Value(True),
          ),
          default=Value(False),
          output_field=BooleanField(),
        )
      )

      # --- OR filter ---
      .filter(
        Q(_is_parent=True) |
        Q(_is_child=True) |
        Q(_is_sibling=True) |
        Q(_is_partner=True)
      )

      # --- relation label + birth ordering ---
      .annotate(
        relation_type=Case(
          When(_is_parent=True, then=Value("parent")),
          When(_is_child=True, then=Value("child")),
          When(_is_partner=True, then=Value("partner")),
          When(_is_sibling=True, then=Value("sibling")),
          default=Value("family"),
          output_field=CharField(),
        ),

        birth_year=Subquery(
          birth_qs.values("year")[:1],
          output_field=IntegerField(),
        ),
        birth_month=Subquery(
          birth_qs.values("month")[:1],
          output_field=IntegerField(),
        ),
        birth_day=Subquery(
          birth_qs.values("day")[:1],
          output_field=IntegerField(),
        ),
      )

      .order_by(
        F("birth_year").asc(nulls_last=True),
        F("birth_month").asc(nulls_last=True),
        F("birth_day").asc(nulls_last=True),
      )
    )

    return qs
  
  def get_parents(self):
    return self.get_family().filter(relation_type="parent")

  def get_children(self):
    return self.get_family().filter(relation_type="child")

  def get_partners(self):
    return self.get_family().filter(relation_type="partner")

  def get_siblings(self):
    return self.get_family().filter(relation_type="sibling")

  def get_father(self):
    return self.get_parents().filter(gender='m')
  def get_mother(self):
    return self.get_parents().filter(gender='f')

  @property
  def get_family_relations(self):
    return ['parent', 'child', 'partner', 'sibling']
  
  def previous_person(self):
    try:
      return Person.objects.filter(id__lt=self.id).order_by('-id').first()
    except Person.DoesNotExist:
      return None
  def next_person(self):
    try:
      return Person.objects.filter(id__gt=self.id).order_by('id').first()
    except Person.DoesNotExist:
      return None
    
  
  ''' Absolute URL
      should return URL with both name and slug
  '''
  def get_absolute_url(self):
    return reverse_lazy('archive:person', kwargs={'pk':self.id, 'name': self.slug})
  

  ''' Processing at save
  '''
  def save(self, *args, **kwargs):
    # ''' First name:
    #     If no first name is given, but given names are mentioned, assume first given name is first-name.
    ''' Slug:
        Slug should always contain given names, last name and married name, but also 
        year of birth and -death.
        Make use of __str__() to get the correct fields
    '''
    self.slug = slugify(self.__str__().replace('(', '')).replace(')', '')
    ''' Related User:
        If a related user is set, copy user information to the related user
        and back
    '''
    if self.related_user and self.first_names:
      self.related_user.first_names = self.first_names
    if self.related_user and self.last_name:
      self.related_user.last_name = self.last_name
    if self.related_user and self.email:
      self.related_user.email = self.email
    if self.related_user:
      self.related_user.save()
    return super(Person, self).save(*args, **kwargs)


''' Family Relations
    Family Relations are stored by defining person A is relation of person B. Currently only relation
    parent or partner can be selected. 
    Children are calculated by fetching one's parents children
'''
class FamilyRelations(models.Model):
  RELATION_CHOICES = [
    ('parent', 'Parent'),
    ('partner', 'Partner'),
  ]
  up                  = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='relation_down')
  down                = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='relation_up')
  type                = models.CharField(choices=RELATION_CHOICES, max_length=16, default='parent')

  class Meta:
    unique_together = ('up', 'down', 'type', )
    indexes = [
      models.Index(fields=["up", "type"]),
      models.Index(fields=["down", "type"]),
      models.Index(fields=["up", "down", "type"]),
    ]

  def __str__(self):
    try:
      return str(self.up) + ' is ' + self.type + ' of ' + str(self.down)
    except Exception as e:
      print(str(e))
      return 'FamilyRelation object ' + str(self.id)

  @property
  def types(self):
    return dict(self.RELATION_CHOICES)

