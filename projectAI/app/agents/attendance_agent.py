from datetime import datetime
from app.extensions import db
from app.models import Session, Attendance, Schedule, User, AgentLog
from app.services.event_bus import event_bus


class AttendanceAgent:
    VERSION = '1.0'
    NAME = 'AttendanceAgent'

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

    def record_checkin(self, user_id, session_id):
        session = Session.query.get(session_id)
        if not session:
            return {'success': False, 'reason': 'Session not found'}

        if session.locked:
            return {'success': False, 'reason': 'Session is already closed and locked'}

        if session.closed_at:
            return {'success': False, 'reason': 'Session has been closed'}

        existing = Attendance.query.filter_by(
            session_id=session_id,
            user_id=user_id
        ).first()

        now = datetime.utcnow()
        input_summary = f'user={user_id} session={session_id}'

        if existing and existing.status == 'present':
            self._log('attendance.checkin', input_summary, 'SKIP', 'Duplicate check-in ignored')
            db.session.commit()
            return {'success': False, 'reason': 'Already marked as present'}

        session_open = session.opened_at
        session_close = session.closed_at

        flag = None
        status = 'present'

        if session_close and now > session_close:
            status = 'anomaly'
            flag = f'Late check-in at {now.strftime("%H:%M")} — session closed at {session_close.strftime("%H:%M")}'

        if existing:
            existing.status = status
            existing.recorded_at = now
            existing.agent_flag = flag
        else:
            record = Attendance(
                session_id=session_id,
                user_id=user_id,
                status=status,
                recorded_at=now,
                agent_flag=flag
            )
            db.session.add(record)

        self._log('attendance.checkin', input_summary, status.upper(), flag or 'On-time check-in')
        db.session.commit()

        if status == 'anomaly':
            event_bus.publish_async('attendance.anomaly', {
                'session_id': session_id,
                'user_id': user_id,
                'flag': flag
            })

        return {'success': True, 'status': status, 'flag': flag}

    def close_session(self, session_id):
        session = Session.query.get(session_id)
        if not session:
            return {'success': False, 'reason': 'Session not found'}

        if session.locked:
            return {'success': False, 'reason': 'Session already locked'}

        now = datetime.utcnow()
        session.closed_at = now

        schedule = session.schedule
        enrolled_students = User.query.filter_by(role='student', active=True).all()

        for student in enrolled_students:
            existing = Attendance.query.filter_by(
                session_id=session_id,
                user_id=student.id
            ).first()
            if not existing:
                record = Attendance(
                    session_id=session_id,
                    user_id=student.id,
                    status='absent',
                    recorded_at=now,
                    agent_flag=None
                )
                db.session.add(record)

        session.locked = True

        self._log(
            'session.close',
            f'session={session_id}',
            'LOCKED',
            f'Session closed at {now.strftime("%H:%M")}, attendance records locked'
        )

        db.session.commit()

        summary = self.get_session_summary(session_id)

        event_bus.publish_async('session.closed', {
            'session_id': session_id,
            'schedule_id': session.schedule_id,
            'summary': summary
        })

        return {'success': True, 'summary': summary}

    def get_session_summary(self, session_id):
        records = Attendance.query.filter_by(session_id=session_id).all()
        total = len(records)
        present = sum(1 for r in records if r.status == 'present')
        absent = sum(1 for r in records if r.status == 'absent')
        anomaly = sum(1 for r in records if r.status == 'anomaly')
        return {'total': total, 'present': present, 'absent': absent, 'anomaly': anomaly}


attendance_agent = AttendanceAgent()
