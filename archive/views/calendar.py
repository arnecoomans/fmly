import datetime
from django.views.generic import ListView

from archive.models import Event
from archive.models.Event import MONTHS


class BirthdayCalendarView(ListView):
  model = Event
  template_name = 'archive/calendar/birthday.html'

  def get_queryset(self):
    return (
      Event.objects
      .filter(type='birth', month__isnull=False)
      .prefetch_related('people')
      .order_by('month', 'day')
    )

  def _get_death_year_map(self):
    """Return {person_pk: year} for all death events."""
    death_year_map = {}
    for event in Event.objects.filter(type='death').prefetch_related('people'):
      for person in event.people.all():
        death_year_map[person.pk] = event.year
    return death_year_map

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    today = datetime.date.today()

    death_year_map = self._get_death_year_map()

    # Build month -> day -> [(person, birth_year, death_year)]
    event_map = {}
    for event in context['object_list']:
      for person in event.people.all():  # uses prefetch cache — no extra queries
        (
          event_map
          .setdefault(event.month, {})
          .setdefault(event.day, [])
          .append((person, event.year, death_year_map.get(person.pk)))
        )

    # All 12 months, each with a full day list of 31 slots
    context['calendar'] = [
      (num, label, [(day, event_map.get(num, {}).get(day, [])) for day in range(1, 32)])
      for num, label in MONTHS
    ]
    context['today'] = today
    context['active_page'] = 'calendar'
    return context
