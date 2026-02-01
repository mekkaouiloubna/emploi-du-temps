"""Initialisation du package des routes"""
from flask import Blueprint

def create_blueprints(app):
    """
    Création et enregistrement de tous les Blueprints (modules de routes).
    Organise l'application en sections distinctes : Auth, Admin, Enseignant, Étudiant.
    """
    from .auth_routes import auth_bp
    from .admin_routes import admin_bp
    from .teacher_routes import teacher_bp
    from .student_routes import student_bp
    
    # Enregistrement des blueprints avec leurs préfixes d'URL respectifs
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(teacher_bp, url_prefix='/teacher')
    app.register_blueprint(student_bp, url_prefix='/student')
