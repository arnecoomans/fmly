from math import floor
from django.conf import settings
from django.db.models import Q

from archive.models import Person

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


''' get_person_queryset
    Returns the person queryset based on active filters
'''
def get_person_queryset(filters):
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
  ''' Free text search
      Searches Person Name, Bio
  '''
  if filters['search']:
    queryset = queryset.filter(first_name__icontains=filters['search']) | \
                queryset.filter(given_names__icontains=filters['search']) | \
                queryset.filter(last_name__icontains=filters['search']) | \
                queryset.filter(married_name__icontains=filters['search']) | \
                queryset.filter(nickname__icontains=filters['search']) | \
                queryset.filter(bio__icontains=filters['search'])
  ''' Overall ordering 
      Ordering is available in last-name, first-name and year of birth
  '''
  if filters['order_by'] == 'first_name':
    queryset = queryset.order_by('first_name', 'last_name', 'year_of_birth')
  elif filters['order_by'] == 'year_of_birth':
    queryset = queryset.order_by('year_of_birth', 'month_of_birth', 'day_of_birth', 'last_name')
  else:
    ''' Default to last_name ordering, allows override in settings by use of correct field_name '''
    queryset = queryset.order_by('last_name', 'first_name', 'year_of_birth')
  return queryset