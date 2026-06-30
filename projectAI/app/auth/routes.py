import bcrypt
from flask import render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import User
from . import auth_bp


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(current_user.role + '.dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = User.query.filter_by(email=email).first()

        if user and user.active and bcrypt.checkpw(password.encode(), user.password_hash.encode()):
            login_user(user)
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return redirect(url_for(user.role + '.dashboard'))

        flash('Invalid email or password.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for(current_user.role + '.dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        role = request.form.get('role', '')
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')

        if not all([name, email, role, password]):
            flash('All fields are required.', 'danger')
            return render_template('auth/register.html')

        if role not in ('student', 'lecturer', 'technician'):
            flash('Invalid role selected.', 'danger')
            return render_template('auth/register.html')

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('auth/register.html')

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'danger')
            return render_template('auth/register.html')

        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        user = User(name=name, email=email, role=role, password_hash=hashed)
        db.session.add(user)
        db.session.commit()

        flash('Account created. You can now sign in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('auth.login'))
