from datetime import datetime, date
from functools import wraps
from flask import render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Laboratory, Seat, Booking, Schedule, Attendance, Session, Notification
from app.agents import booking_agent, recommendation_agent, monitoring_agent
from . import student_bp


def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role != 'student':
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return login_required(decorated)


@student_bp.route('/dashboard')
@student_required
def dashboard():
    now = datetime.utcnow()
    today_dow = now.weekday()

    active_bookings = Booking.query.filter_by(
        user_id=current_user.id, status='approved'
    ).filter(Booking.end_time > now).order_by(Booking.start_time).all()

    todays_sessions = Schedule.query.filter_by(day_of_week=today_dow, active=True).all()

    records = Attendance.query.filter_by(user_id=current_user.id).all()
    total = len(records)
    present = sum(1 for r in records if r.status == 'present')
    attendance_rate = round(present / total * 100) if total > 0 else 0

    unread_count = Notification.query.filter_by(user_id=current_user.id, read=False).count()

    recent_notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).limit(5).all()

    return render_template('student/dashboard.html',
        active_bookings=active_bookings,
        todays_sessions=todays_sessions,
        attendance_rate=attendance_rate,
        unread_count=unread_count,
        recent_notifications=recent_notifications,
        now=now
    )


@student_bp.route('/labs')
@student_required
def labs():
    labs = Laboratory.query.filter_by(status='active').all()
    occupancy = {lab.id: monitoring_agent.get_lab_occupancy(lab.id) for lab in labs}
    return render_template('student/labs.html', labs=labs, occupancy=occupancy)


@student_bp.route('/book/<lab_id>')
@student_required
def book_seat(lab_id):
    lab = Laboratory.query.get_or_404(lab_id)
    seats = Seat.query.filter_by(lab_id=lab_id).order_by(Seat.seat_number).all()
    now = datetime.utcnow()
    recommendations = recommendation_agent.recommend_seats(lab_id, now, now)
    from flask import current_app
    return render_template('student/book_seat.html',
        lab=lab,
        seats=seats,
        recommendations=recommendations,
        config=current_app.config
    )


@student_bp.route('/book', methods=['POST'])
@student_required
def submit_booking():
    seat_id = request.form.get('seat_id')
    start_str = request.form.get('start_time')
    end_str = request.form.get('end_time')

    if not all([seat_id, start_str, end_str]):
        flash('All booking fields are required.', 'danger')
        return redirect(url_for('student.labs'))

    try:
        start_time = datetime.fromisoformat(start_str)
        end_time = datetime.fromisoformat(end_str)
    except ValueError:
        flash('Invalid date format.', 'danger')
        return redirect(url_for('student.labs'))

    if end_time <= start_time:
        flash('End time must be after start time.', 'danger')
        seat = Seat.query.get(seat_id)
        return redirect(url_for('student.book_seat', lab_id=seat.lab_id if seat else ''))

    result = booking_agent.evaluate(current_user.id, seat_id, start_time, end_time)

    if result['decision'] == 'APPROVE':
        flash('Booking confirmed! Your seat is reserved.', 'success')
        seat = Seat.query.get(seat_id)
        monitoring_agent.update_seat_status(seat_id, 'reserved')
        return redirect(url_for('student.bookings'))
    else:
        flash(f'Booking declined: {result["reason"]}', 'danger')
        seat = Seat.query.get(seat_id)
        return redirect(url_for('student.book_seat', lab_id=seat.lab_id if seat else ''))


@student_bp.route('/bookings')
@student_required
def bookings():
    bookings = Booking.query.filter_by(user_id=current_user.id)\
        .order_by(Booking.created_at.desc()).all()
    return render_template('student/bookings.html', bookings=bookings)


@student_bp.route('/schedule')
@student_required
def schedule():
    schedules = Schedule.query.filter_by(active=True)\
        .order_by(Schedule.day_of_week, Schedule.start_time).all()
    return render_template('student/schedule.html', schedules=schedules)


@student_bp.route('/attendance')
@student_required
def attendance():
    records = Attendance.query.filter_by(user_id=current_user.id)\
        .order_by(Attendance.recorded_at.desc()).all()
    present = sum(1 for r in records if r.status == 'present')
    absent = sum(1 for r in records if r.status == 'absent')
    anomaly = sum(1 for r in records if r.status == 'anomaly')
    attendance_summary = {'present': present, 'absent': absent, 'anomaly': anomaly}
    return render_template('student/attendance.html',
        records=records,
        attendance_summary=attendance_summary
    )


@student_bp.route('/notifications')
@student_required
def notifications():
    notifs = Notification.query.filter_by(user_id=current_user.id)\
        .order_by(Notification.created_at.desc()).all()
    for n in notifs:
        if not n.read:
            n.read = True
    db.session.commit()
    unread_count = 0
    return render_template('student/notifications.html',
        notifications=notifs,
        unread_count=unread_count
    )


@student_bp.route('/notifications/mark-all-read', methods=['POST'])
@student_required
def mark_all_read():
    Notification.query.filter_by(user_id=current_user.id, read=False).update({'read': True})
    db.session.commit()
    flash('All notifications marked as read.', 'success')
    return redirect(url_for('student.notifications'))
