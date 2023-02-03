from django import template

register = template.Library()

@register.filter
def dictkey(dict, key):    
  return dict[key]