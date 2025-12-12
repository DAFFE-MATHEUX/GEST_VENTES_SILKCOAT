# gestion_notifications/context_processors.py

from .models import Notification

def notifications_context(request):
    """
    Fournit les notifications pour la navbar.
    Si l'utilisateur n'a pas d'employé lié, renvoie une liste vide.
    """
    notifications = []
    if request.user.is_authenticated:
        employe = getattr(request.user, 'employer', None)  # utilise getattr pour éviter l'AttributeError
        if employe:
            notifications = Notification.objects.filter(employe=employe).order_by('-date_notification')
    return {'notifications': notifications}
