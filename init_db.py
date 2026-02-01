from datetime import datetime, time, timedelta
import random
import uuid 
from app import create_app, db
from models import (
    User, Admin, Teacher, Student, Department, Group, Course, 
    Room, Equipment, TimeSlot, TeacherAvailability, 
    CourseType, room_equipment, teacher_courses
)
from sqlalchemy import text

# Constantes - Mise à jour des données pour respecter les exigences académiques
MAJORS_COURSES = {
    'Informatique': [
        {'name': 'Introduction à la programmation', 'type': 'CM', 'duration': 60},
        {'name': 'Structures de données', 'type': 'CM', 'duration': 60},
        {'name': 'Développement Web', 'type': 'TP', 'duration': 60},
        {'name': 'Systèmes de bases de données', 'type': 'CM', 'duration': 60},
        {'name': 'Réseaux informatiques', 'type': 'TD', 'duration': 60},
        {'name': 'Systèmes d\'exploitation', 'type': 'TP', 'duration': 60}
    ],
    'Mathématiques': [
        {'name': 'Calcul I', 'type': 'CM', 'duration': 60},
        {'name': 'Algèbre linéaire', 'type': 'TD', 'duration': 60},
        {'name': 'Probabilités', 'type': 'CM', 'duration': 60},
        {'name': 'Statistiques', 'type': 'TP', 'duration': 60},
        {'name': 'Équations différentielles', 'type': 'CM', 'duration': 60},
        {'name': 'Analyse numérique', 'type': 'TP', 'duration': 60}
    ],
    'Physique': [
        {'name': 'Mécanique', 'type': 'CM', 'duration': 60},
        {'name': 'Thermodynamique', 'type': 'TD', 'duration': 60},
        {'name': 'Électromagnétisme', 'type': 'CM', 'duration': 60},
        {'name': 'Optique', 'type': 'TP', 'duration': 60},
        {'name': 'Physique quantique', 'type': 'CM', 'duration': 60},
        {'name': 'Électronique', 'type': 'TP', 'duration': 60}
    ],
    'Chimie': [
        {'name': 'Chimie générale', 'type': 'CM', 'duration': 60},
        {'name': 'Chimie organique', 'type': 'TP', 'duration': 60},
        {'name': 'Chimie inorganique', 'type': 'CM', 'duration': 60},
        {'name': 'Chimie analytique', 'type': 'TP', 'duration': 60},
        {'name': 'Chimie physique', 'type': 'TD', 'duration': 60},
        {'name': 'Biochimie', 'type': 'CM', 'duration': 60}
    ],
    'Biologie': [
        {'name': 'Biologie cellulaire', 'type': 'CM', 'duration': 60},
        {'name': 'Génétique', 'type': 'TD', 'duration': 60},
        {'name': 'Microbiologie', 'type': 'TP', 'duration': 60},
        {'name': 'Écologie', 'type': 'CM', 'duration': 60},
        {'name': 'Physiologie', 'type': 'TP', 'duration': 60},
        {'name': 'Biotechnologie', 'type': 'CM', 'duration': 60}
    ]
}

FIRST_NAMES = ['Mohamed', 'Youssef', 'Ahmed', 'Omar', 'Mehdi', 'Amine', 'Karim', 'Hassan', 'Rachid', 'Said', 
               'Fatima', 'Amina', 'Khadija', 'Zineb', 'Ghita', 'Salma', 'Houda', 'Noura', 'Samira', 'Leila']
LAST_NAMES = ['Alami', 'Bennani', 'Tazi', 'Idrissi', 'Fassi', 'Chraibi', 'Berrada', 'Benjelloun', 'El Amrani', 'Daoudi',
              'Mansouri', 'Naciri', 'Alaoui', 'Filali', 'Boukhris', 'Jebari', 'Ouazzani', 'Tahiri', 'Chaoui', 'Saidi']

def generate_moroccan_name():
    """Génère un nom marocain aléatoire pour les données de test."""
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def calculate_weekly_sessions(duration_minutes, required_weekly_hours=3):
    """
    Calcule le nombre de séances hebdomadaires nécessaires.
    Basé sur la durée de la séance et le volume horaire requis.
    """
    duration_hours = duration_minutes / 60.0
    return max(1, round(required_weekly_hours / duration_hours))

def init_db():
    """
    Fonction principale d'initialisation de la base de données.
    Crée les tables et injecte les données factices (Seed).
    """
    app = create_app()
    with app.app_context():
        print("Suppression de toutes les tables...")
        db.drop_all()
        print("Création de toutes les tables...")
        db.create_all()

        # 1. Créer l'Administrateur
        print("Création de l'Administrateur...")
        admin = Admin(
            email='admin@university.edu',
            first_name='System',
            last_name='Admin',
            is_active=True,
            permissions='all'
        )
        admin.set_password('admin123')
        db.session.add(admin)

        # 2. Créer les Départements
        print("Création des Départements...")
        departments = {}
        for name in MAJORS_COURSES.keys():
            code = name[:4].upper()
            dept = Department(name=name, code=code, description=f"Département de {name}")
            db.session.add(dept)
            departments[name] = dept
        db.session.commit()

        # 3. Créer les Équipements
        print("Création des Équipements...")
        eq_computer = Equipment(name='Ordinateurs', quantity=100)
        eq_whiteboard = Equipment(name='Tableau blanc', quantity=50)
        eq_projector = Equipment(name='Projecteur', quantity=30)
        eq_datashow = Equipment(name='Data Show', quantity=20)
        
        db.session.add_all([eq_computer, eq_whiteboard, eq_projector, eq_datashow])
        db.session.commit()

        # 4. Créer les Salles
        print("Création des Salles...")
        
        # Amphithéâtres (Projecteur, Tableau blanc, Data Show)
        amphi_eq = [eq_projector, eq_whiteboard, eq_datashow]
        for i in range(1, 7):
            room = Room(
                name=f"Amphi {i}", 
                code=f"AM{i}", 
                capacity=150, 
                room_type='Amphitheater',
                building='Bâtiment Principal'
            )
            room.equipment = amphi_eq
            db.session.add(room)

        # Salles de classe (Tableau blanc)
        classroom_eq = [eq_whiteboard]
        # B10-B14
        for i in range(10, 15):
            room = Room(name=f"Salle B{i}", code=f"B{i}", capacity=40, room_type='Classroom', building='Bloc B')
            room.equipment = classroom_eq
            db.session.add(room)
        # C10-C14
        for i in range(10, 15):
            room = Room(name=f"Salle C{i}", code=f"C{i}", capacity=40, room_type='Classroom', building='Bloc C')
            room.equipment = classroom_eq
            db.session.add(room)
        # F10-F15
        for i in range(10, 16):
            room = Room(name=f"Salle F{i}", code=f"F{i}", capacity=40, room_type='Classroom', building='Bloc F')
            room.equipment = classroom_eq
            db.session.add(room)
        # G1-G5
        for i in range(1, 6):
            room = Room(name=f"Salle G{i}", code=f"G{i}", capacity=40, room_type='Classroom', building='Bloc G')
            room.equipment = classroom_eq
            db.session.add(room)

        # Laboratoires (Ordinateurs, Tableau blanc, Projecteur)
        lab_eq = [eq_computer, eq_whiteboard, eq_projector]
        for i in range(15, 26):
            room = Room(name=f"Lab E{i}", code=f"E{i}", capacity=30, room_type='Lab', building='Bloc E')
            room.equipment = lab_eq
            db.session.add(room)
            
        db.session.commit()

        # 5. Créer les Cours, Groupes, Étudiants, Enseignants
        print("Création des Données Académiques...")
        
        all_courses = []
        
        i=1  # Compteur global pour les IDs étudiants
        for dept_name, course_list in MAJORS_COURSES.items():
            dept = departments[dept_name]
            
            # Créer les Cours avec les volumes horaires appropriés
            dept_courses = []
            for c_info in course_list:
                # Déterminer si le cours nécessite un laboratoire (TP)
                is_lab_required = (c_info['type'] == 'TP')
                
                # Calcul du nombre de séances selon les exigences (3 heures par semaine)
                weekly_sessions = calculate_weekly_sessions(c_info['duration'], 3)
                
                course = Course(
                    name=c_info['name'],
                    code=f"{dept.code}-{c_info['name'][:3].upper()}-{random.randint(10,99)}",
                    course_type=c_info['type'], 
                    duration_minutes=c_info['duration'],
                    credits=4,
                    requires_lab=is_lab_required,
                    weekly_sessions=weekly_sessions  # Séances requises par semaine
                )
                db.session.add(course)
                dept_courses.append(course)
                all_courses.append(course)
            db.session.commit()
            
            # Créer 2 Groupes par département
            for g_num in range(1, 3):
                group = Group(
                    name=f"{dept_name} Groupe {g_num}",
                    code=f"{dept.code}-G{g_num}",
                    department_id=dept.id,
                    capacity=30,
                    semester=1
                )
                db.session.add(group)
                
                # Assigner tous les cours du département au groupe
                group.courses = dept_courses
                
                # Créer 10 Étudiants par groupe
                for s_num in range(10):
                    full_name = generate_moroccan_name()
                    fname, lname = full_name.split(' ', 1)
                    student = Student(
                        email=f"student{i}@student.university.edu",
                        first_name=fname,
                        last_name=lname,
                        student_id = i,
                        enrollment_year=datetime.now().year,
                        is_active=True
                    )
                    i+=1
                    student.set_password('student123')
                    db.session.add(student)
                    student.groups.append(group)
        
        db.session.commit()

        # 6. Créer les Enseignants et leurs Disponibilités
        print("Création des Enseignants...")
        
        # Calcul du nombre d'enseignants requis :
        # 5 Départements * 6 Cours = 30 Cours au total.
        # Certains enseignants peuvent enseigner plusieurs matières.
        teacher_count = 20  # 20 enseignants sont suffisants pour couvrir la charge
        
        teachers = []
        for i in range(teacher_count):
            full_name = generate_moroccan_name()
            fname, lname = full_name.split(' ', 1)
            teacher = Teacher(
                email=f"teacher{i}@teacher.university.edu",
                first_name=fname,
                last_name=lname,
                specialization=random.choice(list(MAJORS_COURSES.keys())),
                office_location=f"Bureau {random.randint(100, 300)}",
                phone=f"06675431{random.randint(10,99)}",
                is_active=True
            )
            teacher.set_password('teacher123')
            db.session.add(teacher)
            teachers.append(teacher)
        db.session.commit()

        # Distribution des cours aux enseignants
        # Chaque enseignant prend en charge entre 2 et 4 cours
        for course in all_courses:
            # Assigner 1 à 3 enseignants par cours pour la redondance
            num_teachers_for_course = random.randint(1, 3)
            assigned_teachers = random.sample(teachers, min(num_teachers_for_course, len(teachers)))
            
            for teacher in assigned_teachers:
                if course not in teacher.courses:
                    teacher.courses.append(course)
        
        # Vérification : Chaque enseignant doit avoir au moins un cours
        for teacher in teachers:
            if not teacher.courses:
                # Assigner 2 à 3 cours aléatoires
                teacher.courses = random.sample(all_courses, random.randint(2, 3))
        
        db.session.commit()

        # 7. Définir les Disponibilités des Enseignants (Bloc de 4 heures continu)
        print("Définition des Disponibilités des Enseignants...")
        days = [0, 1, 2, 3, 4] # Lundi-Vendredi
        
        for teacher in teachers:
            for day in days:
                # Génération d'un bloc continu de 4 heures
                # 5 options de début possibles : 8h, 9h, 10h, 11h, 12h, 13h
                start_options = [8, 9, 10, 11, 12, 13]
                start_hour = random.choice(start_options)
                
                # Vérifier que le bloc ne dépasse pas 18h
                if start_hour <= 14:
                    start_time = time(start_hour, 0)
                    end_time = time(start_hour + 4, 0)
                    
                    avail = TeacherAvailability(
                        teacher_id=teacher.id,
                        day_of_week=day,
                        start_time=start_time,
                        end_time=end_time,
                        is_available=True
                    )
                    db.session.add(avail)
        
        db.session.commit()
        
        # 8. Finalisation
        # La création manuelle de créneaux a été supprimée pour laisser l'algorithme gérer la cohérence.
        print("Initialisation de la base de données terminée !")
        print(f"══════════════════════════════════════════════════")
        print(f"📊 Statistiques:")
        print(f"   • Administrateur : admin@university.edu / admin123")
        print(f"   • Enseignants : {Teacher.query.count()}")
        print(f"   • Étudiants : {Student.query.count()}")
        print(f"   • Cours : {Course.query.count()}")
        print(f"   • Groupes : {Group.query.count()}")
        print(f"   • Salles : {Room.query.count()}")
        
        # Calcul du total des heures requises
        total_hours_needed = 0
        for course in Course.query.all():
            duration_hours = course.duration_minutes / 60.0
            total_hours_needed += duration_hours * course.weekly_sessions
        
        print(f"   • Total heures requises/semaine : {total_hours_needed:.1f} heures")
        
        # Calcul des heures par groupe
        print(f"\n📈 Détails par groupe:")
        for group in Group.query.all():
            group_hours = 0
            for course in group.courses:
                duration_hours = course.duration_minutes / 60.0
                group_hours += duration_hours * course.weekly_sessions
            
            status = "✅" if 18 <= group_hours <= 24 else "⚠️"
            print(f"   {status} {group.name}: {group_hours:.1f} heures/semaine")
        
        print(f"══════════════════════════════════════════════════")

if __name__ == '__main__':
    init_db()
