from math import floor
from django.conf import settings
from django.db.models import Q
from django.db.models import OuterRef, Subquery, IntegerField

from archive.models import Person, Event

''' get_person_filters
    Returns active filters for a person view
'''
def get_person_filters(request):
  available_filters = {
    'has_photo': False,
    'year': None,
    'decade': None,
    'century': None,
    'family': None,
    'user': None, 
    'search': None,
    'order_by': settings.PEOPLE_ORDERBY_DEFAULT,
  }
  filters = {}
  ''' Loop through available filters as configured in self.filters '''
  for filter, default_value in available_filters.items():
    ''' Check if filter is passed in querystring '''
    if request.GET.get(filter):
      ''' Special Treatment '''
      if request.GET.get(filter).lower() == 'true':
        ''' Process string True as boolan value True'''
        filters[filter] = True
      elif request.GET.get(filter).lower() in ['false', 'none', 'all']:
        ''' Process string False, None or special value All as boolean value False '''
        filters[filter] = False
      else:
        try:
          ''' Try to process Filter Value as Integer '''
          filters[filter] = int(request.GET.get(filter))
          ''' Process value to expected format if Decade or Century filter is active '''
          if filter == 'decade':
            filters[filter] = floor(filters[filter]/10)*10
          elif filter =='century':
            filters[filter] = floor(filters[filter]/100)*100
        except:
          ''' Processing as integer failed, assume value is string ''' 
          if filter == 'order_by':
            if request.GET.get(filter).lower() in settings.PEOPLE_ORDERBY_OPTIONS:
              filters[filter] = request.GET.get(filter).lower()
            else:
              filters[filter] = default_value
          else:
            filters[filter] = request.GET.get(filter).lower()
    else:
      ''' Filter does not appear in querystring
          Use default values '''
      filters[filter] = default_value
  return filters


''' Get a list of centuries of all People '''
def get_centuries(queryset):
  centuries = []
  for person in queryset:
    if person.century():
      if not person.century() in centuries:
        centuries.append(person.century())
  centuries.sort()
  return centuries
  
''' Get a list of all decades a Person has been born in '''
def get_decades(queryset):
  decades = []
  for person in queryset:
    if person.decade():
      for decade in person.decade():
        if not decade in decades:
          decades.append(decade) 
  decades.sort()
  return decades