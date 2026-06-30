import uuid
from datetime import datetime
from flask import current_app
import anthropic

_conversation_store = {}


class ClaudeService:

    def _get_system_prompt(self, user, db):
        from app.models import Laboratory, Booking, Schedule, Session

        role = user.role
        now = datetime.utcnow()

        labs = Laboratory.query.filter_by(status='active').all()
        lab_summary = []
        for lab in labs:
            available = lab.seats.filter_by(status='available').count()
            total = lab.seats.count()
            lab_summary.append(f"{lab.name}: {available}/{total} seats available")

        active_bookings = Booking.query.filter_by(
            user_id=user.id, status='approved'
        ).filter(Booking.end_time > now).all()
        booking_summary = [
            f"{b.seat.laboratory.name} Seat {b.seat.seat_number} — {b.start_time.strftime('%d %b %H:%M')} to {b.end_time.strftime('%H:%M')}"
            for b in active_bookings
        ]

        today_dow = now.weekday()
        todays_schedules = Schedule.query.filter_by(day_of_week=today_dow, active=True).all()
        sched_summary = [
            f"{s.course_name} in {s.laboratory.name} at {s.start_time.strftime('%H:%M')}"
            for s in todays_schedules
        ]

        prompt = f"""You are the AIDLMS AI assistant for a university computer science laboratory management system.

User: {user.name} | Role: {role} | Time: {now.strftime('%A %d %B %Y, %H:%M')}

CURRENT LAB OCCUPANCY:
{chr(10).join(lab_summary) if lab_summary else 'No active labs'}

USER'S ACTIVE BOOKINGS:
{chr(10).join(booking_summary) if booking_summary else 'No active bookings'}

TODAY'S SCHEDULED SESSIONS:
{chr(10).join(sched_summary) if sched_summary else 'No sessions today'}

Answer questions about lab availability, bookings, schedules, and attendance. Be concise and helpful.
Direct the user to the correct page for actions you cannot perform directly.
Do not make up data — use only what is provided above."""

        return prompt

    def chat(self, user, message: str, context_id: str, db=None):
        if not context_id:
            context_id = str(uuid.uuid4())

        if context_id not in _conversation_store:
            _conversation_store[context_id] = []

        history = _conversation_store[context_id]
        history.append({'role': 'user', 'content': message})

        if len(history) > 20:
            history = history[-20:]
            _conversation_store[context_id] = history

        try:
            api_key = current_app.config.get('ANTHROPIC_API_KEY', '')
            if not api_key:
                return {'response': 'AI assistant is not configured. Please set CLAUDE_API_KEY.', 'context_id': context_id}

            client = anthropic.Anthropic(api_key=api_key)

            system_prompt = self._get_system_prompt(user, db)

            response = client.messages.create(
                model='claude-sonnet-4-20250514',
                max_tokens=1000,
                system=system_prompt,
                messages=history
            )

            reply = response.content[0].text
            history.append({'role': 'assistant', 'content': reply})

            if db:
                from app.models import ChatLog
                log = ChatLog(
                    user_id=user.id,
                    message=message,
                    response=reply,
                    context_id=context_id
                )
                db.session.add(log)
                db.session.commit()

            return {'response': reply, 'context_id': context_id}

        except anthropic.APIError as e:
            return {'response': f'AI service error: {str(e)}', 'context_id': context_id}
        except Exception as e:
            return {'response': 'Unable to reach AI service. Please try again.', 'context_id': context_id}
