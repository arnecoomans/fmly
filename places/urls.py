from django.urls import path

from . import views

app_name = 'places'

urlpatterns = [
  path('', views.PlaceListView.as_view(), name='list'),
  # places/<token>/<slug>/ - the token finds the place, the slug is for
  # reading; token-only or outdated slugs redirect (PlaceDetailView).
  path('<str:token>/<slug:slug>/', views.PlaceDetailView.as_view(), name='detail'),
  path('<str:token>/', views.PlaceDetailView.as_view(), name='detail_by_token'),
]
