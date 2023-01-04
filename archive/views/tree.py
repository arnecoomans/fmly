from django.views.generic import ListView, DetailView, View
from django.views.generic.edit import CreateView, UpdateView
from django.template.defaultfilters import slugify

from django.http import HttpResponse

from ..utils import get_person_filters, get_person_queryset

from archive.models import Person

class CreateTreeView(View):
  def get_person_treeline(self, person, indent=0):
    line = ' '*indent
    line += person.given_names + ' '
    line += person.married_name if person.married_name else person.last_name
    line += ' ('
    line += f'id={ slugify(str(person))}, ' 
    line += f'surname={ person.last_name }, ' if person.married_name else ''
    line += f'birthday={ person.year_of_birth }, ' if person.year_of_birth else ''
    line += f'deathday={ person.year_of_death }, ' if person.year_of_death else ''
    line += ')\n'
    return line

  def get(self, request, *args, **kwargs):
    ''' Fetch active filters '''
    filters = get_person_filters(request)
    ''' Fetch person queryset based on filters '''
    queryset = get_person_queryset(filters)
    ''' Override ordering in favor of Family Tree ordering '''
    queryset = queryset.order_by('year_of_birth', 'month_of_birth', 'day_of_birth')

    ''' Start building a family tree per person'''
    tree = ''
    for person in queryset:
      #surname=la Petite Madame, birthday=1667, deathday=1672, id=Louis1661
      tree += self.get_person_treeline(person)
      for partner in person.get_partners():
        tree += self.get_person_treeline(partner)
      for child in person.get_children():
        tree += self.get_person_treeline(child, 2)
    text = '<pre>'
    return HttpResponse(text + tree)