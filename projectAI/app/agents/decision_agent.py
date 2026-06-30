from datetime import datetime
from app.extensions import db
from app.models import AgentLog, Notification, User
from app.services.event_bus import event_bus


class DecisionAgent:
    VERSION = '1.0'
    NAME = 'DecisionAgent'

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

    def _notify_admins(self, message):
        try:
            admins = User.query.filter_by(role='admin', active=True).all()
            for admin in admins:
                notif = Notification(
                    user_id=admin.id,
                    message=message,
                    type='info'
                )
                db.session.add(notif)
            db.session.commit()
        except Exception:
            db.session.rollback()

    def assess_severity(self, context):
        event_type = context.get('event_type', '')
        reason = context.get('reason', '')

        if event_type in ('booking.double_conflict', 'data.inconsistency', 'resource.contention'):
            return 'HIGH'

        if event_type in ('scheduling.overlap', 'attendance.anomaly', 'seat.state_conflict'):
            return 'MEDIUM'

        return 'LOW'

    def handle_conflict(self, event_type, context_dict):
        context_dict['event_type'] = event_type
        severity = self.assess_severity(context_dict)
        input_summary = str(context_dict)[:500]

        if severity == 'LOW':
            resolution = f'Auto-resolved: {event_type}'
            self._log(event_type, input_summary, 'RESOLVED', f'[LOW] {resolution}')
            return {'resolved': True, 'method': 'autonomous', 'severity': severity}

        elif severity == 'MEDIUM':
            resolution = f'Auto-resolved with admin notification: {event_type}'
            self._log(event_type, input_summary, 'RESOLVED', f'[MEDIUM] {resolution}')
            self._notify_admins(f'[Agent Alert] {event_type}: {context_dict.get("reason", "Conflict detected")}')
            return {'resolved': True, 'method': 'autonomous_with_notification', 'severity': severity}

        else:
            self._log(event_type, input_summary, 'ESCALATE', f'[HIGH] Requires human intervention: {event_type}')
            self._notify_admins(
                f'[ESCALATION REQUIRED] {event_type}: {context_dict.get("reason", "High-severity conflict detected")} — manual resolution required.'
            )
            return {'resolved': False, 'method': 'escalated', 'severity': severity}

    def resolve_schedule_conflict(self, lab_id, day_of_week, start_time, end_time, new_schedule_data):
        from app.models import Schedule
        conflicts = Schedule.query.filter_by(
            lab_id=lab_id,
            day_of_week=day_of_week,
            active=True
        ).filter(
            Schedule.start_time < end_time,
            Schedule.end_time > start_time
        ).all()

        if not conflicts:
            return {'has_conflict': False}

        conflict_names = [c.course_name for c in conflicts]

        result = self.handle_conflict('scheduling.overlap', {
            'lab_id': lab_id,
            'day': day_of_week,
            'conflicts': conflict_names,
            'reason': f'Schedule overlaps with: {", ".join(conflict_names)}'
        })

        return {
            'has_conflict': True,
            'conflicts': conflict_names,
            'resolution': result
        }

    def subscribe_to_all_events(self):
        def handle_anomaly(payload):
            self.handle_conflict('attendance.anomaly', {
                'session_id': payload.get('session_id'),
                'user_id': payload.get('user_id'),
                'reason': payload.get('flag', 'Attendance anomaly detected')
            })

        event_bus.subscribe('attendance.anomaly', handle_anomaly)


decision_agent = DecisionAgent()
