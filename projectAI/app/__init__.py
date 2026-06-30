from flask import redirect, url_for
from flask_login import current_user
from flask_socketio import join_room, leave_room

from config import Config
from app.extensions import db, login_manager, migrate, socketio


def create_app(config_class=Config):
    from flask import Flask
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app, async_mode=app.config.get('SOCKETIO_ASYNC_MODE', 'eventlet'), cors_allowed_origins='*')

    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please sign in to continue.'
    login_manager.login_message_category = 'warning'

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(user_id)

    from app.auth import auth_bp
    from app.student import student_bp
    from app.lecturer import lecturer_bp
    from app.admin import admin_bp
    from app.technician import technician_bp
    from app.chatbot import chatbot_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(lecturer_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(technician_bp)
    app.register_blueprint(chatbot_bp)

    @app.route('/')
    def index():
        if current_user.is_authenticated:
            return redirect(url_for(current_user.role + '.dashboard'))
        return redirect(url_for('auth.login'))

    @app.context_processor
    def inject_globals():
        from datetime import datetime
        ctx = {'now': datetime.utcnow()}
        if current_user.is_authenticated:
            from app.models import Notification
            ctx['unread_count'] = Notification.query.filter_by(
                user_id=current_user.id, read=False
            ).count()
        else:
            ctx['unread_count'] = 0
        return ctx

    @socketio.on('join')
    def on_join(data):
        room = data.get('room')
        if room:
            join_room(room)

    @socketio.on('leave')
    def on_leave(data):
        room = data.get('room')
        if room:
            leave_room(room)

    with app.app_context():
        from app.agents import monitoring_agent, decision_agent
        monitoring_agent.subscribe_to_events()
        decision_agent.subscribe_to_all_events()

    return app
