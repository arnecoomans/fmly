from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase


class EditToggleHeaderTests(TestCase):
  """The Edit switch in header.html (cmnsd/edit/mode.py): shown to users
  with a change permission, pressed + body.is-edit-mode while on."""

  def login(self, username, perm=None):
    user = get_user_model().objects.create(username=username)
    if perm:
      user.user_permissions.add(Permission.objects.get(codename=perm))
    user.save()
    client = Client()
    client.force_login(user)
    return client

  def page(self, client):
    return client.get('/people/').content.decode().replace('"', '')

  def test_editor_gets_the_switch_off_by_default(self):
    html = self.page(self.login('editor', 'change_content'))
    self.assertIn('class=edit-toggle', html)
    self.assertIn('aria-pressed=false', html)
    self.assertNotIn('is-edit-mode', html)

  def test_switch_on_marks_the_page(self):
    client = self.login('editor', 'change_content')
    client.post('/ui/edit/', {'on': '1', 'next': '/people/'})
    html = self.page(client)
    self.assertIn('aria-pressed=true', html)
    self.assertIn('class=is-edit-mode', html)

  def test_member_and_visitor_get_no_switch(self):
    self.assertNotIn('edit-toggle', self.page(self.login('member')))
    self.assertNotIn('edit-toggle', self.page(Client()))


class MessageAreaTests(TestCase):
  """cmnsd/messages.html: always on the page, with the Django messages of
  that page load (e.g. after switching edit mode)."""

  def test_area_always_rendered(self):
    html = Client().get('/people/').content.decode().replace('"', '')
    self.assertIn('data-cmnsd-messages', html)

  def test_messages_shown_after_a_redirect(self):
    user = get_user_model().objects.create(username='editor')
    user.user_permissions.add(Permission.objects.get(codename='change_content'))
    user.save()
    client = Client()
    client.force_login(user)
    html = client.post('/ui/edit/', {'on': '1', 'next': '/people/'}, follow=True).content.decode().replace('"', '')
    self.assertIn('class=cmnsd-message cmnsd-message--info', html)
    self.assertIn('Edit mode is on.', html)


class ListEndpointTemplateTests(TestCase):
  """The API list endpoint renders <model>/<model>_list.html - a fragment.
  A page template under that name would come back whole inside the JSON
  (tags and comments had theirs there: now tag_overview / comment_overview)."""

  def setUp(self):
    from core.models import Tag
    self.user = get_user_model().objects.create(username='lister')
    self.user.save()
    Tag.objects.create(name='Boot', status='p', visibility='c', user=self.user)
    self.client.force_login(self.user)

  def test_tag_list_is_a_fragment(self):
    data = self.client.get('/api/tag/?q=boot').json()
    self.assertTrue(data['ok'])
    self.assertNotIn('<html', data.get('html', '').lower())
    self.assertIn('Boot', str(data.get('html') or data.get('results')))

  def test_comment_list_is_not_a_page(self):
    data = self.client.get('/api/comment/').json()
    self.assertNotIn('<html', data.get('html', '').lower())

  def test_pages_still_render(self):
    self.assertContains(self.client.get('/tags/'), 'tag-page__name')
    self.assertEqual(self.client.get('/comments/').status_code, 200)


class CommentTargetVisibilityTests(TestCase):
  """A comment is visible only where its target is too
  (Comment.filter_visibility) - also through the API's comment list and
  actions, not only on the comments page."""

  def setUp(self):
    from content.models import Content
    from core.models import Comment
    self.owner = get_user_model().objects.create(username='owner')
    self.owner.save()
    self.viewer = get_user_model().objects.create(username='viewer')
    self.viewer.save()
    hidden = Content.objects.create(name='Privé', kind='photo', user=self.owner, status='p', visibility='q')
    shown = Content.objects.create(name='Open', kind='photo', user=self.owner, status='p', visibility='c')
    self.on_hidden = Comment.objects.create(target=hidden, user=self.owner, content='Geheim', status='p', visibility='c')
    self.on_shown = Comment.objects.create(target=shown, user=self.owner, content='Open', status='p', visibility='c')
    self.client.force_login(self.viewer)

  def test_api_list_leaves_out_comments_on_hidden_items(self):
    tokens = [row['token'] for row in self.client.get('/api/comment/').json()['results']]
    self.assertEqual(tokens, [self.on_shown.token])

  def test_comments_page_and_owner(self):
    self.assertNotContains(self.client.get('/comments/'), 'Geheim')
    owner = Client()
    owner.force_login(self.owner)
    self.assertContains(owner.get('/comments/'), 'Geheim')                  # the item's owner sees both

  def test_no_action_on_a_hidden_items_comment(self):
    response = self.client.post(f'/api/comment/{self.on_hidden.token}/toggle_hidden/', '{}', content_type='application/json')
    self.assertEqual(response.status_code, 404)


class MarkdownAutolinkTests(TestCase):
  """|markdown links bare http(s) addresses (cmnsd/markdown/autolink.py) -
  still sanitized (nh3)."""

  def render(self, text):
    from cmnsd.templatetags.markdown import markdown
    return str(markdown(text))

  def test_bare_url_becomes_a_link_without_trailing_punctuation(self):
    html = self.render('Zie https://www.delpher.nl/view?query=a_b&coll=ddd.')
    self.assertIn('<a href="https://www.delpher.nl/view?query=a_b&amp;coll=ddd" target="_blank" rel="noopener noreferrer">', html)
    self.assertTrue(html.endswith('</a>.</p>'))

  def test_existing_links_and_code_stay_as_they_are(self):
    self.assertEqual(self.render('[bron](https://x.nl/a)').count('<a '), 1)
    self.assertNotIn('<a ', self.render('`https://code.nl`'))

  def test_only_http(self):
    self.assertNotIn('<a ', self.render('javascript:alert(1) en www.foo.nl'))


class MarkdownExternalLinksTests(TestCase):
  """|markdown: links to other sites open in a new tab
  (cmnsd/markdown/external_links.py), the site's own don't."""

  def render(self, text):
    from cmnsd.templatetags.markdown import markdown
    return str(markdown(text))

  def test_external_links_in_every_form(self):
    for text in ('[bron](https://www.delpher.nl/x)', 'zie https://openarchieven.nl/a', '<https://x.nl>'):
      self.assertIn('target="_blank"', self.render(text), text)

  def test_own_links_stay(self):
    self.assertNotIn('target=', self.render('[Willem](/person/abc/willem/)'))

  def test_no_other_target_gets_through(self):
    self.assertNotIn('target=', self.render('<a href="/x" target="_top">x</a>'))


class PrepareReleaseTests(TestCase):
  """manage.py prepare_release: the Loose end tag, the groups, and every
  account without a group a Visitor - twice is the same as once."""

  def test_prepare_release(self):
    from io import StringIO
    from django.contrib.auth.models import Group
    from django.core.management import call_command
    from core.tags import loose_end_tag
    User = get_user_model()
    User.objects.create(username='beheer', is_superuser=True)
    member = User.objects.create(username='lid')
    gone = User.objects.create(username='weg', is_active=False)
    for _ in range(2):
      call_command('prepare_release', stdout=StringIO())
    self.assertEqual(loose_end_tag().name, 'Loose end')
    visitors, editors = Group.objects.get(name='Visitors'), Group.objects.get(name='Editors')
    self.assertEqual(list(visitors.permissions.values_list('codename', flat=True)), ['add_comment'])
    member = User.objects.get(pk=member.pk)
    self.assertTrue(member.has_perm('core.add_comment'))
    self.assertFalse(member.has_perm('people.add_person'))
    self.assertFalse(gone.groups.exists())
    editor = User.objects.create(username='redacteur')
    editor.groups.add(editors)
    self.assertTrue(editor.has_perm('people.change_person'))
    self.assertTrue(editor.has_perm('content.add_transcript'))
    self.assertFalse(editor.has_perm('content.delete_content'))

  def test_all_editors(self):
    from io import StringIO
    from django.core.management import call_command
    User = get_user_model()
    User.objects.create(username='beheer', is_superuser=True)
    member = User.objects.create(username='lid')
    gone = User.objects.create(username='weg', is_active=False)
    call_command('prepare_release', all_editors=True, stdout=StringIO())
    self.assertEqual(sorted(member.groups.values_list('name', flat=True)), ['Editors', 'Visitors'])
    self.assertFalse(gone.groups.exists())

  def test_needs_a_superuser(self):
    from django.core.management import CommandError, call_command
    with self.assertRaises(CommandError):
      call_command('prepare_release')


class SearchTests(TestCase):
  """/search/ (core/search.py): every kind through its own list search,
  visibility first; transcripts, a book's author and a biography count,
  a hit in its text shows the words around it."""

  def setUp(self):
    from content.models import Content
    from people.models import Person
    User = get_user_model()
    self.user = User.objects.create(username='zoeker')
    self.user.save()
    self.other = User.objects.create(username='ander')
    self.client = Client()
    self.client.force_login(self.user)
    self.person = Person.objects.create(given_name='Albert', last_name='Coomans', biography='Het gezin kwam in 1946 weer bij elkaar in Medan.', user=self.user, status='p', visibility='c')
    Person.objects.create(given_name='Verborgen', last_name='Medan', user=self.other, status='p', visibility='q')
    self.letter = Content.objects.create(name='Brief', kind='document', user=self.user, status='p', visibility='c')

  def get(self, query, **params):
    return self.client.get('/search/', {'q': query, **params}).content.decode().replace('"', '')

  def test_names_and_texts(self):
    from content.models import Transcript
    Transcript.objects.create(content=self.letter, kind='original', language='nl', text='Lieve moeder, wij zijn veilig aangekomen in Medan.')
    html = self.get('medan')
    self.assertIn('Albert', html)                                  # by the biography
    self.assertIn('bij elkaar in <mark class=search-hit>Medan</mark>', html)
    self.assertIn('Brief', html)                                   # by the transcript
    self.assertIn('veilig aangekomen in', html)
    self.assertNotIn('Verborgen', html)                            # not theirs to see

  def test_a_hidden_part_doesnt_reveal_its_book(self):
    from content.models import Content, Transcript
    page = Content.objects.create(name='Pagina', kind='document', parent=self.letter, user=self.other, status='c', visibility='c')
    Transcript.objects.create(content=page, kind='original', language='nl', text='Geheime tekst over Padang')
    self.assertNotIn('Brief', self.get('padang'))
    page.status = 'p'
    page.save()
    self.assertIn('Brief', self.get('padang'))                     # visible now: its book is found

  def test_book_author(self):
    from content.models import Content
    book = Content.objects.create(name='Gedenkboek', kind='book', user=self.user, status='p', visibility='c')
    book.ensure_detail()
    book.book_detail.author = 'J. Fabricius'
    book.book_detail.save()
    self.assertIn('Gedenkboek', self.get('fabricius'))

  def test_one_kind_too_short_and_live(self):
    from content.models import Content
    for n in range(7):
      Content.objects.create(name=f'Foto Coomans {n}', kind='photo', user=self.user, status='p', visibility='c')
    html = self.get('coomans')
    self.assertIn('kind=content', html)                            # 7 hits, 5 shown: show all
    self.assertEqual(self.get('coomans').count('class=search-hit-row '), 1 + 5)          # Albert, 5 of the 7 photos
    self.assertEqual(self.get('coomans', kind='content').count('class=search-hit-row '), 7)
    self.assertIn('at least two letters', self.get('c'))
    response = self.client.get('/search/', {'q': 'albert'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
    self.assertIn('Albert', response.json()['html'])

  def test_signed_in_only(self):
    self.assertEqual(Client().get('/search/?q=medan').status_code, 302)
    self.assertNotIn('action=/search/', Client().get('/people/').content.decode().replace('"', ''))
    self.assertIn('action=/search/', self.client.get('/people/').content.decode().replace('"', ''))


class AdminLinkAndHierarchyTests(TestCase):
  """A comment links to where it's shown (admin "view on site"); a tag's
  hierarchy can't loop, and a looped one (saved around clean) still shows."""

  def test_comment_url(self):
    from content.models import Content
    from core.models import Comment
    user = get_user_model().objects.create(username='a')
    item = Content.objects.create(name='Foto', user=user, status='p', visibility='c')
    comment = Comment.objects.create(target=item, user=user, content='Mooi', status='p')
    self.assertEqual(comment.get_absolute_url(), f'{item.get_absolute_url()}#comment-{comment.token}')

  def test_no_loops(self):
    from django.core.exceptions import ValidationError
    from core.models import Tag
    user = get_user_model().objects.create(username='a')
    root = Tag.objects.create(name='Collection', user=user)
    child = Tag.objects.create(name='Paspoort', parent=root, user=user)
    root.parent = child
    with self.assertRaises(ValidationError):
      root.clean()
    Tag.objects.filter(pk=child.pk).update(parent=child)   # as the import once did
    child.refresh_from_db()
    self.assertEqual(str(child), 'Paspoort')


class PreferencesTests(TestCase):
  """/preferences/: language and family; relatives' accounts first."""

  def test_family_and_language(self):
    from people.models import Person, PersonRelation
    User = get_user_model()
    me, sister, stranger = (User.objects.create(username=n) for n in ('ik', 'zus', 'vreemde'))
    for user in (me, sister, stranger):
      user.save()
    mine = Person.objects.create(given_name='Ik', user=me, status='p', visibility='c', related_user=me)
    hers = Person.objects.create(given_name='Zus', user=me, status='p', visibility='c', related_user=sister)
    mother = Person.objects.create(given_name='Moeder', user=me, status='p', visibility='c')
    for child in (mine, hers):
      PersonRelation.objects.create(person_from=mother, person_to=child, relation_type=PersonRelation.RelationType.PARENT)
    client = Client()
    client.force_login(me)
    html = client.get('/preferences/').content.decode()
    self.assertLess(html.index('Zus'), html.index('vreemde'))               # the sister first, in the tree
    self.assertIn('in your family tree'.capitalize(), html)
    client.post('/preferences/', {'language': 'nl', 'family': [sister.pk]})
    me.refresh_from_db()
    self.assertEqual(list(me.preferences.family.all()), [sister])
    self.assertEqual(me.preferences.language, 'nl')
    self.assertEqual(Client().get('/preferences/').status_code, 302)          # signed in only
    menu = client.get('/people/').content.decode().replace('"', '')
    self.assertIn('href=/accounts/profile/', menu)
    self.assertIn('href=/preferences/', menu)


class MultilingualPageTests(TestCase):
  """cmnsd Page per language: the visitor's language, else the site's
  default; create_default_pages makes the cookie statement in both."""

  def test_language_and_fallback(self):
    from io import StringIO
    from django.core.management import call_command
    from cmnsd.models import Page
    from core.models import Preferences
    call_command('create_default_pages', stdout=StringIO())
    self.assertEqual(Page.objects.filter(slug='cookie-statement').count(), 2)
    self.assertContains(Client().get('/pages/cookie-statement/'), 'Cookie statement')    # signed out: the default
    user = get_user_model().objects.create(username='nederlander')
    user.save()
    Preferences.objects.create(user=user, language='nl')
    client = Client()
    client.force_login(user)
    self.assertContains(client.get('/pages/cookie-statement/'), 'Cookieverklaring')
    Page.objects.create(slug='over', language='en', title='About', body='Hi', status='p')
    self.assertContains(client.get('/pages/over/'), 'About')                               # no Dutch one: the default
    self.assertEqual(client.get('/pages/nergens/').status_code, 404)
