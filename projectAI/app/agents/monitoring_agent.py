from datetime import datetime
from app.extensions import db, socketio
from app.models import Seat, Laboratory, AgentLog
from app.services.event_bus import event_bus


class MonitoringAgent:
    VERSION = '1.0'
    NAME = 'MonitoringAgent'

    def _log(self, event_type, input_summary, decision, reason):
        try:
            log = AgentLog(
                agent_name=self.NAME,
                event_type=event_type,
                input_summary=input_summary,
                decision=decision,
                reason=reason,
                agent_version=self.VERSION
            )
            db.session.add(log)
            db.session.commit()
        except Exception:
            db.session.rollback()

    def update_seat_status(self, seat_id, new_status):
        seat = Seat.query.get(seat_id)
        if not seat:
            return False

        old_status = seat.status
        if old_status == new_status:
            return True

        seat.status = new_status
        seat.updated_at = datetime.utcnow()

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return False

        self._log(
            'seat.update',
            f'seat={seat_id}',
            'UPDATED',
            f'{old_status} → {new_status}'
        )

        socketio.emit('seat_state_changed', {
            'seat_id': seat_id,
            'lab_id': seat.lab_id,
            'old_status': old_status,
            'new_status': new_status,
            'timestamp': datetime.utcnow().isoformat()
        }, room=f'lab_{seat.lab_id}')

        return True

    def get_lab_occupancy(self, lab_id):
        seats = Seat.query.filter_by(lab_id=lab_id).all()
        total = len(seats)
        available = sum(1 for s in seats if s.status == 'available')
        reserved = sum(1 for s in seats if s.status == 'reserved')
        occupied = sum(1 for s in seats if s.status == 'occupied')
        faulty = sum(1 for s in seats if s.status == 'faulty')
        return {
            'total': total,
            'available': available,
            'reserved': reserved,
            'occupied': occupied,
            'faulty': faulty
        }

    def get_all_occupancy(self):
        labs = Laboratory.query.filter_by(status='active').all()
        result = {}
        for lab in labs:
            result[lab.id] = self.get_lab_occupancy(lab.id)
        return result

    def subscribe_to_events(self):
        def on_booking_approved(payload):
            seat_id = payload.get('seat_id')
            if seat_id:
                self.update_seat_status(seat_id, 'reserved')

        def on_session_closed(payload):
            pass

        event_bus.subscribe('booking.approved', on_booking_approved)
        event_bus.subscribe('session.closed', on_session_closed)


monitoring_agent = MonitoringAgent()
