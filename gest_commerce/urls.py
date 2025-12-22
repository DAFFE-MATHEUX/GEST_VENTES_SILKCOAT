"""
URL configuration for gest_commerce project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from .views import handler404, handler403, handler500

urlpatterns = [
    # Admin
    path('secure-admin-2025/', admin.site.urls),

    # Gestion utilisateur (login, logout, tableau de bord utilisateur)
    path('', include('gestion_utilisateur.urls', namespace='gestionUtilisateur')),

    # Allauth (social login)
    path('accounts/', include('allauth.urls')),

    # Social auth
    path('auth/', include('social_django.urls', namespace='social')),

    # Autres apps
    path('gest_entreprise/', include('gest_entreprise.urls')),
    path('produits/', include('gestion_produits.urls')),
    path('rapports/', include('gestion_rapports.urls')),
    path('audit/', include('gestion_audit.urls')),
    path('notifications/', include('gestion_notifications.urls')),
]

# Media
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Gestion des erreurs
handler404 = 'gest_commerce.views.handler404'
handler403 = 'gest_commerce.views.handler403'
handler500 = 'gest_commerce.views.handler500'
