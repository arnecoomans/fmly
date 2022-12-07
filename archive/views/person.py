from django.views import generic
from django.views.generic.edit import CreateView, DeleteView, UpdateView, FormView

from django.urls import reverse, reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.template.defaultfilters import slugify
from django.db.models import Q

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

from math import floor

from archive.models import Person



class PersonView(generic.DetailView):
  model = Person

class PersonListView(generic.ListView):
  model = Person
  filters = {
    'has_photo': False,
    'year': None,
    'decade': None,
    'century': None,
    'family': None,
  }

  def dispatch(self, request, *args, **kwargs):
    ''' Process filter argument and prepare these to be useful '''
    if self.request.GET.get('family'):
      if self.request.GET.get('family').lower() == 'none' or self.request.GET.get('family').lower() == 'all':
        self.filters['family'] = None
      else:
        self.filters['family'] = self.request.GET.get('family')[:1].upper() + self.request.GET.get('family')[1:].lower()
    if self.request.GET.get('has_photo'):
      self.filters['has_photo'] = True
    else:
      self.filters['has_photo'] = False
    if self.request.GET.get('year'):
      try: 
        self.filters['year'] = int(self.request.GET.get('year'))
      except:
        self.filters['year'] = None
      else:
        self.filters['decade'] = None
        self.filters['century'] = None
    elif self.request.GET.get('decade'):
      try:
        self.filters['decade'] = floor(int(self.request.GET.get('decade'))/10)*10
      except:
        self.filters['decade'] = None
      else:
        self.filters['year'] = None
        self.filters['century'] = None
    elif self.request.GET.get('century'):
      try:
        self.filters['century'] = floor(int(self.request.GET.get('century'))/100)*100
      except:
        self.filters['century'] = None
      else:
        self.filters['decade'] = None
        self.filters['year'] = None
    return super(PersonListView, self).dispatch(request, *args, **kwargs)
  
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['origin'] = 'person'
    context['page_scope'] = 'personen'
    context['filter'] = self.filters
    context['available_centuries'] = self.get_centuries()
    context['available_decades'] = self.get_decades()
    context['available_families'] = ['Coomans', 'Bake']
    #context['available_years'] = self.get_years()
    #context['dev'] = self.get_centuries()
    ''' Page description
        is dynamically describing active filters
    '''
    context['page_description'] = 'Overzicht van personen in de familie'
    if self.filters['family']:
      context['page_description'] += f" {str(self.filters['family'])}"
    if self.filters['has_photo']:
      context['page_description'] += f" met afbeelding gekoppeld"
    if self.filters['year']:
      context['page_description'] += f" in leven in {str(self.filters['year'])}"
    elif self.filters['decade']:
      context['page_description'] += f" in leven tussen {str(self.filters['decade'])} en {str(self.filters['decade']+9)}"
    elif self.filters['century']:
      context['page_description'] += f" in leven tussen {str(self.filters['century'])} en {str(self.filters['century']+99)}"
    context['page_description'] += "."
    return context

  def get_queryset(self):
    queryset = Person.objects.all()
    ''' Only show members in family '''
    if self.filters['family']:
      queryset = queryset.filter(last_name=self.filters['family']) | queryset.filter(married_name=self.filters['family'])
    ''' Only show results with photo '''
    if self.filters['has_photo']:
      queryset = queryset.filter(~Q(images=None))
    ''' Show results based on year, decade or century '''
    if self.filters['year']:
      ''' Use ?year=1234 to see all people who lived in this year'''
      queryset = queryset.filter(year_of_birth=self.filters['year']) | queryset.filter(year_of_birth__lte=self.filters['year']).filter(year_of_death__gte=self.filters['year']) | queryset.filter(year_of_birth__lte=self.filters['year']).filter(year_of_death=None)
    elif self.filters['decade']:
      ''' Use ?decade=1980 to see al people who lived in this decade
          Do not mix with ?year=
      '''
      queryset = queryset.filter(year_of_birth__gte=self.filters['decade']).filter(year_of_birth__lte=self.filters['decade']+9) | queryset.filter(year_of_birth__lte=self.filters['decade']).filter(year_of_death__gte=self.filters['decade']+9)
    elif self.filters['century']:
      ''' Use ?century=1980 to see al people who lived in this century
          Do not mix with ?year= or ?decade
      '''
      queryset = queryset.filter(year_of_birth__gte=self.filters['century']).filter(year_of_birth__lte=self.filters['century']+99) | queryset.filter(year_of_birth__lte=self.filters['century']).filter(year_of_death__lte=self.filters['century']+99)
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




# Renamed PersonsView to PersonWithImageListView
class PersonWithImageListView(generic.ListView):
  model = Person
  template_name = 'people/list.html'

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['origin'] = 'person'
    context['page_scope'] = 'personen'
    context['page_description'] = 'Personen met afbeelding | <a href="' + reverse('archive:all-people') + '">Alle personen</a>.'
    return context
  def get_queryset(self):      
    return Person.objects.all().filter(~Q(images=None)).order_by('last_name', 'first_name')

# Renamed PersonsAllView to PersonAllListView
class PersonAllListView(generic.ListView):
  model = Person
  template_name = 'people/list.html'

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['origin'] = 'person'
    context['page_scope'] = 'personen'
    context['page_description'] = '<a href="' + reverse('archive:people') + '">Personen met afbeelding</a> | Alle personen - op geboortejaar'
    return context
  def get_queryset(self):      
    return Person.objects.all().order_by('last_name', 'year_of_birth')

# Renamed PersonUpdateView to EditPersonView
class EditPersonView(UpdateView):
  model = Person
  fields = ['first_name', 'given_names', 'last_name', 'nickname', 
            'date_of_birth', 'year_of_birth', 'place_of_birth', 
            'date_of_death', 'year_of_death', 'place_of_death',
            'bio']
  # fields = '__all__'
  def get_form(self):
    if self.request.user == self.get_object().related_user:
      self.fields.append('email')
    form = super(EditPersonView, self).get_form()
    return form

  def form_valid(self, form):
    return super().form_valid(form)

# Renamed AddPerson to AddPersonView
class AddPersonView(PermissionRequiredMixin, CreateView):
  permission_required = 'archive.create_person'

  model = Person
  fields = ['first_name', 'given_names', 'last_name', 'nickname', 
            'date_of_birth', 'year_of_birth', 'place_of_birth', 
            'date_of_death', 'year_of_death', 'place_of_death',
            'bio']

  def form_valid(self, form):
    form.instance.user = self.request.user
    # Moved to model:
    #form.instance.slug = slugify(form.instance.first_name + ' ' + form.instance.last_name)
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