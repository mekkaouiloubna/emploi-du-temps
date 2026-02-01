"""Point d'entrée principal de l'application Flask"""
from flask import Flask, redirect, url_for, render_template
from flask_login import LoginManager, current_user
from config import config
from models import db, User, Admin, Teacher, Student
from routes import create_blueprints
import os

def create_app(config_name='development'):
    """
    Fabrique d'application (Application Factory).
    Configure et initialise l'instance de l'application Flask.
    
    Args:
        config_name: Nom de la configuration à utiliser (development, production, testing).
        
    Returns:
        L'instance de l'application Flask configurée.
    """
    app = Flask(__name__)
    
    # Chargement de la configuration
    app.config.from_object(config[config_name])
    
    # Initialisation de la base de données
    db.init_app(app)
    
    # Initialisation du gestionnaire d'authentification
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        """Chargement de l'utilisateur par ID pour Flask-Login"""
        return User.query.get(int(user_id))
    
    # Enregistrement des blueprints (modules de routes)
    create_blueprints(app)
    
    # Création des tables de la base de données si elles n'existent pas
    with app.app_context():
        db.create_all()
    
    # Route racine
    @app.route('/')
    def index():
        """
        La route racine redirige vers le tableau de bord approprié.
        Si l'utilisateur n'est pas connecté, redirige vers la page de connexion.
        """
        if current_user.is_authenticated:
            # Redirection polymorphique selon le rôle
            if isinstance(current_user, Admin):
                return redirect(url_for('admin.dashboard'))
            elif isinstance(current_user, Teacher):
                return redirect(url_for('teacher.dashboard'))
            elif isinstance(current_user, Student):
                return redirect(url_for('student.dashboard'))
        return redirect(url_for('auth.login'))
    return app

if __name__ == '__main__':
    # Création du dossier instance si nécessaire
    os.makedirs('instance', exist_ok=True)
    
    # Création de l'application
    app = create_app(os.environ.get('FLASK_ENV', 'development'))
    
    # Lancement du serveur de développement
    app.run(debug=True, host='0.0.0.0', port=5000)
