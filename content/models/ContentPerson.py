from django.db import models
from django.utils.translation import gettext_lazy as _

from cmnsd.models.mixins import RegionMixin


class ContentPerson(RegionMixin, models.Model):
  """A person on an item (Content.people) and how (issue #471): in it
  (or perhaps), made it, received it, it's about them, it was theirs - or unknown (no
  role): linked, without saying how. One role per person per item. Not a
  mention: a mention is a text referring to someone (cmnsd Mention), kept
  from the text itself; this is a link someone chose.

  The table is the one Content.people always had (content_content_people):
  existing links became rows without a role - not a guess from the kind of
  item. A book's authors aren't here but on its detail (BookContent.authors):
  on a book, creator isn't offered.

  Where they are on it (issue #480): a frame (RegionMixin - a box as
  fractions of the image as shown), for who is where on a photo. A portrait
  (content.Portrait) is a face on a photo too: the frames started from the
  portrait crops (migration 0007), and a portrait builds on its frame."""

  class Role(models.TextChoices):
    # In order of weight: where several fit, the first that does is the one
    # (a passport request with his photo: subject, not depicted). The menu
    # and the person page's pills follow this order.
    SUBJECT = 'subject', _("subject")       # it's about them - their record, their request
    CREATOR = 'creator', _("creator")       # wrote or made it - a letter, a photo (the photographer)
    ADDRESSEE = 'addressee', _("addressee") # it's addressed to them - a letter, a postcard
    DEPICTED = 'depicted', _("depicted")    # in it - a photo; #472's "seen in"
    # Perhaps in it - an identification to confirm. Its own value, as
    # "possibly family": what builds on depicted (seen in, portraits, the
    # GEDCOM export) leaves it out; readers see the doubt.
    POSSIBLY_DEPICTED = 'possibly_depicted', _("possibly depicted")
    OWNER = 'owner', _("owner")             # it was theirs - a library, a passport, a medal

  # Who can be pointed out on it: who is depicted (or possibly) - or not
  # known yet (no role: pointing out is a reason to set it). Not a subject -
  # it's about them, which is another thing than where they are in it - nor
  # a creator, addressee or owner. A frame kept from before shows again when
  # the role is one of these.
  FRAME_ROLES = ('', Role.DEPICTED, Role.POSSIBLY_DEPICTED)

  content = models.ForeignKey('content.Content', on_delete=models.CASCADE, related_name='person_links')
  person = models.ForeignKey('people.Person', on_delete=models.CASCADE, related_name='content_links')
  role = models.CharField(max_length=20, choices=Role.choices, blank=True, default='')

  class Meta:
    db_table = 'content_content_people'
    unique_together = [('content', 'person')]

  def __str__(self):
    return f"{self.person} - {self.content}" + (f" ({self.get_role_display()})" if self.role else '')
