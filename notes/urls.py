from django.urls import path

from . import views

app_name = 'notes'

urlpatterns = [
  path('', views.NoteListView.as_view(), name='list'),
  path('new/', views.note_create, name='create'),
  path('<str:token>/', views.NoteDetailView.as_view(), name='detail'),
]
