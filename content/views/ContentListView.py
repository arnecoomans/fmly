from django.views.generic import ListView

from cmnsd.api.filtering import build_list, list_context

from ..models import Content


class ContentListView(ListView):
  """/content/ - every whole this viewer may see (parts show on their
  whole's page), with filters by kind and the remembered sort (content
  grid), unpaginated like the People list. Visibility, status and ?q=
  search come from cmnsd.api.filtering.build_list() - the same function
  the list API (live search) uses - and both render
  content/content_list.html."""
  model = Content
  template_name = 'content/content_list_page.html'

  def get(self, request, *args, **kwargs):
    self.result = build_list(Content, request)
    return super().get(request, *args, **kwargs)

  def get_queryset(self):
    return self.result['objects']

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context.update(list_context(Content, self.result, self.request))
    return context
