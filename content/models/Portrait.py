from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

_fraction = [MinValueValidator(0.0), MaxValueValidator(1.0)]


class Portrait(models.Model):
  """A photo used as a person's portrait (Person.portraits /
  Content.portrait_of) - a through table, so one group photo can be the
  portrait of several people, each with their own crop.

  The crop is stored as fractions of the image (0-1), not pixels, so it
  survives the file being replaced by a larger scan - of the image as shown,
  turned by `rotation` first. All crop fields empty = the whole image. is_primary marks the one used for the avatar - at most
  one per person."""

  person = models.ForeignKey('people.Person', on_delete=models.CASCADE, related_name='portrait_links')
  content = models.ForeignKey('content.Content', on_delete=models.CASCADE, related_name='portrait_links')
  crop_x = models.FloatField(null=True, blank=True, validators=_fraction)
  crop_y = models.FloatField(null=True, blank=True, validators=_fraction)
  crop_w = models.FloatField(null=True, blank=True, validators=_fraction)
  crop_h = models.FloatField(null=True, blank=True, validators=_fraction)
  is_primary = models.BooleanField(default=False)
  # Turned before cropping, clockwise: for a photo pasted sideways (e.g. on
  # a passport page). The crop is taken on the turned photo - as the
  # cropper shows it (people.forms.PersonPortraitForm).
  rotation = models.PositiveSmallIntegerField(
    default=0, choices=[(0, '0°'), (90, '90°'), (180, '180°'), (270, '270°')],
  )

  class Meta:
    constraints = [
      models.UniqueConstraint(fields=['person', 'content'], name='content_portrait_unique_person_content'),
      models.UniqueConstraint(fields=['person'], condition=Q(is_primary=True), name='content_portrait_one_primary_per_person'),
    ]

  def __str__(self):
    return f"{self.person} - {self.content}"

  @property
  def crop_box(self):
    """(x, y, w, h) as fractions, or None for the whole image."""
    values = (self.crop_x, self.crop_y, self.crop_w, self.crop_h)
    return None if any(v is None for v in values) else values

  @property
  def version(self):
    """Changes whenever the crop changes - appended to the avatar URL so a
    browser doesn't keep showing the previous crop from its cache."""
    crop = '-'.join(f'{v:.4f}' for v in self.crop_box) if self.crop_box else 'full'
    return f'{crop}-r{self.rotation}' if self.rotation else crop

  def clean(self):
    values = (self.crop_x, self.crop_y, self.crop_w, self.crop_h)
    if any(v is not None for v in values) and self.crop_box is None:
      raise ValidationError(_("Set all four crop values, or none."))
    if self.crop_box and (self.crop_x + self.crop_w > 1 or self.crop_y + self.crop_h > 1):
      raise ValidationError(_("The crop must lie within the image."))
