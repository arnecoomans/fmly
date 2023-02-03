from django.urls import path

from . import views

app_name = 'datepicker'
urlpatterns = [
    path('', views.EventList.as_view(), name='events'),
    #path('<str:slug>/store_attendance/', views.SubmitAttandance.as_view(), name='sumbitAttendance'),
    path('<str:slug>/', views.EventDetail.as_view(), name='event'),
    path('<str:slug>/attend/', views.AttendanceForm.as_view(), name='attendance'),
]
