"""Routes pour les enseignants"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db, Teacher, TimeSlot, Course, Room, BookingRequest, TeacherAvailability, Notification
from forms import TeacherAvailabilityForm, BookingRequestForm, SearchRoomForm
from routes.auth_routes import role_required
from datetime import datetime, time
from utils.export_utils import TimetableExporter
from flask import send_file
import io

teacher_bp = Blueprint('teacher', __name__)

@teacher_bp.route('/dashboard')
@login_required
@role_required(Teacher)
def dashboard():
    """
    Tableau de bord de l'enseignant.
    Affiche un résumé des cours, des réservations et des notifications.
    """
    # Récupération des cours de l'enseignant
    courses = current_user.courses
    
    # --- Optimisation de la requête ---
    # Utilisation directe de teacher_id au lieu de filtrer par cours.
    # Plus précis et performant pour récupérer l'emploi du temps personnel.
    today = datetime.utcnow().date()
    upcoming_slots = TimeSlot.query.filter(
        TimeSlot.teacher_id == current_user.id, # Filtre direct sur l'ID de l'enseignant
        # Note: Un filtre de date pourrait être ajouté ici si nécessaire
    ).order_by(TimeSlot.day_of_week, TimeSlot.start_time).limit(10).all()
    
    # Comptage des demandes de réservation en attente
    pending_bookings = BookingRequest.query.filter_by(
        teacher_id=current_user.id,
        status='pending'
    ).count()
    
    # Récupération des notifications non lues
    unread_notifications = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).count()
    
    stats = {
        'courses_count': len(courses),
        'upcoming_slots': len(upcoming_slots),
        'pending_bookings': pending_bookings,
        'unread_notifications': unread_notifications
    }
    
    return render_template('teacher/dashboard.html', 
                         stats=stats, 
                         courses=courses,
                         upcoming_slots=upcoming_slots)

@teacher_bp.route('/timetable')
@login_required
@role_required(Teacher)
def timetable():
    """
    Affichage de l'emploi du temps personnel de l'enseignant.
    """
    # Récupération de tous les créneaux associés aux cours de l'enseignant
    timeslots = TimeSlot.query.filter(
        TimeSlot.course_id.in_([c.id for c in current_user.courses])
    ).all()
    
    # Regroupement par jour de la semaine
    timetable_data = {day: [] for day in range(7)}
    for slot in timeslots:
        if slot.day_of_week is not None:
            timetable_data[slot.day_of_week].append(slot)
    
    return render_template('teacher/timetable.html', timetable=timetable_data)

@teacher_bp.route('/timetable/export/pdf')
@login_required
@role_required(Teacher)
def export_timetable_pdf():
    """
    Export de l'emploi du temps enseignant au format PDF.
    """
    timeslots = TimeSlot.query.filter(
        TimeSlot.course_id.in_([c.id for c in current_user.courses])
    ).all()
    
    exporter = TimetableExporter(timeslots, title=f"Emploi du temps - {current_user.full_name}")
    
    # Création du PDF en mémoire
    pdf_buffer = io.BytesIO()
    exporter.export_to_pdf(pdf_buffer)
    pdf_buffer.seek(0)
    
    return send_file(
        pdf_buffer,
        as_attachment=True,
        download_name='mon_emploi_du_temps.pdf',
        mimetype='application/pdf'
    )

@teacher_bp.route('/timetable/export/excel')
@login_required
@role_required(Teacher)
def export_timetable_excel():
    """
    Export de l'emploi du temps enseignant au format Excel.
    """
    timeslots = TimeSlot.query.filter(
        TimeSlot.course_id.in_([c.id for c in current_user.courses])
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

@teacher_bp.route('/availability', methods=['GET', 'POST'])
@login_required
@role_required(Teacher)
def availability():
    """
    Gestion des disponibilités de l'enseignant.
    Permet de définir les plages horaires préférentielles ou indisponibles.
    """
    form = TeacherAvailabilityForm()
    
    if form.validate_on_submit():
        availability = TeacherAvailability(
            teacher_id=current_user.id,
            day_of_week=form.day_of_week.data,
            start_time=form.start_time.data,
            end_time=form.end_time.data,
            is_available=form.is_available.data
        )
        db.session.add(availability)
        db.session.commit()
        flash('Disponibilité mise à jour avec succès', 'success')
        return redirect(url_for('teacher.availability'))
    
    # Récupération des disponibilités actuelles
    availabilities = TeacherAvailability.query.filter_by(
        teacher_id=current_user.id
    ).all()
    
    days = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    
    return render_template('teacher/availability.html', 
                         form=form, 
                         availabilities=availabilities,
                         days=days)

@teacher_bp.route('/availability/<int:avail_id>/delete', methods=['POST'])
@login_required
@role_required(Teacher)
def delete_availability(avail_id):
    """Suppression d'une plage de disponibilité"""
    availability = TeacherAvailability.query.get_or_404(avail_id)
    
    # Vérification des droits
    if availability.teacher_id != current_user.id:
        flash('Non autorisé', 'danger')
        return redirect(url_for('teacher.availability'))
    
    db.session.delete(availability)
    db.session.commit()
    flash('Disponibilité supprimée', 'info')
    return redirect(url_for('teacher.availability'))

@teacher_bp.route('/rooms/search', methods=['GET', 'POST'])
@login_required
@role_required(Teacher)
def search_rooms():
    """
    Recherche de salles disponibles pour des réservations ponctuelles.
    Permet de filtrer par capacité et type de salle.
    """
    form = SearchRoomForm()
    available_rooms = []
    
    if form.validate_on_submit():
        query = Room.query
        
        if form.required_capacity.data:
            query = query.filter(Room.capacity >= form.required_capacity.data)
        
        if form.room_type.data:
            query = query.filter(Room.room_type == form.room_type.data)
        
        # Filtre de disponibilité (simplifié pour l'exemple)
        available_rooms = query.filter_by(is_available=True).all()
    
    return render_template('teacher/room_search.html', form=form, rooms=available_rooms)

@teacher_bp.route('/bookings', methods=['GET', 'POST'])
@login_required
@role_required(Teacher)
def bookings():
    """
    Gestion des demandes de réservation de salle.
    Vérifie les conflits potentiels avant de soumettre la demande.
    """
    form = BookingRequestForm()
    form.room_id.choices = [(r.id, r.name) for r in Room.query.all()]
    # Remplissage des choix de cours avec ceux de l'enseignant
    form.course_id.choices = [(c.id, f"{c.code} - {c.name}") for c in current_user.courses]
    
    # Remplissage des choix de groupes basés sur les cours de l'enseignant
    # Utilisation d'un set pour éviter les doublons
    available_groups = set()
    for course in current_user.courses:
        for group in course.groups:
            available_groups.add((group.id, f"{group.name} ({group.department.code})"))
            
    # Tri par nom et ajout de l'option par défaut
    group_choices = sorted(list(available_groups), key=lambda x: x[1])
    form.group_id.choices = [(0, 'Tous les groupes / Pas de groupe spécifique')] + group_choices
    
    # Pré-sélection de la salle si passée en paramètre GET
    selected_room_id = request.args.get('room_id', type=int)
    if request.method == 'GET' and selected_room_id:
        form.room_id.data = selected_room_id
    
    if form.validate_on_submit():
        # Gestion de group_id : si 0, considéré comme None
        group_id = form.group_id.data if form.group_id.data and form.group_id.data != 0 else None
        requested_date = datetime.combine(form.requested_date.data, time(0, 0))
        start_time = form.start_time.data
        end_time = form.end_time.data
        day_of_week = form.requested_date.data.weekday()

        course = Course.query.get(form.course_id.data)
        room = Room.query.get(form.room_id.data)
        
        # Vérification des équipements pour les TP
        if course and course.course_type.value == "TP":
            has_computers = any(e.name.lower() == "computers" for e in room.equipment)
            if not has_computers:
                flash('La salle sélectionnée ne dispose pas des ordinateurs requis pour un TP.', 'danger')
                return render_template('teacher/bookings.html', form=form, bookings=BookingRequest.query.filter_by(teacher_id=current_user.id).order_by(BookingRequest.created_at.desc()).all(), show_modal=True)

        # Vérification 1 : Disponibilité de la salle (TimeSlot existant)
        room_busy_timeslot = TimeSlot.query.filter(
            TimeSlot.day_of_week == day_of_week,
            TimeSlot.room_id == form.room_id.data,
            TimeSlot.start_time < end_time,
            TimeSlot.end_time > start_time
        ).first()

        if room_busy_timeslot:
            flash(f'Conflit détecté : La salle est déjà occupée par {room_busy_timeslot.course.code} de {room_busy_timeslot.start_time} à {room_busy_timeslot.end_time}. Veuillez choisir une autre salle ou un autre créneau.', 'danger')
            return render_template('teacher/bookings.html', form=form, bookings=BookingRequest.query.filter_by(teacher_id=current_user.id).order_by(BookingRequest.created_at.desc()).all(), show_modal=True)

        # Vérification 2 : Disponibilité de la salle (Réservations approuvées)
        # Note : On se base principalement sur les TimeSlots pour les créneaux confirmés.
        
        # Vérification 3 : Disponibilité de l'enseignant (Est-il déjà en cours ?)
        teacher_busy_timeslot = TimeSlot.query.join(TimeSlot.course).filter(
            TimeSlot.day_of_week == day_of_week,
            TimeSlot.start_time < end_time,
            TimeSlot.end_time > start_time,
            Course.teachers.any(id=current_user.id)
        ).first()

        if teacher_busy_timeslot:
             flash(f'Conflit détecté : Vous enseignez déjà {teacher_busy_timeslot.course.code} de {teacher_busy_timeslot.start_time} à {teacher_busy_timeslot.end_time}.', 'danger')
             return render_template('teacher/bookings.html', form=form, bookings=BookingRequest.query.filter_by(teacher_id=current_user.id).order_by(BookingRequest.created_at.desc()).all(), show_modal=True)

        # Vérification 4 : Disponibilité du groupe (Le groupe est-il déjà occupé ?)
        if group_id:
             group_busy_timeslot = TimeSlot.query.join(TimeSlot.course).filter(
                TimeSlot.day_of_week == day_of_week,
                TimeSlot.start_time < end_time,
                TimeSlot.end_time > start_time,
                Course.groups.any(id=group_id)
            ).first()
             
             if group_busy_timeslot:
                 flash(f'Conflit détecté : Le groupe sélectionné est déjà occupé par {group_busy_timeslot.course.code} de {group_busy_timeslot.start_time} à {group_busy_timeslot.end_time}.', 'danger')
                 return render_template('teacher/bookings.html', form=form, bookings=BookingRequest.query.filter_by(teacher_id=current_user.id).order_by(BookingRequest.created_at.desc()).all(), show_modal=True)


        booking = BookingRequest(
            teacher_id=current_user.id,
            course_id=form.course_id.data,
            group_id=group_id,
            room_id=form.room_id.data,
            requested_date=requested_date,
            start_time=start_time,
            end_time=end_time,
            reason=form.reason.data,
            status='pending'
        )
        db.session.add(booking)
        db.session.commit()
        flash('Demande de réservation soumise avec succès', 'success')
        return redirect(url_for('teacher.bookings'))
    
    # Récupération de l'historique des réservations
    bookings = BookingRequest.query.filter_by(teacher_id=current_user.id).order_by(BookingRequest.created_at.desc()).all()
    
    return render_template('teacher/bookings.html', form=form, bookings=bookings, show_modal=bool(selected_room_id))

@teacher_bp.route('/bookings/<int:booking_id>/cancel', methods=['POST'])
@login_required
@role_required(Teacher)
def cancel_booking(booking_id):
    """Annulation d'une demande de réservation"""
    booking = BookingRequest.query.get_or_404(booking_id)
    if booking.teacher_id != current_user.id:
        flash('Non autorisé', 'danger')
        return redirect(url_for('teacher.bookings'))
    
    if booking.status != 'pending':
        flash('Seules les demandes en attente peuvent être annulées', 'warning')
        return redirect(url_for('teacher.bookings'))
    
    db.session.delete(booking)
    db.session.commit()
    flash('Réservation annulée', 'info')
    return redirect(url_for('teacher.bookings'))

@teacher_bp.route('/notifications')
@login_required
@role_required(Teacher)
def notifications():
    """Affichage des notifications"""
    page = request.args.get('page', 1, type=int)
    notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).paginate(page=page, per_page=20)
    
    return render_template('teacher/notifications.html', notifications=notifications)

@teacher_bp.route('/notifications/<int:notif_id>/read', methods=['POST'])
@login_required
@role_required(Teacher)
def mark_notification_read(notif_id):
    """Marquer une notification comme lue"""
    notification = Notification.query.get_or_404(notif_id)
    if notification.user_id != current_user.id:
        return jsonify({'error': 'Non autorisé'}), 403
    
    notification.is_read = True
    db.session.commit()
    return jsonify({'status': 'ok'})
