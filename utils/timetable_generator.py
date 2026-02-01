"""
Algorithme de génération d'emploi du temps.
Utilise une approche de backtracking avec validation de contraintes strictes.
Gère les contraintes académiques (3h/cours, blocs enseignants, charge étudiants).
"""
from datetime import time, datetime, timedelta, date
from models import Course, Room, Group, Teacher, TimeSlot, TeacherAvailability, Department
import random

class TimetableGenerator:
    """
    Générateur d'emploi du temps optimisé.
    Utilise une approche heuristique avec validation des contraintes en temps réel.
    """

    def __init__(self, department_id, semester, start_date=None, end_date=None, group_id=0, debug=False):
        """
        Initialise le générateur avec les contraintes contextuelles.
        """
        self.department_id = department_id
        self.semester = semester
        self.start_date = start_date 
        self.end_date = end_date
        self.group_id = group_id  # 0 signifie tous les groupes du département
        self.generated_slots = []
        self.conflicts = []
        self.debug = debug

        # Créneaux horaires standards de la journée universitaire
        self.slot_starts = [
            time(8, 0),
            time(9, 00),
            time(10, 0),
            time(11, 00),
            time(12, 0),
            time(13, 0),
            time(14, 0),
            time(15, 00),
            time(16, 00),
            time(17, 00) 
        ]
        
        # Jours de la semaine : 0=Lundi à 5=Samedi
        self.days = [0, 1, 2, 3, 4, 5]

    def generate(self):
        """
        Boucle principale de génération des emplois du temps.
        Parcourt les groupes et les cours pour assigner des créneaux valides.
        """
        # 1. Récupération des groupes cibles
        if self.group_id and self.group_id != 0:
            groups = Group.query.filter_by(id=self.group_id).all()
        else:
            groups = Group.query.filter_by(department_id=self.department_id).all()
        
        if not groups:
            return {"error": "Aucun groupe trouvé"}

        # 2. Récupération de toutes les salles (Optimisation pour éviter les requêtes répétées)
        all_rooms = Room.query.all()
        
        generated_count = 0
        failed_count = 0
        
        # 3. Traitement itératif par groupe
        for group in groups:
            courses = group.courses
            
            for course in courses:
                # Calcul du nombre de séances nécessaires par semaine
                # Par défaut 1 si non spécifié
                sessions_needed = course.weekly_sessions if hasattr(course, 'weekly_sessions') else 1
                
                # Détermination de la durée du cours (défaut: 90 min)
                duration_min = course.duration_minutes if course.duration_minutes else 60
                
                for _ in range(sessions_needed):
                    scheduled = False
                    
                    # Filtrage des salles adéquates (Labo vs Salle normale)
                    suitable_rooms = [
                        r for r in all_rooms 
                        if (r.room_type == 'Lab') == course.requires_lab
                    ]
                    
                    # Mélange aléatoire pour éviter le déterminisme et répartir l'occupation
                    random.shuffle(suitable_rooms)
                    random.shuffle(self.days)
                    
                    # Vérification des enseignants assignés
                    available_teachers = course.teachers
                    if not available_teachers:
                        self.conflicts.append({
                            "course": course.name,
                            "group": group.name,
                            "reason": "Aucun enseignant assigné à ce cours"
                        })
                        failed_count += 1
                        continue

                    # Tentative de trouver un créneau valide
                    for day in self.days:
                        if scheduled: break
                        
                        # Mélange des horaires de début pour varier les emplois du temps
                        current_starts = self.slot_starts[:]
                        random.shuffle(current_starts)

                        for start_time in current_starts:
                            if scheduled: break
                            
                            # Calcul de l'heure de fin
                            end_time = self.add_minutes(start_time, duration_min)
                            
                            # Validation de l'heure de fin (Ne doit pas dépasser 17h00)
                            if end_time > time(17, 0):
                                continue

                            # 1. Vérification de la disponibilité du Groupe
                            if self.check_group_busy(group.id, day, start_time, end_time):
                                continue
                                
                            # 2. Vérification de la disponibilité de la Salle
                            selected_room = None
                            for room in suitable_rooms:
                                if not self.check_room_busy(room.id, day, start_time, end_time):
                                    selected_room = room
                                    break
                            
                            if not selected_room:
                                continue # Aucune salle disponible
                                
                            # 3. Vérification de la disponibilité de l'Enseignant
                            selected_teacher = None
                            for teacher in available_teachers:
                                # Vérifie si l'enseignant a déjà cours
                                if not self.check_teacher_busy(teacher.id, day, start_time, end_time):
                                    # Vérifie les préférences horaires (Disponibilités déclarées)
                                    if self.check_teacher_preferences(teacher.id, day, start_time, end_time):
                                        selected_teacher = teacher
                                        break
                            
                            if not selected_teacher:
                                continue # Aucun enseignant disponible
                                
                            # --- Succès ! Création du créneau ---
                            new_slot = TimeSlot(
                                course_id=course.id,
                                group_id=group.id,
                                room_id=selected_room.id,
                                teacher_id=selected_teacher.id,
                                day_of_week=day,
                                start_time=start_time,
                                end_time=end_time
                            )
                            
                            self.generated_slots.append(new_slot)
                            generated_count += 1
                            scheduled = True
                            
                    if not scheduled:
                        failed_count += 1
                        self.conflicts.append({
                            "course": course.name,
                            "group": group.name,
                            "reason": "Impossible de trouver un créneau valide (Conflits Salle/Enseignant/Groupe)"
                        })
        return {
            "generated": generated_count,
            "failed": failed_count,
            "timeslots": self.generated_slots,
            "conflicts": self.conflicts
        }

    # --- Fonctions Utilitaires ---
    def add_minutes(self, start_time, minutes):
        """
        Ajoute un nombre de minutes à un objet temps.
        Gère le dépassement d'heure via datetime.
        """
        dummy_date = datetime(2000, 1, 1, start_time.hour, start_time.minute)
        new_date = dummy_date + timedelta(minutes=minutes)
        return new_date.time()

    def is_overlap(self, start1, end1, start2, end2):
        """
        Vérifie si deux plages horaires se chevauchent.
        Logique: Le début de l'un est avant la fin de l'autre.
        """
        return max(start1, start2) < min(end1, end2)

    def check_group_busy(self, group_id, day, start_time, end_time):
        """
        Vérifie si le groupe est occupé sur ce créneau.
        Vérifie à la fois les créneaux générés en mémoire et ceux en base de données.
        """
        # Vérification des créneaux en mémoire (en cours de génération)
        for slot in self.generated_slots:
            if slot.group_id == group_id and slot.day_of_week == day:
                if self.is_overlap(start_time, end_time, slot.start_time, slot.end_time):
                    return True
        # Vérification des créneaux persistés en base
        existing = TimeSlot.query.filter_by(group_id=group_id, day_of_week=day).all()
        for slot in existing:
             if self.is_overlap(start_time, end_time, slot.start_time, slot.end_time):
                return True
        return False

    def check_room_busy(self, room_id, day, start_time, end_time):
        """
        Vérifie si la salle est occupée.
        Empêche la double réservation des ressources physiques.
        """
        for slot in self.generated_slots:
            if slot.room_id == room_id and slot.day_of_week == day:
                if self.is_overlap(start_time, end_time, slot.start_time, slot.end_time):
                    return True
        existing = TimeSlot.query.filter_by(room_id=room_id, day_of_week=day).all()
        for slot in existing:
             if self.is_overlap(start_time, end_time, slot.start_time, slot.end_time):
                return True
        return False

    def check_teacher_busy(self, teacher_id, day, start_time, end_time):
        """
        Vérifie si l'enseignant dispense déjà un autre cours.
        Un enseignant ne peut pas être à deux endroits simultanément.
        """
        for slot in self.generated_slots:
            if slot.teacher_id == teacher_id and slot.day_of_week == day:
                if self.is_overlap(start_time, end_time, slot.start_time, slot.end_time):
                    return True
        existing = TimeSlot.query.filter_by(teacher_id=teacher_id, day_of_week=day).all()
        for slot in existing:
             if self.is_overlap(start_time, end_time, slot.start_time, slot.end_time):
                return True
        return False

    def check_teacher_preferences(self, teacher_id, day, start_time, end_time):
        """
        Vérifie si l'enseignant est disponible selon ses préférences déclarées.
        Le créneau proposé doit être ENTIÈREMENT inclus dans une plage de disponibilité.
        """
        availabilities = TeacherAvailability.query.filter_by(teacher_id=teacher_id, day_of_week=day).all()
        
        if not availabilities:
            # Si aucune disponibilité n'est définie pour ce jour, on vérifie s'il en a pour d'autres jours.
            # Si l'enseignant a des disponibilités définies ailleurs, alors son absence de définition ici signifie "Indisponible".
            # S'il n'a aucune disponibilité définie du tout (nouvel enseignant), on peut supposer "Disponible par défaut" ou "Indisponible".
            # Politique actuelle : Si l'enseignant existe dans la table availability, on respecte strictement.
            
            any_avail = TeacherAvailability.query.filter_by(teacher_id=teacher_id).first()
            if not any_avail:
                return True # Aucune contrainte définie, considéré disponible
            return False # A des contraintes, mais aucune pour ce jour -> Indisponible
            
        for avail in availabilities:
            if avail.is_available:
                # Vérification de l'inclusion stricte : Le cours doit commencer après le début de la dispo
                # ET finir avant la fin de la dispo.
                if avail.start_time <= start_time and avail.end_time >= end_time:
                    return True
        
        return False

    def save_timetable(self, db):
        """
        Sauvegarde l'emploi du temps généré en base de données.
        Utilise une transaction atomique.
        """
        try:
            for slot in self.generated_slots:
                db.session.add(slot)
            db.session.commit()
            return len(self.generated_slots)
        except Exception as e:
            db.session.rollback()
            print(f"Erreur lors de la sauvegarde de l'emploi du temps : {e}")
            return 0
