from datetime import datetime, timedelta
from flask import current_app
from app.extensions import db
from app.models import Seat, Booking, Notification, AgentLog
from app.services.event_bus import event_bus


class BookingAgent:
    VERSION = '1.0'
    NAME = 'BookingAgent'

    def _log(self, event_type, input_summary, decision, reason):
        log = AgentLog(
            agent_name=self.NAME,
            event_type=event_type,
            input_summary=input_summary,
            decision=decision,
            reason=reason,
            agent_version=self.VERSION
        )
        db.session.add(log)

    def _notify(self, user_id, message, notif_type='booking'):
        notif = Notification(user_id=user_id, message=message, type=notif_type)
        db.session.add(notif)

    def evaluate(self, user_id, seat_id, start_time, end_time):
        input_summary = f'user={user_id} seat={seat_id} start={start_time} end={end_time}'

        seat = Seat.query.get(seat_id)
        if not seat:
            self._log('booking.evaluate', input_summary, 'REJECT', 'Seat not found')
            db.session.commit()
            return {'decision': 'REJECT', 'reason': 'Seat not found', 'booking_id': None}

        if seat.status == 'faulty':
            reason = 'Seat is currently marked as faulty'
            self._log('booking.evaluate', input_summary, 'REJECT', reason)
            self._notify(user_id, f'Booking rejected: {reason}')
            db.session.commit()
            return {'decision': 'REJECT', 'reason': reason, 'booking_id': None}

        overlapping = Booking.query.filter(
            Booking.seat_id == seat_id,
            Booking.status.in_(['approved', 'pending']),
            Booking.start_time < end_time,
            Booking.end_time > start_time
        ).first()

        if overlapping:
            reason = 'Seat already booked for this time period'
            self._log('booking.evaluate', input_summary, 'REJECT', reason)
            self._notify(user_id, f'Booking rejected: {reason}')
            db.session.commit()
            return {'decision': 'REJECT', 'reason': reason, 'booking_id': None}

        max_hours = current_app.config.get('MAX_BOOKING_DURATION_HOURS', 4)
        duration = (end_time - start_time).total_seconds() / 3600
        if duration > max_hours:
            reason = f'Booking exceeds maximum allowed duration of {max_hours} hours'
            self._log('booking.evaluate', input_summary, 'REJECT', reason)
            self._notify(user_id, f'Booking rejected: {reason}')
            db.session.commit()
            return {'decision': 'REJECT', 'reason': reason, 'booking_id': None}

        if duration <= 0:
            reason = 'End time must be after start time'
            self._log('booking.evaluate', input_summary, 'REJECT', reason)
            db.session.commit()
            return {'decision': 'REJECT', 'reason': reason, 'booking_id': None}

        daily_limit = current_app.config.get('DAILY_BOOKING_LIMIT', 2)
        booking_date = start_time.date()
        daily_count = Booking.query.filter(
            Booking.user_id == user_id,
            Booking.status == 'approved',
            db.func.date(Booking.start_time) == booking_date
        ).count()

        if daily_count >= daily_limit:
            reason = f'Daily booking limit of {daily_limit} reached for {booking_date}'
            self._log('booking.evaluate', input_summary, 'REJECT', reason)
            self._notify(user_id, f'Booking rejected: {reason}')
            db.session.commit()
            return {'decision': 'REJECT', 'reason': reason, 'booking_id': None}

        booking = Booking(
            user_id=user_id,
            seat_id=seat_id,
            start_time=start_time,
            end_time=end_time,
            status='approved',
            agent_decision='APPROVE',
            agent_reason='All validation checks passed'
        )
        db.session.add(booking)

        self._log('booking.evaluate', input_summary, 'APPROVE', 'All validation checks passed')
        self._notify(user_id, f'Booking confirmed: {seat.laboratory.name} Seat {seat.seat_number} on {start_time.strftime("%d %b %H:%M")}')

        db.session.commit()

        event_bus.publish_async('booking.approved', {
            'booking_id': booking.id,
            'seat_id': seat_id,
            'lab_id': seat.lab_id,
            'user_id': user_id,
            'start_time': start_time.isoformat(),
            'end_time': end_time.isoformat()
        })

        return {'decision': 'APPROVE', 'reason': 'All validation checks passed', 'booking_id': booking.id}


booking_agent = BookingAgent()
