"""Routes pour les étudiants"""
from flask import Blueprint, render_template, request
from flask_login import login_required, current_user
from models import db, Student, TimeSlot, Room, Group, Notification, Course
from routes.auth_routes import role_required
from utils.export_utils import TimetableExporter
from flask import send_file
import io

student_bp = Blueprint('student', __name__)

@student_bp.route('/dashboard')
@login_required
@role_required(Student)
def dashboard():
    """
    Tableau de bord de l'étudiant.
    Affiche un résumé des cours à venir et des notifications.
    """
    # Récupération de la seule groupe de l'étudiant
    group = current_user.groups[0]  # L'étudiant appartient à une seule groupe
    
    # Récupération des créneaux horaires pour le groupe de l'étudiant
    # Joint les cours et les groupes pour ne récupérer que les créneaux correspondant à ce groupe
    timeslots = TimeSlot.query \
    .filter(TimeSlot.group_id == group.id) \
    .order_by(TimeSlot.day_of_week, TimeSlot.start_time) \
    .all()
    
    
    # Récupération des notifications non lues
    unread_notifications = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    
    stats = {
        'upcoming_classes': len(timeslots),
        'unread_notifications': unread_notifications
    }
    
    return render_template('student/dashboard.html', 
                         stats=stats, 
                         group=group,
                         timeslots=timeslots)

@student_bp.route('/timetable')
@login_required
@role_required(Student)
def timetable():
    """
    Affichage complet de l'emploi du temps de l'étudiant.
    Inclut :
    - Les cours des groupes auxquels l'étudiant appartient.
    - Les cours généraux (group_id=None) accessibles à tous.
    - Tri par jour de la semaine et heure de début.
    """

    group = current_user.groups[0]  # L'étudiant appartient à une seule groupe
    
    # Récupération des créneaux horaires pour le groupe de l'étudiant
    # Joint les cours et les groupes pour ne récupérer que les créneaux correspondant à ce groupe
    timeslots = TimeSlot.query \
    .filter(TimeSlot.group_id == group.id) \
    .order_by(TimeSlot.day_of_week, TimeSlot.start_time) \
    .all()

    # Organisation des créneaux par jour pour le template
    timetable_data = {day: [] for day in range(7)}
    for slot in timeslots:
        if slot.day_of_week is not None:
            timetable_data[slot.day_of_week].append(slot)

    # Noms des jours
    days = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']

    return render_template('student/timetable.html', timetable=timetable_data, days=days)


@student_bp.route('/timetable/export/pdf')
@login_required
@role_required(Student)
def export_timetable_pdf():
    """
    Export de l'emploi du temps personnel au format PDF.
    Génère un fichier PDF en mémoire et le renvoie en téléchargement.
    """
    groups = current_user.groups
    group_ids = [g.id for g in groups]
    
    courses_ids = []
    for group in groups:
        courses_ids.extend([c.id for c in group.courses])
    
    from sqlalchemy import or_
    timeslots = TimeSlot.query.filter(
        TimeSlot.course_id.in_(courses_ids),
        or_(TimeSlot.group_id.is_(None), TimeSlot.group_id.in_(group_ids))
    ).all()
    
    exporter = TimetableExporter(timeslots, title=f"Emploi du temps - {current_user.full_name}")
    
    # Création du PDF en mémoire (évite les fichiers temporaires)
    pdf_buffer = io.BytesIO()
    exporter.export_to_pdf(pdf_buffer)
    pdf_buffer.seek(0)
    
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name='mon_emploi_du_temps.pdf',
        mimetype='application/pdf'
    )

@student_bp.route('/timetable/export/excel')
@login_required
@role_required(Student)
def export_timetable_excel():
    """
    Export de l'emploi du temps personnel au format Excel.
    """
    groups = current_user.groups
    group_ids = [g.id for g in groups]
    
    courses_ids = []
    for group in groups:
        courses_ids.extend([c.id for c in group.courses])
    
    from sqlalchemy import or_
    timeslots = TimeSlot.query.filter(
        TimeSlot.course_id.in_(courses_ids),
        or_(TimeSlot.group_id.is_(None), TimeSlot.group_id.in_(group_ids))
    ).all()
    
    exporter = TimetableExporter(timeslots, title=f"Emploi du temps - {current_user.full_name}")
    
    # Création du fichier Excel en mémoire
    excel_buffer = io.BytesIO()
    exporter.export_to_excel(excel_buffer)
    excel_buffer.seek(0)
    
    return send_file(
        excel_buffer,
        as_attachment=True,
        download_name='mon_emploi_du_temps.xlsx',
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@student_bp.route('/rooms/available')
@login_required
@role_required(Student)
def available_rooms():
    """
    Recherche des salles disponibles.
    Permet aux étudiants de trouver une salle libre pour étudier.
    """
    # Récupération de toutes les salles marquées comme disponibles
    rooms = Room.query.filter_by(is_available=True).all()
    
    return render_template('student/available_rooms.html', rooms=rooms)

@student_bp.route('/notifications')
@login_required
@role_required(Student)
def notifications():
    """Affichage de l'historique des notifications"""
    page = request.args.get('page', 1, type=int)
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).paginate(page=page, per_page=20)
    
    return render_template('student/notifications.html', notifications=notifications)
