"""
Validateurs personnalisés pour les formulaires et les données.
Assure l'intégrité des données saisies par l'utilisateur.
"""
from wtforms.validators import ValidationError
from models import User, Room, Course
from datetime import datetime

class UniqueEmail:
    """
    Validateur pour vérifier l'unicité de l'adresse email.
    Utilisé lors de l'inscription ou de la création d'utilisateurs.
    """
    def __init__(self, message="Cette adresse email est déjà enregistrée"):
        self.message = message
    
    def __call__(self, form, field):
        """Vérifie si l'email existe déjà en base de données."""
        if User.query.filter_by(email=field.data).first():
            raise ValidationError(self.message)

class UniqueRoomCode:
    """
    Validateur pour vérifier l'unicité du code de la salle.
    Empêche la création de doublons dans le référentiel des salles.
    """
    def __init__(self, message="Ce code de salle existe déjà"):
        self.message = message
    
    def __call__(self, form, field):
        """Vérifie si le code salle existe déjà."""
        if Room.query.filter_by(code=field.data).first():
            raise ValidationError(self.message)

class UniqueCourseCode:
    """
    Validateur pour vérifier l'unicité du code du cours.
    Chaque cours doit avoir un identifiant unique.
    """
    def __init__(self, message="Ce code de cours existe déjà"):
        self.message = message
    
    def __call__(self, form, field):
        """Vérifie si le code cours existe déjà."""
        if Course.query.filter_by(code=field.data).first():
            raise ValidationError(self.message)

class ValidTimeRange:
    """
    Validateur pour vérifier la cohérence des plages horaires.
    S'assure que l'heure de fin est postérieure à l'heure de début.
    """
    def __init__(self, message="L'heure de fin doit être après l'heure de début"):
        self.message = message
    
    def __call__(self, form, field):
        """Vérifie la chronologie des horaires saisis."""
        if hasattr(form, 'start_time') and hasattr(form, 'end_time'):
            if form.start_time.data and form.end_time.data:
                if form.start_time.data >= form.end_time.data:
                    raise ValidationError(self.message)
