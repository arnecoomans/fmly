from .PersonDetailView import PersonDetailView, person_redirect
from .PersonListView import PersonListView
from .PersonCreateView import PersonCreateView
from .similar import person_similar

__all__ = [
  'PersonCreateView',
  'PersonDetailView',
  'PersonListView',
  'person_redirect',
  'person_similar',
]
