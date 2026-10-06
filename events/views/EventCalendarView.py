import calendar
from datetime import date

from django.utils import formats
from django.views.generic import TemplateView

from ..anniversaries import anniversaries


class EventCalendarView(TemplateView):
  """events/calendar/?month=10 - a month of anniversaries: every event with
  a known day, by day, across the years (events/anniversaries.py:
  only what this viewer may see, a birth only of someone who has died).
  The current month by default, today marked; previous / next month."""
  template_name = 'event/event_calendar.html'

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    today = date.today()
    try:
      month = int(self.request.GET.get('month', today.month))
    except ValueError:
      month = today.month
    if not 1 <= month <= 12:
      month = today.month
    days = {}
    for event in anniversaries(self.request, month=month):
      days.setdefault(event.day, []).append(event)
    context.update({
      'month': month,
      'month_name': formats.date_format(date(2000, month, 1), 'F'),
      'days': sorted(days.items()),
      'today': today.day if month == today.month else None,
      'previous': 12 if month == 1 else month - 1,
      'next': 1 if month == 12 else month + 1,
      'months': [(m, formats.date_format(date(2000, m, 1), 'M')) for m in range(1, 13)],
      'count': sum(len(events) for events in days.values()),
    })
    return context
