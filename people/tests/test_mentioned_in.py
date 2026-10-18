from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, RequestFactory, TestCase

from cmnsd.models import Mention
from cmnsd.models.Mention import mentioned_in
from content.models import Content
from core.models import Comment
from notes.models import Note
from people.models import Person


class MentionIndexTests(TestCase):
  """The index of mentions (issue #470): rebuilt from the text on every
  save, gone with its source or target - and "mentioned in", only the
  sources this viewer may see."""

  def setUp(self):
    User = get_user_model()
    self.me = User.objects.create(username='ik')
    self.me.save()
    self.other = User.objects.create(username='ander')
    self.other.save()
    make = lambda given, **f: Person.objects.create(given_name=given, last_name='Riedé', user=self.me, status='p', visibility='c', **f)
    self.corry, self.joot, self.wiwi = make('Corry'), make('Joot'), make('Wiwi')
    self.item = Content.objects.create(name='Trouwfoto', user=self.me, status='p', visibility='c')

  def request(self, user=None):
    request = RequestFactory().get('/')
    request.user = user or self.me
    request.session = {}
    return request

  def mention(self, person, label='hem'):
    return f'[{label}](person:{person.token})'

  def targets(self, source):
    return {row.target for row in Mention.objects.filter(source_id=source.pk, source_content_type__model=source._meta.model_name)}

  # --- the index follows the text ---

  def test_indexed_on_save_and_kept_in_line(self):
    self.corry.biography = f'Trouwt {self.mention(self.joot)}, later {self.mention(self.wiwi)}.'
    self.corry.save()
    self.assertEqual(self.targets(self.corry), {self.joot, self.wiwi})
    self.corry.biography = f'Trouwt {self.mention(self.wiwi)}.'
    self.corry.save()
    self.assertEqual(self.targets(self.corry), {self.wiwi})            # gone from the text: gone from the index

  def test_unknown_tokens_and_itself_not_recorded(self):
    self.corry.biography = f'[niemand](person:NOSUCHTOKEN) en {self.mention(self.corry, "zij")}'
    self.corry.save()
    self.assertEqual(self.targets(self.corry), set())

  def test_a_save_without_the_text_leaves_the_index(self):
    self.corry.biography = self.mention(self.joot)
    self.corry.save()
    Person.objects.filter(pk=self.corry.pk).update(biography='')     # a bulk update: no save()
    self.corry.refresh_from_db()
    self.corry.save(update_fields=['given_name'])
    self.assertEqual(self.targets(self.corry), {self.joot})            # untouched: not one of its text fields

  def test_deleting_a_source_or_target_removes_its_rows(self):
    comment = Comment.objects.create(target=self.item, user=self.me, content=self.mention(self.joot), status='p', visibility='c')
    self.corry.biography = self.mention(self.joot)
    self.corry.save()
    self.assertEqual(Mention.objects.count(), 2)
    comment.delete()
    self.assertEqual(Mention.objects.count(), 1)
    self.joot.delete()
    self.assertEqual(Mention.objects.count(), 0)

  def test_command_builds_the_index(self):
    Person.objects.filter(pk=self.corry.pk).update(biography=self.mention(self.joot))   # without save(): not indexed
    self.assertEqual(Mention.objects.count(), 0)
    call_command('mentions_index', stdout=open('/dev/null', 'w'))
    self.assertEqual(self.targets(self.corry), {self.joot})

  # --- mentioned in: only what this viewer may see ---

  def test_mentioned_in_by_kind(self):
    self.corry.biography = self.mention(self.joot)
    self.corry.save()
    note = Note.objects.create(user=self.me, title='Waarom twee broers?', body=self.mention(self.joot), status='p', visibility='c')
    Comment.objects.create(target=self.item, user=self.me, content=self.mention(self.joot), status='p', visibility='c')
    rows = mentioned_in(self.joot, self.request())
    self.assertEqual([row['kind'] for row in rows], ['person', 'note', 'comment'])
    self.assertEqual(rows[1]['source'], note)

  def test_hidden_sources_dont_show(self):
    Note.objects.create(user=self.other, title='Privé', body=self.mention(self.joot))   # someone else's private draft
    hidden_item = Content.objects.create(name='Privé', user=self.other, status='p', visibility='q')
    Comment.objects.create(target=hidden_item, user=self.other, content=self.mention(self.joot), status='p', visibility='c')
    self.wiwi.private = True
    self.wiwi.biography = self.mention(self.joot)
    self.wiwi.save()
    mine = mentioned_in(self.joot, self.request())
    self.assertEqual([row['kind'] for row in mine], [])                # a private note, a comment on a hidden item, a private page
    self.assertEqual(mentioned_in(self.joot, None), [])                # no request: none

  # --- what it says: an excerpt ---

  def test_excerpt_four_words_on_either_side(self):
    self.corry.biography = f'Zij trouwt in 1915 eerst met {self.mention(self.joot, "Joot")}, scheidt later van hem en trouwt zijn broer.'
    self.corry.save()
    excerpt = str(mentioned_in(self.joot, self.request())[0]['excerpts'][0])
    self.assertTrue(excerpt.startswith('… in 1915 eerst met <strong><span class="mention mention--current">Joot</span></strong>'), excerpt)   # this page: no link back
    self.assertTrue(excerpt.endswith('</strong>, scheidt later van hem …'), excerpt)   # the comma sticks to the mention

  def test_every_mention_its_excerpt_close_ones_shared(self):
    far = ' '.join(['woord'] * 12)
    self.corry.biography = f'Eerst {self.mention(self.joot, "Joot")} {far} later weer {self.mention(self.joot, "Joot")} en {self.mention(self.joot, "hij")} {far} slot {self.mention(self.joot, "Joot")} {far} eind {self.mention(self.joot, "Joot")}'
    self.corry.save()
    row = mentioned_in(self.joot, self.request())[0]
    self.assertEqual(len(row['excerpts']), 3)                                   # the limit
    self.assertEqual(str(row['excerpts'][1]).count('<strong>'), 2)             # "weer Joot en hij": close - one excerpt, both bold
    self.assertEqual(row['more'], 1)                                           # and one more

  def test_excerpt_links_others_not_this_page(self):
    self.corry.biography = f'{self.mention(self.joot, "Joot")} en {self.mention(self.wiwi, "Wiwi")}'
    self.corry.save()
    excerpt = str(mentioned_in(self.joot, self.request())[0]['excerpts'][0])
    self.assertIn('mention--current">Joot<', excerpt)                         # Joot's own page: no link
    self.assertIn(f'href="{self.wiwi.page_url()}"', excerpt)                  # someone else: a link
    self.assertNotIn(f'href="{self.joot.page_url()}"', excerpt)

  def test_excerpt_hides_what_the_viewer_may_not_see(self):
    secret = Person.objects.create(given_name='Geheime', last_name='Minnaar', user=self.other, status='p', visibility='q')
    self.corry.biography = f'Met {self.mention(secret, "Geheime Minnaar")} en {self.mention(self.joot, "Joot")}.'
    self.corry.save()
    excerpt = str(mentioned_in(self.joot, self.request())[0]['excerpts'][0])
    self.assertNotIn('Geheime', excerpt)
    self.assertIn('G… M…', excerpt)

  def test_excerpt_of_an_empty_label_names_it(self):
    self.corry.biography = f'Trouwt [](person:{self.joot.token}).'
    self.corry.save()
    self.assertIn('Joot Riedé', str(mentioned_in(self.joot, self.request())[0]['excerpts'][0]))

  def test_fixed_number_of_queries(self):
    for person in (self.corry, self.wiwi):
      person.biography = self.mention(self.joot)
      person.save()
    Note.objects.create(user=self.me, title='Vraag', body=self.mention(self.joot), status='p', visibility='c')
    with self.assertNumQueries(5):   # the rows; the people (with their private-page rule); the notes; the subject once for every excerpt - not one per row
      mentioned_in(self.joot, self.request())

  # --- transcripts as sources (issue #474) ---

  def test_a_transcript_mentions_once_per_item(self):
    from content.models import Transcript
    Transcript.objects.create(content=self.item, kind='translation', language='en', text=f'married {self.mention(self.joot, "Joot")}')
    Transcript.objects.create(content=self.item, kind='original', language='nl', text=f'getrouwd met {self.mention(self.joot, "Joot")}')
    rows = [row for row in mentioned_in(self.joot, self.request()) if row['kind'] == 'transcript']
    self.assertEqual(len(rows), 1)                                              # one item, two languages: once
    self.assertEqual(rows[0]['source'].kind, 'original')                       # the original first
    self.assertIn('getrouwd met', str(rows[0]['excerpts'][0]))

  def test_a_transcript_doesnt_count_for_its_own_item(self):
    from content.models import Transcript
    page = Content.objects.create(name='Pagina 2', user=self.me, status='p', visibility='c', parent=self.item)
    other = Content.objects.create(name='Foto van het schip', user=self.me, status='p', visibility='c')
    transcript = Transcript.objects.create(content=page, language='nl', text=(
      f'[deze akte](content:{page.token}), [het boek](content:{self.item.token}) en [de foto](content:{other.token})'
    ))
    self.assertEqual(self.targets(transcript), {other})                       # its own page and its whole don't count

  def test_a_transcript_as_visible_as_its_item(self):
    from content.models import Transcript
    hidden = Content.objects.create(name='Privé', user=self.other, status='p', visibility='q')
    Transcript.objects.create(content=hidden, language='nl', text=self.mention(self.joot))
    self.assertEqual([row for row in mentioned_in(self.joot, self.request()) if row['kind'] == 'transcript'], [])

  def test_the_transcribe_field_mentions_only_around_the_words(self):
    from django.contrib.auth.models import Permission
    for codename in ('change_content', 'add_transcript', 'change_transcript'):
      self.me.user_permissions.add(Permission.objects.get(codename=codename))
    self.me.save()
    client = Client()
    client.force_login(self.me)
    html = client.get(f'/content/{self.item.token}/transcribe/').content.decode().replace('"', '')
    self.assertRegex(html, r'<textarea [^>]*data-cmnsd-mentions-mode=label')
    self.assertIn('data-cmnsd-mentions-button=@ mention', html)

  def test_section_only_when_mentioned(self):
    client = Client()
    client.force_login(self.me)
    self.assertNotIn('Mentioned in', client.get(self.joot.page_url()).content.decode())
    self.corry.biography = self.mention(self.joot)
    self.corry.save()
    html = client.get(self.joot.page_url()).content.decode()
    self.assertIn('Mentioned in', html)
    self.assertIn('biography of', html)


class MentionHousekeepingTests(TestCase):
  """Mentions that lead nowhere (housekeeping), and removing a link - the
  words stay (core.views.unlink_mention)."""

  def setUp(self):
    from django.contrib.auth.models import Permission
    User = get_user_model()
    self.staff = User.objects.create(username='staf', is_staff=True)
    for codename in ('delete_content', 'change_person', 'change_comment'):
      self.staff.user_permissions.add(Permission.objects.get(codename=codename))
    self.staff.save()
    self.author = User.objects.create(username='schrijver')
    self.author.save()
    self.editor = User.objects.create(username='redacteur')
    self.editor.user_permissions.add(Permission.objects.get(codename='change_comment'))
    self.editor.save()
    make = lambda given, status='p': Person.objects.create(given_name=given, last_name='Riedé', user=self.staff, status=status, visibility='c')
    self.joot, self.gone_soon, self.revoked = make('Joot'), make('Weg'), make('Ingetrokken', 'r')
    self.item = Content.objects.create(name='Trouwfoto', user=self.staff, status='p', visibility='c')

  def comment(self, text, user=None):
    return Comment.objects.create(target=self.item, user=user or self.author, content=text, status='p', visibility='c')

  def unlink(self, client, source, scheme, token, next_url='/'):
    from django.contrib.contenttypes.models import ContentType
    return client.post('/mentions/unlink/', {
      'source_type': ContentType.objects.get_for_model(source).pk, 'source_id': source.pk,
      'scheme': scheme, 'token': token, 'next': next_url,
    })

  def login(self, user):
    client = Client()
    client.force_login(user)
    return client

  def test_problems_gone_revoked_deleted(self):
    from cmnsd.models.Mention import mention_problems
    token = self.gone_soon.token
    self.comment(f'[Joot](person:{self.joot.token}) [Weg](person:{token}) [Ingetrokken](person:{self.revoked.token}) [Fout](person:NOSUCHTOKEN)')
    self.gone_soon.delete()
    problems = {(row['label'], row['problem']) for row in mention_problems()}
    self.assertEqual(problems, {('Weg', 'gone'), ('Ingetrokken', 'revoked'), ('Fout', 'gone')})   # Joot: fine

  def test_unlink_keeps_the_words(self):
    from cmnsd.models.Mention import unlink_mention
    comment = self.comment(f'getrouwd met [O. RIEDÉ](person:{self.joot.token}) en [](person:{self.joot.token}).')
    self.assertEqual(unlink_mention(comment, 'person', self.joot.token), 2)
    comment.refresh_from_db()
    self.assertEqual(comment.content, 'getrouwd met O. RIEDÉ en Joot Riedé.')   # an empty label: the name
    self.assertFalse(Mention.objects.filter(source_id=comment.pk).exists())       # the index follows

  def test_who_may_remove_a_link_from_a_comment(self):
    comment = self.comment(f'[Joot](person:{self.joot.token})')
    self.assertEqual(self.unlink(self.login(self.editor), comment, 'person', self.joot.token).status_code, 404)   # someone else's comment
    self.assertIn('](person:', Comment.objects.get(pk=comment.pk).content)
    response = self.unlink(self.login(self.author), comment, 'person', self.joot.token, next_url='/comments/')
    self.assertRedirects(response, '/comments/', fetch_redirect_response=False)
    self.assertEqual(Comment.objects.get(pk=comment.pk).content, 'Joot')
    from django.contrib.admin.models import LogEntry
    self.assertTrue(LogEntry.objects.filter(change_message__startswith='Removed the link of a mention').exists())

  def test_staff_may_and_next_stays_on_this_site(self):
    comment = self.comment(f'[Joot](person:{self.joot.token})')
    response = self.unlink(self.login(self.staff), comment, 'person', self.joot.token, next_url='https://elders.example/')
    self.assertRedirects(response, '/', fetch_redirect_response=False)                # not to another site
    self.assertEqual(Comment.objects.get(pk=comment.pk).content, 'Joot')

  def test_housekeeping_lists_them(self):
    self.comment(f'zie [Ingetrokken](person:{self.revoked.token})')
    html = self.login(self.staff).get('/dashboard/housekeeping/mentions/').content.decode()
    self.assertIn('Ingetrokken', html)
    self.assertIn('/mentions/unlink/', html)

  def test_remove_link_in_edit_mode_only_for_who_may(self):
    self.comment(f'zie [Joot](person:{self.joot.token})')
    client = self.login(self.author)
    client.post('/ui/edit/', {'on': '1', 'next': '/'})
    self.assertNotIn('remove link', client.get(self.joot.page_url()).content.decode())   # the author may - but has no edit mode for people
    staff = self.login(self.staff)
    staff.post('/ui/edit/', {'on': '1', 'next': '/'})
    self.assertIn('remove link', staff.get(self.joot.page_url()).content.decode())


class MentionWarningTests(TestCase):
  """Before revoking or deleting something that's mentioned: say so - and
  where to fix it after."""

  def setUp(self):
    from django.contrib.auth.models import Permission
    self.staff = get_user_model().objects.create(username='staf', is_staff=True)
    for codename in ('change_person', 'delete_content', 'delete_place'):
      self.staff.user_permissions.add(Permission.objects.get(codename=codename))
    self.staff.save()
    self.joot = Person.objects.create(given_name='Joot', user=self.staff, status='p', visibility='c')
    self.corry = Person.objects.create(given_name='Corry', user=self.staff, status='p', visibility='c', biography='')
    self.client = Client()
    self.client.force_login(self.staff)
    self.client.post('/ui/edit/', {'on': '1', 'next': '/'})

  def mention_joot(self):
    self.corry.biography = f'trouwt [Joot](person:{self.joot.token})'
    self.corry.save()

  def test_status_buttons_warn_when_mentioned(self):
    html = self.client.get(self.joot.page_url()).content.decode()
    self.assertNotIn("It's mentioned in", html)
    self.mention_joot()
    html = self.client.get(self.joot.page_url()).content.decode()
    self.assertIn("It's mentioned in 1 text - that link will lead nowhere for most readers.", html)

  def test_after_revoking_where_to_fix(self):
    from people.forms import PersonStatusForm
    from django.test import RequestFactory
    self.mention_joot()
    request = RequestFactory().post('/')
    request.user = self.staff
    request.session = {}
    form = PersonStatusForm({'status': 'r', 'reason': 'dubbel'}, instance=self.joot)
    form.request = request
    self.assertTrue(form.is_valid(), form.errors)
    form.save()
    self.assertIn('Housekeeping → mentions that lead nowhere', form.success_message())

  def test_a_mentioned_place_isnt_unused(self):
    from dashboard.housekeeping import unused_places
    from places.models import Place
    place = Place.objects.create(name='Rengat', user=self.staff)
    self.assertIn(place, unused_places())
    self.corry.biography = f'woonde in [Rengat](place:{place.token})'
    self.corry.save()
    self.assertNotIn(place, unused_places())
