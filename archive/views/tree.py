from django.views.generic import ListView, DetailView, View
from django.views.generic.edit import CreateView, UpdateView
from django.template.defaultfilters import slugify

from django.http import HttpResponse
# from django.utils.html import escape

from ..utils import get_person_filters, get_person_queryset

# import string
from datetime import date
import graphviz

from archive.models import Person

class CreateTreeView(View):
  
  # def get_free_node_name(self):
  #   if not hasattr(self, 'free_names'):
  #     ltrs = string.ascii_uppercase
  #     self.free_names = [''.join([a,b]) for a in ltrs for b in ltrs]
  #   free_name = self.free_names[0]
  #   self.free_names.remove(free_name)
  #   return free_name

  
  ''' add_person
      Adds person to list of featured people. 
  '''
  def add_person(self, person_id):
    ''' Ensure placeholder exists '''
    if not hasattr(self, 'people'):
      self.people = {}
    ''' Add Person id as Key in Dict to avoid doubles since person id is always unique '''
    self.people[person_id] = True
    
  ''' store_partner_relation 
      a partner-relation consists of one extra node on the same level
      and one relationship on the same level
  '''
  def store_partner_relation(self, person_id, related_person_id):
    ''' Ensure placeholders exist '''
    if not hasattr(self, 'relations'):
      self.relations = {}
    if not hasattr(self, 'relation_points'):
      self.relation_points = {}
    if not hasattr(self, 'people_data'):
      self.people_data = Person.objects.all()
    ''' Create relation key
        Key is used to store relations and node points
        Sort key by lowest_id:highest_id '''
    if person_id < related_person_id:
      key = f"{ str(person_id) }{ str(related_person_id) }"
    else:
      key = f"{ str(related_person_id) }{ str(person_id) }"
    ''' Add relationship-point and relation on the same level '''
    self.relation_points[key] = 'shape=circle,label="",height=0.01,width=0.01;'
    self.relations[key] = f"{{rank=same; { str(person_id) } -> { key } -> { str(related_person_id) }}}"
    ''' Add Relationship mountpoint one level below '''
    if person_id < related_person_id:
      mount = f"{ str(person_id).zfill(4) }{ str(related_person_id).zfill(4) }"
    else:
      mount = f"{ str(related_person_id).zfill(4) }{ str(person_id).zfill(4) }"
    if len(self.people_data.get(pk=person_id).get_children()) > 0:
      self.relation_points[key] = 'shape=invis,label="",height=0.01,width=0.01;'
      self.relations[mount] = f"{ str(key) } -> { mount }"
    
  def store_child_relation(self, child_id):
    if not hasattr(self, 'relations'):
      self.relations = {}
    if not hasattr(self, 'relation_points'):
      self.relation_points = {}
    if not hasattr(self, 'people_data'):
      self.people_data = Person.objects.all()
    if self.people_data.filter(pk=child_id).count() > 0:
      child = self.people_data.get(pk=child_id)
      parents = []
      for parent in child.get_parents():
        parents.append(parent.id)
      parents.sort()
      if len(parents) == 1:
        self.relations[str(parents[0]).zfill(4) + str(child_id).zfill(4)] = f'{ parents[0]} -> { child_id }'
      elif len(parents) > 1:
        parents_relationpoint = ''.join(str(parent).zfill(4) for parent in parents)
        ''' Add Relation '''
        self.relations[str(parents_relationpoint) + str(child_id).zfill(4)] = f"{ parents_relationpoint } -> { child_id }"




  ''' populate_people():
      Build a Node listing of all gathered people
  '''
  def populate_people(self):
    if not hasattr(self, 'people'):
      self.people = {}
    if not hasattr(self, 'people_data'):
      self.people_data = Person.objects.all()
    self.graph.append('')
    self.graph.append('  # List People')
    for person in self.people.keys():
      ''' Prepare year-of-birth and year-of-death neatly '''
      data = self.people_data.get(pk=person)
      yob = str(data.year_of_birth) if data.year_of_birth else ''
      if data.year_of_death:
        yod = str(data.year_of_death)
      else:
        if data.year_of_birth:
          if date.today().year - data.year_of_birth > 90:
            yod = '?'
          else:
            yod = ''
        else:
          yod = ''
      ''' Set Attributes of person '''
      attributes = {
        'label': f'"{ data.full_name() }\n{ yob }-{ yod }"',
        'shape': '"box"',
        'regular': '0',
        'color': '"black"',
        'style': '"filled"',
        'fillcolor': '"lightgrey"',
      }
      ''' If person is in queryset, make bold to distinct from partners/children '''
      if self.queryset.filter(pk=person).count() > 0:
        attributes['style'] = '"bold, filled"'
      attribute_list = ''
      for key, value in attributes.items():
        attribute_list += f'{ key }={ str(value) }, '
      ''' Remove trailing ', ' from attribute list '''
      attribute_list = attribute_list[:-2]
      ''' Write person details to graph '''
      self.graph.append(f'  "{ str(person) }" [{ attribute_list }]')
  
  ''' A relation point is between two people that share children '''
  def populate_relation_points(self):
    if not hasattr(self, 'relation_points'):
      self.relation_points = {}
    self.graph.append('')
    self.graph.append('  # Relation centerpoints')
    for relation_point in self.relation_points:
      self.graph.append(f'  { relation_point } [{ self.relation_points[relation_point] }]')

  def populate_relations(self):
    if not hasattr(self, 'relations'):
      self.relations = {}
    self.graph.append('')
    self.graph.append('  # Relations')
    for relation in self.relations.values():
      self.graph.append(f'  {relation}')

  def get(self, request):
    debug = []
    ''' Fetch Active Filters '''
    self.filters = get_person_filters(request)
    ''' Fetch Queryset '''
    self.queryset = get_person_queryset(self.filters)
    ''' Populate Person List '''
    for person in self.queryset:
      ''' Store Person'''
      self.add_person(person.id)
      ''' Store Partner Relations '''
      for partner in person.get_partners():
        self.add_person(partner.id)
        self.store_partner_relation(person.id, partner.id)
      ''' Store Child Relations '''
      for child in person.get_children():
        debug.append(str(child))
        self.add_person(child.id)
        self.store_child_relation(child.id)

    ''' Start Building Graph Source '''
    self.graph = []
    self.graph.append('digraph G {')
    self.graph.append('  edge [dir=none];')
    self.graph.append('  node [shape=box];')
    self.graph.append('  splines=false;')
    self.populate_people()
    self.populate_relation_points()
    self.populate_relations()
    self.graph.append('}')
    
    ''' Pipe Graph list into newline seperated string '''
    result = str('\n'.join(str(line) for line in self.graph))

    dot = graphviz.Source(result)
    dot.name = 'fmly-tree'
    dot.format = 'svg'
    dot.render(directory='public/documents/forest/')
    response = f"<img width=\"100%\" height=\"100%\" src=\"/documents/forest/Source.gv.svg\">"
    return HttpResponse(response)