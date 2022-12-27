from django.conf import settings

# Define content that will be available in templates
def setting_data(request):
  result = {
    'website_title': settings.WEBSITE_TITLE,
    'LANGUAGE_CODE': settings.LANGUAGE_CODE,
    'master_css': settings.MASTER_CSS,
    'families': settings.FAMILIES,
  }
  ''' Verified settings '''
  result['unauthenticated_welcome'] = settings.UNAUTHENTICATED_WELCOME if hasattr(settings, 'UNAUTHENTICATED_WELCOME') else f'Welcome to { settings.WEBSITE_TITLE }'
  result['matomo_id'] = settings.MATOMO_TRACKING_ID if hasattr(settings, 'MATOMO_TRACKING_ID') else None

  return result
