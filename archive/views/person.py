from django.views import generic
from django.views.generic.edit import CreateView, DeleteView, UpdateView, FormView

#from django.urls import reverse, reverse_lazy
from django.shortcuts import get_object_or_404, redirect
#from django.template.defaultfilters import slugify
from django.db.models import Q
from django.conf import settings
from django.contrib import messages

from django.contrib.auth.mixins import PermissionRequiredMixin

from math import floor

from archive.models import Person, FamilyRelations

class PersonView(generic.DetailView):
  model = Person
  template_name = 'archive/people/detail.html'

class PersonListView(generic.ListView):
  model = Person
  template_name = 'archive/people/list.html'
  context_object_name = 'people'
  filters = {
    'has_photo': False,
    'year': None,
    'decade': None,
    'century': None,
    'family': None,
  }
  def getFilters(self):
    filters = {}
    for filter, default in self.filters.items():
      if self.request.GET.get(filter):
        if self.request.GET.get(filter).lower() == 'true':
          filters[filter] = True
        elif self.request.GET.get(filter).lower() in ['false', 'none', 'all']:
          filters[filter] = False
        else: 
          try:
            filters[filter] = int(self.request.GET.get(filter))
            if filter == 'decade':
              filters[filter] = floor(filters[filter]/10)*10
            elif filter =='century':
              filters[filter] = floor(filters[filter]/100)*100
          except:
            filters[filter] = self.request.GET.get(filter)
      else:
        filters[filter] = default
    return filters

  def hasActiveFilters(self):
    for key, value in self.getFilters().items():
      if value not in [False, None]:
        return True
    return False
  
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['has_active_filters'] = self.hasActiveFilters()
    context['filters'] = self.getFilters()
    
    context['available_centuries'] = self.get_centuries()
    context['available_decades'] = self.get_decades()
    context['available_families'] = settings.FAMILIES
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
    return context

  def get_queryset(self):
    filters = self.getFilters()
    queryset = Person.objects.all()
    ''' Only show members in family '''
    if filters['family']:
      queryset = queryset.filter(last_name__iexact=filters['family']) | queryset.filter(married_name__iexact=filters['family'])
    ''' Only show results with photo '''
    if filters['has_photo']:
      queryset = queryset.filter(~Q(images=None))
    ''' Show results based on year, decade or century '''
    if filters['year']:
      ''' Use ?year=1234 to see all people who lived in this year'''
      queryset =  queryset.filter(year_of_birth__lte=filters['year']).filter(year_of_death__gte=filters['year']) | \
                  queryset.filter(year_of_birth__lte=filters['year']).filter(year_of_death=None)
      queryset =  queryset.exclude(year_of_birth__lte=filters['year']-80)
    elif filters['decade']:
      ''' Use ?decade=1980 to see al people who lived in this decade
          Do not mix with ?year=
      '''
      queryset = queryset.exclude(year_of_birth__gt=filters['decade']+9).\
                          exclude(year_of_death__lte=filters['decade']).\
                          filter(year_of_birth__gte=filters['decade']-90)
    elif filters['century']:
      ''' Use ?century=1980 to see al people who lived in this century
          Do not mix with ?year= or ?decade
      '''
      queryset = queryset.exclude(year_of_birth__gt=filters['century']+99).\
                          exclude(year_of_death__lte=filters['century']).\
                          filter(year_of_birth__gte=filters['century']-90)
    ''' Overall ordering '''
    queryset = queryset.order_by('last_name', 'first_name')
    return queryset

  def get_centuries(self):
    decades = []
    for year in Person.objects.all().values_list('year_of_birth'):
      if year[0]:
        decade = floor(int(year[0])/100)*100
        if not decade in decades:
          decades.append(decade)
    decades.sort()
    return decades
  def get_decades(self):
    centuries = []
    for year in Person.objects.all().values_list('year_of_birth'):
      if year[0]:
        year = floor(int(year[0])/10)*10
        if not year in centuries:
          centuries.append(year)
    centuries.sort()
    return centuries

class EditPersonView(PermissionRequiredMixin, UpdateView):
  model = Person
  permission_required = 'archive.change_person'
  template_name = 'archive/people/edit.html'
  fields = ['first_name', 'given_names', 'last_name', 'married_name', 'nickname', 
            'day_of_birth', 'month_of_birth', 'year_of_birth', 'place_of_birth', 
            'day_of_death', 'month_of_death', 'year_of_death', 'place_of_death',
            'moment_of_death_unconfirmed',
            'bio',]
  
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['available_relations'] = Person.objects.all()
    return context

  def get_form(self):
    if self.request.user == self.get_object().related_user:
      self.fields.append('email')
    form = super(EditPersonView, self).get_form()
    return form

  def form_valid(self, form):
    return super().form_valid(form)

class AddPersonView(PermissionRequiredMixin, CreateView):
  permission_required = 'archive.add_person'
  template_name = 'archive/people/edit.html'
  model = Person
  fields = ['first_name', 'given_names', 'last_name', 'married_name', 'nickname', 
            'day_of_birth', 'month_of_birth', 'year_of_birth', 'place_of_birth', 
            'day_of_death', 'month_of_death', 'year_of_death', 'place_of_death',
            'moment_of_death_unconfirmed',
            'bio',]
  
  def form_valid(self, form):
    form.instance.user = self.request.user
    return super().form_valid(form)

## Special views
# Renamed MyPersonDetails to PersonUserView
class PersonUserView(generic.DetailView):
  permission_required = 'archive.view_person'
  model = Person
  def get(self, request, *args, **kwargs):
    if 'username' in  self.kwargs:
      person = get_object_or_404(Person, related_user__username=self.kwargs['username'])
    # If no username is supplied, assume current logged in user
    else:
      person = Person.objects.get(related_user=self.request.user)
    return redirect('archive:person', person.id, person.slug )

# Renamed PersonRedirect to PersonRedirectView
class PersonRedirectView(generic.DetailView):
  def get(self, request, *args, **kwargs):
    # Redirect to document with slug
    person = Person.objects.get(pk=self.kwargs['pk'])
    return redirect('archive:person', person.id, person.slug )

class PersonRemoveRelationView(PermissionRequiredMixin, generic.DetailView):
  permission_required = 'archive.change_person'
  def get(self, request, *args, **kwargs):
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

class PersonAddRelationView(PermissionRequiredMixin, CreateView):
  permission_required = 'archive.change_person'

  def post(self, request, *args, **kwargs):
    subject = Person.objects.get(pk=self.request.POST.get('subject'))
    type = self.request.POST.get('type').lower()
    person = Person.objects.get(pk=self.request.POST.get('person'))
    vertaling = {
      'parent': 'ouder',
      'child': 'kind',
      'partner': 'partner',
    }
    if type == 'parent':
      try:
        relation = FamilyRelations(up_id=person.id, down_id=subject.id, type='parent')
        relation.save()
      except:
        messages.add_message(self.request, messages.ERROR, f"Kan \"{ person }\" niet als ouder toevoegen van \"{ subject }\".")
        return redirect('archive:person-edit', subject.id )
    elif type == 'child':
      try:
        relation = FamilyRelations(up_id=subject.id, down_id=person.id, type='parent')
        relation.save()
      except:
        messages.add_message(self.request, messages.ERROR, f"Kan \"{ person }\" niet als kind toevoegen van \"{ subject }\".")
        return redirect('archive:person-edit', subject.id )
    elif type == 'partner':
      try:
        relation = FamilyRelations(up_id=subject.id, down_id=person.id, type='partner')
        relation.save()
      except:
        messages.add_message(self.request, messages.ERROR, f"Kan \"{ person }\" niet als partner toevoegen van \"{ subject }\".")
        return redirect('archive:person-edit', subject.id ) 

    messages.add_message(self.request, messages.SUCCESS, f"\"{ person }\" is { vertaling[type] } van \"{ subject }\"")
    return redirect('archive:person-edit', subject.id )
  