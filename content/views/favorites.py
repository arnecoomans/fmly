from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView


class FavoritesView(LoginRequiredMixin, TemplateView):
  """content/favorites/ - your favorites (issue #453): the items you
  favorited and may still see, the most recently favorited first, in the
  content grid (core.favorites.my_favorites)."""
  template_name = 'content/favorites.html'

  def get_context_data(self, **kwargs):
    from core.favorites import my_favorites
    context = super().get_context_data(**kwargs)
    context['items'] = my_favorites(self.request)
    return context
