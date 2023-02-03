
from django.db import models

class Attendee(models.Model):
  name                = models.CharField(max_length=255)
  email               = models.EmailField(max_length=254)

  def __str__(self) -> str:
    return self.name