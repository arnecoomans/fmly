from django.views import generic
from django.views.generic.edit import CreateView, DeleteView, UpdateView, FormView

from django.urls import reverse, reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.template.defaultfilters import slugify
from django.db.models import Q

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin


from archive.models import Person



class PersonView(generic.DetailView):
  model = Person

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