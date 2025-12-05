from django.db import models

class BaseIcon(models.Model):
  icon = models.CharField(max_length=255, blank=True, help_text='bootstrap icon name')

  class Meta:
    abstract = True

  def get_icon_file(self):
    if self.icon:
      return f'img/bootstrap-icons/{self.icon}.svg'
    return 'img/bootstrap-icons/list.svg'