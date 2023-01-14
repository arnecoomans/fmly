from django.views.generic import DetailView, ListView
#from django.conf import settings

#from django.http import HttpResponse
from django.utils.html import escape

#from ..person_utils import get_person_filters, get_person_queryset, get_centuries, get_decades

import graphviz
from math import floor

from archive.models import Person

class Tree:
  ''' Initialize Graphviz Family Tree
      1. Collect Scope of Family Tree (list of featured people)
  '''
  def __init__(self, ancestor, direction='down') -> None:
    ''' Configurations '''
    self.indent = 0
    self.spacer = 8
    self.gender_colours = {'m': 'lightblue', 'f': 'pink'}
    ''' Tree Components '''
    self.people = {}
    self.relations =[]
    self.processed_relations = []
    self.ranks = {}
    self.nodes = {}
    self.mountpoints = {}
    ''' Initialize Tree'''
    self.populate(ancestor)
    self.get_people()
    self.set_relations(ancestor)
    self.get_relations()
    self.close()
    self.get_tree_source(ancestor)
    

  def populate(self, person):
    if person.id not in self.people:
      ''' Person has not been processed yet, so can be created '''
      ''' Store Person in People '''
      self.people[person.id] = {
        'label':     f"<<b>{ person.full_name() }</b><BR/> { person.get_lifespan() }>",
        #'label':     f"\"{ person.full_name() }\"",
        'gender':    f"\"{ person.get_gender_display() }\"",
        'color':     f"\"{ self.gender_colours[person.gender] if person.gender in self.gender_colours else 'black' }\"",
      }
      ''' Add Related People '''
      for partner in person.get_partners():
        self.populate(partner)
      for child in person.get_children():
        self.populate(child)

  def set_relations(self, person):
    ''' Check if Person Partner Relations need to be set '''
    self.relations.append(f"subgraph cluster_{ person.id } {{")
    self.relations.append(f"style=\"invis\";")
    if len(person.get_partners()) > 0:
      ''' Person has relation(s): Build relationship '''
      reverse = False
      for partner in person.get_partners():
        relation_id = self.get_relation_id([person, partner])
        relation = ['P' + str(person.id), 'P' + str(partner.id)]
        if relation_id not in self.processed_relations:
          if self.share_children(person, partner):
            mountpoint = 'P'+relation_id
            self.set_mountpoint(mountpoint, [person, partner, relation_id])
            relation.insert(floor(len(relation)/2), mountpoint)
          self.ranks[relation_id] = relation
          if reverse:
            relation.reverse()
          self.relations.append(' -> '.join(relation))
          reverse = False if reverse else True
          self.processed_relations.append(relation_id)
    else:
      ''' Person has no relation '''
      self.set_mountpoint('P'+str(person.id), person)
    ''' Process Person's Children '''
    for child in person.get_children():
      mountpoint = 'P' + self.get_relation_id(child.get_parents())
      self.relations.append(' -> '.join([mountpoint, 'P'+str(child.id)]))
      ''' Add Child information to node as well '''
      self.set_relations(child)
    self.relations.append('}')

      
  
  def get_tree_source(self, ancestor):
    newline = '\n'
    graph = ''
    graph = newline.join(self.tree)
    dot = graphviz.Source(graph)
    dot.name = 'fmly-tree'
    dot.format = 'svg'
    dot.filename = str(ancestor.id)
    dot.render(directory='public/documents/forest/')
    return f"<pre>{ newline }{ graph }{ newline }</pre>"

  ''' open()
      The starting lines to open the digraph
  '''
  def open(self):
    self.add('digraph G {')
    attributes = [
      'edge [dir=none];',
      'node [shape=box];',
      'splines=false;',
      'newrank=true;',
      'ratio="compress"',
    ]
    self.add(attributes)
  def close(self):
    self.add('}')
  
  ''' add()
      Add a line to the data buffer. Accepts lists and dicts, ints and strings, 
      but only stores content as a string.
  '''
  def add(self, data):
    if not hasattr(self, 'tree'):
      self.tree = []
      self.open()
    if type(data) is list:
      for line in data:
        self.add(line)
    elif type(data) is dict:
      for line in data.values():
        self.add(line)
    elif type(data) is int:
      self.add(str(data))
    elif type(data) is str:
      if data == '}':
        self.indent += -2
      self.tree.append(' '*self.indent + data)
      if '{' in data:
        self.indent += 2
    if '}' in data and data != '}':
        self.indent += -2


  def get_relation_id(self, people):
    relation = []
    for person in people:
      relation.append(person.id)
    relation.sort()
    return str('x'.join(str(id) for id in relation))
  ''' Get Shared Children '''
  def share_children(self, person, partner):
    for child in person.get_children():
      if child in partner.get_children():
        return True
    return False
  def get_shared_children(self, person, partner=None):
    children = []
    if type(person) == list:
      if len(person) > 1:
        partner = person[1]
      person = person[0]
    for child in person.get_children():
      if child not in children and partner in child.get_parents():
        children.append(child)
    if partner:
      for child in partner.get_children():
        if child not in children and person in child.get_parents():
          children.append(child)
    return children
  ''' Mountpoints '''
  def get_mountpoint(self, person):
    if type(person) == list:
      person = 'x'.join(str(id.id) for id in person)
      self.add(f'# --> { person }')
    if type(person) != str:
      person = person.id
    if person in self.mountpoints:
      return self.mountpoints[person]
    return 'P' + str(person)
  def set_mountpoint(self, mountpoint, person):
    if type(person) == list:
      for p in person:
        self.set_mountpoint(mountpoint, p)
    else:
      if type(person) != str:
        person = str(person.id)
      self.mountpoints[person] = mountpoint


  ''' Populate_people() '''
  def get_people(self):
    self.add('# People featured in tree')
    self.add('node[shape=box,fontname="sans-serif",fontsize=8;color="black",width=1,height=0.5,style=filled]')
    for id, person in self.people.items():
      spacer = ' '*(self.spacer - len(str(id)))
      person_line = []
      for key, value in person.items():
        person_line.append(f"{ key }={ value }")
      self.add(f"\"P{ str(id)}\"{ spacer } [ { ', '.join(person_line) } ]")

  ''' populate_relations() '''
  def get_relations(self):
    self.add('# Relations')
    self.add('node[label="", width=0, height=0];')
    for id, rank in self.ranks.items():
      if len(rank) > 1:
        self.add(f"{{ rank=same; { '; '.join(rank) } }} # { id }")
    for relation in self.relations:
      if type(relation) is list:
        for line in relation:
          self.add(line)
      else:
        self.add(relation)
    self.add('# Mountpoints ')
    for line in self.mountpoints:
      self.add('# ' + str(line) + ': ' + str(self.mountpoints[line]))
    self.add('# Processed Relations')
    for line in self.processed_relations:
      self.add('# ' + str(line))
  
''' End of class Tree '''




class TreeView(DetailView):
  model = Person
  template_name = 'archive/people/tree.html'
  context_object_name = 'person'

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_page'] = 'people'
    ''' Tree '''
    tree =  Tree(ancestor=self.get_object())
    context['tree'] = tree
    return context







