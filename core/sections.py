"""A Markdown text in sections - for editing one at a time, not for showing:
the text stays one field, as written; a page in edit mode shows it per
section, each with its own pencil (a note's body, note/blocks/body.html).

A section starts at a heading line (# to ######) and runs to the next one;
text before the first heading is a section of its own (an intro). A # in a
fenced code block (``` or ~~~) is no heading. Joined, the sections are the
text exactly - nothing is rewritten.

Saving one puts the new text in its place: removing its heading merges it
into the one above, typing a heading splits it - both follow from the text.
Empty, it's removed. One past the last is a new section at the end.
"""

import re

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from cmnsd.forms.widgets import MentionTextarea

HEADING = re.compile(r'#{1,6}(?!#)')
FENCE = re.compile(r'\s{0,3}(```|~~~)')


def split_sections(text):
  """The text's sections, as written: ''.join(them) == text. [] for none."""
  sections, current, fenced = [], [], False
  for line in (text or '').splitlines(keepends=True):
    if FENCE.match(line):
      fenced = not fenced
    elif not fenced and HEADING.match(line) and current:
      sections.append(''.join(current))
      current = []
    current.append(line)
  if current:
    sections.append(''.join(current))
  return sections


def replace_section(text, index, new):
  """The text with section `index` replaced by `new` - its blank lines
  after kept, so the next heading stays apart. `index` one past the last:
  added at the end. Empty `new`: the section removed."""
  sections = split_sections(text)
  new = new.strip('\r\n')
  if index >= len(sections):
    if not new:
      return text
    before = (text or '').rstrip('\r\n')
    return f"{before}\n\n{new}\n" if before else f"{new}\n"
  old = sections[index]
  trail = old[len(old.rstrip('\r\n')):]
  if new and index < len(sections) - 1 and trail.count('\n') < 2:
    trail = '\n\n'                       # a heading follows: a blank line before it
  sections[index] = f"{new}{trail}" if new else ''
  return ''.join(sections)


class SectionForm(forms.ModelForm):
  """One section of a Markdown field (`section_field`) - a block form for
  cmnsd object_form. Opened with ?section=<n> (one past the last: a new
  one), which goes along as a hidden field. The page reloads after a save:
  the sections - and their numbers - follow from the new text. The stale
  check (the object's date_modified) keeps the number right: a text
  changed since the form was opened isn't saved into."""
  section_field = 'body'
  reload_page = 'always'

  section = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
  text = forms.CharField(required=False, label=_("section"), widget=MentionTextarea(attrs={'rows': 8}))

  def prepare(self):
    raw = self.data.get(self.add_prefix('section')) if self.is_bound else self.request.GET.get('section')
    try:
      index = max(0, int(raw))
    except (TypeError, ValueError):
      index = 0
    sections = split_sections(getattr(self.instance, self.section_field))
    index = min(index, len(sections))
    self.initial['section'] = index
    self.initial['text'] = sections[index].rstrip('\r\n') if index < len(sections) else '# '
    self.is_new = index == len(sections)

  def clean(self):
    data = super().clean()
    if 'section' in data and data['section'] > len(split_sections(getattr(self.instance, self.section_field))):
      raise ValidationError(_("That section isn't there any more - reload the page."))
    if 'section' in data and 'text' in data:
      text = data['text'] if data['text'].strip() not in ('', '#') else ''
      setattr(self.instance, self.section_field, replace_section(getattr(self.instance, self.section_field), data['section'], text))
    return data
