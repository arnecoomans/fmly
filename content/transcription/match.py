"""
Finding the part of a longer text that an image shows: Delpher's article
text (good OCR, but often more than the clipping - a column of ads run
together) against a rough OCR of the clipping itself. The stretch of
Delpher's words that shares the most words with the rough OCR is the
clipping; Delpher's own wording is returned, being the better OCR.
"""

import re
from collections import Counter
from difflib import SequenceMatcher

# Below this share of the rough OCR's words found in the best stretch, the
# match isn't trusted (a bad OCR, or a clipping Delpher's text doesn't hold).
MIN_SHARE = 0.4

_WORD = re.compile(r"\w+", re.UNICODE)


def _norm(word):
  return word.lower()


def words(text):
  """[(word as written, normalized)] - punctuation stays with the written
  word, matching uses letters and digits only."""
  result = []
  for token in (text or '').split():
    letters = ''.join(_WORD.findall(token))
    if letters:
      result.append((token, _norm(letters)))
  return result


def without_noise(text):
  """The OCR text without lines of noise - a ruled line or a scratch read
  as letters ("he gem te 7 lt vn"): three or more fragments, mostly one or
  two characters long. Only for matching; a real short line ("T 1880") has
  fewer fragments and stays."""
  kept = []
  for line in (text or '').splitlines():
    tokens = [norm for _token, norm in words(line)]
    if len(tokens) >= 3 and sum(1 for t in tokens if len(t) <= 2) / len(tokens) >= 0.7:
      continue
    kept.append(line)
  return '\n'.join(kept)


def best_part(long_text, rough_text):
  """(part of long_text, share) - the stretch of long_text, about as long
  as rough_text, sharing the most words with it; share = matched words /
  rough words. (None, 0) when there's nothing to compare."""
  long_words = words(long_text)
  rough = [norm for _token, norm in words(without_noise(rough_text))]
  if not long_words or not rough:
    return None, 0
  wanted = Counter(rough)
  size = min(len(rough), len(long_words))
  normalized = [norm for _token, norm in long_words]

  # Slide a window of the rough text's length over the long text, keeping
  # the window with the most words in common (multiset overlap).
  window = Counter(normalized[:size])
  best_start, best_score = 0, sum((window & wanted).values())
  for start in range(1, len(normalized) - size + 1):
    window[normalized[start - 1]] -= 1
    window[normalized[start + size - 1]] += 1
    score = sum((window & wanted).values())
    if score > best_score:
      best_start, best_score = start, score

  # Trim the ends by order, not just by word: align the stretch with the
  # rough OCR word by word, and keep from the first to the last aligned
  # word - a common word right after the clipping ("te", the next ad's
  # first line) isn't kept just because the clipping also has it.
  stop = best_start + size
  blocks = [b for b in SequenceMatcher(None, normalized[best_start:stop], rough, autojunk=False).get_matching_blocks() if b.size]
  if blocks:
    stop = best_start + blocks[-1].a + blocks[-1].size
    best_start = best_start + blocks[0].a
  part = ' '.join(token for token, _norm in long_words[best_start:stop])
  return part, best_score / len(rough)
