from django.conf import settings

# Define content that will be available in templates
def setting_data(request):
  default_ajax_load = True
  result = {
    'website_title': getattr(settings, 'WEBSITE_TITLE', 'Family Reseach'),
    'LANGUAGE_CODE': getattr(settings, 'LANGUAGE_CODE', 'en-us'),
    'master_css': getattr(settings, 'MASTER_CSS', 'css/master.css'),
    'families': getattr(settings, 'FAMILIES', []),
    'unauthenticated_welcome': getattr(settings, 'UNAUTHENTICATED_WELCOME', f'Welcome to { getattr(settings, 'WEBSITE_TITLE', 'Family Reseach') }'),
    'matomo_id': getattr(settings, 'MATOMO_TRACKING_ID', None),

    'ajax_load_comments': getattr(settings, 'AJAX_LOAD_COMMENTS', default_ajax_load),
    'ajax_image_load_people': getattr(settings, 'AJAX_IMAGE_LOAD_PEOPLE', default_ajax_load),
    'ajax_image_load_tags': getattr(settings, 'AJAX_IMAGE_LOAD_TAGS', default_ajax_load),
    'ajax_image_load_description': getattr(settings, 'AJAX_IMAGE_LOAD_DESCRIPTION', default_ajax_load),
  }
  return result
