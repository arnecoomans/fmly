from django.urls import path

from . import views

app_name = 'people'

urlpatterns = [
  # person/<token>/<slug>/ - the token finds the person, the slug is for
  # reading. person/<token>/ and old person/<slug>/ addresses redirect.
  path('person/<str:token>/<slug:slug>/', views.PersonDetailView.as_view(), name='person_detail'),
  path('person/<str:key>/', views.person_redirect, name='person_redirect'),
  path('people/', views.PersonListView.as_view(), name='person_list'),
  path('people/new/', views.PersonCreateView.as_view(), name='person_create'),
  path('people/similar/', views.person_similar, name='person_similar'),
]
