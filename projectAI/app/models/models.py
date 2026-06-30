import uuid
from datetime import datetime
from flask_login import UserMixin
from app.extensions import db


def gen_uuid():
    return str(uuid.uuid4())


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum('student', 'lecturer', 'technician', 'admin', name='user_role'), nullable=False)
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bookings = db.relationship('Booking', foreign_keys='Booking.user_id', backref='user', lazy='dynamic')
    attendance_records = db.relationship('Attendance', foreign_keys='Attendance.user_id', backref='user', lazy='dynamic')
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')
    chat_logs = db.relationship('ChatLog', backref='user', lazy='dynamic')
    sessions_opened = db.relationship('Session', foreign_keys='Session.lecturer_id', backref='lecturer', lazy='dynamic')
    schedules = db.relationship('Schedule', foreign_keys='Schedule.lecturer_id', backref='lecturer', lazy='dynamic')

    def is_active(self):
        return self.active

    def get_id(self):
        return self.id


class Laboratory(db.Model):
    __tablename__ = 'laboratories'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    name = db.Column(db.String(100), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    status = db.Column(db.Enum('active', 'inactive', 'maintenance', name='lab_status'), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    seats = db.relationship('Seat', backref='laboratory', lazy='dynamic', cascade='all, delete-orphan')
    schedules = db.relationship('Schedule', backref='laboratory', lazy='dynamic')
    equipment = db.relationship('Equipment', backref='laboratory', lazy='dynamic', cascade='all, delete-orphan')


class Seat(db.Model):
    __tablename__ = 'seats'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    lab_id = db.Column(db.String(36), db.ForeignKey('laboratories.id'), nullable=False)
    seat_number = db.Column(db.String(10), nullable=False)
    status = db.Column(db.Enum('available', 'reserved', 'occupied', 'faulty', name='seat_status'), default='available')
    has_power = db.Column(db.Boolean, default=False)
    has_network = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    bookings = db.relationship('Booking', backref='seat', lazy='dynamic')


class Booking(db.Model):
    __tablename__ = 'bookings'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    seat_id = db.Column(db.String(36), db.ForeignKey('seats.id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.Enum('pending', 'approved', 'rejected', 'cancelled', 'completed', name='booking_status'), default='pending')
    agent_decision = db.Column(db.String(10))
    agent_reason = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Schedule(db.Model):
    __tablename__ = 'schedules'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    course_name = db.Column(db.String(150), nullable=False)
    lab_id = db.Column(db.String(36), db.ForeignKey('laboratories.id'), nullable=False)
    lecturer_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    active = db.Column(db.Boolean, default=True)

    sessions = db.relationship('Session', backref='schedule', lazy='dynamic')


class Session(db.Model):
    __tablename__ = 'sessions'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    schedule_id = db.Column(db.String(36), db.ForeignKey('schedules.id'), nullable=False)
    lecturer_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    opened_at = db.Column(db.DateTime, default=datetime.utcnow)
    closed_at = db.Column(db.DateTime, nullable=True)
    locked = db.Column(db.Boolean, default=False)

    attendance_records = db.relationship('Attendance', backref='session', lazy='dynamic', cascade='all, delete-orphan')


class Attendance(db.Model):
    __tablename__ = 'attendance'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    session_id = db.Column(db.String(36), db.ForeignKey('sessions.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.Enum('present', 'absent', 'anomaly', name='attendance_status'), default='absent')
    recorded_at = db.Column(db.DateTime, default=datetime.utcnow)
    agent_flag = db.Column(db.Text, nullable=True)


class Equipment(db.Model):
    __tablename__ = 'equipment'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    lab_id = db.Column(db.String(36), db.ForeignKey('laboratories.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.Enum('operational', 'faulty', 'maintenance', 'decommissioned', name='equipment_status'), default='operational')
    last_maintained = db.Column(db.Date, nullable=True)
    fault_notes = db.Column(db.Text, nullable=True)


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(50), default='info')
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AgentLog(db.Model):
    __tablename__ = 'agent_logs'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    agent_name = db.Column(db.String(50), nullable=False)
    event_type = db.Column(db.String(100), nullable=False)
    input_summary = db.Column(db.Text)
    decision = db.Column(db.String(50))
    reason = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    agent_version = db.Column(db.String(20), default='1.0')


class ChatLog(db.Model):
    __tablename__ = 'chat_logs'

    id = db.Column(db.String(36), primary_key=True, default=gen_uuid)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    context_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
