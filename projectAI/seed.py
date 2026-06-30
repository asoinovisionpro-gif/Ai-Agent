import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import bcrypt
from datetime import time, date
from app import create_app
from app.extensions import db
from app.models import User, Laboratory, Seat, Equipment, Schedule


def seed():
    app = create_app()

    with app.app_context():
        db.create_all()

        def get_or_create_user(email, name, role, password):
            user = User.query.filter_by(email=email).first()
            if user:
                return user
            hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
            user = User(name=name, email=email, role=role, password_hash=hashed)
            db.session.add(user)
            db.session.flush()
            print(f'  Created user: {email}')
            return user

        print('Seeding users...')
        admin = get_or_create_user('admin@aidlms.com', 'System Admin', 'admin', 'Admin1234!')
        lecturer = get_or_create_user('lecturer@aidlms.com', 'Dr. Adaeze Okonkwo', 'lecturer', 'Lecturer1234!')
        student1 = get_or_create_user('student1@aidlms.com', 'Chukwuemeka Nwosu', 'student', 'Student1234!')
        student2 = get_or_create_user('student2@aidlms.com', 'Amaka Eze', 'student', 'Student1234!')
        tech = get_or_create_user('tech@aidlms.com', 'Biodun Adeyemi', 'technician', 'Tech1234!')

        def get_or_create_lab(name, location, capacity):
            lab = Laboratory.query.filter_by(name=name).first()
            if lab:
                return lab
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

            print(f'  Created lab: {name} with {capacity} seats')
            return lab

        print('Seeding labs...')
        lab_a = get_or_create_lab('Lab A', 'Block B, Room 101', 30)
        lab_b = get_or_create_lab('Lab B', 'Block C, Room 204', 20)

        def seed_equipment(lab, items):
            for name, eq_type in items:
                exists = Equipment.query.filter_by(lab_id=lab.id, name=name).first()
                if not exists:
                    eq = Equipment(
                        lab_id=lab.id,
                        name=name,
                        type=eq_type,
                        status='operational',
                        last_maintained=date.today()
                    )
                    db.session.add(eq)

        print('Seeding equipment...')
        seed_equipment(lab_a, [
            ('Computer #01', 'Desktop'), ('Computer #02', 'Desktop'),
            ('Computer #03', 'Desktop'), ('Computer #04', 'Desktop'),
            ('Computer #05', 'Desktop'), ('Projector A1', 'Projector')
        ])
        seed_equipment(lab_b, [
            ('Computer #01', 'Desktop'), ('Computer #02', 'Desktop'),
            ('Computer #03', 'Desktop'), ('Computer #04', 'Desktop'),
            ('Computer #05', 'Desktop'), ('Projector B1', 'Projector')
        ])

        print('Seeding schedule...')
        exists = Schedule.query.filter_by(
            course_name='CS101 Introduction to Programming',
            lab_id=lab_a.id
        ).first()
        if not exists:
            sched = Schedule(
                course_name='CS101 Introduction to Programming',
                lab_id=lab_a.id,
                lecturer_id=lecturer.id,
                day_of_week=0,
                start_time=time(9, 0),
                end_time=time(11, 0)
            )
            db.session.add(sched)
            print('  Created schedule: CS101 Monday 09:00-11:00')

        db.session.commit()
        print('\nSeed complete.')
        print('\nLogin credentials:')
        print('  admin@aidlms.com      / Admin1234!')
        print('  lecturer@aidlms.com   / Lecturer1234!')
        print('  student1@aidlms.com   / Student1234!')
        print('  student2@aidlms.com   / Student1234!')
        print('  tech@aidlms.com       / Tech1234!')


if __name__ == '__main__':
    seed()
