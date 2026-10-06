from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from cmnsd.views.api.object_children import child_permissions
from cmnsd.views.api.request import request_data
from cmnsd.views.api.response import api_response, api_view

from ..models import Content
from ..transcription import TranscriptionError, guess


@api_view
@require_POST
def transcribe_guess(request, token):
  """POST content/<token>/transcribe/guess/ {source} - a first version of
  the text from the named source (content/transcription: 'delpher',
  'tesseract') - the transcribe page's source buttons. No default: the
  source is always chosen by the person. Nothing is saved here: the
  page puts the text in its field, and autosave stores it as "automatic,
  not checked". Needs the transcript permissions; a hidden item is a 404.
  Answers in the cmnsd API shape: {ok, text, language, source, note} or
  {ok: false, error}."""
  # Signed out: a 403 in the API shape - not login_required's redirect,
  # which fetch() would follow to an HTML page and read as a success.
  if not request.user.is_authenticated:
    return api_response(request, status=403, error=_("Sign in to do this."), errors={'permission': 'sign_in'})
  content = Content.objects.visible_to(request).filter(token=token).first()
  if content is None:
    return api_response(request, status=404, error=_("Not found."), errors={'not_found': True})
  perms = child_permissions(request.user, content, 'transcripts')
  if not (perms['add'] or perms['change']):
    return api_response(request, status=403, error=_("You may not transcribe."), errors={'permission': True})
  try:
    data = request_data(request)
    if not data.get('source'):
      raise ValueError(_("Choose where the text should come from."))
    source, result = guess(content, data['source'])
  except ValueError as error:
    return api_response(request, status=400, error=str(error), errors={'request': str(error)})
  except TranscriptionError as error:
    return api_response(request, status=422, error=str(error), errors={'guess': str(error)})
  return api_response(
    request, text=result.text, language=result.language, note=result.note,
    source={'name': source.name, 'label': str(source.label)},
  )
