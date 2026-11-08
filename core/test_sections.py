from django.test import SimpleTestCase

from core.sections import replace_section, split_sections

TEXT = """# Algemene archieven
* CBG
* [IGV](https://igv.nl/)

# Gemeentelijke archieven
* Den Haag

# Hulpmiddelen
* Delpher
"""


class SectionTests(SimpleTestCase):
  """A Markdown text in sections (core/sections.py): split at headings,
  joined back exactly; one replaced, removed, merged, split or added."""

  def test_split_and_joined_exactly(self):
    sections = split_sections(TEXT)
    self.assertEqual(len(sections), 3)
    self.assertEqual(''.join(sections), TEXT)
    self.assertTrue(sections[1].startswith('# Gemeentelijke'))
    self.assertEqual(''.join(split_sections(TEXT.replace('\n', '\r\n'))), TEXT.replace('\n', '\r\n'))   # as a browser sends it

  def test_an_intro_and_code(self):
    text = "Intro\n\n# Een\n```\n# geen kop\n```\n## Twee\n"
    self.assertEqual([s.splitlines()[0] for s in split_sections(text)], ['Intro', '# Een', '## Twee'])
    self.assertEqual(split_sections(''), [])

  def test_replace_keeps_the_rest(self):
    new = replace_section(TEXT, 1, "# Gemeentelijke archieven\n* Den Haag\n* Utrecht")
    self.assertEqual(new, TEXT.replace("* Den Haag\n", "* Den Haag\n* Utrecht\n"))

  def test_remove_merge_split_add(self):
    self.assertNotIn('Gemeentelijke', replace_section(TEXT, 1, ''))
    self.assertEqual(len(split_sections(replace_section(TEXT, 1, '* Den Haag'))), 2)                     # heading gone: joins the one above
    self.assertEqual(len(split_sections(replace_section(TEXT, 1, '# A\n* x\n\n# B\n* y'))), 4)           # a heading typed: split
    added = replace_section(TEXT, 3, '# Kranten\n* Delpher')
    self.assertTrue(added.endswith('* Delpher\n\n# Kranten\n* Delpher\n'))

  def test_a_heading_after_keeps_its_blank_line(self):
    self.assertIn("* Den Haag\n* Rotterdam\n\n# Hulpmiddelen", replace_section(TEXT.replace("* Den Haag\n\n", "* Den Haag\n"), 1, "# Gemeentelijke archieven\n* Den Haag\n* Rotterdam"))
