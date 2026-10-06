from django.contrib import admin
from django.shortcuts import redirect
from django.templatetags.static import static
from django.views.generic import TemplateView
from django.urls import include, path
from django.conf import settings

handler400 = 'cmnsd.views.errors.bad_request'
handler403 = 'cmnsd.views.errors.permission_denied'
handler404 = 'cmnsd.views.errors.page_not_found'

urlpatterns = [
  path("robots.txt", TemplateView.as_view(
        template_name="robots.txt",
        content_type="text/plain"
    )),
  # Asked for by browsers and tools that don't read the page's <link rel=icon>.
  path('favicon.ico', lambda request: redirect(static('images/favicon/favicon.ico'), permanent=True)),
  path('', include('dashboard.urls')),
  path('', include('people.urls')),
  path('api/', include('cmnsd.api_urls')),
  path('', include('core.urls')),
  path('content/', include('content.urls')),
  path('places/', include('places.urls')),
  path('notes/', include('notes.urls')),
  path('events/', include('events.urls')),
  path('admin/', admin.site.urls),
  path('accounts/', include('cmnsd.auth_urls')),
  path('ui/', include('cmnsd.ui_urls')),
  path('pages/', include('cmnsd.urls')),
]

if settings.DEBUG:
  from django.urls import include, path as dpath
  import debug_toolbar
  urlpatterns = [dpath('__debug__/', include(debug_toolbar.urls))] + urlpatterns