from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
  path('', views.DashboardView.as_view(), name='home'),
  path('dashboard/loose-ends/<slug:name>/', views.LooseEndView.as_view(), name='loose_end'),
  path('dashboard/housekeeping/', views.HousekeepingView.as_view(), name='housekeeping'),
  path('dashboard/accounts/', views.AccountsView.as_view(), name='accounts'),
  path('dashboard/housekeeping/preview/', views.housekeeping_preview, name='housekeeping_preview'),
]
