from datetime import datetime, timedelta
from app.extensions import db
from app.models import Seat, Booking, Laboratory, AgentLog


class RecommendationAgent:
    VERSION = '1.0'
    NAME = 'RecommendationAgent'

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
        db.session.commit()

    def _score_seat(self, seat, start_time, end_time):
        score = 0
        reasons = []

        if seat.has_power:
            score += 2
            reasons.append('power outlet')

        if seat.has_network:
            score += 2
            reasons.append('network port')

        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_faults = Booking.query.join(Seat).filter(
            Seat.id == seat.id,
            Booking.status == 'rejected'
        ).count()

        if recent_faults == 0:
            score += 1
            reasons.append('no recent faults')

        recent_bookings = Booking.query.filter(
            Booking.seat_id == seat.id,
            Booking.status == 'completed',
            Booking.created_at > thirty_days_ago
        ).count()

        all_bookings = Booking.query.filter(
            Booking.status == 'completed',
            Booking.created_at > thirty_days_ago
        ).count()

        avg = all_bookings / max(Seat.query.count(), 1)
        if recent_bookings < avg * 0.9:
            score += 1
            reasons.append('low utilisation')

        return score, ', '.join(reasons) if reasons else 'standard seat'

    def recommend_seats(self, lab_id, start_time, end_time, count=5):
        available_seats = Seat.query.filter_by(lab_id=lab_id, status='available').all()

        if not available_seats:
            return []

        booked_ids = {
            b.seat_id for b in Booking.query.filter(
                Booking.status.in_(['approved', 'pending']),
                Booking.start_time < end_time,
                Booking.end_time > start_time
            ).all()
        }

        candidates = [s for s in available_seats if s.id not in booked_ids]

        scored = []
        for seat in candidates:
            score, reason = self._score_seat(seat, start_time, end_time)
            scored.append({
                'seat_id': seat.id,
                'seat_number': seat.seat_number,
                'score': score,
                'reason': f'Score {score}: {reason}'
            })

        scored.sort(key=lambda x: x['score'], reverse=True)
        result = scored[:count]

        self._log(
            'seat.recommend',
            f'lab={lab_id}',
            'RANKED',
            f'Returned {len(result)} recommendations'
        )

        return result

    def recommend_lab(self, cohort_size, day_of_week, start_time, end_time):
        from app.models import Schedule
        labs = Laboratory.query.filter_by(status='active').all()

        scored = []
        for lab in labs:
            score = 0
            reasons = []

            if lab.capacity >= cohort_size:
                fill_rate = cohort_size / lab.capacity
                if fill_rate <= 0.9:
                    score += 3
                    reasons.append(f'good capacity fit ({int(fill_rate*100)}% fill)')
                else:
                    score += 1
                    reasons.append('near capacity')
            else:
                continue

            operational = lab.equipment.filter_by(status='operational').count()
            total_eq = lab.equipment.count()
            if total_eq > 0 and operational / total_eq >= 0.9:
                score += 2
                reasons.append('equipment in good shape')

            conflict = Schedule.query.filter_by(
                lab_id=lab.id,
                day_of_week=day_of_week,
                active=True
            ).filter(
                Schedule.start_time < end_time,
                Schedule.end_time > start_time
            ).first()

            if not conflict:
                score += 2
                reasons.append('no schedule conflict')

            scored.append({
                'lab_id': lab.id,
                'name': lab.name,
                'score': score,
                'reason': '; '.join(reasons)
            })

        scored.sort(key=lambda x: x['score'], reverse=True)

        self._log(
            'lab.recommend',
            f'cohort={cohort_size} day={day_of_week}',
            'RANKED',
            f'Returned {len(scored)} lab recommendations'
        )

        return scored


recommendation_agent = RecommendationAgent()
