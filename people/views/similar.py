from django.contrib.auth.decorators import permission_required
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET

from cmnsd.views.api.response import api_response

from ..forms import NAME_FIELDS
from ..similar import similar_people


@require_GET
@permission_required('people.add_person', raise_exception=True)
def person_similar(request):
  """people/similar/?given_name=...&last_name=... - possible duplicates of
  the person being added (people/similar.py), as {html}: asked while typing
  by cmnsd.js hints.js from the names of a new-person form. ?dialog=1: in
  the "+ new person" dialog, each also offers "use this one" (cmnsd.js
  dialog.js data-cmnsd-dialog-answer) - the picker then takes that person."""
  people, count = similar_people(request, {field: request.GET.get(field, '') for field in NAME_FIELDS})
  html = render_to_string('people/_similar.html', {
    'similar': people, 'similar_count': count, 'in_dialog': request.GET.get('dialog') == '1',
  }, request=request)
  return api_response(request, html=html)
