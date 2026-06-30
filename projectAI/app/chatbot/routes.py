import uuid
from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.services import claude_service
from . import chatbot_bp


@chatbot_bp.route('/')
@login_required
def index():
    context_id = str(uuid.uuid4())
    return render_template('chatbot/index.html', context_id=context_id)


@chatbot_bp.route('/message', methods=['POST'])
@login_required
def message():
    data = request.get_json()
    if not data:
        return jsonify({'response': 'Invalid request.', 'context_id': ''}), 400

    user_message = data.get('message', '').strip()
    context_id = data.get('context_id', str(uuid.uuid4()))

    if not user_message:
        return jsonify({'response': 'Message cannot be empty.', 'context_id': context_id})

    result = claude_service.chat(current_user, user_message, context_id, db=db)
    return jsonify(result)
