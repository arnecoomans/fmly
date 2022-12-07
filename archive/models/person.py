from django.db import models
from django.urls import reverse, reverse_lazy
from django.contrib.auth.models import User
from django.template.defaultfilters import slugify


class Person(models.Model):
  first_name          = models.CharField(max_length=255, blank=True, verbose_name='Roepnaam')
  given_names         = models.CharField(max_length=255, blank=True, verbose_name='Voornamen', help_text='Alle voornamen, inclusief roepnaam')
  last_name           = models.CharField(max_length=255, blank=True, verbose_name='Achternaam', help_text='Achternaam bij geboorte')
  married_name        = models.CharField(max_length=255, blank=True, verbose_name='Getrouwde Achternaam', help_text='Achternaam van echtgeno(o)t(e)')

  nickname            = models.CharField(max_length=255, blank=True, verbose_name='Bijnaam')
  email               = models.EmailField(blank=True, help_text='Dit veld is alleen zichtbaar voor jou en voor de site-beheerder(s). Vul je e-mailadres in zodat we je een wachtwoord-reset email kunnen sturen als je niet langer kan inloggen.')
  slug                = models.CharField(max_length=255, unique=True)
  # Information
  place_of_birth      = models.CharField(max_length=255, blank=True)
  place_of_death      = models.CharField(max_length=255, blank=True)
  # Dating
  date_of_birth       = models.DateField(null=True, blank=True, help_text='Format: year-month-date, for example 1981-08-11')
  year_of_birth       = models.PositiveSmallIntegerField(blank=True, null=True, help_text='Is automatically filled when date is supplied')
  date_of_death       = models.DateField(null=True, blank=True, help_text='Format: year-month-date, for example 1981-08-11')
  year_of_death       = models.PositiveSmallIntegerField(blank=True, null=True, help_text='Is automatically filled when date is supplied')
  moment_of_death_unconfirmed = models.BooleanField(default=False, help_text='Set True if moment of death is unknown but person has deceased.')

  # Bio
  bio                 = models.TextField(blank=True, help_text='Markdown supported')
  # Meta
  related_user        = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='related_person')
  user                = models.ForeignKey(User, on_delete=models.CASCADE)
  
  def __str__(self):
    value = self.full_name()
    if self.year_of_birth or self.year_of_death:
        value += ' ('
        value += str(self.year_of_birth) if self.year_of_birth else ' '
        value += ' - '
        value += str(self.year_of_death) if self.year_of_death else ' '
        value += ')'
    return value

  def name(self):
    return ' '.join([self.first_name, self.last_name])

  def full_name(self):
    call_sign = ''
    if self.first_name and  self.first_name not in self.given_names.split(' '):
      call_sign = '(' + self.first_name + ') '
    return ' '.join([call_sign, self.given_names, self.last_name, self.married_name])

  def get_first_name(self):
    if self.first_name:
      return self.first_name if self.first_name not in self.given_names else None
    else:
      return self.given_names

  def age(self):
    if self.date_of_birth and self.date_of_death:
      age = self.date_of_death.year - self.date_of_birth.year
      age -= ((self.date_of_birth.month, self.date_of_birth.day) <
         (self.date_of_birth.month, self.date_of_birth.day))
      return age
    elif self.year_of_birth and self.year_of_death:
      return self.year_of_death - self.year_of_birth

  # Process Family Relations
  def get_parents(self):
    if self.relation_up:
      parents = []
      for parent in self.relation_up.filter(type='parent').order_by('up__year_of_birth'):
        parents.append(parent.up)
      return parents

  def get_children(self):
    if self.relation_down:
      children = []
      for child in self.relation_down.filter(type='parent').order_by('down__year_of_birth'):
        children.append(child.down)
      return children
  
  def get_partners(self):
    if self.relation_down:
      partners = []
      for child in self.relation_down.filter(type='parent'):
        for parent in child.down.relation_up.filter(type='parent'):
          if parent.up not in partners and parent.up != self:
            partners.append(parent.up)
      for partner in self.relation_up.filter(type='partner'):
        partners.append(partner.up)
      for partner in self.relation_down.filter(type='partner'):
        partners.append(partner.down)
      return partners

  def get_siblings(self):
    if self.relation_up:
      siblings = []
      for parent in self.relation_up.filter(type='parent'):
        for child in parent.up.relation_down.all():
          if child.down not in siblings and child.down != self:
            siblings.append(child.down)
      return siblings

  class Meta:
    ordering = ('last_name', 'first_name')
  
  def get_absolute_url(self):
    return reverse('archive:person', kwargs={'pk':self.id, 'name': self.slug})
  
  def save(self, *args, **kwargs):
    # Ensure there is a first name. If no first name is mentioned,
    # use the first word from given name
    if self.given_names and not self.first_name:
      if ' ' in self.given_names:
        self.first_name = self.given_names.split()[1]
      else:
        self.first_name = self.given_names
    # Set user
    if not self.user:
      self.user = request.user
    # Automatically fill year of birth/death if date is known
    if not self.year_of_birth and self.date_of_birth:
      self.year_of_birth = int(self.date_of_birth.year)
    if not self.year_of_death and self.date_of_death:
      self.year_of_death = int(self.date_of_death.year)
    # Recalculate slug
    # Slug should be (first-name) given-names lastname (birth-death)
    slug = self.full_name()
    if self.year_of_birth or self.year_of_death:
      slug += '-'
      slug += str(self.year_of_birth) if self.year_of_birth else ''
      slug += ' - ' + str(self.year_of_death) if self.year_of_death else ''
    self.slug = slugify(slug)
    # if Person.objects.filter(slug=self.slug).count() > 1:
    #   names = self.given_names if self.given_names else self.first_name
    #   slug = ' '.join(names, self.last_name) + '('
    #   if self.year_of_birth:
    #     slug += str(self.year_of_birth)
    #   slug += '-'
    #   if self.year_of_death:
    #     slug += self.year_of_death
    #   slug += ')'
    #   self.slug = slugify(slug)

    # Pass person information to user object if linked
    if self.related_user and self.first_name:
      self.related_user.first_name = self.first_name
    if self.related_user and self.last_name:
      self.related_user.last_name = self.last_name
    if self.related_user and self.email:
      self.related_user.email = self.email
    if self.related_user:
      self.related_user.save()
    return super(Person, self).save(*args, **kwargs)

class FamilyRelations(models.Model):
  RELATION_CHOICES = [
    ('parent', 'Parent'),
    ('partner', 'Partner'),
  ]
  up                  = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='relation_down')
  down                = models.ForeignKey(Person, on_delete=models.CASCADE, related_name='relation_up')
  type                = models.CharField(choices=RELATION_CHOICES, max_length=16, default='parent')

  def __str__(self):
    return str(self.up) + ' is ' + self.type + ' of ' + str(self.down)

