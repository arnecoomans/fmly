"""
Django settings for family project.
"""
import environ
from pathlib import Path
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
  DEBUG=(bool, False),
)
environ.Env.read_env(BASE_DIR / '.env')

# Security
SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])

# Application definition
INSTALLED_APPS = [
  'django.contrib.admin',
  'django.contrib.auth',
  'django.contrib.contenttypes',
  'django.contrib.sessions',
  'django.contrib.messages',
  'django.contrib.staticfiles',
  'archive',
  # 'datepicker',
  'cmnsd',
]

MIDDLEWARE = [
  'django.middleware.security.SecurityMiddleware',
  'django.contrib.sessions.middleware.SessionMiddleware',
  'django.middleware.locale.LocaleMiddleware',
  'django.middleware.common.CommonMiddleware',
  'django.middleware.csrf.CsrfViewMiddleware',
  'django.contrib.auth.middleware.AuthenticationMiddleware',
  'django.contrib.messages.middleware.MessageMiddleware',
  'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'family.urls'

TEMPLATES = [
  {
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],
    'APP_DIRS': True,
    'OPTIONS': {
      'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
        'cmnsd.context_processors.setting_data',
        'context_processors.setting_data',
      ],
      'builtins': [
        'templatetags.abs',
        'django.templatetags.i18n',
        'cmnsd.templatetags.markdown',
        'cmnsd.templatetags.query_filters',
        'cmnsd.templatetags.queryset_filters',
        'cmnsd.templatetags.text_filters',
        'cmnsd.templatetags.math_filters',
        'cmnsd.templatetags.humanize_date',
        'cmnsd.templatetags.cmnsd',
      ],
    },
  },
]

WSGI_APPLICATION = 'family.wsgi.application'

# Database
DATABASES = {
  'default': env.db('DATABASE_URL', default=f'sqlite:///{BASE_DIR / "db.sqlite3"}'),
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
  {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
  {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
  {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
  {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'CET'
USE_I18N = True
USE_L10N = True
USE_TZ = True

LANGUAGES = (
  ('en', _('English')),
  ('nl', _('Dutch')),
)
LOCALE_PATHS = [BASE_DIR / 'locale/']

# Static / media files
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'public' / 'static'
STATICFILES_DIRS = [BASE_DIR / 'project_static']
MEDIA_URL = 'documents/'
MEDIA_ROOT = BASE_DIR / 'public' / 'documents'

LOGIN_REDIRECT_URL = 'archive:home'
LOGOUT_REDIRECT_URL = 'archive:home'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Sendfile
SENDFILE_ROOT = MEDIA_ROOT / 'files'
SENDFILE_BACKEND = 'django_sendfile.backends.nginx'
SENDFILE_URL = '/attachment/download/'

# Website
WEBSITE_TITLE = env('WEBSITE_TITLE', default="Coomans' Family Archive")
META_DESCRIPTION = env('META_DESCRIPTION', default='An archive with photos and documents of the Coomans, Bake and ancestors families.')
MASTER_CSS = env('MASTER_CSS', default='fmly.css')
FAMILIES = env.list('FAMILIES', default=['Coomans', 'Bake'])
PAGINATE = 24
UNAUTHENTICATED_WELCOME = "Fmly.cmns.nl is een archief met foto's en documenten van de familie Coomans, Bake en voorouderen."
OBJECT_FORM_FIELDS = ['tag', 'in_group', 'attachments', 'is_portrait_of']
PEOPLE_ORDERBY_OPTIONS = ['last_name', 'first_name', 'year_of_birth']
PEOPLE_ORDERBY_DEFAULT = 'last_name'
NEW_USER_DEFAULT_GROUP = 'familie - kijken'
MIN_COMMENT_LENGTH = 4

# CMNSD
SITE_NAME = 'Vakantieplanner DEVELOPMENT'
AJAX_BLOCKED_MODELS = []
AJAX_DEFAULT_DATA_SOURCES = ['kwargs', 'GET', 'POST', 'json', 'headers']
AJAX_PROTECTED_FIELDS = []
AJAX_RESTRICTED_FIELDS = []
AJAX_RENDER_REMOVE_NEWLINES = not DEBUG
AJAX_ALLOW_FK_CREATION_MODELS = ['comment', 'location']
AJAX_ALLOW_RELATED_CREATION_MODELS = ['tag', 'comment', 'location']
AJAX_MAX_DEPTH_RECURSION = 3
AJAX_IGNORE_CHANGE_FIELDS = ['id', 'date_created', 'date_modified']
AJAX_MODES = ['editable', 'add', 'timeline']
DEFAULT_MODEL_STATUS = 'p'
DEFAULT_MODEL_VISIBILITY = 'p'
SEARCH_EXCLUDE_CHARACTER = 'exclude'
SEARCH_MIN_LENGTH = 2
SEARCH_QUERY_CHARACTER = 'search'

# Debug toolbar
if DEBUG:
  INSTALLED_APPS += ['debug_toolbar']
  MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
  INTERNAL_IPS = ['127.0.0.1']
