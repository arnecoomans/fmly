from dataclasses import dataclass


@dataclass
class Guess:
  """A guessed transcription: the text, its language (a content.languages
  code, or '' when unknown) and a note for the person checking it."""
  text: str
  language: str = ''
  note: str = ''


class TranscriptionSource:
  """One way to guess what's written on an item. Subclasses say whether
  they apply to this item (applies), whether they can run on this server
  at all (available) and do the guessing (guess). Both checks return
  (bool, reason) - the reason is shown with a disabled option."""
  name = ''
  label = ''        # the button: says plainly what it does ("Fetch text from Delpher")
  short = ''        # in messages: "Delpher found no text"
  icon = 'file-text'
  explanation = ''  # one line under the button: what happens, what's sent where

  def applies(self, content):
    return True, ''

  def available(self):
    return True, ''

  def guess(self, content):
    """A Guess, or None when nothing useful came back. May raise
    TranscriptionError with a readable message."""
    raise NotImplementedError


class TranscriptionError(Exception):
  """A source couldn't deliver - the message is shown to the user."""
