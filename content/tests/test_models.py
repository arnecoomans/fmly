import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings

from content.files import is_meaningless_filename
from content.models import Content, Portrait
from people.models import Person

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA)
class ContentTestCase(TestCase):
  @classmethod
  def tearDownClass(cls):
    super().tearDownClass()
    shutil.rmtree(MEDIA, ignore_errors=True)

  def setUp(self):
    self.user = get_user_model().objects.create(username='owner')

  def make(self, filename=None, **fields):
    content = Content(user=self.user, **fields)
    if filename:
      content.file = ContentFile(b'data', name=filename)
    content.save()
    return content

  def stored_name(self, content):
    return content.file.name.rsplit('/', 1)[-1]


class MeaninglessFilenameTests(TestCase):
  def test_meaningless(self):
    for name in ['IMG_1234.JPG', 'DSC01234.jpg', 'PXL_20230101_123456.jpg', 'Schermafbeelding 2023-12-10 om 10.00.00.png',
                 'Screenshot 2024-01-01.png', 'WhatsApp Image 2023-01-01 at 12.00.00.jpeg',
                 '140E6992-CC70-44F1-BEAB-7D7A7A98595C.jpeg', '0001.jpg', 'scan.pdf', 'image3.png', '']:
      self.assertTrue(is_meaningless_filename(name), name)

  def test_scanner_names(self):
    for name in ['Scan 2 Oct 2026 at 16.11 page 15.jpg', 'Scan_20_Jan_2022_at_16.04_page_1.jpg',
                 'Scan 2 okt. 2026 om 16.11 pagina 15.jpg', 'Scannen.jpg', 'Scannen0009.jpg', 'Scannen0018_gekleurd.jpg']:
      self.assertTrue(is_meaningless_filename(name), name)
    self.assertFalse(is_meaningless_filename('Scan van het paspoort van Johan.jpg'))   # words: kept

  def test_meaningless_after_a_date(self):
    for name in ['2023-12-10-IMG_1234.jpg', '2023-12-10_IMG_1234.JPG', '20231210_123456.jpg',
                 '2023-12-10-Screenshot 2023-12-10.png', '2023-12-10.jpg']:
      self.assertTrue(is_meaningless_filename(name), name)

  def test_date_followed_by_words_is_meaningful(self):
    for name in ['2026-09-15-Guido Gezelles dichtwerken II.jpg', '2023-12-10-wimmy reny bake.png']:
      self.assertFalse(is_meaningless_filename(name), name)

  def test_meaningful(self):
    for name in ['NL-HaNA_2.10.50.03_418_0867s.jpg', 'Paspoort Johan Coomans.jpg', 'Eric_18.jpg',
                 '1985_Nederlands_Patriciaat.pdf', 'familiewapen_Bake.png']:
      self.assertFalse(is_meaningless_filename(name), name)


class FilenameSyncTests(ContentTestCase):
  def test_meaningless_upload_is_named_after_slug_and_follows_it(self):
    content = self.make('IMG_1234.JPG')
    self.assertEqual(content.original_filename, 'IMG_1234.JPG')
    # No name yet: the slug comes from the token, and the file is named after it.
    self.assertEqual(content.slug, content.token.lower())
    self.assertEqual(self.stored_name(content), f'{content.slug}.jpg')
    content.name = 'Paspoort Johan Coomans'
    content.save()
    self.assertEqual(content.slug, 'paspoort-johan-coomans')
    self.assertEqual(self.stored_name(content), 'paspoort-johan-coomans.jpg')
    self.assertTrue(content.file.storage.exists(content.file.name))
    self.assertEqual(content.original_filename, 'IMG_1234.JPG')

  def test_meaningful_name_is_kept(self):
    content = self.make('NL-HaNA_2.10.50.03_418_0867s.jpg', name='Interneringskaart')
    self.assertEqual(self.stored_name(content), 'NL-HaNA_2.10.50.03_418_0867s.jpg')
    content.name = 'Something else'
    content.save()
    self.assertEqual(self.stored_name(content), 'NL-HaNA_2.10.50.03_418_0867s.jpg')

  def test_unnamed_meaningful_upload_takes_slug_from_filename(self):
    content = self.make('Paspoort Johan.jpg')
    self.assertEqual(content.slug, 'paspoort-johan')

  def test_sync_is_stable(self):
    content = self.make('IMG_1.jpg', name='Same name')
    other = self.make('IMG_2.jpg', name='Same name')
    self.assertNotEqual(content.slug, other.slug)
    self.assertFalse(other.sync_filename())
    self.assertFalse(content.sync_filename())

  def test_file_moves_to_year_of_date_created(self):
    content = self.make('IMG_1.jpg', name='Old photo')
    Content.objects.filter(pk=content.pk).update(date_created='2022-01-06T12:00:00Z')
    content.refresh_from_db()
    self.assertTrue(content.sync_filename())
    self.assertEqual(content.file.name, 'content/2022/old-photo.jpg')
    self.assertTrue(content.file.storage.exists(content.file.name))

  def test_record_without_file(self):
    content = self.make(name='Missing cover', original_filename='cover.JPG')
    self.assertFalse(content.sync_filename())
    self.assertEqual(content.media_type, 'image')


class ContentModelTests(ContentTestCase):
  def test_default_kind_is_unknown_without_detail(self):
    content = self.make('IMG_1.jpg')
    self.assertEqual(content.kind, Content.Kind.UNKNOWN)
    self.assertIsNone(content.get_detail())

  def test_detail_created_when_kind_is_set(self):
    content = self.make('IMG_1.jpg')
    content.kind = Content.Kind.DOCUMENT
    content.save()
    self.assertEqual(content.get_detail().document_kind, 'other')

  def test_media_type_from_file(self):
    self.assertEqual(self.make('a.pdf', name='a').media_type, 'pdf')
    self.assertEqual(self.make('b.mp3', name='b').media_type, 'audio')

  def test_listable_hides_parts(self):
    book = self.make('front.jpg', name='Bushido', kind=Content.Kind.BOOK)
    part = self.make('back.jpg', name='Bushido back', parent=book, position=1)
    self.assertIn(book, Content.objects.listable())
    self.assertNotIn(part, Content.objects.listable())
    self.assertEqual(list(book.parts.all()), [part])


class PortraitTests(ContentTestCase):
  def setUp(self):
    super().setUp()
    self.photo = self.make('IMG_1.jpg', kind=Content.Kind.PHOTO)
    self.person = Person.objects.create(given_name='Eric', user=self.user)

  def test_one_primary_per_person(self):
    Portrait.objects.create(person=self.person, content=self.photo, is_primary=True)
    other = self.make('IMG_2.jpg', kind=Content.Kind.PHOTO)
    with self.assertRaises(IntegrityError), transaction.atomic():
      Portrait.objects.create(person=self.person, content=other, is_primary=True)

  def test_crop_all_or_nothing(self):
    self.assertIsNone(Portrait(person=self.person, content=self.photo).crop_box)
    with self.assertRaises(ValidationError):
      Portrait(person=self.person, content=self.photo, crop_x=0.1).clean()
    with self.assertRaises(ValidationError):
      Portrait(person=self.person, content=self.photo, crop_x=0.5, crop_y=0, crop_w=0.6, crop_h=0.5).clean()

  def test_reverse_accessors(self):
    Portrait.objects.create(person=self.person, content=self.photo)
    self.assertEqual(list(self.person.portraits.all()), [self.photo])


class DocumentLanguageTests(ContentTestCase):
  def test_new_document_has_no_language_yet(self):
    document = self.make(name='Brief', kind=Content.Kind.DOCUMENT)
    self.assertEqual(document.get_detail().language, '')

  def test_language_shown_on_the_content_page(self):
    document = self.make(name='Brief', kind=Content.Kind.DOCUMENT, status='p', visibility='p')
    detail = document.get_detail()
    detail.language = 'jv'
    detail.save()
    self.assertContains(self.client.get(document.get_absolute_url()), 'Javanese')

  def test_legacy_import_marks_documents_dutch(self):
    from legacy_import.management.commands.import_content import Command
    document = self.make(name='Paspoort', kind=Content.Kind.DOCUMENT)
    Command().set_detail_kind(document, 'identity')
    detail = Content.objects.get(pk=document.pk).get_detail()
    self.assertEqual((detail.document_kind, detail.language), ('identity', 'nl'))


class FindDocumentTests(ContentTestCase):
  def test_legacy_underscores_match_a_file_with_spaces(self):
    import tempfile
    from pathlib import Path
    from legacy_import.management.commands.import_content import Command
    folder = Path(tempfile.mkdtemp())
    (folder / 'De Japanse Burgerkampen.JPG').write_bytes(b'x')
    command = Command()
    command.documents = folder
    self.assertEqual(command.find_document('De_Japanse_Burgerkampen.JPG').name, 'De Japanse Burgerkampen.JPG')
    self.assertIsNone(command.find_document('Onbekend.jpg'))
