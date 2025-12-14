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
from django.urls import path
from django.urls import include
from django.conf import settings
from django.conf.urls.static import static
from gest_commerce.views import dashboard
from .views import handler404,handler404, handler500 

urlpatterns = [
    path('admin/', admin.site.urls),
    path('dashboard/', dashboard, name='dashboard'), 
     
    path('accounts/', include('allauth.urls')),  # Pour django allauth
    path('auth/', include('social_django.urls', namespace='social')),  # Pour social auth
    
    path('gest_entreprise', include('gest_entreprise.urls')),
    path('produits/', include('gestion_produits.urls')),
    path('rapports/', include('gestion_rapports.urls')),
    path('', include('gestion_utilisateur.urls')),
    path('audit/', include('gestion_audit.urls')),
    path('notifications/', include('gestion_notifications.urls')),
]+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# ======================================================================================

handler404 = 'gest_commerce.views.handler404'
handler403 = 'gest_commerce.views.handler403'
handler500 = 'gest_commerce.views.handler500'

# =======================================================================================
