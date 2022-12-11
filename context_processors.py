from django.conf import settings

# Define content that will be available in templates
def setting_data(request):
  return {
    'website_title': settings.WEBSITE_TITLE,
    'LANGUAGE_CODE': settings.LANGUAGE_CODE,
    'master_css': settings.MASTER_CSS,
    'families': settings.FAMILIES,
    'unauthenticated_welcome': settings.UNAUTHENTICATED_WELCOME,
  }
