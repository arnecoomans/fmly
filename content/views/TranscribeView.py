from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.urls import reverse
from django.views.generic import TemplateView

from cmnsd.views.api.object_children import child_permissions, child_urls
from cmnsd.views.api.object_form import _modified

from ..forms import TranscriptForm
from ..models import Content, Transcript
from ..transcription import TranscriptionError, options
from ..transcription import delpher


class TranscribeView(LoginRequiredMixin, TemplateView):
  """content/<token>/transcribe/ - the transcribe page: the item's image,
  zoomable (cmnsd.js viewer.js), beside its transcript, which saves itself
  (autosave.js, through cmnsd's child-record endpoints - the same checks as
  on the item page). ?transcript=<id> opens that transcript, ?transcript=new
  a new one; without it: the original, else the first, else new. Steps
  through the whole and its parts - each page its own transcript
  (docs/issues.md, the transcribe view). Needs the transcript permissions
  (content.add_transcript / change_transcript); a hidden item is a 404."""
  template_name = 'content/transcribe.html'

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    request = self.request
    content = Content.objects.visible_to(request).select_related('document_detail', 'parent').filter(token=kwargs['token']).first()
    if content is None:
      raise Http404("No such item.")
    perms = child_permissions(request.user, content, 'transcripts')
    if not (perms['add'] or perms['change']):
      raise PermissionDenied("You may not transcribe.")

    transcripts = list(content.transcripts.all())
    wanted = request.GET.get('transcript', '')
    if wanted == 'new':
      transcript = None
    elif wanted:
      transcript = next((t for t in transcripts if str(t.pk) == wanted), None)
      if transcript is None:
        raise Http404("No such transcript.")
    else:
      transcript = next((t for t in transcripts if t.kind == Transcript.Kind.ORIGINAL), transcripts[0] if transcripts else None)
    if (transcript is None and not perms['add']) or (transcript is not None and not perms['change']):
      raise PermissionDenied("You may not do this.")

    if transcript is None:
      # A new one: the original if there's none yet, else a translation;
      # in the document's language, else Dutch (the archive's own).
      has_original = any(t.kind == Transcript.Kind.ORIGINAL for t in transcripts)
      document = getattr(content, 'document_detail', None) if content.kind == 'document' else None
      instance = Transcript(
        content=content,
        kind=Transcript.Kind.TRANSLATION if has_original else Transcript.Kind.ORIGINAL,
        language=(getattr(document, 'language', '') or 'nl') if not has_original else '',
      )
      action = child_urls('content', content, 'transcripts')['add']
    else:
      instance = transcript
      action = child_urls('content', content, 'transcripts', transcript)['edit']

    # The left side: the image, or - to translate - the original's text.
    # A translation with an original opens on the original; ?left= switches.
    original = next((t for t in transcripts if t.kind == Transcript.Kind.ORIGINAL), None)
    translating = (transcript.kind if transcript else instance.kind) == Transcript.Kind.TRANSLATION
    has_image = bool(content.file and content.media_type == 'image')
    left = request.GET.get('left') or ('original' if translating and original else 'image')
    if left == 'original' and not (original and original != transcript):
      left = 'image'
    # The Delpher article's own text, for an item with a Delpher link
    # (?left=source) - fetched when chosen, cached for a day.
    has_source_text = delpher.DelpherSource().applies(content)[0]
    source_text, source_error = None, ''
    if left == 'source' and has_source_text:
      try:
        source_text = delpher.fetch_article(delpher.link_parts(content.source)[0])
      except TranscriptionError as error:
        source_error = str(error)
    elif left == 'source':
      left = 'image'
    query = request.GET.copy()
    query.pop('left', None)
    switch = lambda value: f"?{query.urlencode()}{'&' if query else ''}left={value}"

    context.update({
      'left': left,
      'left_original': original if left == 'original' else None,
      'can_show_original': bool(original and original != transcript),
      'show_left_switch': bool(original and original != transcript) or has_source_text,
      'switch_image': switch('image'),
      'switch_original': switch('original'),
      'switch_source': switch('source'),
      'has_source_text': has_source_text,
      'source_text': source_text,
      'source_error': source_error,
      # "Guess transcription": only while the text is empty.
      'guess_options': options(content) if not (transcript and transcript.text.strip()) else [],
      'content': content,
      'image': has_image,
      'transcripts': transcripts,
      'transcript': transcript,
      'form': TranscriptForm(instance=instance, prefix='transcripts'),
      'form_action': action,
      'modified': _modified(transcript) if transcript else '',
      'can_add': perms['add'],
      **self._pages(content, request),
    })
    return context

  @staticmethod
  def _pages(content, request):
    """Previous / next page: the whole, then its parts in order - each
    opened on its own original (no ?transcript)."""
    whole = content.parent if content.parent_id else content
    pages = [whole, *whole.parts.visible_to(request).order_by('position', 'pk')]
    if len(pages) < 2:
      return {}
    index = next((i for i, page in enumerate(pages) if page.pk == content.pk), 0)
    url = lambda page: reverse('content:transcribe', args=[page.token])
    return {
      'page_number': index + 1, 'page_count': len(pages),
      'previous_page': url(pages[index - 1]) if index > 0 else None,
      'next_page': url(pages[index + 1]) if index + 1 < len(pages) else None,
    }
