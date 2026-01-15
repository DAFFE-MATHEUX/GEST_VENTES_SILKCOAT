from django.conf import settings

class DevHTTPSIgnoreMiddleware:
    """
    Middleware pour ignorer HTTPS en DEV.
    Ne fait rien en production.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Si on est en DEBUG, ignorer HTTPS
        if settings.DEBUG:
            request.scheme = 'http'
        return self.get_response(request)
