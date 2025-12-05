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

from .Event import Event

from cmnsd.models.cmnsd_basemodel import BaseModel, VisibilityModel
from cmnsd.models.cmnsd_basemethod import ajax_function, searchable_function


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
  place_of_birth      = models.CharField(max_length=255, blank=True)
  place_of_death      = models.CharField(max_length=255, blank=True)
  # Dating
  MONTHS = [(1, 'januari'), (2, 'februari'), (3, 'maart'), (4, 'april'), (5, 'mei'), (6, 'juni'), (7, 'juli'), (8, 'augustus'), (9, 'september'), (10, 'oktober'), (11, 'november'), (12, 'december')]
  date_of_birth       = models.DateField(null=True, blank=True, help_text='Format: year-month-date, for example 1981-08-11')
  year_of_birth       = models.PositiveSmallIntegerField(blank=True, null=True, help_text='Is automatically filled when date is supplied')
  month_of_birth      = models.PositiveSmallIntegerField(blank=True, null=True, help_text='', choices=MONTHS)
  day_of_birth        = models.PositiveSmallIntegerField(blank=True, null=True, help_text='', validators=[MaxValueValidator(31), MinValueValidator(1)])
  date_of_death       = models.DateField(null=True, blank=True, help_text='Format: year-month-date, for example 1981-08-11')
  year_of_death       = models.PositiveSmallIntegerField(blank=True, null=True, help_text='Is automatically filled when date is supplied')
  month_of_death      = models.PositiveSmallIntegerField(blank=True, null=True, help_text='', choices=MONTHS)
  day_of_death        = models.PositiveSmallIntegerField(blank=True, null=True, help_text='')

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
    if len(self.get_lifespan()) > 0:
      name += f" ({ self.get_lifespan() })"
    return name

  @property
  def months(self):
    return self.MONTHS
  @property
  def genders(self):
    return self.GENDERS
  
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
      'date_of_birth': self.date_of_birth,
      'date_of_death': self.date_of_death,
      'year_of_birth': self.year_of_birth,
      'year_of_death': self.year_of_death,
      'month_of_birth': self.month_of_birth,
      'month_of_death': self.month_of_death,
      'day_of_birth': self.day_of_birth,
      'day_of_death': self.day_of_death,
      'moment_of_death_unconfirmed': self.moment_of_death_unconfirmed,
    }
  
  def name(self):
    return ' '.join([self.first_names, self.last_name])

  def full_name(self):
    if self.private:
      return ' '.join([self.first_names, self.last_name]).strip()
    else:
      value = self.first_names
      if self.given_name:
        value += f" ({ self.given_name})"
      if self.married_name:
        value += f" { self.married_name } - { self.last_name }"
      else:
        value += f" { self.last_name }"
      return value.strip()
  
  def short_name(self):
    if self.given_name:
      return f"{ self.given_name } { self.last_name }"
    return f"{ self.first_names.split(' ')[0] } { self.last_name }"
  
  @searchable_function
  def century(self):
    if self.year_of_birth:
      return floor(self.year_of_birth/100)*100
  @searchable_function
  def decade(self):
    if self.year_of_birth:
      return floor(self.year_of_birth/10)*10
  
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
  
  
  ## Life Events
  def get_major_events(self):
    events = (
      self.events
      .annotate(
        effective_importance_db=Coalesce('importance', F('type__importance'))
      )
      .filter(effective_importance_db__gte=1)
    )
    return events.order_by('year', 'month', 'day').distinct()
  
  def get_all_events(self):
    events = self.events.all()
    print("Starting events", events)
    for parent in self.get_parents() or []:
      events = events | parent.events.filter(type__slug='birth') | parent.events.filter(type__slug='death')
      print(events)
    for partner in self.get_partners() or []:
      events = events | partner.events.filter(type__slug='death')
    for child in self.get_children() or []:
      events = events | child.events.filter(type__slug='birth') | child.events.filter(type__slug='death')
    events = events |Event.objects.filter(type__is_global=True)
    events = events.filter(year__gte=self.year_of_birth or 0, year__lte=self.year_of_death or datetime.datetime.now().year+1)
    return events.order_by('year', 'month', 'day').distinct()
  
  @ajax_function
  def get_date_of_birth(self):
    if self.events.filter(type='birth').exists():
      event = self.events.filter(type='birth').first()
      return datetime.date(year=event.year, month=event.month or 1, day=event.day or 1)
  
  @ajax_function
  def get_date_of_death(self):
    if self.events.filter(type='death').exists():
      event = self.events.filter(type='death').first()
      return datetime.date(year=event.year, month=event.month or 1, day=event.day or 1)
  
  def birth(self):
    return self.events.filter(type='birth').first()
  def death(self):
    return self.events.filter(type='death').first()
  
  @ajax_function
  def event(self, event__id, event__token):
    try:
      event = self.events.filter(id=event__id, token=event__token).first()
      return event
    except:
      return 'FOO'
    
  def get_lifespan(self):
    lifespan = ''
    if self.year_of_birth:
      lifespan += str(self.year_of_birth)
    if self.year_of_death or self.moment_of_death_unconfirmed:
      lifespan += ' - '
    if self.year_of_death:
      lifespan += str(self.year_of_death)
    return lifespan

  def get_lifespan_display(self):
    lifespan = ''
    if self.date_of_birth:
      lifespan += self.date_of_birth.strftime('%d-%m-%Y')
    elif self.year_of_birth:
      lifespan += str(self.year_of_birth)
    if self.place_of_birth:
      lifespan += f" ({ self.place_of_birth })"
    if self.date_of_death or self.year_of_death or self.moment_of_death_unconfirmed:
      lifespan += ' - '
    if self.date_of_death:
      lifespan += self.date_of_death.strftime('%d-%m-%Y')
    elif self.year_of_death:
      lifespan += str(self.year_of_death)
    if self.place_of_death:
      lifespan += f" ({ self.place_of_death })"
    return lifespan
  
  def has_dates(self):
    if self.date_of_birth or self.month_of_birth or self.year_of_birth or self.place_of_birth or \
       self.date_of_death or self.month_of_death or self.year_of_death or self.place_of_death:
      return True
    return False
  

  def ageatdeath(self):
    if self.date_of_birth and self.date_of_death:
      age = self.date_of_death.year - self.date_of_birth.year
      age -= ((self.date_of_birth.month, self.date_of_birth.day) <
         (self.date_of_birth.month, self.date_of_birth.day))
      return age
    elif self.year_of_birth and self.year_of_death:
      return self.year_of_death - self.year_of_birth

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

  def get_parents(self, person=None):
    if not person:
      person = self
    if person.relation_up:
      parents = []
      for parent in person.relation_up.filter(type='parent').order_by('up__year_of_birth'):
        parent.up.relation_id = parent.id
        parents.append(parent.up)
      return parents
  def get_father(self):
    if self.relation_up:
      for parent in self.relation_up.filter(type='parent', up__gender='m').order_by('up__year_of_birth'):
        return parent.up
  def get_mother(self):
    if self.relation_up:
      for parent in self.relation_up.filter(type='parent', up__gender='f').order_by('up__year_of_birth'):
        return parent.up
  
  ''' get_children()
      Childern have a simple relation
      down is child of parent up
  '''
  def get_children(self, person=None):
    if not person:
      person = self
    if person.relation_down:
      children = []
      for child in person.relation_down.filter(type='parent').order_by('down__year_of_birth'):
        child_obj = child.down
        child_obj.relation_id = child.id
        children.append(child_obj)
      return children
  
  ''' get_partners()
      partners have a two-sided relation
      a is partner of b, or b is partner of a
  '''
  def get_partners(self, person=None):
    if not person:
      person = self
    if person.relation_down:
      partners = []
      ''' Partner is the other parent of a child '''
      for child in self.get_children():
        for parent in self.get_parents(child):
          if parent not in partners and parent != person:
            # A relation is assumed because of shared parentage,
            # but relation_id is assigned in get_parents(). 
            # Force to None here.
            parent.relation_id = None
            partners.append(parent)
      ''' Partner is also found by relation type=partner '''
      for partner in person.relation_up.filter(type='partner'):
        if partner.up not in partners:
          partner_obj = partner.up
          partner_obj.relation_id = partner.id
          partners.append(partner_obj)
      for partner in person.relation_down.filter(type='partner'):
        if partner.down not in partners:
          partner_obj = partner.down
          partner_obj.relation_id = partner.id
          partners.append(partner_obj)
      return partners

  ''' get_siblings
      siblings have a two-hop relation:
      for each parent, fetch children
  '''
  def get_siblings(self, person=None):
    if not person:
      person = self
    if person.relation_up:
      siblings = []
      for parent in self.get_parents():
        for child in self.get_children(parent):
          if child not in siblings and child != person:
            child.relation_id = child.id
            siblings.append(child)
      return siblings
  
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

  def __str__(self):
    try:
      return str(self.up) + ' is ' + self.type + ' of ' + str(self.down)
    except Exception as e:
      print(str(e))
      return 'FamilyRelation object ' + str(self.id)

  @property
  def types(self):
    return dict(self.RELATION_CHOICES)

