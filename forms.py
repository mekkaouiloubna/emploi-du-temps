from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, EmailField, IntegerField, TextAreaField, SelectField, TimeField, DateField, BooleanField, SubmitField, SelectMultipleField, widgets
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, ValidationError
from models import User, Teacher, Student, Course, Room, Group, Department, Constraint
from datetime import datetime

class LoginForm(FlaskForm):
    """Formulaire de connexion utilisateur"""
    email = EmailField('Courriel', validators=[DataRequired(), Email()])
    password = PasswordField('Mot de passe', validators=[DataRequired()])
    remember_me = BooleanField('Se souvenir de moi')
    submit = SubmitField('Se connecter')

class RegisterTeacherForm(FlaskForm):
    """Formulaire d'inscription des enseignants"""
    email = EmailField('Courriel', validators=[DataRequired(), Email()])
    password = PasswordField('Mot de passe', validators=[DataRequired(), Length(min=8)])
    password_confirm = PasswordField('Confirmer le mot de passe', validators=[DataRequired(), EqualTo('password')])
    first_name = StringField('Prénom', validators=[DataRequired(), Length(min=2)])
    last_name = StringField('Nom', validators=[DataRequired(), Length(min=2)])
    specialization = StringField('Spécialisation', validators=[Optional()])
    office_location = StringField('Bureau', validators=[Optional()])
    phone = StringField('Téléphone', validators=[Optional()])
    courses = SelectMultipleField('Cours', coerce=int, validators=[Optional()])
    submit = SubmitField("S'inscrire")
    
    def validate_email(self, email):
        """Vérifie l'unicité de l'email"""
        if User.query.filter_by(email=email.data).first():
            raise ValidationError('Cet email est déjà enregistré')
    
    def __init__(self, *args, **kwargs):
        super(RegisterTeacherForm, self).__init__(*args, **kwargs)
        # Vérifie si la table existe pour éviter les erreurs lors de l'init_db
        try:
            self.courses.choices = [(c.id, f"{c.code} - {c.name}") for c in Course.query.all()]
        except:
            self.courses.choices = []

class RegisterStudentForm(FlaskForm):
    """Formulaire d'inscription des étudiants"""
    email = EmailField('Courriel', validators=[DataRequired(), Email()])
    password = PasswordField('Mot de passe', validators=[DataRequired(), Length(min=8)])
    password_confirm = PasswordField('Confirmer le mot de passe', validators=[DataRequired(), EqualTo('password')])
    first_name = StringField('Prénom', validators=[DataRequired(), Length(min=2)])
    last_name = StringField('Nom', validators=[DataRequired(), Length(min=2)])
    student_id = StringField('Matricule', validators=[DataRequired(), Length(min=5)])
    enrollment_year = IntegerField("Année d'inscription", validators=[Optional()])
    department_id = SelectField('Département (Filière)', coerce=int, validators=[Optional()])
    group_id = SelectField('Groupe', coerce=int, validators=[Optional()])
    submit = SubmitField("S'inscrire")
    
    def __init__(self, *args, **kwargs):
        super(RegisterStudentForm, self).__init__(*args, **kwargs)
        try:
            self.department_id.choices = [(0, 'Sélectionner un département')] + [(d.id, d.name) for d in Department.query.all()]
            self.group_id.choices = [(0, 'Sélectionner un groupe')] + [(g.id, g.name) for g in Group.query.all()]
        except:
            self.department_id.choices = []
            self.group_id.choices = []

    def validate_student_id(self, student_id):
        """Vérifie l'unicité du matricule étudiant"""
        if Student.query.filter_by(student_id=student_id.data).first():
            raise ValidationError('Ce matricule est déjà enregistré')

class CreateCourseForm(FlaskForm):
    """Formulaire de création de cours"""
    name = StringField('Nom du cours', validators=[DataRequired(), Length(min=3)])
    code = StringField('Code du cours', validators=[DataRequired(), Length(min=3)])
    description = TextAreaField('Description', validators=[Optional()])
    course_type = SelectField('Type de cours', choices=[('CM', 'Cours Magistral'), ('TD', 'Travaux Dirigés'), ('TP', 'Travaux Pratiques')])
    duration_minutes = IntegerField('Durée (minutes)', default=90)
    credits = IntegerField('Crédits', default=4)
    
    # --- Ajout du champ pour la compatibilité avec l'algorithme ---
    requires_lab = BooleanField('Nécessite une salle TP ?')
    weekly_sessions = IntegerField('Séances par semaine', default=1)
    
    teachers = SelectMultipleField('Enseignants', coerce=int, validators=[Optional()])
    submit = SubmitField('Créer le cours')
    
    def __init__(self, *args, **kwargs):
        super(CreateCourseForm, self).__init__(*args, **kwargs)
        try:
            self.teachers.choices = [(t.id, t.full_name) for t in Teacher.query.all()]
        except:
            self.teachers.choices = []

class CreateRoomForm(FlaskForm):
    """Formulaire de création de salle"""
    name = StringField('Nom de la salle', validators=[DataRequired()])
    code = StringField('Code de la salle', validators=[DataRequired()])
    building = StringField('Bâtiment', validators=[Optional()])
    floor = IntegerField('Étage', validators=[Optional()])
    capacity = IntegerField('Capacité', validators=[DataRequired()])
    room_type = SelectField('Type de salle', choices=[('Classroom', 'Salle de cours'), ('Lab', 'Laboratoire'), ('Amphitheater', 'Amphithéâtre')])
    submit = SubmitField('Créer la salle')

class CreateGroupForm(FlaskForm):
    """Formulaire de création de groupe"""
    name = StringField('Nom du groupe', validators=[DataRequired()])
    code = StringField('Code du groupe', validators=[DataRequired()])
    department_id = SelectField('Département', coerce=int)
    capacity = IntegerField('Capacité', default=30)
    semester = IntegerField('Semestre', validators=[Optional()])
    submit = SubmitField('Créer le groupe')
    
    def __init__(self, *args, **kwargs):
        super(CreateGroupForm, self).__init__(*args, **kwargs)
        try:
            self.department_id.choices = [(d.id, d.name) for d in Department.query.all()]
        except:
            self.department_id.choices = []

class TeacherAvailabilityForm(FlaskForm):
    """Formulaire de disponibilité enseignant"""
    day_of_week = SelectField('Jour de la semaine', choices=[
        (0, 'Lundi'), (1, 'Mardi'), (2, 'Mercredi'),
        (3, 'Jeudi'), (4, 'Vendredi'), (5, 'Samedi'), (6, 'Dimanche')
    ], coerce=int)
    start_time = TimeField('Heure de début', validators=[DataRequired()])
    end_time = TimeField('Heure de fin', validators=[DataRequired()])
    is_available = BooleanField('Disponible', default=True)
    submit = SubmitField('Enregistrer')

class BookingRequestForm(FlaskForm):
    """Formulaire de demande de réservation de salle"""
    room_id = SelectField('Salle', coerce=int)
    course_id = SelectField('Cours', coerce=int, validators=[DataRequired()])
    group_id = SelectField('Groupe', coerce=int, validators=[Optional()])
    requested_date = DateField('Date', validators=[DataRequired()])
    start_time = TimeField('Heure de début', validators=[DataRequired()])
    end_time = TimeField('Heure de fin', validators=[DataRequired()])
    reason = TextAreaField('Motif', validators=[DataRequired()])
    submit = SubmitField('Demander la réservation')
    
    def __init__(self, *args, **kwargs):
        super(BookingRequestForm, self).__init__(*args, **kwargs)
        try:
            self.room_id.choices = [(r.id, f"{r.code} ({r.room_type})") for r in Room.query.all()]
            self.course_id.choices = [(c.id, c.name) for c in Course.query.all()]
            self.group_id.choices = [(0, 'Aucun groupe spécifique')] + [(g.id, g.name) for g in Group.query.all()]
        except:
            pass

class GenerateTimetableForm(FlaskForm):
    """Formulaire de génération d'emploi du temps"""
    department_id = SelectField('Département (Filière)', coerce=int, validators=[DataRequired()])
    group_id = SelectField('Groupe', coerce=int, choices=[(0, 'Tous les groupes')], validators=[Optional()])
    semester = SelectField('Semestre', coerce=int, choices=[(1, 'Semestre 1'), (2, 'Semestre 2')], default=1)
    submit = SubmitField("Générer l'emploi du temps")
    
    def __init__(self, *args, **kwargs):
        super(GenerateTimetableForm, self).__init__(*args, **kwargs)
        try:
            self.department_id.choices = [(d.id, d.name) for d in Department.query.all()]
            self.group_id.choices = [(0, 'Tous les groupes')] + [(g.id, g.code) for g in Group.query.all()]
        except:
            self.department_id.choices = []

class SearchRoomForm(FlaskForm):
    """Formulaire de recherche de salle"""
    required_capacity = IntegerField('Capacité minimale', validators=[Optional()])
    date = DateField('Date', validators=[Optional()])
    start_time = TimeField('Heure de début', validators=[Optional()])
    end_time = TimeField('Heure de fin', validators=[Optional()])
    room_type = SelectField('Type de salle', choices=[('', 'Tous types'), ('Classroom', 'Salle de cours'), ('Lab', 'Laboratoire')], validators=[Optional()])
    submit = SubmitField('Rechercher')

class EditTimeSlotForm(FlaskForm):
    """Formulaire de modification manuelle d'un créneau"""
    room_id = SelectField('Salle', coerce=int, validators=[DataRequired()])
    
    # Ajout du champ enseignant
    teacher_id = SelectField('Enseignant', coerce=int, validators=[DataRequired()])
    
    day_of_week = SelectField('Day', choices=[
        (0, 'Lundi'), (1, 'Mardi'), (2, 'Mercredi'),
        (3, 'Jeudi'), (4, 'Vendredi'), (5, 'Samedi'), (6, 'Dimanche')
    ], coerce=int, validators=[DataRequired()])
    start_time = TimeField('Heure de début', validators=[DataRequired()])
    end_time = TimeField('Heure de fin', validators=[DataRequired()])
    submit = SubmitField('Mettre à jour le créneau')
    
    def __init__(self, *args, **kwargs):
        super(EditTimeSlotForm, self).__init__(*args, **kwargs)
        try:
            self.room_id.choices = [(r.id, f"{r.code} - {r.room_type}") for r in Room.query.all()]
            # Remplissage de la liste des enseignants
            self.teacher_id.choices = [(t.id, t.full_name) for t in Teacher.query.all()]
        except:
            self.room_id.choices = []
            self.teacher_id.choices = []
