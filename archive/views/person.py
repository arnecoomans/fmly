from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, UpdateView
from django.urls import reverse_lazy, reverse
from django.shortcuts import redirect
from django.conf import settings
from django.contrib import messages
from django.template.defaultfilters import slugify
from django.db.models import (
    IntegerField,
    Value,
    Case,
    When,
    Exists,
    OuterRef,
    Q,
    F,
    Subquery,
  )
from django import http
from django.db.models.functions import Coalesce

from django.contrib.auth.mixins import PermissionRequiredMixin
from datetime import date
from math import floor

from ..person_utils import get_person_filters, get_centuries, get_decades

from archive.models import Person, FamilyRelations, Image, Event

from cmnsd.views.cmnsd_filter import FilterMixin
from cmnsd.views.utils__request import RequestMixin
from cmnsd.views.utils__response import ResponseMixin
from cmnsd.views.utils__messages import MessageMixin

''' Class Functions '''
''' get_fields()
    Returns a list of fields to use in formsets
'''
def get_fields():
  return ['first_names', 'given_name', 'last_name', 'married_name', 'nickname', 'gender',
          'moment_of_death_unconfirmed',
          'bio', 'private']


''' PersonView
    PersonView is actually a ListView of model Images. This allows for query adaptation such
    as show/hide hidden and pagination.
    The Person is added via Context.
'''
class PersonView(ListView):
  model = Image
  template_name = 'archive/people/detail.html'
  paginate_by = settings.PAGINATE
  added_context = {}
  
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_page'] = 'people'
    ''' Add Person to the context
        In a normal situation you'd expect this to be a DetailView. But the larger part 
        of the person detail view is the related images view. 
        So this is where the person-object is added to the related data.
    '''
    context['person'] = Person.objects.get(pk=self.kwargs['pk'])
    ''' Add additional context created by the get_queryset actions'''
    if len(self.added_context) > 0:
      for key in self.added_context:
        context[key] = self.added_context[key]
    context['ajax'] = {}
    for key in getattr(settings, 'AJAX_MODES', []):
      if key in self.request.GET.keys():
        context['ajax'][key] = True
    return context
  
  ''' show_hidden_files()
      Checks if current user has prerence entry. 
      If user has preferences, it returns the show_hidden_files-prefence of the user.
      Then it checks if the current default or preference should be overridden with the 
      request querystring ?hidden=true/false.
      This allows to start off with the default value or user preference, and override with
      request querystring.
  '''
  def show_hidden_files(self) -> bool:
    result = False
    if hasattr(self.request.user, 'preference'):
      if self.request.user.preference.show_hidden_files == True:
        result = True
    if self.request.GET.get('hidden'):
      if self.request.GET.get('hidden').lower() == 'true':
        result = True
      elif self.request.GET.get('hidden').lower() == 'false':
        result = False
    return result

  ''' Return filtered queryset with Images for this Person '''
  def get_queryset(self):
    ''' Fetch images with Person in field people '''
    queryset = Image.objects.filter(people=Person.objects.get(pk=self.kwargs['pk']))
    ''' Always remove deleted images '''
    queryset = queryset.filter(status='p')
    ''' Show or hide hidden files '''
    if not self.show_hidden_files():
      if queryset.filter(visibility_frontpage=False).count() > 0:
        self.added_context['images_hidden'] = queryset.filter(visibility_person_page=False).count()
        queryset = queryset.exclude(visibility_person_page=False)
      else:
        self.added_context['images_hidden'] =  False
    else:
      self.added_context['images_hidden'] = queryset.filter(visibility_person_page=False).count() * -1
    self.added_context['count_images'] = queryset.count()
    ''' Order images '''
    queryset = queryset.order_by('date_created')
    ''' Return result '''
    return queryset

''' PersonListView
    Display a list of people, grouped by family (Last_name or Married_name)
    Allows for additional filtering
'''
class PersonListView(FilterMixin, RequestMixin, ListView):
  model = Person
  template_name = 'archive/people/list.html'
  context_object_name = 'people'
  ''' Filters and their default values '''
  translate_orderby = {
    'last_name': 'achternaam',
    'first_names': 'voornaam',
  }

  ''' Check if a current filters are different than default values '''
  def hasActiveFilters(self):
    for value in self.getFilters().values():
      if value not in [False, None]:
        return True
    return False
  
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_page'] = 'people'
    context['filters'] = get_person_filters(self.request)
    context['deactivated_filters'] = []
    context['available_centuries'] = get_centuries(self.get_queryset())
    context['available_decades'] = get_decades(self.get_queryset())
    context['available_families'] = settings.FAMILIES
    #context['all_people'] = Person.objects.all()
    ''' Page description
        is dynamically describing active filters
    '''
    context['page_description'] = f'Overzicht van {str(self.get_queryset().count())} personen in de familie'
    if context['filters']['family']:
      context['page_description'] += f" {str(context['filters']['family'])[:1].upper()}{str(context['filters']['family'])[1:].lower()}"
    if context['filters']['has_photo']:
      context['page_description'] += f" met afbeelding gekoppeld"
    if context['filters']['year']:
      context['page_description'] += f" in leven in {str(context['filters']['year'])}"
    elif context['filters']['decade']:
      context['page_description'] += f" in leven tussen {str(context['filters']['decade'])} en {str(context['filters']['decade']+9)}"
    elif context['filters']['century']:
      context['page_description'] += f" in leven tussen {str(context['filters']['century'])} en {str(context['filters']['century']+99)}"
    if context['filters']['search']:
      context['page_description'] += f" en met zoekterm \"{ context['filters']['search'] }\""
    if context['filters']['order_by']:
      context['page_description'] += f" gesorteerd op \"{ self.translate_orderby[context['filters']['order_by']]}\""
    return context

  def get_queryset(self):
    # Return cached queryset if available
    if hasattr(self, 'queryset') and self.queryset is not None:
      return self.queryset
    # Build initial queryset
    self.queryset = Person.objects.all()
    self.queryset = self.filter(self.queryset, mapping={})
    self.queryset = self.queryset.distinct().order_by('last_name', 'first_names')
    return self.queryset
    


''' Edit Person '''
class EditPersonView(PermissionRequiredMixin, UpdateView):
  model = Person
  permission_required = 'archive.change_person'
  template_name = 'archive/people/edit.html'
  redirect_to_edit = False

  ''' Use get_fields() as general function in this file to maintain fields in one spot '''
  fields = get_fields()
  
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_page'] = 'people'
    return context
  
  ''' Build form '''
  def get_form(self):
    ''' If person has related user, add e-mail as field '''
    if self.request.user == self.get_object().related_user:
      self.fields.append('email')
    form = super(EditPersonView, self).get_form()
    return form

''' Add Person view '''
class AddPersonView(PermissionRequiredMixin, CreateView):
  permission_required = 'archive.add_person'
  template_name = 'archive/people/edit.html'
  model = Person
  ''' Use get_fields() as general function in this file to maintain fields in one spot '''
  fields = get_fields()

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_page'] = 'people'
    return context

  def form_valid(self, form):
    form.instance.user = self.request.user
    return super().form_valid(form)
  
  def get_success_url(self):
    return reverse_lazy('archive:person-edit', kwargs={'pk': self.object.id})

''' Redirect View
    Redirect calls to person by only id to id and slug
'''
class PersonRedirectView(DetailView):
  def get(self, request, *args, **kwargs):
    # Redirect to document with slug
    person = Person.objects.get(pk=self.kwargs['pk'])
    return redirect('archive:person', person.id, person.slug )

''' Family Relations
    Family Relations are stored in a seperate model where it is stored that
    Person A is related by type to Person B.
    Available types are parent and partner.
    Children are stored by inverting the parent relation.
'''
''' Family Relation: Add Relation '''
class PersonAddRelationView(PermissionRequiredMixin, CreateView):
  permission_required = 'archive.change_person'

  def post(self, request, *args, **kwargs):
    ''' Process input '''
    subject = Person.objects.get(pk=self.request.POST.get('subject'))
    type = self.request.POST.get('type').lower()
    person = Person.objects.get(pk=self.request.POST.get('person'))
    ''' Translate table for relation to relation type'''
    vertaling = {
      'parent': 'ouder',
      'child': 'kind',
      'partner': 'partner',
      'sibling': 'broer/zus',
    }
    ''' Creating relations is caught in a try, to catch restrictions such as existing relations 
        The exception triggers a message to the user and a redirect to the edit page, not saving changes.
    '''
    if type == 'parent':
      ''' Add Parent Relation '''
      ''' Check age difference before adding relation '''
      # if person.year_of_birth and subject.year_of_birth:
      #   message = None
      #   if person.year_of_birth > subject.year_of_birth:
      #     ''' Check age difference before adding relation '''
      #     message = f"{ person.first_names } ({ person.year_of_birth }) was nog niet geboren toen { subject.first_names } ({ subject.year_of_birth }) werd geboren"
      #   elif person.year_of_birth + 12 > subject.year_of_birth:
      #     ''' Parent was under 12 when child was born '''
      #     message = f"{ person.first_names } ({ person.year_of_birth }) is te jong om ouder te zijn van { subject.first_names } ({ subject.year_of_birth })"
      #   elif subject.year_of_birth - person.year_of_birth > 80:
      #     ''' Parent was over 80 when child was born '''
      #     message = f"{ person.first_names } ({ person.year_of_birth }) is te oud om ouder te zijn van { subject.first_names } ({ subject.year_of_birth })"
      #   if message:
      #     messages.add_message(self.request, messages.WARNING, f"Relatie kan niet worden toegevoegd: { message }.")
      #     return redirect('archive:person-edit', subject.id )
      try:
        relation = FamilyRelations(up_id=person.id, down_id=subject.id, type='parent')
        relation.save()
      except:
        messages.add_message(self.request, messages.ERROR, f"Kan \"{ person }\" niet als ouder toevoegen van \"{ subject }\".")
        return redirect('archive:person-edit', subject.id )
    elif type == 'child':
      ''' Add Child Relation '''
      ''' Check age difference before adding relation '''
      # if person.year_of_birth and subject.year_of_birth:
      #   message = None
      #   if subject.year_of_birth > person.year_of_birth:
      #     ''' Child was born before parent '''
      #     message = f"{ subject.first_names } ({ subject.year_of_birth }) was nog niet geboren toen { person.first_names } ({ person.year_of_birth }) werd geboren"
      #   elif subject.year_of_birth + 12 > person.year_of_birth:
      #     ''' Parent was under 12 when child was born '''
      #     message = f"{ subject.first_names } ({ subject.year_of_birth }) is te jong om ouder te zijn van { person.first_names } ({ person.year_of_birth })"
      #   elif person.year_of_birth - subject.year_of_birth > 80:
      #     ''' Parent was over 80 when child was born '''
      #     message = f"{ subject.first_names } ({ subject.year_of_birth }) is te oud om ouder te zijn van { person.first_names } ({ person.year_of_birth })"
      #   if message:
      #     messages.add_message(self.request, messages.WARNING, f"Relatie kan niet worden toegevoegd: { message }.")
      #     return redirect('archive:person-edit', subject.id )
      ''' Proceed with setting relation '''
      try:
        relation = FamilyRelations(up_id=subject.id, down_id=person.id, type='parent')
        relation.save()
      except:
        messages.add_message(self.request, messages.ERROR, f"Kan \"{ person }\" niet als kind toevoegen van \"{ subject }\".")
        return redirect('archive:person-edit', subject.id )
    elif type == 'sibling':
      ''' Add Sibling relation by adding shared parents '''
      for parent in person.get_parents():
        try:
          relation = FamilyRelations(up_id=parent.id, down_id=subject.id, type='parent')
          relation.save()
          messages.add_message(self.request, messages.SUCCESS, f"\"{ parent }\" is nu ouder van \"{ subject }\".")
        except:
          messages.add_message(self.request, messages.ERROR, f"Kan \"{ parent }\" niet als ouder toevoegen van \"{ subject }\".")
          return redirect('archive:person-edit', subject.id )

    elif type == 'partner':
      ''' Add Partner relation'''
      ''' Check if both person and subject were alive during their relationship '''
      # if person.year_of_birth and subject.year_of_birth and person.year_of_death and subject.year_of_death:
      #   ''' if person died before subject was born or subject died before person was born '''
      #   if person.year_of_birth > subject.year_of_death or subject.year_of_birth > person.year_of_death:
      #     message = f"{ subject.first_names } ({ subject.year_of_birth }) en { person.first_names } ({ person.year_of_birth }) leefden niet tegelijkertijd."
      #     messages.add_message(self.request, messages.WARNING, f"Relatie kan niet worden toegevoegd: { message }.")
      #     return redirect('archive:person-edit', subject.id )
      ''' Proceed with setting relation '''
      try:
        relation = FamilyRelations(up_id=subject.id, down_id=person.id, type='partner')
        relation.save()
      except:
        messages.add_message(self.request, messages.ERROR, f"Kan \"{ person }\" niet als partner toevoegen van \"{ subject }\".")
        return redirect('archive:person-edit', subject.id ) 
    ''' No errors and redirects have been made, so notifuy user of succesful creation '''
    messages.add_message(self.request, messages.SUCCESS, f"\"{ person }\" is { vertaling[type] } van \"{ subject }\"")
    return redirect('archive:person-edit', subject.id )

''' Family Relation: Remove Relation '''
class PersonRemoveRelationView(PermissionRequiredMixin, DetailView):
  permission_required = 'archive.change_person'

  def get(self, request, *args, **kwargs):
    ''' Process input'''
    subject = Person.objects.get(pk=kwargs['subject'])
    type = kwargs['type'].lower()
    removed_person = Person.objects.get(pk=kwargs['removed_person'])
    
    if type == 'parent':
      try:
        relation = FamilyRelations.objects.get(up_id=removed_person.id, down_id=subject.id, type=type)
        messages.add_message(self.request, messages.SUCCESS, f"\"{ removed_person }\" verwijderd als ouder van \"{ subject }\".")
        relation.delete()
      except:
        messages.add_message(self.request, messages.WARNING, f"Fout! Kan relatie tussen \"{ removed_person }\" en \"{ subject }\" niet verwijderen.")
    elif type == "child":
      try:
        relation = FamilyRelations.objects.get(up_id=subject.id, down_id=removed_person.id, type='parent')
        messages.add_message(self.request, messages.SUCCESS, f"\"{ subject }\" verwijderd als ouder van \"{ removed_person }\".")
        relation.delete()
      except:
        messages.add_message(self.request, messages.WARNING, f"Fout! Kan relatie tussen \"{ removed_person }\" en \"{ subject }\" niet verwijderen.")
    elif type == 'sibling':
      pass # @TODO
    elif type == 'partner':
      try:
        relation = FamilyRelations.objects.get(up_id=removed_person.id, down_id=subject.id, type=type)
      except FamilyRelations.DoesNotExist:
        relation = FamilyRelations.objects.get(up_id=subject.id, down_id=removed_person.id, type=type)
      try:
        relation.delete()
      except:
        messages.add_message(self.request, messages.WARNING, f"Fout! Kan relatie tussen \"{ removed_person }\" en \"{ subject }\" niet verwijderen.")
      else:
        messages.add_message(self.request, messages.SUCCESS, f"\"{ removed_person }\" verwijderd als partner van \"{ subject }\".")
    return redirect('archive:person-edit', subject.id )

class RemovePortraitView(PermissionRequiredMixin, DetailView):
  model = Person
  permission_required = 'archive.change_person'

  def get(self, request, *args, **kwargs):
    person = Person.objects.get(pk=kwargs['subject'])
    image = Image.objects.get(pk=kwargs['removed_image'])
    image.is_portrait_of = None
    image.save()
    messages.add_message(self.request, messages.SUCCESS, f"\"{ image }\" verwijderd als portret van \"{ person }\".")
    return redirect(reverse('archive:image-edit', kwargs={'pk':image.id}))


class SuggestFamilyView(RequestMixin, FilterMixin, ResponseMixin, MessageMixin, DetailView):
  model = Person

  def get_suggestions(self):
    qs = Person.objects.all()
    # Apply search and visibility filters
    qs = self.filter(qs)
    # Remove self
    qs = qs.exclude(pk=self.get_object().pk)
    print(f"Suggestions before family filtering: {qs.count()}")
    # Remove family members
    if self.request.GET.get('exclude_family', 'false').lower() == 'true':
      print('Excluding family members')
      qs = qs.exclude(pk__in=self.get_object().get_family().values_list('pk', flat=True))
    elif self.request.GET.get('limit_to_family', 'false').lower() == 'true':
      print('Limiting to family members')
      qs = qs.filter(pk__in=self.get_object().get_family().values_list('pk', flat=True))
    # Apply Relevance ordering
    print(f"Suggestions before relevance filtering: {qs.count()}")
    qs = self.with_relevance(qs)
    print(f"Suggestions after relevance filtering: {qs.count()}")
    # Order by relevance
    qs = qs.order_by('-relevance', 'last_name', 'first_names')
    return qs

  def with_relevance(self, qs):
    """
    Annotate a queryset of Person objects with a computed `relevance` score.

    Relevance rules (each adds +1 point):
      1. Person shares the same last name as the subject.
      2. Person was alive at any point during the subject's lifespan.
      3. Person shares an indirect family member with the subject
        (e.g. shared parent or family overlap), excluding direct relations
        which are assumed to be filtered out beforehand.

    The resulting queryset is ordered by descending relevance.

    Args:
      qs (QuerySet): A queryset of Person objects.

    Returns:
      QuerySet: The annotated and ordered queryset.
    """
    PersonModel = self.__class__

    # --------------------------------------------------
    # Subject birth / death (single-row subqueries)
    # --------------------------------------------------
    subject_birth = (
      Event.objects
      .filter(people=self.get_object(), type="birth")
      .values("year")[:1]
    )

    subject_death = (
      Event.objects
      .filter(people=self.get_object(), type="death")
      .values("year")[:1]
    )

    # --------------------------------------------------
    # Candidate birth / death (per-row subqueries)
    # --------------------------------------------------
    candidate_birth = (
      Event.objects
      .filter(people=OuterRef("pk"), type="birth")
      .values("year")[:1]
    )

    candidate_death = (
      Event.objects
      .filter(people=OuterRef("pk"), type="death")
      .values("year")[:1]
    )

    # --------------------------------------------------
    # Shared family (indirect relationship)
    # --------------------------------------------------
    self_parents = FamilyRelations.objects.filter(
      type="parent",
      down_id=self.get_object().pk,
    ).values("up_id")

    shared_family = FamilyRelations.objects.filter(
      type="parent",
      up_id__in=Subquery(self_parents),
      down_id=OuterRef("pk"),
    )

    # --------------------------------------------------
    # Start relevance annotation
    # --------------------------------------------------
    qs = qs.annotate(
      relevance=Value(0, output_field=IntegerField()),
    )

    # +1 if same last name
    qs = qs.annotate(
      relevance=F("relevance") + Case(
        When(last_name=self.get_object().last_name, then=Value(1)),
        default=Value(0),
        output_field=IntegerField(),
      )
    )

    # Add birth/death year annotations
    qs = qs.annotate(
      candidate_birth_year=Subquery(candidate_birth, IntegerField()),
      candidate_death_year=Subquery(candidate_death, IntegerField()),
      subject_birth_year=Subquery(subject_birth, IntegerField()),
      subject_death_year=Subquery(subject_death, IntegerField()),
    )

    # +1 if alive during subject's lifespan
    qs = qs.annotate(
      candidate_death_year_norm=Coalesce("candidate_death_year", Value(9999)),
      subject_death_year_norm=Coalesce("subject_death_year", Value(9999)),
    )

    qs = qs.annotate(
      relevance=F("relevance") + Case(
        When(
          candidate_birth_year__lte=F("subject_death_year_norm"),
          candidate_death_year_norm__gte=F("subject_birth_year"),
          then=Value(1),
        ),
        default=Value(0),
        output_field=IntegerField(),
      )
    )

    # +1 if shared indirect family member
    qs = qs.annotate(
      relevance=F("relevance") + Case(
        When(Exists(shared_family), then=Value(1)),
        default=Value(0),
        output_field=IntegerField(),
      )
    )
    # Return annotated queryset
    return qs
  
  def get(self, request, *args, **kwargs):
    person = self.get_object()
    context = {
      'person': person,
      'people': self.get_suggestions(),
    }
    template_names = ['model/people.json',]
    
    rendered_field = self.render(format='json', context=context, template_names=template_names)
    return self.return_response(payload={'people': rendered_field})