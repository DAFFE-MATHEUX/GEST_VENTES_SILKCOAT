import re
from django.core.exceptions import ValidationError as ve
from django.utils.translation import gettext as _

class StrongPasswordValidator :
    def validate(self, password, user = None):
        if not re.search(r"[A-Z]", password):
            raise ve(_("Le mot de passe doit contenir au moins une majuscule, Obligation."))
        
        if not re.search(r"a-z", password):
            raise ve(_("Le mot de passe doit contenir au moins une miniscule, Obligation."))
        
        if not re.search(r"\d"):
            raise ve(_("Le mot de passe doit contenir au moins un chiffre, Obligation."))
        
        if not re.search(r"[!@#$%^&*()_+{}\[\]:;<>,.?-\\-]"):
            raise ve(_("Le mot de passe doit contenir au moins un caractère spéciaux, Obligation."))
                    
    def get_help_text(self):
        return _(
            "Le mot de passe doit contenir au moins une majuscule."
            "une mascul, un chiffre et caractère spéciaux."
        )
        
        
        
                    