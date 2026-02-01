from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timezone, time
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, Time, Enum, ForeignKey, Table, UniqueConstraint
from sqlalchemy.orm import relationship
import bcrypt
import enum

# ------------------ Initialisation de SQLAlchemy ------------------
db = SQLAlchemy()

# ------------------- Énumérations -------------------
class CourseType(enum.Enum):
    """
    Type de cours disponible dans l'université.
    CM: Cours Magistral
    TD: Travaux Dirigés
    TP: Travaux Pratiques
    Exam: Examen
    Autre: Autre activité
    """
    LECTURE = "CM"
    TUTORIAL = "TD"
    LAB = "TP"
    EXAM = "Exam"
    OTHER = "Autre"

    @classmethod
    def _missing_(cls, value):
        """
        Gère la conversion des chaînes de caractères vers l'énumération.
        Permet une correspondance flexible des types de cours.
        """
        if isinstance(value, str):
            mapping = {
                'CM': cls.LECTURE,
                'TD': cls.TUTORIAL,
                'TP': cls.LAB,
                'Exam': cls.EXAM,
                'Autre': cls.OTHER
            }
            return mapping.get(value, cls.LECTURE)
        return None

# ------------------- Modèles d'Utilisateurs -------------------
class User(UserMixin, db.Model):
    """
    Modèle de base pour tous les utilisateurs (Polymorphisme).
    Gère l'authentification et les informations communes.
    """
    __tablename__ = 'user'
    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)
    type = Column(String(50)) # Discriminant pour le polymorphisme
    notifications = relationship('Notification', back_populates='user', cascade='all, delete-orphan')

    __mapper_args__ = {'polymorphic_on': type, 'polymorphic_identity': 'user'}

    def set_password(self, password):
        """Hache et stocke le mot de passe de l'utilisateur."""
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        """Vérifie si le mot de passe fourni correspond au hash stocké."""
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

    @property
    def full_name(self):
        """Retourne le nom complet de l'utilisateur."""
        return f"{self.first_name} {self.last_name}"

class Admin(User):
    """
    Modèle pour les administrateurs du système.
    A les droits de gestion globale (emploi du temps, utilisateurs, etc.).
    """
    __tablename__ = 'admin'
    id = Column(Integer, ForeignKey('user.id'), primary_key=True)
    permissions = Column(String(500), default='all')
    __mapper_args__ = {'polymorphic_identity': 'admin'}

class Teacher(User):
    """
    Modèle pour les enseignants.
    Contient les informations spécifiques : spécialisation, disponibilités, cours enseignés.
    """
    __tablename__ = 'teacher'
    id = Column(Integer, ForeignKey('user.id'), primary_key=True)
    specialization = Column(String(255))
    office_location = Column(String(255))
    phone = Column(String(20))
    # Relation Many-to-Many avec Course
    courses = relationship('Course', secondary='teacher_courses', back_populates='teachers')
    # Relation One-to-Many avec TeacherAvailability
    availability = relationship('TeacherAvailability', back_populates='teacher', cascade='all, delete-orphan')
    booking_requests = relationship('BookingRequest', back_populates='teacher')
    __mapper_args__ = {'polymorphic_identity': 'teacher'}

class Student(User):
    """
    Modèle pour les étudiants.
    Lié à des groupes pour la gestion des emplois du temps.
    """
    __tablename__ = 'student'
    id = Column(Integer, ForeignKey('user.id'), primary_key=True)
    student_id = Column(String(50), unique=True, nullable=False) # Numéro d'étudiant (CNE/Massar)
    enrollment_year = Column(Integer)
    groups = relationship('Group', secondary='student_groups', back_populates='students')
    __mapper_args__ = {'polymorphic_identity': 'student'}

# ------------------- Modèles Académiques -------------------
class Department(db.Model):
    """
    Représente un département académique (ex: Informatique, Mathématiques).
    Regroupe plusieurs filières ou groupes.
    """
    __tablename__ = 'department'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    code = Column(String(50), nullable=False, unique=True)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    groups = relationship('Group', back_populates='department')

class Course(db.Model):
    """
    Représente un module ou une matière enseignée.
    Définit le volume horaire et les contraintes spécifiques.
    """
    __tablename__ = 'course'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    course_type = Column(Enum(CourseType, values_callable=lambda obj: [e.value for e in obj]),
                         default=CourseType.LECTURE)
    duration_minutes = Column(Integer, default=60) # Durée standard d'une séance
    credits = Column(Integer, default=3)
    
    # Indique si le cours nécessite une salle équipée (Labo)
    requires_lab = Column(Boolean, default=False)
    
    # Nombre de séances hebdomadaires requises
    weekly_sessions = Column(Integer, default=1)
    
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    teachers = relationship('Teacher', secondary='teacher_courses', back_populates='courses')
    groups = relationship('Group', secondary='group_courses', back_populates='courses')
    timeslots = relationship('TimeSlot', back_populates='course', cascade='all, delete-orphan')

class Group(db.Model):
    """
    Groupe d'étudiants (Classe/TD/TP).
    L'entité principale pour laquelle l'emploi du temps est généré.
    """
    __tablename__ = 'group'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    department_id = Column(Integer, ForeignKey('department.id', ondelete='RESTRICT'), nullable=False)
    capacity = Column(Integer, default=30)
    semester = Column(Integer)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    
    department = relationship('Department', back_populates='groups')
    students = relationship('Student', secondary='student_groups', back_populates='groups')
    courses = relationship('Course', secondary='group_courses', back_populates='groups')

# ------------------- Tables d'Association -------------------
# Table de liaison Enseignant <-> Cours
teacher_courses = db.Table(
    'teacher_courses',
    db.metadata,
    Column('teacher_id', Integer, ForeignKey('teacher.id'), primary_key=True),
    Column('course_id', Integer, ForeignKey('course.id'), primary_key=True)
)

# Table de liaison Étudiant <-> Groupe
student_groups = db.Table(
    'student_groups',
    db.metadata,
    Column('student_id', Integer, ForeignKey('student.id'), primary_key=True),
    Column('group_id', Integer, ForeignKey('group.id'), primary_key=True)
)

# Table de liaison Groupe <-> Cours (Programme du groupe)
group_courses = db.Table(
    'group_courses',
    db.metadata,
    Column('group_id', Integer, ForeignKey('group.id'), primary_key=True),
    Column('course_id', Integer, ForeignKey('course.id'), primary_key=True)
)

# Table de liaison Salle <-> Équipement
room_equipment = db.Table(
    'room_equipment',
    db.metadata,
    Column('room_id', Integer, ForeignKey('room.id'), primary_key=True),
    Column('equipment_id', Integer, ForeignKey('equipment.id'), primary_key=True)
)

# ------------------- Modèles de Salles et Équipements -------------------
class Equipment(db.Model):
    """
    Équipement disponible dans les salles (Projecteur, Ordinateurs, etc.).
    """
    __tablename__ = 'equipment'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    quantity = Column(Integer, default=1)

class Room(db.Model):
    """
    Salle de cours, laboratoire ou amphithéâtre.
    Possède une capacité et des équipements spécifiques.
    """
    __tablename__ = 'room'
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)
    code = Column(String(50), unique=True, nullable=False)
    building = Column(String(100))
    floor = Column(Integer)
    capacity = Column(Integer, nullable=False)
    room_type = Column(String(50)) # Ex: 'Lab', 'Classroom', 'Amphitheater'
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    equipment = relationship('Equipment', secondary='room_equipment')
    timeslots = relationship('TimeSlot', back_populates='room', cascade='all, delete-orphan')
    booking_requests = relationship('BookingRequest', back_populates='room')

# ------------------- Modèles de Planification -------------------
class TimeSlot(db.Model):
    """
    Créneau horaire (Séance de cours).
    Associe un Cours, un Groupe, un Enseignant et une Salle à un moment précis.
    """
    __tablename__ = 'timeslot'
    id = Column(Integer, primary_key=True)
    
    # Clés étrangères avec suppression en cascade
    teacher_id = Column(Integer, ForeignKey('teacher.id', ondelete='CASCADE'), nullable=False)
    course_id = Column(Integer, ForeignKey('course.id', ondelete='CASCADE'), nullable=False)
    group_id = Column(Integer, ForeignKey('group.id', ondelete='CASCADE'), nullable=True) # Null si cours magistral commun
    room_id = Column(Integer, ForeignKey('room.id', ondelete='CASCADE'), nullable=False)
    
    day_of_week = Column(Integer) # 0=Lundi, 6=Dimanche
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    
    # Verrouillage pour empêcher la modification automatique par l'algorithme
    is_locked = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    
    # Relations ORM
    teacher = relationship('Teacher')
    course = relationship('Course', back_populates='timeslots')
    group = relationship('Group')
    room = relationship('Room', back_populates='timeslots')
    
    # Contraintes d'unicité pour éviter les conflits au niveau de la base de données
    __table_args__ = (
        UniqueConstraint('room_id', 'day_of_week', 'start_time', name='unique_room_time'),
        UniqueConstraint('teacher_id', 'day_of_week', 'start_time', name='unique_teacher_time'),
    )

class TeacherAvailability(db.Model):
    """
    Disponibilités déclarées par les enseignants.
    Définit les plages horaires où un enseignant PEUT enseigner.
    """
    __tablename__ = 'teacher_availability'
    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey('teacher.id', ondelete='CASCADE'), nullable=False)
    day_of_week = Column(Integer)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    is_available = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    teacher = relationship('Teacher', back_populates='availability')

# ------------------- Modèles de Réservation et Notification -------------------
class BookingRequest(db.Model):
    """
    Demande de réservation de salle ponctuelle par un enseignant.
    """
    __tablename__ = 'booking_request'
    id = Column(Integer, primary_key=True)
    teacher_id = Column(Integer, ForeignKey('teacher.id', ondelete='CASCADE'), nullable=False)
    course_id = Column(Integer, ForeignKey('course.id', ondelete='CASCADE'), nullable=True)
    group_id = Column(Integer, ForeignKey('group.id', ondelete='CASCADE'), nullable=True)
    room_id = Column(Integer, ForeignKey('room.id', ondelete='CASCADE'), nullable=False)
    requested_date = Column(DateTime, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    reason = Column(Text)
    status = Column(String(50), default='pending') # pending, approved, rejected
    approved_by = Column(Integer, ForeignKey('admin.id', ondelete='SET NULL'))
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))
    
    teacher = relationship('Teacher', back_populates='booking_requests')
    course = relationship('Course')
    group = relationship('Group')
    room = relationship('Room', back_populates='booking_requests')

class Notification(db.Model):
    """
    Système de notification pour les utilisateurs.
    """
    __tablename__ = 'notification'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    title = Column(String(255), nullable=False)
    message = Column(Text)
    notification_type = Column(String(50))
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    user = relationship('User', back_populates='notifications')

# ------------------- Autres Modèles -------------------
class Constraint(db.Model):
    """
    Configuration dynamique des contraintes (Non utilisé dans la version actuelle).
    """
    __tablename__ = 'constraint'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    constraint_type = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Constraint {self.name}>"
