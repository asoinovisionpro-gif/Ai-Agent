from datetime import datetime, date
from functools import wraps
from flask import render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models import Equipment, Laboratory, Seat
from app.agents import monitoring_agent
from . import technician_bp


def technician_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if current_user.role != 'technician':
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return login_required(decorated)


@technician_bp.route('/dashboard')
@technician_required
def dashboard():
    open_faults = Equipment.query.filter_by(status='faulty').count()
    maintenance_count = Equipment.query.filter_by(status='maintenance').count()
    total_equipment = Equipment.query.count()

    week_start = datetime.utcnow().date()
    resolved_this_week = Equipment.query.filter(
        Equipment.status == 'operational',
        Equipment.last_maintained >= week_start
    ).count()

    faulty_equipment = Equipment.query.filter_by(status='faulty')\
        .order_by(Equipment.last_maintained).limit(10).all()

    labs = Laboratory.query.filter_by(status='active').all()
    equipment_by_lab = {}
    for lab in labs:
        total = lab.equipment.count()
        operational = lab.equipment.filter_by(status='operational').count()
        faulty = lab.equipment.filter_by(status='faulty').count()
        equipment_by_lab[lab.id] = {
            'total': total,
            'operational': operational,
            'faulty': faulty
        }

    return render_template('technician/dashboard.html',
        open_faults=open_faults,
        maintenance_count=maintenance_count,
        total_equipment=total_equipment,
        resolved_this_week=resolved_this_week,
        faulty_equipment=faulty_equipment,
        labs=labs,
        equipment_by_lab=equipment_by_lab
    )


@technician_bp.route('/equipment')
@technician_required
def equipment():
    labs = Laboratory.query.all()
    filters = {
        'lab_id': request.args.get('lab_id', ''),
        'status': request.args.get('status', '')
    }

    query = Equipment.query
    if filters['lab_id']:
        query = query.filter_by(lab_id=filters['lab_id'])
    if filters['status']:
        query = query.filter_by(status=filters['status'])

    equipment = query.order_by(Equipment.status, Equipment.name).all()

    return render_template('technician/equipment.html',
        equipment=equipment,
        labs=labs,
        filters=filters
    )


@technician_bp.route('/equipment/fault', methods=['POST'])
@technician_required
def log_fault():
    equipment_id = request.form.get('equipment_id')
    fault_notes = request.form.get('fault_notes', '').strip()

    if not all([equipment_id, fault_notes]):
        flash('Equipment and fault description are required.', 'danger')
        return redirect(url_for('technician.equipment'))

    eq = Equipment.query.get_or_404(equipment_id)
    eq.status = 'faulty'
    eq.fault_notes = fault_notes
    db.session.commit()

    faulty_seat = Seat.query.filter_by(lab_id=eq.lab_id, status='available').first()
    if faulty_seat:
        monitoring_agent.update_seat_status(faulty_seat.id, 'faulty')

    flash(f'Fault logged for {eq.name}.', 'warning')
    return redirect(url_for('technician.equipment'))


@technician_bp.route('/equipment/resolve/<equipment_id>', methods=['POST'])
@technician_required
def resolve_fault(equipment_id):
    eq = Equipment.query.get_or_404(equipment_id)
    eq.status = 'operational'
    eq.fault_notes = None
    eq.last_maintained = date.today()
    db.session.commit()

    flash(f'{eq.name} marked as resolved and operational.', 'success')
    return redirect(url_for('technician.equipment'))


@technician_bp.route('/equipment/add', methods=['POST'])
@technician_required
def add_equipment():
    name = request.form.get('name', '').strip()
    eq_type = request.form.get('type', '').strip()
    lab_id = request.form.get('lab_id', '')

    if not all([name, eq_type, lab_id]):
        flash('All fields are required.', 'danger')
        return redirect(url_for('technician.equipment'))

    eq = Equipment(name=name, type=eq_type, lab_id=lab_id, status='operational')
    db.session.add(eq)
    db.session.commit()

    flash(f'Equipment "{name}" added.', 'success')
    return redirect(url_for('technician.equipment'))


@technician_bp.route('/labs/status')
@technician_required
def labs_status():
    labs = Laboratory.query.filter_by(status='active').all()
    occupancy = {lab.id: monitoring_agent.get_lab_occupancy(lab.id) for lab in labs}
    seats_by_lab = {
        lab.id: Seat.query.filter_by(lab_id=lab.id).order_by(Seat.seat_number).all()
        for lab in labs
    }
    return render_template('technician/labs_status.html',
        labs=labs,
        occupancy=occupancy,
        seats_by_lab=seats_by_lab
    )
