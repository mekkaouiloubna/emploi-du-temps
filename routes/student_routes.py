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
    Recherche des salles disponibles avec filtrage avancé.
    Permet aux étudiants de trouver une salle libre pour étudier.
    """
    # Récupération des paramètres de filtrage
    room_type_filter = request.args.get('room_type', 'all')
    building_filter = request.args.get('building', 'all')
    min_capacity = request.args.get('min_capacity', type=int) or None
    search_query = request.args.get('search', '').strip()
    sort_by = request.args.get('sort_by', 'name')
    sort_order = request.args.get('sort_order', 'asc')
    
    # Construction de la requête de base (salles disponibles uniquement)
    query = Room.query.filter_by(is_available=True)
    
    # Filtre par type de salle
    if room_type_filter != 'all':
        query = query.filter(Room.room_type == room_type_filter)
    
    # Filtre par bâtiment
    if building_filter != 'all':
        query = query.filter(Room.building == building_filter)
    
    # Filtre par capacité minimale
    if min_capacity:
        query = query.filter(Room.capacity >= min_capacity)
    
    # Recherche textuelle (nom ou code)
    if search_query:
        search_pattern = f'%{search_query}%'
        query = query.filter(
            db.or_(
                Room.name.ilike(search_pattern),
                Room.code.ilike(search_pattern)
            )
        )
    
    # Tri dynamique
    if sort_by == 'capacity':
        sort_column = Room.capacity
    elif sort_by == 'building':
        sort_column = Room.building
    elif sort_by == 'type':
        sort_column = Room.room_type
    else:  # 'name' par défaut
        sort_column = Room.name
    
    if sort_order == 'desc':
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())
    
    rooms = query.all()
    
    # Récupération des valeurs uniques pour les filtres
    all_buildings = db.session.query(Room.building).distinct().filter(
        Room.building.isnot(None),
        Room.is_available == True
    ).all()
    buildings = [b[0] for b in all_buildings]
    
    all_room_types = db.session.query(Room.room_type).distinct().filter(
        Room.room_type.isnot(None),
        Room.is_available == True
    ).all()
    room_types = [rt[0] for rt in all_room_types]
    
    # Statistiques
    stats = {
        'total': len(rooms),
        'total_available': Room.query.filter_by(is_available=True).count()
    }
    
    return render_template('student/available_rooms.html', 
                         rooms=rooms,
                         current_type_filter=room_type_filter,
                         current_building_filter=building_filter,
                         current_min_capacity=min_capacity,
                         current_search=search_query,
                         current_sort_by=sort_by,
                         current_sort_order=sort_order,
                         buildings=buildings,
                         room_types=room_types,
                         stats=stats)

@student_bp.route('/notifications')
@login_required
@role_required(Student)
def notifications():
    """Affichage de l'historique des notifications"""
    page = request.args.get('page', 1, type=int)
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).paginate(page=page, per_page=20)
    
    return render_template('student/notifications.html', notifications=notifications)
