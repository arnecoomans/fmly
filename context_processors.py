from django.conf import settings

# Define content that will be available in templates
def setting_data(request):
  result = {
    'website_title': getattr(settings, 'WEBSITE_TITLE', 'Family Reseach'),
    'LANGUAGE_CODE': getattr(settings, 'LANGUAGE_CODE', 'en-us'),
    'master_css': getattr(settings, 'MASTER_CSS', 'css/master.css'),
    'families': getattr(settings, 'FAMILIES', []),
    'unauthenticated_welcome': getattr(settings, 'UNAUTHENTICATED_WELCOME', f'Welcome to { getattr(settings, 'WEBSITE_TITLE', 'Family Reseach') }'),
    'matomo_id': getattr(settings, 'MATOMO_TRACKING_ID', None),
  }
  return result
