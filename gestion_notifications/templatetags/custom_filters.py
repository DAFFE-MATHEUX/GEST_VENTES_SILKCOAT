from django import template

register = template.Library()

# Exemple : vérifier si un objet a un attribut
@register.filter
def has_attr(obj, attr_name):
    return hasattr(obj, attr_name)

# Exemple : afficher "Oui" si True, "Non" si False
@register.filter
def oui_non(value):
    return "Oui" if value else "Non"
