from django.db import models
from django.utils.translation import gettext_lazy as _


class PersonRelation(models.Model):
  class RelationType(models.TextChoices):
    PARENT = "parent", _("parent")
    PARTNER = "partner", _("partner")
    OTHER = "other", _("other")

  person_from = models.ForeignKey('Person', on_delete=models.CASCADE, related_name='relations_from')
  person_to = models.ForeignKey('Person', on_delete=models.CASCADE, related_name='relations_to')
  relation_type = models.CharField(max_length=10, choices=RelationType.choices)

  class Meta:
    unique_together = ('person_from', 'person_to', 'relation_type')
    indexes = [
      # Real query shapes always pair one FK side with relation_type
      # ("X's children", "X's parents", "X's partners") - the
      # unique_together index only partially serves person_from+type
      # (person_to sits between them), and doesn't cover person_to+type
      # at all.
      models.Index(fields=['person_from', 'relation_type']),
      models.Index(fields=['person_to', 'relation_type']),
    ]
    constraints = [
      models.CheckConstraint(
        condition=~models.Q(person_from=models.F('person_to')),
        name='personrelation_no_self_relation',
      ),
    ]

  def save(self, *args, **kwargs):
    # PARTNER is symmetric (A-partner-B is the same fact as B-partner-A),
    # unlike PARENT/OTHER which are directional - order the pair canonically
    # so the same partnership can never be stored as two independent rows
    # that could drift out of sync. Querying still needs to check both
    # relations_from and relations_to, since which side a given person
    # lands on depends on the *other* person's pk, not on them specifically.
    if self.relation_type == self.RelationType.PARTNER and self.person_from_id and self.person_to_id:
      if self.person_from_id > self.person_to_id:
        self.person_from_id, self.person_to_id = self.person_to_id, self.person_from_id
    super().save(*args, **kwargs)

  def __str__(self):
    return f"{self.person_from} is {self.get_relation_type_display()} of {self.person_to}"
