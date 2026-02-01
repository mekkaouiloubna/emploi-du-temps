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

        # Créneaux horaires structurés (plages fixes pour éviter la fragmentation)
        # AMÉLIORATION: Horaires organisés en blocs cohérents
        self.morning_slots = [
            time(8, 0),   # 8h-9h30
            time(9, 30),  # 9h30-11h
            time(10, 0),  # 10h-11h30
            time(11, 0),  # 11h-12h30
        ]
        
        # AMÉLIORATION: Pause déjeuner respectée (12h-14h)
        # Aucun créneau entre 12h et 14h
        
        self.afternoon_slots = [
            time(14, 0),  # 14h-15h30
            time(15, 0),  # 15h-16h30
            time(15, 30), # 15h30-17h
            time(16, 0),  # 16h-17h30
        ]
        
        # Combinaison des créneaux matin et après-midi
        self.slot_starts = self.morning_slots + self.afternoon_slots
        
        # Jours de la semaine : 0=Lundi à 5=Samedi
        self.days = [0, 1, 2, 3, 4, 5]
        
        # AMÉLIORATION: Limites de temps pour la pause déjeuner
        self.lunch_break_start = time(12, 0)
        self.lunch_break_end = time(14, 0)

    def generate(self):
        """
        Boucle principale de génération des emplois du temps.
        Parcourt les groupes et les cours pour assigner des créneaux valides.
        """
        # 1. Récupération des groupes cibles avec filtrage par semestre
        if self.group_id and self.group_id != 0:
            # Si un groupe spécifique est sélectionné, on le récupère directement
            groups = Group.query.filter_by(id=self.group_id).all()
        else:
            # Sinon, on récupère tous les groupes du département ET du semestre spécifié
            # CRITIQUE: Filtrage par semestre pour éviter la surcharge d'heures
            groups = Group.query.filter_by(
                department_id=self.department_id,
                semester=self.semester
            ).all()
        
        if not groups:
            return {
                "error": f"Aucun groupe trouvé pour le département {self.department_id} et le semestre {self.semester}",
                "generated": 0,
                "failed": 0,
                "timeslots": [],
                "conflicts": [{
                    "course": "N/A",
                    "group": "N/A",
                    "reason": f"Aucun groupe n'existe pour le semestre {self.semester} dans ce département. Veuillez d'abord créer des groupes pour ce semestre."
                }]
            }

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
                    # AMÉLIORATION: Ajouter vérification de capacité
                    suitable_rooms = [
                        r for r in all_rooms 
                        if (r.room_type == 'Lab') == course.requires_lab
                        and self.check_room_capacity(r, group)
                    ]
                    
                    # AMÉLIORATION: Ne plus mélanger aléatoirement pour avoir des horaires cohérents
                    # Les créneaux sont déjà organisés (matin puis après-midi)
                    # random.shuffle(suitable_rooms)  # Commenté pour garder l'ordre
                    # random.shuffle(self.days)  # Commenté pour garder l'ordre des jours
                    
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

                        for start_time in self.slot_starts:  # AMÉLIORATION: Utiliser l'ordre structuré
                            if scheduled: break
                            
                            # Calcul de l'heure de fin
                            end_time = self.add_minutes(start_time, duration_min)
                            
                            # Validation de l'heure de fin (Ne doit pas dépasser 18h00)
                            if end_time > time(18, 0):
                                continue
                            
                            # AMÉLIORATION: Vérification de la pause déjeuner
                            if not self.check_lunch_break(start_time, end_time):
                                continue
                            
                            # AMÉLIORATION: Vérification des cours consécutifs
                            if not self.check_consecutive_courses(group.id, day, start_time, end_time):
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

    def check_lunch_break(self, start_time, end_time):
        """
        AMÉLIORATION: Vérifie que le créneau ne chevauche pas la pause déjeuner (12h-14h).
        Retourne True si le créneau est valide (ne chevauche pas), False sinon.
        """
        # Le créneau est invalide s'il chevauche la pause déjeuner
        if self.is_overlap(start_time, end_time, self.lunch_break_start, self.lunch_break_end):
            return False
        return True

    def check_room_capacity(self, room, group):
        """
        AMÉLIORATION: Vérifie que la capacité de la salle est suffisante pour le groupe.
        Retourne True si la salle peut accueillir le groupe, False sinon.
        """
        if not group:
            return True  # Pas de groupe spécifique, pas de contrainte
        
        # Vérifier la capacité du groupe
        group_size = group.capacity if hasattr(group, 'capacity') and group.capacity else 30
        
        # La salle doit avoir au moins la capacité du groupe
        if room.capacity >= group_size:
            return True
        
        return False

    def check_consecutive_courses(self, group_id, day, start_time, end_time):
        """
        AMÉLIORATION: Vérifie qu'un groupe n'a pas trop de cours consécutifs.
        Maximum 3 heures de cours d'affilée (180 minutes).
        Retourne True si le créneau respecte la limite, False sinon.
        """
        # Récupérer tous les créneaux du groupe pour ce jour
        existing_slots = [slot for slot in self.generated_slots 
                         if slot.group_id == group_id and slot.day_of_week == day]
        
        # Ajouter les créneaux de la base de données
        db_slots = TimeSlot.query.filter_by(group_id=group_id, day_of_week=day).all()
        existing_slots.extend(db_slots)
        
        if not existing_slots:
            return True  # Pas de cours existants, OK
        
        # Calculer la durée totale des cours consécutifs incluant le nouveau créneau
        # Trier les créneaux par heure de début
        all_slots = existing_slots + [type('obj', (object,), {
            'start_time': start_time, 
            'end_time': end_time
        })]
        
        all_slots.sort(key=lambda x: x.start_time)
        
        # Vérifier les blocs consécutifs
        consecutive_minutes = 0
        last_end = None
        
        for slot in all_slots:
            if last_end is None:
                # Premier créneau du bloc
                duration = (datetime.combine(date.min, slot.end_time) - 
                           datetime.combine(date.min, slot.start_time)).total_seconds() / 60
                consecutive_minutes = duration
                last_end = slot.end_time
            else:
                # Vérifier si ce créneau est consécutif au précédent (max 15 min d'écart)
                gap = (datetime.combine(date.min, slot.start_time) - 
                      datetime.combine(date.min, last_end)).total_seconds() / 60
                
                if gap <= 15:  # Considéré comme consécutif si écart <= 15 min
                    duration = (datetime.combine(date.min, slot.end_time) - 
                               datetime.combine(date.min, slot.start_time)).total_seconds() / 60
                    consecutive_minutes += duration
                    last_end = slot.end_time
                    
                    # Vérifier la limite de 180 minutes (3 heures)
                    if consecutive_minutes > 180:
                        return False
                else:
                    # Nouveau bloc, réinitialiser
                    duration = (datetime.combine(date.min, slot.end_time) - 
                               datetime.combine(date.min, slot.start_time)).total_seconds() / 60
                    consecutive_minutes = duration
                    last_end = slot.end_time
        
        return True

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
