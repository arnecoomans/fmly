# Testing

FMLY3 uses Django's own test runner. The tests are in each app's `tests.py` or `tests/` folder - cmnsd's included.

```sh
.venv/bin/python manage.py test                      # everything, a few seconds
.venv/bin/python manage.py test people               # one app
.venv/bin/python manage.py test content.tests.test_upload.InboxTests   # one class
```

Every change ends with the full suite green.

## Writing a test

- **Plain models, no fixtures:** create what the test needs in `setUp` (`Person.objects.create(...)`). Shared helpers live in the test module, like `DashboardTestCase.person()`.
- **Signing in:** call `user.save()` before `client.force_login(user)` - without it, Django 6 sessions don't hold.
- **Permissions:** add exactly the codenames the test needs (`Permission.objects.get(codename='add_content')`), so a test also shows what the feature requires.
- **Edit mode:** post to `/ui/edit/` with `on=1`, as the header's switch does.
- **The API:** `client.post('/api/<model>/<token>/<action>/', json.dumps(...), content_type='application/json')`; an edit block's form at `/api/<model>/<token>/form/<block>/` with the block name as the field prefix.

## Privacy in tests

For anything that shows objects, test a viewer who may **not** see them: another account, a signed-out visitor, a private or draft object. Most bugs worth catching are a hidden name or count showing up.

## Files

Tests that store files use a temporary media folder - **never** the real `private/`:

```python
MEDIA = tempfile.mkdtemp()

@override_settings(MEDIA_ROOT=MEDIA, SENDFILE_ROOT=MEDIA, SENDFILE_BACKEND='django_sendfile.backends.simple')
class MyTests(TestCase):
  @classmethod
  def tearDownClass(cls):
    super().tearDownClass()
    shutil.rmtree(MEDIA, ignore_errors=True)
```

A subclass inherits the override. To check nothing leaks, count the files in `private/` before and after a full run - they must be equal.

## Things the setup takes care of

- **Static files:** while testing, plain file names are used (`TESTING` in `fmly/settings.py`), so no `collectstatic` is needed.
- **Minified HTML:** compare without quotes - `html.replace('"', '')`.
- **Language:** switch it with `translation.override()`, never `activate()` - that leaks into the next test, which then sees Dutch dates.

## Trying a change in a browser

Use a **copy** of the database for anything that writes - `sqlite3 db.sqlite3 ".backup /tmp/probe.sqlite3"` and `DATABASE_URL=sqlite:////tmp/probe.sqlite3 manage.py runserver` - so a probe never changes the real archive.
