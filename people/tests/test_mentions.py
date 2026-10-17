from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase

from cmnsd.templatetags.markdown import markdown
from content.models import Content
from core.models import Comment
from events.models import Event
from notes.models import Note
from people.models import Person
from places.models import Place


class MentionTests(TestCase):
  """Mentions in text (issue #468): [Eric](person:<token>) links to what this
  viewer may see; anything else stays text - a person's name obfuscated.
  Fail closed: without a request, nothing is visible."""

  def setUp(self):
    User = get_user_model()
    self.me = User.objects.create(username='ik')
    self.me.save()
    self.other = User.objects.create(username='ander')
    self.other.save()
    self.eric = Person.objects.create(given_name='Eric', last_name='Coomans', user=self.me, status='p', visibility='c')
    self.secret = Person.objects.create(given_name='Geheime', last_name='Persoon', user=self.other, status='p', visibility='q')
    self.item = Content.objects.create(name='Paspoort', user=self.me, status='p', visibility='c')
    self.place = Place.objects.create(name='Soerabaja', user=self.me)
    self.event = Event.objects.create(kind='marriage', year=1942, user=self.me)
    self.event.people.set([self.eric])

  def request(self, user=None):
    request = RequestFactory().get('/')
    request.user = user or self.me
    request.session = {}
    return request

  def render(self, text, request=...):
    return str(markdown(text, self.request() if request is ... else request))

  # --- what each viewer gets ---

  def test_visible_mentions_link(self):
    html = self.render(
      f'[Eric](person:{self.eric.token}), [het paspoort](content:{self.item.token}), '
      f'[het huwelijk](event:{self.event.token}) in [Soerabaja](place:{self.place.token})'
    )
    for obj in (self.item, self.event, self.place):
      self.assertIn(f'href="{obj.get_absolute_url()}"', html)
    self.assertIn(f'href="{self.eric.page_url()}"', html)
    self.assertEqual(html.count('class="mention"'), 4)

  def test_notes_can_be_mentioned_only_by_who_may_see_them(self):
    mine = Note.objects.create(user=self.me, title='Vraag: wie is Corry?', status='p', visibility='c')
    draft = Note.objects.create(user=self.other, title='Concept van een ander')   # private draft
    html = self.render(f'zie [](note:{mine.token}) en [die notitie](note:{draft.token})')
    self.assertIn(f'href="{mine.get_absolute_url()}"', html)
    self.assertIn('Vraag: wie is Corry?', html)
    self.assertIn('<span class="mention mention--hidden">die notitie</span>', html)
    self.assertNotIn('Concept', html)

  def test_hidden_person_is_obfuscated_text(self):
    html = self.render(f'met [Geheime Persoon](person:{self.secret.token})')
    self.assertNotIn('Geheime', html)
    self.assertNotIn('Persoon', html)
    self.assertNotIn(self.secret.token, html)
    self.assertIn('<span class="mention mention--hidden">G… P…</span>', html)

  def test_without_request_nothing_is_visible(self):
    html = self.render(f'[Eric](person:{self.eric.token}) en [het paspoort](content:{self.item.token})', request=None)
    self.assertNotIn('href', html)
    self.assertNotIn('Eric', html)                                # a person: obfuscated
    self.assertIn('het paspoort', html)                           # an item: its text, no link

  def test_unknown_token_looks_like_hidden(self):
    hidden = self.render(f'[Geheime Persoon](person:{self.secret.token})')
    unknown = self.render('[Geheime Persoon](person:NOSUCHTOKEN)')
    self.assertEqual(hidden, unknown)

  def test_a_private_person_by_name_without_a_link(self):
    self.eric.private = True
    self.eric.save()
    request = self.request(self.other)
    html = self.render(f'[Eric](person:{self.eric.token})', request=request)
    self.assertNotIn('href', html)

  def test_hidden_item_is_text_not_obfuscated(self):
    hidden = Content.objects.create(name='Privé', user=self.other, status='p', visibility='q')
    html = self.render(f'[de brief](content:{hidden.token})')
    self.assertIn('<span class="mention mention--hidden">de brief</span>', html)

  def test_empty_label_takes_its_name_as_this_viewer_may_see_it(self):
    trip = Event.objects.create(kind='other', title='Roots-reis', year=1992, user=self.me)
    trip.people.set([self.eric, self.secret])
    html = self.render(f'Was aanwezig bij [](event:{trip.token})')
    self.assertIn(f'href="{trip.get_absolute_url()}"', html)
    self.assertIn('Roots-reis of Eric Coomans, G… P…', html)         # its name now - its people as this viewer may see them
    self.assertIn('marriage of Eric Coomans', self.render(f'[](event:{self.event.token})'))   # a kind that names itself
    hidden = self.render(f'met [](person:{self.secret.token})')
    self.assertIn('<span class="mention mention--hidden">person</span>', hidden)   # only its kind
    self.assertIn('>person<', self.render(f'[](person:{self.eric.token})', request=None))

  def test_label_formatting_doesnt_leak(self):
    html = self.render(f'[**Geheime** Persoon](person:{self.secret.token})')
    self.assertNotIn('Geheime', html)

  # --- the sanitizer still decides the rest ---

  def test_only_mention_classes_survive(self):
    html = self.render('<span class="evil mention" onclick="x()">a</span> [b](javascript:alert(1))')
    self.assertNotIn('evil', html)
    self.assertNotIn('onclick', html)
    self.assertNotIn('javascript', html)

  def test_one_query_per_kind(self):
    other = Person.objects.create(given_name='Corry', user=self.me, status='p', visibility='c')
    text = f'[Eric](person:{self.eric.token}) [Corry](person:{other.token}) [paspoort](content:{self.item.token})'
    request = self.request()
    with self.assertNumQueries(2):
      markdown(text, request)

  def test_stripped_snippets_obfuscate_too(self):
    from django.template import Context, Template
    out = Template('{% load markdown %}{{ text|markdown:request|striptags }}').render(Context({'text': f'[Geheime Persoon](person:{self.secret.token}) zei', 'request': self.request()}))
    self.assertEqual(out.strip(), 'G… P… zei')

  # --- every place that renders text passes the viewer ---

  def test_each_text_on_its_page_shows_the_real_name(self):
    """A forgotten request would show initials here instead."""
    mention = f'met [Eric](person:{self.eric.token})'
    self.eric.biography = mention
    self.eric.save()
    self.item.description = mention
    self.item.save()
    self.event.description = mention
    self.event.save()
    self.place.description = mention
    self.place.save()
    note = Note.objects.create(user=self.me, title='Vraag', body=mention, status='p', visibility='c')
    Comment.objects.create(target=self.item, user=self.me, content=mention, status='p', visibility='c')
    client = Client()
    client.force_login(self.me)
    link = f'href={self.eric.page_url()}'
    for url in (self.eric.page_url(), self.item.get_absolute_url(), self.event.get_absolute_url(), self.place.get_absolute_url(), note.get_absolute_url()):
      html = client.get(url).content.decode().replace('"', '')
      self.assertIn('class=mention', html, url)
      self.assertNotIn('mention--hidden', html, url)
    # The dashboard's conversation: a stripped snippet - no markup, the full name.
    dashboard = client.get('/').content.decode()
    self.assertIn('met Eric', dashboard)
    self.assertNotIn('met E…', dashboard)
    self.assertIn(link, client.get(self.item.get_absolute_url()).content.decode().replace('"', ''))
