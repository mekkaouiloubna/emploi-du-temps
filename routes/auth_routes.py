"""Routes d'authentification"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_user, logout_user, current_user, login_required
from models import db, User, Admin, Teacher, Student, Group
from forms import LoginForm, RegisterTeacherForm, RegisterStudentForm
from functools import wraps

auth_bp = Blueprint('auth', __name__)

def role_required(role):
    """
    Décorateur pour restreindre l'accès à un rôle utilisateur spécifique.
    
    Args:
        role: La classe du modèle utilisateur autorisé (ex: Admin, Teacher, Student)
    
    Returns:
        La fonction décorée si l'utilisateur a le bon rôle, sinon une redirection.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Veuillez vous connecter d\'abord', 'warning')
                return redirect(url_for('auth.login'))
            
            # Vérification du type polymorphique de l'utilisateur
            if not isinstance(current_user, role):
                flash('Vous n\'avez pas la permission d\'accéder à cette page', 'danger')
                return redirect(url_for('auth.dashboard'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Note: La route racine '/' est gérée dans app.py pour éviter les conflits

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Page de connexion des utilisateurs.
    Redirige automatiquement vers le tableau de bord approprié selon le rôle.
    """
    # Redirection si déjà connecté
    if current_user.is_authenticated:
        if isinstance(current_user, Admin):
            return redirect(url_for('admin.dashboard'))
        elif isinstance(current_user, Teacher):
            return redirect(url_for('teacher.dashboard'))
        elif isinstance(current_user, Student):
            return redirect(url_for('student.dashboard'))
    
    form = LoginForm()
    if form.validate_on_submit():
        # Recherche de l'utilisateur par email
        user = User.query.filter_by(email=form.email.data).first()
        
        # Vérification des identifiants
        if user is None or not user.check_password(form.password.data):
            flash('Email ou mot de passe invalide', 'danger')
            return redirect(url_for('auth.login'))
        
        # Vérification du statut du compte
        if not user.is_active:
            flash('Votre compte a été désactivé', 'danger')
            return redirect(url_for('auth.login'))
        
        # Connexion de l'utilisateur (création de session)
        login_user(user, remember=form.remember_me.data)
        flash(f'Bienvenue, {user.full_name}!', 'success')
        
        # Redirection basée sur le rôle (polymorphisme)
        if isinstance(user, Admin):
            return redirect(url_for('admin.dashboard'))
        elif isinstance(user, Teacher):
            return redirect(url_for('teacher.dashboard'))
        elif isinstance(user, Student):
            return redirect(url_for('student.dashboard'))
        
        return redirect(url_for('auth.dashboard'))
    
    return render_template('auth/login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """
    Page d'inscription des utilisateurs (Enseignant ou Étudiant).
    Le type d'utilisateur est déterminé par le paramètre GET 'type'.
    """
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))
    
    # Détermine le type d'inscription (par défaut étudiant)
    user_type = request.args.get('type', 'student')
    
    if user_type == 'teacher':
        form = RegisterTeacherForm()
        if form.validate_on_submit():
            # Création de l'objet Teacher
            teacher = Teacher(
                email=form.email.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                specialization=form.specialization.data,
                office_location=form.office_location.data,
                phone=form.phone.data
            )
            teacher.set_password(form.password.data)
            
            # Association des cours sélectionnés (Relation Many-to-Many)
            if form.courses.data:
                from models import Course
                selected_courses = Course.query.filter(Course.id.in_(form.courses.data)).all()
                teacher.courses.extend(selected_courses)
            
            db.session.add(teacher)
            db.session.commit()
            
            flash('Inscription réussie ! Veuillez vous connecter.', 'success')
            return redirect(url_for('auth.login'))
        
        return render_template('auth/register_teacher.html', form=form)
    
    else:  # student
        form = RegisterStudentForm()
        if form.validate_on_submit():
            # Création de l'objet Student
            student = Student(
                email=form.email.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                student_id=form.student_id.data,
                enrollment_year=form.enrollment_year.data
            )
            student.set_password(form.password.data)
            
            # Affectation au groupe si sélectionné
            if form.group_id.data and form.group_id.data != 0:
                group = Group.query.get(form.group_id.data)
                if group:
                    student.groups.append(group)
            
            db.session.add(student)
            db.session.commit()
            
            flash('Inscription réussie ! Veuillez vous connecter.', 'success')
            return redirect(url_for('auth.login'))
        
        return render_template('auth/register_student.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    """Déconnexion de l'utilisateur"""
    logout_user()
    flash('Vous avez été déconnecté', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/dashboard')
@login_required
def dashboard():
    """
    Redirection centrale vers le tableau de bord approprié.
    Sert de point d'entrée après connexion ou pour les liens génériques.
    """
    if isinstance(current_user, Admin):
        return redirect(url_for('admin.dashboard'))
    elif isinstance(current_user, Teacher):
        return redirect(url_for('teacher.dashboard'))
    elif isinstance(current_user, Student):
        return redirect(url_for('student.dashboard'))
    
    return redirect(url_for('auth.login'))

@auth_bp.route('/profile')
@login_required
def profile():
    """Page de profil utilisateur"""
    return render_template('auth/profile.html', user=current_user)
