import bcrypt
from datetime import datetime, date
from functools import wraps
from flask import render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models import (
    User, Laboratory, Seat, Booking, Schedule,
    Session, Attendance, AgentLog, Notification
)
from app.agents import monitoring_agent, decision_agent
from . import admin_bp


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role != 'admin':
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return login_required(decorated)


@admin_bp.route('/dashboard')
@admin_required
def dashboard():
    now = datetime.utcnow()
    today = now.date()

    stats = {
        'total_users': User.query.filter_by(active=True).count(),
        'bookings_today': Booking.query.filter(
            db.func.date(Booking.created_at) == today
        ).count(),
        'active_labs': Laboratory.query.filter_by(status='active').count(),
        'escalations': AgentLog.query.filter_by(decision='ESCALATE').count()
    }

    labs = Laboratory.query.filter_by(status='active').all()
    occupancy = {lab.id: monitoring_agent.get_lab_occupancy(lab.id) for lab in labs}

    recent_agent_logs = AgentLog.query.order_by(AgentLog.timestamp.desc()).limit(10).all()

    return render_template('admin/dashboard.html',
        stats=stats,
        labs=labs,
        occupancy=occupancy,
        recent_agent_logs=recent_agent_logs
    )


@admin_bp.route('/users', methods=['GET'])
@admin_required
def users():
    role_filter = request.args.get('role', 'all')
    query = User.query
    if role_filter and role_filter != 'all':
        query = query.filter_by(role=role_filter)
    users = query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users, role_filter=role_filter)


@admin_bp.route('/users/create', methods=['POST'])
@admin_required
def create_user():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    role = request.form.get('role', '')
    password = request.form.get('password', '')

    if not all([name, email, role, password]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('admin.users'))

    if User.query.filter_by(email=email).first():
        flash('Email already in use.', 'danger')
        return redirect(url_for('admin.users'))

    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    user = User(name=name, email=email, role=role, password_hash=hashed)
    db.session.add(user)
    db.session.commit()

    flash(f'User {name} created successfully.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/toggle/<user_id>', methods=['POST'])
@admin_required
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'warning')
        return redirect(url_for('admin.users'))
    user.active = not user.active
    db.session.commit()
    flash(f'User {"activated" if user.active else "deactivated"}.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/labs', methods=['GET'])
@admin_required
def labs():
    labs = Laboratory.query.order_by(Laboratory.name).all()
    occupancy = {lab.id: monitoring_agent.get_lab_occupancy(lab.id) for lab in labs}
    return render_template('admin/labs.html', labs=labs, occupancy=occupancy)


@admin_bp.route('/labs/create', methods=['POST'])
@admin_required
def create_lab():
    name = request.form.get('name', '').strip()
    location = request.form.get('location', '').strip()
    capacity = request.form.get('capacity', 0, type=int)

    if not all([name, location, capacity]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('admin.labs'))

    lab = Laboratory(name=name, location=location, capacity=capacity)
    db.session.add(lab)
    db.session.flush()

    for i in range(1, capacity + 1):
        seat = Seat(
            lab_id=lab.id,
            seat_number=str(i).zfill(2),
            status='available',
            has_power=(i % 2 == 0),
            has_network=(i % 3 == 0)
        )
        db.session.add(seat)

    db.session.commit()
    flash(f'Lab "{name}" created with {capacity} seats.', 'success')
    return redirect(url_for('admin.labs'))


@admin_bp.route('/labs/toggle/<lab_id>', methods=['POST'])
@admin_required
def toggle_lab(lab_id):
    lab = Laboratory.query.get_or_404(lab_id)
    lab.status = 'inactive' if lab.status == 'active' else 'active'
    db.session.commit()
    flash(f'Lab status set to {lab.status}.', 'success')
    return redirect(url_for('admin.labs'))


@admin_bp.route('/labs/<lab_id>/seats')
@admin_required
def lab_seats(lab_id):
    lab = Laboratory.query.get_or_404(lab_id)
    seats = Seat.query.filter_by(lab_id=lab_id).order_by(Seat.seat_number).all()
    return render_template('admin/lab_seats.html', lab=lab, seats=seats)


@admin_bp.route('/labs/<lab_id>/seats/add', methods=['POST'])
@admin_required
def add_seats(lab_id):
    lab = Laboratory.query.get_or_404(lab_id)
    seat_count = request.form.get('seat_count', 0, type=int)

    if seat_count < 1:
        flash('Enter a valid seat count.', 'danger')
        return redirect(url_for('admin.lab_seats', lab_id=lab_id))

    existing = Seat.query.filter_by(lab_id=lab_id).count()
    for i in range(existing + 1, existing + seat_count + 1):
        seat = Seat(
            lab_id=lab_id,
            seat_number=str(i).zfill(2),
            status='available',
            has_power=(i % 2 == 0),
            has_network=(i % 3 == 0)
        )
        db.session.add(seat)

    lab.capacity = existing + seat_count
    db.session.commit()
    flash(f'{seat_count} seats added.', 'success')
    return redirect(url_for('admin.lab_seats', lab_id=lab_id))


@admin_bp.route('/seats/update', methods=['POST'])
@admin_required
def update_seat_status():
    seat_id = request.form.get('seat_id')
    status = request.form.get('status')

    if not all([seat_id, status]):
        flash('Invalid request.', 'danger')
        return redirect(url_for('admin.labs'))

    monitoring_agent.update_seat_status(seat_id, status)
    flash('Seat status updated.', 'success')

    seat = Seat.query.get(seat_id)
    return redirect(url_for('admin.lab_seats', lab_id=seat.lab_id if seat else ''))


@admin_bp.route('/schedules', methods=['GET'])
@admin_required
def schedules():
    schedules = Schedule.query.order_by(Schedule.day_of_week, Schedule.start_time).all()
    labs = Laboratory.query.filter_by(status='active').all()
    lecturers = User.query.filter_by(role='lecturer', active=True).all()
    return render_template('admin/schedules.html',
        schedules=schedules,
        labs=labs,
        lecturers=lecturers
    )


@admin_bp.route('/schedules/create', methods=['POST'])
@admin_required
def create_schedule():
    from datetime import time as dtime
    course_name = request.form.get('course_name', '').strip()
    lab_id = request.form.get('lab_id')
    lecturer_id = request.form.get('lecturer_id')
    day_of_week = request.form.get('day_of_week', type=int)
    start_str = request.form.get('start_time')
    end_str = request.form.get('end_time')

    if not all([course_name, lab_id, lecturer_id, start_str, end_str]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('admin.schedules'))

    try:
        start_parts = start_str.split(':')
        end_parts = end_str.split(':')
        start_time = dtime(int(start_parts[0]), int(start_parts[1]))
        end_time = dtime(int(end_parts[0]), int(end_parts[1]))
    except (ValueError, IndexError):
        flash('Invalid time format.', 'danger')
        return redirect(url_for('admin.schedules'))

    conflict_result = decision_agent.resolve_schedule_conflict(
        lab_id, day_of_week, start_time, end_time, {}
    )

    if conflict_result['has_conflict']:
        flash(
            f'Schedule conflict detected with: {", ".join(conflict_result["conflicts"])}. '
            f'Resolution: {conflict_result["resolution"]["method"]}.',
            'warning'
        )

    schedule = Schedule(
        course_name=course_name,
        lab_id=lab_id,
        lecturer_id=lecturer_id,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time
    )
    db.session.add(schedule)
    db.session.commit()

    flash(f'Schedule for "{course_name}" created.', 'success')
    return redirect(url_for('admin.schedules'))


@admin_bp.route('/schedules/toggle/<schedule_id>', methods=['POST'])
@admin_required
def toggle_schedule(schedule_id):
    schedule = Schedule.query.get_or_404(schedule_id)
    schedule.active = not schedule.active
    db.session.commit()
    flash(f'Schedule {"activated" if schedule.active else "deactivated"}.', 'success')
    return redirect(url_for('admin.schedules'))


@admin_bp.route('/bookings')
@admin_required
def bookings():
    labs = Laboratory.query.all()
    filters = {
        'lab_id': request.args.get('lab_id'),
        'status': request.args.get('status'),
        'date': request.args.get('date')
    }

    query = Booking.query

    if filters['lab_id']:
        query = query.join(Seat).filter(Seat.lab_id == filters['lab_id'])
    if filters['status']:
        query = query.filter(Booking.status == filters['status'])
    if filters['date']:
        try:
            d = date.fromisoformat(filters['date'])
            query = query.filter(db.func.date(Booking.start_time) == d)
        except ValueError:
            pass

    bookings = query.order_by(Booking.created_at.desc()).limit(200).all()

    return render_template('admin/bookings.html',
        bookings=bookings,
        labs=labs,
        filters=filters
    )


@admin_bp.route('/agent-logs')
@admin_required
def agent_logs():
    filters = {
        'agent_name': request.args.get('agent_name', ''),
        'decision': request.args.get('decision', '')
    }
    page = request.args.get('page', 1, type=int)
    per_page = 50

    query = AgentLog.query

    if filters['agent_name']:
        query = query.filter_by(agent_name=filters['agent_name'])
    if filters['decision']:
        query = query.filter_by(decision=filters['decision'])

    total = query.count()
    logs = query.order_by(AgentLog.timestamp.desc())\
        .offset((page - 1) * per_page).limit(per_page).all()

    total_pages = (total + per_page - 1) // per_page

    return render_template('admin/agent_logs.html',
        logs=logs,
        filters=filters,
        current_page=page,
        total_pages=total_pages
    )


@admin_bp.route('/reports')
@admin_required
def reports():
    tab = request.args.get('tab', 'attendance')
    labs = Laboratory.query.all()
    occupancy = {lab.id: monitoring_agent.get_lab_occupancy(lab.id) for lab in labs}

    attendance_stats = {
        'present': Attendance.query.filter_by(status='present').count(),
        'absent': Attendance.query.filter_by(status='absent').count(),
        'anomaly': Attendance.query.filter_by(status='anomaly').count(),
        'rate': 0
    }
    total_att = attendance_stats['present'] + attendance_stats['absent'] + attendance_stats['anomaly']
    if total_att > 0:
        attendance_stats['rate'] = round(attendance_stats['present'] / total_att * 100)

    attendance_by_course = []
    schedules = Schedule.query.filter_by(active=True).all()
    for sched in schedules:
        sessions = Session.query.filter_by(schedule_id=sched.id).all()
        session_ids = [s.id for s in sessions]
        if not session_ids:
            continue
        present = Attendance.query.filter(
            Attendance.session_id.in_(session_ids),
            Attendance.status == 'present'
        ).count()
        total = Attendance.query.filter(
            Attendance.session_id.in_(session_ids)
        ).count()
        attendance_by_course.append({
            'course_name': sched.course_name,
            'lab_name': sched.laboratory.name,
            'sessions': len(sessions),
            'present': present,
            'absent': total - present,
            'rate': round(present / total * 100) if total > 0 else 0
        })

    booking_stats = {
        'total': Booking.query.count(),
        'approved': Booking.query.filter_by(status='approved').count(),
        'rejected': Booking.query.filter_by(status='rejected').count(),
        'rejection_rate': 0
    }
    if booking_stats['total'] > 0:
        booking_stats['rejection_rate'] = round(
            booking_stats['rejected'] / booking_stats['total'] * 100
        )

    booking_by_lab = []
    for lab in labs:
        total = Booking.query.join(Seat).filter(Seat.lab_id == lab.id).count()
        approved = Booking.query.join(Seat).filter(
            Seat.lab_id == lab.id, Booking.status == 'approved'
        ).count()
        rejected = Booking.query.join(Seat).filter(
            Seat.lab_id == lab.id, Booking.status == 'rejected'
        ).count()
        booking_by_lab.append({
            'lab_name': lab.name,
            'total': total,
            'approved': approved,
            'rejected': rejected
        })

    return render_template('admin/reports.html',
        tab=tab,
        labs=labs,
        occupancy=occupancy,
        attendance_stats=attendance_stats,
        attendance_by_course=attendance_by_course,
        booking_stats=booking_stats,
        booking_by_lab=booking_by_lab,
        ai_insights=None
    )


@admin_bp.route('/notifications/send', methods=['GET', 'POST'])
@admin_required
def send_notification():
    if request.method == 'POST':
        target_role = request.form.get('target_role', 'all')
        message = request.form.get('message', '').strip()
        notif_type = request.form.get('type', 'info')

        if not message:
            flash('Message cannot be empty.', 'danger')
            return redirect(url_for('admin.send_notification'))

        query = User.query.filter_by(active=True)
        if target_role != 'all':
            query = query.filter_by(role=target_role)

        users = query.all()
        for user in users:
            notif = Notification(
                user_id=user.id,
                message=message,
                type=notif_type
            )
            db.session.add(notif)

        db.session.commit()
        flash(f'Notification sent to {len(users)} users.', 'success')
        return redirect(url_for('admin.send_notification'))

    recent_notifications = Notification.query\
        .order_by(Notification.created_at.desc()).limit(20).all()

    return render_template('admin/send_notification.html',
        recent_notifications=recent_notifications
    )
