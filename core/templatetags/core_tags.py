from django import template

register = template.Library()

@register.filter(name='dict_get')
def dict_get(dictionary, key):
    """Obtiene un valor de un diccionario por clave dinámica."""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None

@register.filter(name='attr')
def get_attribute(obj, attr_name):
    """Obtiene un atributo de un objeto."""
    return getattr(obj, attr_name, None)
