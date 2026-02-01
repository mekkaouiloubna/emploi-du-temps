"""
Routes d'administration.
Gère le tableau de bord administrateur, la gestion des ressources (cours, salles, groupes),
la génération des emplois du temps et la validation des réservations.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import (
    db, Admin, User, Teacher, Student, Course, Room, Group, Department,
    TimeSlot, BookingRequest, Notification, CourseType
)
from sqlalchemy.exc import IntegrityError
from forms import CreateCourseForm, CreateRoomForm, CreateGroupForm, GenerateTimetableForm, EditTimeSlotForm
from routes.auth_routes import role_required
from datetime import datetime
import io
from flask import send_file

# Import des utilitaires
from utils.conflict_detector import ConflictDetector
from utils.timetable_generator import TimetableGenerator
from utils.export_utils import TimetableExporter

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/dashboard')
@login_required
@role_required(Admin)
def dashboard():
    """
    Tableau de bord principal de l'administrateur.
    Affiche les statistiques globales et les activités récentes.
    """
    total_students = Student.query.count()
    total_teachers = Teacher.query.count()
    total_courses = Course.query.count()
    total_rooms = Room.query.count()
    total_bookings = BookingRequest.query.count()
    pending_bookings = BookingRequest.query.filter_by(status='pending').count()
    
    recent_bookings = BookingRequest.query.order_by(BookingRequest.created_at.desc()).limit(5).all()
    
    stats = {
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_courses': total_courses,
        'total_rooms': total_rooms,
        'total_bookings': total_bookings,
        'pending_bookings': pending_bookings
    }
    
    return render_template('admin/dashboard.html', stats=stats, recent_bookings=recent_bookings)

# =========================================================
# GESTION DES COURS
# =========================================================

@admin_bp.route('/courses', methods=['GET', 'POST'])
@login_required
@role_required(Admin)
def courses():
    """
    Liste et création des cours avec filtrage.
    Gère l'affichage paginé et le formulaire d'ajout.
    """
    form = CreateCourseForm()
    teachers = Teacher.query.all()
    form.teachers.choices = [(t.id, t.full_name) for t in teachers]
    
    if form.validate_on_submit():
        course_type_map = {
            'CM': CourseType.LECTURE, 'TD': CourseType.TUTORIAL,
            'TP': CourseType.LAB, 'Exam': CourseType.EXAM, 'Autre': CourseType.OTHER
        }
        course_type = course_type_map.get(form.course_type.data, CourseType.LECTURE)
        
        course = Course(
            name=form.name.data,
            code=form.code.data,
            description=form.description.data,
            course_type=course_type,
            duration_minutes=form.duration_minutes.data,
            credits=form.credits.data,
            requires_lab=form.requires_lab.data
        )
        
        if form.teachers.data:
            selected_teachers = Teacher.query.filter(Teacher.id.in_(form.teachers.data)).all()
            course.teachers.extend(selected_teachers)
            
        db.session.add(course)
        db.session.commit()
        flash(f'Cours "{course.name}" créé avec succès', 'success')
        return redirect(url_for('admin.courses'))
    
    # Récupération des paramètres de filtrage
    course_type_filter = request.args.get('course_type', 'all')
    search_query = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    
    # Construction de la requête avec filtres
    query = Course.query
    
    # Filtre par type de cours
    if course_type_filter != 'all':
        course_type_map = {
            'CM': CourseType.LECTURE,
            'TD': CourseType.TUTORIAL,
            'TP': CourseType.LAB,
            'Exam': CourseType.EXAM,
            'Autre': CourseType.OTHER
        }
        if course_type_filter in course_type_map:
            query = query.filter(Course.course_type == course_type_map[course_type_filter])
    
    # Filtre par recherche (nom ou code)
    if search_query:
        query = query.filter(
            db.or_(
                Course.name.ilike(f'%{search_query}%'),
                Course.code.ilike(f'%{search_query}%')
            )
        )
    
    courses = query.paginate(page=page, per_page=20)
    
    return render_template('admin/courses.html', 
                         form=form, 
                         courses=courses,
                         current_type_filter=course_type_filter,
                         current_search=search_query)

@admin_bp.route('/courses/<int:course_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required(Admin)
def edit_course(course_id):
    """
    Modification d'un cours existant.
    Met à jour les informations et les affectations d'enseignants.
    """
    course = Course.query.get_or_404(course_id)
    form = CreateCourseForm(obj=course)
    teachers = Teacher.query.all()
    form.teachers.choices = [(t.id, t.full_name) for t in teachers]
    
    if request.method == 'GET':
        form.course_type.data = course.course_type.value
        form.teachers.data = [t.id for t in course.teachers]
    
    if form.validate_on_submit():
        try:
            course.name = form.name.data
            course.code = form.code.data
            course.description = form.description.data
            course.duration_minutes = form.duration_minutes.data
            course.credits = form.credits.data
            course.requires_lab = form.requires_lab.data
            
            course_type_map = {'CM': CourseType.LECTURE, 'TD': CourseType.TUTORIAL, 'TP': CourseType.LAB}
            course.course_type = course_type_map.get(form.course_type.data, CourseType.LECTURE)
            
            if form.teachers.data:
                selected_teachers = Teacher.query.filter(Teacher.id.in_(form.teachers.data)).all()
                course.teachers = selected_teachers
            else:
                course.teachers = []
            
            db.session.commit()
            flash(f'Cours "{course.name}" mis à jour', 'success')
            return redirect(url_for('admin.courses'))
        except IntegrityError:
            db.session.rollback()
            flash('Erreur: Le code du cours existe déjà.', 'danger')
        
    return render_template('admin/edit_course.html', form=form, course=course)

@admin_bp.route('/courses/<int:course_id>/delete', methods=['POST'])
@login_required
@role_required(Admin)
def delete_course(course_id):
    """
    Suppression d'un cours.
    Vérifie les contraintes d'intégrité avant suppression.
    """
    course = Course.query.get_or_404(course_id)
    try:
        db.session.delete(course)
        db.session.commit()
        flash('Cours supprimé', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Impossible de supprimer le cours (utilisé ailleurs).', 'danger')
    return redirect(url_for('admin.courses'))

# =========================================================
# GESTION DES SALLES (ROOMS)
# =========================================================

@admin_bp.route('/rooms', methods=['GET', 'POST'])
@login_required
@role_required(Admin)
def rooms():
    """
    Gestion des salles de cours (Liste et Ajout) avec filtrage.
    """
    form = CreateRoomForm()
    if form.validate_on_submit():
        room = Room(
            name=form.name.data,
            code=form.code.data,
            building=form.building.data,
            floor=form.floor.data,
            capacity=form.capacity.data,
            room_type=form.room_type.data
        )
        db.session.add(room)
        db.session.commit()
        flash(f'Salle "{room.name}" créée', 'success')
        return redirect(url_for('admin.rooms'))
    
    # Récupération des paramètres de filtrage
    room_type_filter = request.args.get('room_type', 'all')
    building_filter = request.args.get('building', 'all')
    min_capacity = request.args.get('min_capacity', type=int) or None
    max_capacity = request.args.get('max_capacity', type=int) or None
    page = request.args.get('page', 1, type=int)
    
    # Construction de la requête avec filtres
    query = Room.query
    
    # Filtre par type de salle
    if room_type_filter != 'all':
        query = query.filter(Room.room_type == room_type_filter)
    
    # Filtre par bâtiment
    if building_filter != 'all':
        query = query.filter(Room.building == building_filter)
    
    # Filtre par capacité minimale
    if min_capacity:
        query = query.filter(Room.capacity >= min_capacity)
    
    # Filtre par capacité maximale
    if max_capacity:
        query = query.filter(Room.capacity <= max_capacity)
    
    rooms = query.paginate(page=page, per_page=20)
    
    # Récupération des bâtiments uniques pour le filtre
    buildings = db.session.query(Room.building).distinct().filter(Room.building.isnot(None)).all()
    buildings = [b[0] for b in buildings]
    
    return render_template('admin/rooms.html', 
                         form=form, 
                         rooms=rooms,
                         current_type_filter=room_type_filter,
                         current_building_filter=building_filter,
                         current_min_capacity=min_capacity,
                         current_max_capacity=max_capacity,
                         buildings=buildings)

@admin_bp.route('/rooms/<int:room_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required(Admin)
def edit_room(room_id):
    """Modification d'une salle existante."""
    room = Room.query.get_or_404(room_id)
    form = CreateRoomForm(obj=room)
    if form.validate_on_submit():
        form.populate_obj(room)
        db.session.commit()
        flash('Salle mise à jour', 'success')
        return redirect(url_for('admin.rooms'))
    return render_template('admin/edit_room.html', form=form, room=room)

@admin_bp.route('/rooms/<int:room_id>/delete', methods=['POST'])
@login_required
@role_required(Admin)
def delete_room(room_id):
    """Suppression d'une salle."""
    room = Room.query.get_or_404(room_id)
    try:
        db.session.delete(room)
        db.session.commit()
        flash('Salle supprimée', 'success')
    except:
        db.session.rollback()
        flash('Erreur lors de la suppression.', 'danger')
    return redirect(url_for('admin.rooms'))

# =========================================================
# GESTION DES GROUPES (GROUPS)
# =========================================================

@admin_bp.route('/groups', methods=['GET', 'POST'])
@login_required
@role_required(Admin)
def groups():
    """Gestion des groupes d'étudiants (Liste et Ajout)."""
    form = CreateGroupForm()
    form.department_id.choices = [(d.id, d.name) for d in Department.query.all()]
    
    if form.validate_on_submit():
        group = Group(
            name=form.name.data,
            code=form.code.data,
            department_id=form.department_id.data,
            capacity=form.capacity.data,
            semester=form.semester.data
        )
        db.session.add(group)
        db.session.commit()
        flash('Groupe créé', 'success')
        return redirect(url_for('admin.groups'))
    
    page = request.args.get('page', 1, type=int)
    groups = Group.query.paginate(page=page, per_page=20)
    return render_template('admin/groups.html', form=form, groups=groups)

# =========================================================
# EMPLOI DU TEMPS (TIMETABLE)
# =========================================================

@admin_bp.route('/timetable/generate', methods=['GET', 'POST'])
@login_required
@role_required(Admin)
def generate_timetable():
    """
    Interface de génération automatique de l'emploi du temps.
    Utilise l'algorithme de backtracking défini dans TimetableGenerator.
    """
    form = GenerateTimetableForm()
    
    # Préparation des données pour le JavaScript (Listes liées Dept -> Groupes)
    all_depts = Department.query.all()
    all_groups = Group.query.all()
    dept_groups = {}
    for dept in all_depts:
        dept_groups[str(dept.id)] = [{'id': g.id, 'name': g.name} for g in all_groups if g.department_id == dept.id]

    if form.validate_on_submit():
        try:
            generator = TimetableGenerator(
                department_id=form.department_id.data,
                semester=form.semester.data,
                group_id=form.group_id.data
            )
            result = generator.generate()
            generator.save_timetable(db)
            
            if result['generated'] > 0:
                flash(f'Succès! {result["generated"]} créneaux générés.', 'success')
            else:
                flash('Aucun créneau généré. Vérifiez les contraintes.', 'warning')
                
            return render_template('admin/generate_timetable.html', form=form, dept_groups=dept_groups, generated_timetable=result)
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'danger')

    return render_template('admin/generate_timetable.html', form=form, dept_groups=dept_groups)

@admin_bp.route('/timetable/view')
@login_required
@role_required(Admin)
def view_timetable():
    """
    Visualisation globale de l'emploi du temps avec filtrage avancé par dropdowns.
    """
    # Récupération des paramètres de filtrage
    semester_filter = request.args.get('semester', 'all')
    department_filter = request.args.get('department', 'all')
    course_type_filter = request.args.get('course_type', 'all')
    teacher_filter = request.args.get('teacher', 'all')
    room_type_filter = request.args.get('room_type', 'all')
    sort_by = request.args.get('sort_by', 'day')
    sort_order = request.args.get('sort_order', 'asc')
    
    # Récupération de tous les départements et enseignants pour les dropdowns
    all_departments = Department.query.all()
    all_teachers = Teacher.query.order_by(Teacher.last_name, Teacher.first_name).all()
    
    # Construction de la requête de base
    base_query = TimeSlot.query.join(Group).join(Course).join(Room).outerjoin(Teacher, TimeSlot.teacher_id == Teacher.id)
    
    # Application du filtre de semestre
    if semester_filter != 'all':
        try:
            semester_value = int(semester_filter)
            base_query = base_query.filter(Group.semester == semester_value)
        except ValueError:
            pass
    
    # Application du filtre de département
    if department_filter != 'all':
        try:
            department_value = int(department_filter)
            base_query = base_query.filter(Group.department_id == department_value)
        except ValueError:
            pass
    
    # Application du filtre de type de cours
    if course_type_filter != 'all':
        course_type_map = {
            'CM': CourseType.LECTURE,
            'TD': CourseType.TUTORIAL,
            'TP': CourseType.LAB,
            'Exam': CourseType.EXAM
        }
        if course_type_filter in course_type_map:
            base_query = base_query.filter(Course.course_type == course_type_map[course_type_filter])
    
    # Application du filtre par enseignant
    if teacher_filter != 'all':
        try:
            teacher_value = int(teacher_filter)
            base_query = base_query.filter(TimeSlot.teacher_id == teacher_value)
        except ValueError:
            pass
    
    # Application du filtre par type de salle
    if room_type_filter != 'all':
        base_query = base_query.filter(Room.room_type == room_type_filter)
    
    # Application du tri
    if sort_by == 'day':
        sort_column = TimeSlot.day_of_week
    elif sort_by == 'time':
        sort_column = TimeSlot.start_time
    elif sort_by == 'course':
        sort_column = Course.name
    elif sort_by == 'teacher':
        sort_column = Teacher.last_name
    else:
        sort_column = TimeSlot.day_of_week
    
    if sort_order == 'asc':
        base_query = base_query.order_by(sort_column.asc())
    else:
        base_query = base_query.order_by(sort_column.desc())
    
    # Récupération des créneaux filtrés
    all_slots = base_query.all()
    
    # Organisation des créneaux par département
    timetable_data = {}
    departments_to_show = all_departments
    if department_filter != 'all':
        try:
            department_value = int(department_filter)
            departments_to_show = [dept for dept in all_departments if dept.id == department_value]
        except ValueError:
            pass
    
    for dept in departments_to_show:
        # Construction de la requête pour chaque département
        query = TimeSlot.query.join(Group).join(Course).join(Room).outerjoin(Teacher, TimeSlot.teacher_id == Teacher.id)
        query = query.filter(Group.department_id == dept.id)
        
        # Application des mêmes filtres
        if semester_filter != 'all':
            try:
                semester_value = int(semester_filter)
                query = query.filter(Group.semester == semester_value)
            except ValueError:
                pass
        
        if course_type_filter != 'all':
            course_type_map = {
                'CM': CourseType.LECTURE,
                'TD': CourseType.TUTORIAL,
                'TP': CourseType.LAB,
                'Exam': CourseType.EXAM
            }
            if course_type_filter in course_type_map:
                query = query.filter(Course.course_type == course_type_map[course_type_filter])
        
        if teacher_filter != 'all':
            try:
                teacher_value = int(teacher_filter)
                query = query.filter(TimeSlot.teacher_id == teacher_value)
            except ValueError:
                pass
        
        if room_type_filter != 'all':
            query = query.filter(Room.room_type == room_type_filter)
        
        # Application du tri
        if sort_by == 'day':
            sort_column = TimeSlot.day_of_week
        elif sort_by == 'time':
            sort_column = TimeSlot.start_time
        elif sort_by == 'course':
            sort_column = Course.name
        elif sort_by == 'teacher':
            sort_column = Teacher.last_name
        else:
            sort_column = TimeSlot.day_of_week
        
        if sort_order == 'asc':
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())
        
        slots = query.all()
        if slots:
            timetable_data[dept] = slots
    
    # Récupération des semestres disponibles
    available_semesters = db.session.query(Group.semester).distinct().filter(
        Group.semester.isnot(None)
    ).order_by(Group.semester).all()
    available_semesters = [s[0] for s in available_semesters if s[0]]
    
    # Récupération des types de salles disponibles
    available_room_types = db.session.query(Room.room_type).distinct().filter(
        Room.room_type.isnot(None)
    ).all()
    available_room_types = [rt[0] for rt in available_room_types if rt[0]]
    
    # Calcul des statistiques
    total_slots = len(all_slots)
    stats = {
        'total': total_slots,
        'cm': len([s for s in all_slots if s.course.course_type == CourseType.LECTURE]),
        'td': len([s for s in all_slots if s.course.course_type == CourseType.TUTORIAL]),
        'tp': len([s for s in all_slots if s.course.course_type == CourseType.LAB]),
        'exam': len([s for s in all_slots if s.course.course_type == CourseType.EXAM])
    }
            
    return render_template('admin/timetable_view.html', 
                         timetable_data=timetable_data, 
                         timeslots=all_slots,
                         current_semester=semester_filter,
                         current_department=department_filter,
                         current_course_type=course_type_filter,
                         current_teacher=teacher_filter,
                         current_room_type=room_type_filter,
                         current_sort_by=sort_by,
                         current_sort_order=sort_order,
                         available_semesters=available_semesters,
                         available_room_types=available_room_types,
                         all_departments=all_departments,
                         all_teachers=all_teachers,
                         stats=stats)

@admin_bp.route('/conflicts')
@login_required
@role_required(Admin)
def detect_conflicts():
    """
    Page de rapport des conflits.
    Exécute le détecteur de conflits et affiche les résultats.
    """
    detector = ConflictDetector()
    report = detector.detect_all_conflicts()
    return render_template('admin/conflicts.html', conflicts=report['conflicts'], stats=report)

@admin_bp.route('/timeslot/<int:slot_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required(Admin)
def edit_timeslot(slot_id):
    """
    Modification manuelle d'un créneau horaire avec vérification des conflits.
    Permet d'ajuster le planning tout en évitant les conflits d'enseignants et de salles.
    """
    # Récupération du créneau à modifier
    slot = TimeSlot.query.get_or_404(slot_id)

    # Initialisation du formulaire avec les données existantes du créneau
    form = EditTimeSlotForm(obj=slot)
    
    if form.validate_on_submit():
        # Récupération des nouvelles données saisies par l'utilisateur
        new_room_id = form.room_id.data
        new_teacher_id = form.teacher_id.data
        new_day = form.day_of_week.data
        new_start = form.start_time.data
        new_end = form.end_time.data

        # Vérification des conflits avec les autres créneaux de l'enseignant
        conflict = TimeSlot.query.filter(
            TimeSlot.teacher_id == new_teacher_id,
            TimeSlot.day_of_week == new_day,
            TimeSlot.start_time < new_end,
            TimeSlot.end_time > new_start,
            TimeSlot.id != slot.id  # Ignorer le créneau actuel
        ).first()

        if conflict:
            flash(f"Erreur : L'enseignant {conflict.teacher.name} a déjà un créneau à ce moment.", "danger")
            return render_template('admin/edit_timeslot.html', form=form, slot=slot)

        # Vérification des conflits avec la salle sélectionnée
        room_conflict = TimeSlot.query.filter(
            TimeSlot.room_id == new_room_id,
            TimeSlot.day_of_week == new_day,
            TimeSlot.start_time < new_end,
            TimeSlot.end_time > new_start,
            TimeSlot.id != slot.id  # Ignorer le créneau actuel
        ).first()

        if room_conflict:
            flash(f"Erreur : La salle {room_conflict.room.name} est déjà occupée à ce moment.", "danger")
            return render_template('admin/edit_timeslot.html', form=form, slot=slot)

        # Pas de conflit détecté : mise à jour du créneau
        slot.room_id = new_room_id
        slot.teacher_id = new_teacher_id
        slot.day_of_week = new_day
        slot.start_time = new_start
        slot.end_time = new_end

        # Sauvegarde dans la base de données
        db.session.commit()
        flash('Créneau mis à jour avec succès', 'success')
        return redirect(url_for('admin.view_timetable'))
    
    # Requête GET : affichage du formulaire avec les données existantes
    return render_template('admin/edit_timeslot.html', form=form, slot=slot)


# =========================================================
# RÉSERVATIONS
# =========================================================

@admin_bp.route('/bookings', methods=['GET', 'POST'])
@login_required
@role_required(Admin)
def bookings():
    """
    Gestion des demandes de réservation de salles par les enseignants.
    """
    bookings = BookingRequest.query.order_by(BookingRequest.created_at.desc()).all()
    return render_template('admin/bookings.html', bookings=bookings)

@admin_bp.route('/bookings/approve/<int:booking_id>', methods=['POST'])
@login_required
@role_required(Admin)
def approve_booking(booking_id):
    """
    Approbation d'une demande de réservation.
    Crée un créneau horaire verrouillé et notifie l'enseignant.
    """
    booking = BookingRequest.query.get_or_404(booking_id)
    booking.status = 'approved'
    booking.approved_by = current_user.id
    
    # Création du créneau dans l'emploi du temps
    new_slot = TimeSlot(
        course_id=booking.course_id,
        group_id=booking.group_id,
        room_id=booking.room_id,
        teacher_id=booking.teacher_id,
        day_of_week=booking.requested_date.weekday(),
        start_time=booking.start_time,
        end_time=booking.end_time,
        is_locked=True
    )
    db.session.add(new_slot)
    
    # Envoi de la notification
    notif = Notification(
        user_id=booking.teacher_id,
        title="Réservation Approuvée",
        message=f"Votre demande pour {booking.room.code} a été acceptée.",
        notification_type="success"
    )
    db.session.add(notif)
    
    db.session.commit()
    flash('Réservation approuvée et ajoutée au planning.', 'success')
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/bookings/reject/<int:booking_id>', methods=['POST'])
@login_required
@role_required(Admin)
def reject_booking(booking_id):
    """
    Rejet d'une demande de réservation.
    Notifie l'enseignant du refus.
    """
    booking = BookingRequest.query.get_or_404(booking_id)
    booking.status = 'rejected'
    
    notif = Notification(
        user_id=booking.teacher_id,
        title="Réservation Rejetée",
        message=f"Votre demande pour {booking.room.code} a été refusée.",
        notification_type="danger"
    )
    db.session.add(notif)
    
    db.session.commit()
    flash('Réservation rejetée.', 'warning')
    return redirect(url_for('admin.dashboard'))

# =========================================================
# EXPORTS
# =========================================================

@admin_bp.route('/timetable/export/pdf')
@login_required
@role_required(Admin)
def export_timetable_pdf():
    """Exportation de l'emploi du temps complet au format PDF."""
    timeslots = TimeSlot.query.all()
    exporter = TimetableExporter(timeslots, title="Emploi du Temps")
    pdf_buffer = io.BytesIO()
    exporter.export_to_pdf(pdf_buffer)
    pdf_buffer.seek(0)
    return send_file(pdf_buffer, as_attachment=True, download_name='timetable.pdf', mimetype='application/pdf')

@admin_bp.route('/timetable/export/excel')
@login_required
@role_required(Admin)
def export_timetable_excel():
    """Exportation de l'emploi du temps complet au format Excel."""
    timeslots = TimeSlot.query.all()
    exporter = TimetableExporter(timeslots, title="Emploi du Temps")
    excel_buffer = io.BytesIO()
    exporter.export_to_excel(excel_buffer)
    excel_buffer.seek(0)
    return send_file(excel_buffer, as_attachment=True, download_name='timetable.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@admin_bp.route('/users')
@login_required
@role_required(Admin)
def list_users():
    """Liste de tous les utilisateurs du système avec filtrage avancé."""
    # Récupération des paramètres de filtrage
    user_type = request.args.get('user_type', 'all')
    status_filter = request.args.get('status', 'all')
    search_query = request.args.get('search', '').strip()
    sort_by = request.args.get('sort_by', 'created_at')
    sort_order = request.args.get('sort_order', 'desc')
    page = request.args.get('page', 1, type=int)
    per_page = 15
    
    # Construction de la requête de base
    query = User.query
    
    # Filtre par type d'utilisateur
    if user_type == 'admin':
        query = query.filter(User.type == 'admin')
    elif user_type == 'teacher':
        query = query.filter(User.type == 'teacher')
    elif user_type == 'student':
        query = query.filter(User.type == 'student')
    # Si 'all', on garde tous les utilisateurs
    
    # Filtre par statut (actif/inactif)
    if status_filter == 'active':
        query = query.filter(User.is_active == True)
    elif status_filter == 'inactive':
        query = query.filter(User.is_active == False)
    
    # Recherche textuelle (nom, prénom, email)
    if search_query:
        search_pattern = f'%{search_query}%'
        query = query.filter(
            db.or_(
                User.first_name.ilike(search_pattern),
                User.last_name.ilike(search_pattern),
                User.email.ilike(search_pattern)
            )
        )
    
    # Tri dynamique
    if sort_by == 'name':
        sort_column = User.first_name
    elif sort_by == 'email':
        sort_column = User.email
    elif sort_by == 'type':
        sort_column = User.type
    else:  # 'created_at' par défaut
        sort_column = User.created_at
    
    if sort_order == 'asc':
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())
    
    # Pagination
    users_paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Calcul des statistiques pour l'affichage
    stats = {
        'total': User.query.count(),
        'admins': User.query.filter(User.type == 'admin').count(),
        'teachers': User.query.filter(User.type == 'teacher').count(),
        'students': User.query.filter(User.type == 'student').count(),
        'active': User.query.filter(User.is_active == True).count(),
        'inactive': User.query.filter(User.is_active == False).count()
    }
    
    return render_template('admin/users.html', 
                         users=users_paginated.items,
                         pagination=users_paginated,
                         current_filter=user_type,
                         current_status=status_filter,
                         current_search=search_query,
                         current_sort_by=sort_by,
                         current_sort_order=sort_order,
                         stats=stats)

@admin_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@role_required(Admin)
def delete_user(user_id):
    """
    Suppression d'un utilisateur.
    Empêche l'auto-suppression.
    """
    if current_user.id == user_id:
        flash("Vous ne pouvez pas supprimer votre propre compte.", "warning")
        return redirect(url_for('admin.list_users'))

    user = User.query.get(user_id)
    if not user:
        flash("Utilisateur introuvable.", "danger")
        return redirect(url_for('admin.list_users'))
    
    try:
        db.session.delete(user)
        db.session.commit()
        flash(f"Utilisateur {user.full_name} supprimé avec succès.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la suppression: {str(e)}", "danger")

    return redirect(url_for('admin.list_users'))

@admin_bp.route('/timeslot/<int:slot_id>/delete', methods=['POST'])
@login_required
@role_required(Admin)
def delete_timeslot(slot_id):
    """
    Suppression d'un créneau horaire de l'emploi du temps.
    Permet de supprimer des séances individuelles du planning global.
    """
    slot = TimeSlot.query.get_or_404(slot_id)
    
    try:
        # Sauvegarde des informations pour le message de confirmation
        course_name = slot.course.name if slot.course else "Cours inconnu"
        group_name = slot.group.name if slot.group else "Groupe inconnu"
        
        db.session.delete(slot)
        db.session.commit()
        flash(f'Créneau "{course_name}" pour {group_name} supprimé avec succès.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la suppression du créneau: {str(e)}', 'danger')
    
    return redirect(url_for('admin.view_timetable'))
