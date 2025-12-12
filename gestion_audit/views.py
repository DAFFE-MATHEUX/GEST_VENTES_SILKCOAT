# utils.py
from MySQLdb import DatabaseError
from .models import AuditLog
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from .utils import pagination_liste
from django.contrib.auth.decorators import login_required
from datetime import date
from gestion_utilisateur.models import Utilisateur

@login_required
def enregistrer_audit(utilisateur, action, table, ancienne_valeur=None, nouvelle_valeur=None):
    
    AuditLog.objects.create(
        utilisateur = utilisateur,
        action = action,
        table_modifiee = table,
        ancienne_valeur = str(ancienne_valeur) if ancienne_valeur else "",
        nouvelle_valeur = str(nouvelle_valeur) if nouvelle_valeur else ""
    )

@login_required
def liste_audit(request):
    liste_audit = AuditLog.objects.select_related('utilisateur').order_by('-date_action')
    total_audit = liste_audit.count()
    liste_utilisateur = Utilisateur.objects.all()

    # --- FILTRAGE ---
    date_filtre = request.GET.get("date_filtre")
    utilisateur_filtre = request.GET.get("utilisateur_filtre")
    audit_du_jour = request.GET.get("aujourdhui")

    if audit_du_jour:  # bouton "Audit du jour"
        liste_audit = liste_audit.filter(date_action__date=date.today())
    elif date_filtre:
        liste_audit = liste_audit.filter(date_action__date=date_filtre)
    if utilisateur_filtre:
        liste_audit = liste_audit.filter(utilisateur_id=utilisateur_filtre)

    # Pagination
    liste_audit = pagination_liste(request, liste_audit)

    context = {
        "liste_audit": liste_audit,
        "total_audit": total_audit,
        "audit_du_jour": audit_du_jour,
        "date_filtre": date_filtre,
        "utilisateur_filtre": utilisateur_filtre,
        "liste_utilisateur": liste_utilisateur,
    }
    return render(request, "gestion_audit/listes_auditlog.html", context)

@login_required
def supprimer_audit(request):
    if request.method == "POST":
        try:
            audit_id = request.POST.get("id_supprimer")
            audit = get_object_or_404(AuditLog, id=audit_id)
            audit.delete()
            messages.success(request, "Audit supprimé avec succès.")
            return redirect('audit:liste_audit')
        except Exception as e:
            messages.error(request, f"Erreur lors de la suppression de l'audit : {str(e)}")
        except AuditLog.DoesNotExist as dne:
            messages.error(request, f"L'audit spécifié n'existe pas. {str(dne)}")
        except ValueError as ve :
            messages.error(request, f"ID d'audit invalide. {str(ve)}")
        except DatabaseError as db_err:
            messages.error(request, f"Erreur de base de données : {str(db_err)}")
    return redirect('audit:liste_audit')  

# Rediriger vers la liste des audits

