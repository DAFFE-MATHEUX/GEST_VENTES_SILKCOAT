from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiplie value par arg"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
    
@register.filter
def has_attr(obj, attr_name):
    """Retourne True si l'objet a l'attribut attr_name"""
    return hasattr(obj, attr_name)
