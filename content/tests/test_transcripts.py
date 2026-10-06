from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.db import IntegrityError, transaction
from django.test import RequestFactory, TestCase

from content.admin import ContentAdmin
from content.models import Content, Transcript


class TranscriptTests(TestCase):
  def setUp(self):
    self.user = get_user_model().objects.create(username='owner', is_staff=True, is_superuser=True)
    self.item = Content.objects.create(name='Interneringskaart', kind=Content.Kind.DOCUMENT, user=self.user,
                                       status='p', visibility='p')

  def transcript(self, **fields):
    fields.setdefault('language', 'ja')
    fields.setdefault('text', '抑留者')
    return Transcript.objects.create(content=self.item, **fields)

  def test_one_per_language_and_one_original(self):
    self.transcript()
    with self.assertRaises(IntegrityError), transaction.atomic():
      self.transcript(kind='translation')                      # same language again
    with self.assertRaises(IntegrityError), transaction.atomic():
      self.transcript(language='nl')                           # a second original
    self.transcript(language='nl', kind='translation', text='Geïnterneerde')
    self.assertEqual([t.kind for t in self.item.transcripts.all()], ['original', 'translation'])

  def test_automatic_never_overwrites_manual_or_checked(self):
    manual = self.transcript(method='manual')
    self.assertIsNone(Transcript.save_automatic(self.item, 'ja', 'OCR guess'))
    manual.refresh_from_db()
    self.assertEqual(manual.text, '抑留者')
    translated = Transcript.save_automatic(self.item, 'nl', 'Machinevertaling', kind='translation')
    self.assertTrue(translated.is_unchecked)
    self.assertEqual(Transcript.save_automatic(self.item, 'nl', 'Betere vertaling', kind='translation').text, 'Betere vertaling')

  def run_action(self, queryset):
    request = RequestFactory().post('/')
    request.user = self.user
    request.session = {}
    request._messages = FallbackStorage(request)
    ContentAdmin(Content, AdminSite()).move_description_to_transcript(request, queryset)

  def test_move_description_to_transcript(self):
    self.item.description = 'PETRONELLA-HOSPITAAL\nKLASSE - AFDEELING'
    self.item.save()
    detail = self.item.get_detail()
    detail.language = 'nl'
    detail.save()
    empty = Content.objects.create(name='Leeg', user=self.user)
    self.run_action(Content.objects.filter(pk__in=[self.item.pk, empty.pk]))
    self.item.refresh_from_db()
    self.assertEqual(self.item.description, '')
    transcript = self.item.transcripts.get()
    self.assertEqual((transcript.kind, transcript.language, transcript.method), ('original', 'nl', 'manual'))
    self.assertIn('KLASSE - AFDEELING', transcript.text)
    self.assertFalse(empty.transcripts.exists())

  def test_shown_on_the_page_escaped_with_language_pills(self):
    self.transcript(text='<script>x</script> regel 1\nregel 2')
    self.transcript(language='nl', kind='translation', method='automatic', text='vertaald')
    html = self.client.get(self.item.get_absolute_url()).content.decode()
    self.assertNotIn('<script>x', html)
    self.assertIn('regel 1<br>regel 2', html)
    self.assertIn('vertaald', html)
    self.assertIn('automatic, not checked', html)
    self.assertIn('data-cmnsd-filter', html)
