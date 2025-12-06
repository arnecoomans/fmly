"""family URL Configuration"""

from django.contrib import admin
from django.urls import path, include

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
  # path('pick/', include('datepicker.urls')),
  path('', include('archive.urls')),
  path('ajax/', include('cmnsd.urls')),
  path('admin/', admin.site.urls),
  path('', include('django.contrib.auth.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

