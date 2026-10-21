"""
"Same day" in a list of events (event/_event.html same_day): a row on the
exact date of the row before it says so instead of repeating the date -
twins, a mother dying the day her child is born, a double wedding:
connections that take effort to spot otherwise. Only a complete, exact date
(a year, or "ca.", isn't a moment); and only within a group, where the list
has groups a filter can hide (a timeline's history), so it never points at a
row that isn't shown.
"""


def day_of(event):
  """(year, month, day) for a complete, exact date - else None."""
  if event.year and event.month and event.day and event.date_qualifier == 'exact':
    return (event.year, event.month, event.day)
  return None


def mark_same_day(rows, event=lambda row: row, group=lambda row: None):
  """row.same_day for each row, in the list's order. `event`: the row's
  event (a timeline entry holds one); `group`: rows are compared only
  within theirs."""
  previous = {}
  for row in rows:
    key = day_of(event(row))
    row.same_day = key is not None and previous.get(group(row)) == key
    previous[group(row)] = key
  return rows
