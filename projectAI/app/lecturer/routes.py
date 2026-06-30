import csv
import io
from datetime import datetime
from functools import wraps
from flask import render_template, redirect, url_for, request, flash, make_response
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Schedule, Session, Attendance, Laboratory, User, Notification
from app.agents import attendance_agent, monitoring_agent, recommendation_agent
from . import lecturer_bp


def lecturer_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role != 'lecturer':
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return login_required(decorated)


@lecturer_bp.route('/dashboard')
@lecturer_required
def dashboard():
    now = datetime.utcnow()
    today_dow = now.weekday()

    todays_schedules = Schedule.query.filter_by(
        lecturer_id=current_user.id,
        day_of_week=today_dow,
        active=True
    ).all()

    open_sessions = Session.query.filter_by(
        lecturer_id=current_user.id,
        locked=False
    ).filter(Session.closed_at == None).all()

    total_sessions = Session.query.filter_by(lecturer_id=current_user.id).count()

    all_records = Attendance.query.join(Session).filter(
        Session.lecturer_id == current_user.id,
        Attendance.status == 'present'
    ).count()
    all_total = Attendance.query.join(Session).filter(
        Session.lecturer_id == current_user.id
    ).count()
    avg_attendance = round(all_records / all_total * 100) if all_total > 0 else 0

    return render_template('lecturer/dashboard.html',
        todays_schedules=todays_schedules,
        open_sessions=open_sessions,
        total_sessions=total_sessions,
        avg_attendance=avg_attendance,
        now=now
    )


@lecturer_bp.route('/sessions')
@lecturer_required
def sessions():
    filter_val = request.args.get('filter', 'all')

    query = Session.query.filter_by(lecturer_id=current_user.id)

    if filter_val == 'open':
        query = query.filter(Session.closed_at == None)
    elif filter_val == 'closed':
        query = query.filter(Session.closed_at != None)

    sessions = query.order_by(Session.opened_at.desc()).all()

    session_summaries = {s.id: attendance_agent.get_session_summary(s.id) for s in sessions}

    return render_template('lecturer/sessions.html',
        sessions=sessions,
        session_summaries=session_summaries,
        filter=filter_val
    )


@lecturer_bp.route('/sessions/open/<schedule_id>', methods=['POST'])
@lecturer_required
def open_session(schedule_id):
    schedule = Schedule.query.get_or_404(schedule_id)
    if schedule.lecturer_id != current_user.id:
        flash('You are not assigned to this schedule.', 'danger')
        return redirect(url_for('lecturer.dashboard'))

    session = Session(
        schedule_id=schedule_id,
        lecturer_id=current_user.id
    )
    db.session.add(session)
    db.session.commit()

    flash(f'Session opened for {schedule.course_name}.', 'success')
    return redirect(url_for('lecturer.session_attendance', session_id=session.id))


@lecturer_bp.route('/sessions/close/<session_id>', methods=['POST'])
@lecturer_required
def close_session(session_id):
    session = Session.query.get_or_404(session_id)
    if session.lecturer_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('lecturer.sessions'))

    result = attendance_agent.close_session(session_id)

    if result['success']:
        summary = result['summary']
        flash(
            f'Session closed. {summary["present"]} present, {summary["absent"]} absent, {summary["anomaly"]} anomalies.',
            'success'
        )
    else:
        flash(result.get('reason', 'Error closing session.'), 'danger')

    return redirect(url_for('lecturer.sessions'))


@lecturer_bp.route('/sessions/<session_id>/attendance')
@lecturer_required
def session_attendance(session_id):
    session = Session.query.get_or_404(session_id)
    if session.lecturer_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('lecturer.sessions'))

    records = Attendance.query.filter_by(session_id=session_id)\
        .join(User).order_by(User.name).all()

    summary = attendance_agent.get_session_summary(session_id)

    return render_template('lecturer/session_attendance.html',
        session=session,
        attendance_records=records,
        summary=summary
    )


@lecturer_bp.route('/sessions/<session_id>/checkin/<user_id>', methods=['POST'])
@lecturer_required
def manual_checkin(session_id, user_id):
    session = Session.query.get_or_404(session_id)
    if session.lecturer_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('lecturer.sessions'))

    result = attendance_agent.record_checkin(user_id, session_id)
    if result['success']:
        flash('Student marked as present.', 'success')
    else:
        flash(result.get('reason', 'Could not mark attendance.'), 'warning')

    return redirect(url_for('lecturer.session_attendance', session_id=session_id))


@lecturer_bp.route('/schedule')
@lecturer_required
def schedule():
    schedules = Schedule.query.filter_by(
        lecturer_id=current_user.id, active=True
    ).order_by(Schedule.day_of_week, Schedule.start_time).all()
    return render_template('lecturer/schedule.html', schedules=schedules)


@lecturer_bp.route('/labs')
@lecturer_required
def labs():
    labs = Laboratory.query.filter_by(status='active').all()
    occupancy = {lab.id: monitoring_agent.get_lab_occupancy(lab.id) for lab in labs}
    now = datetime.utcnow()
    recommendations = recommendation_agent.recommend_lab(20, now.weekday(), now.time(), now.time())
    return render_template('lecturer/labs.html',
        labs=labs,
        occupancy=occupancy,
        recommendations=recommendations
    )


@lecturer_bp.route('/reports/attendance/<session_id>')
@lecturer_required
def attendance_report(session_id):
    session = Session.query.get_or_404(session_id)
    if session.lecturer_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('lecturer.sessions'))

    records = Attendance.query.filter_by(session_id=session_id)\
        .join(User).order_by(User.name).all()
    summary = attendance_agent.get_session_summary(session_id)

    return render_template('lecturer/attendance_report.html',
        session=session,
        records=records,
        summary=summary
    )


@lecturer_bp.route('/reports/attendance/<session_id>/csv')
@lecturer_required
def download_attendance_csv(session_id):
    session = Session.query.get_or_404(session_id)
    if session.lecturer_id != current_user.id:
        flash('Access denied.', 'danger')
        return redirect(url_for('lecturer.sessions'))

    records = Attendance.query.filter_by(session_id=session_id)\
        .join(User).order_by(User.name).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Name', 'Email', 'Status', 'Time', 'Flag'])
    for rec in records:
        writer.writerow([
            rec.user.name,
            rec.user.email,
            rec.status,
            rec.recorded_at.strftime('%H:%M:%S'),
            rec.agent_flag or ''
        ])

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=attendance_{session_id[:8]}.csv'
    response.headers['Content-Type'] = 'text/csv'
    return response
