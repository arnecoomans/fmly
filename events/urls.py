from django.urls import path

from . import views

app_name = 'events'

urlpatterns = [
  path('', views.EventListView.as_view(), name='list'),
  path('calendar/', views.EventCalendarView.as_view(), name='calendar'),
  path('<str:token>/', views.EventDetailView.as_view(), name='detail'),
]
