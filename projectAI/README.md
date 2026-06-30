## AIDLMS Backend — Setup

### Requirements
- Python 3.11+
- PostgreSQL 15+ (or SQLite for local dev)

### Quickstart

```bash
git clone <repo> && cd aidlms

python -m venv venv
source venv/bin/activate

pip install -r requirements.txt

cp .env.example .env

flask db init
flask db migrate -m "init"
flask db upgrade

python seed.py

python run.py
```

Server runs at http://localhost:5000

### Project layout

```
app/
  __init__.py          app factory
  extensions.py        db, login, migrate, socketio
  models/models.py     all SQLAlchemy models
  agents/
    booking_agent.py
    attendance_agent.py
    monitoring_agent.py
    recommendation_agent.py
    decision_agent.py
  services/
    event_bus.py       in-process pub/sub
    claude_service.py  Claude API wrapper
  auth/routes.py
  student/routes.py
  lecturer/routes.py
  admin/routes.py
  technician/routes.py
  chatbot/routes.py
config.py
run.py
seed.py
```

### Environment variables

| Variable | Default | Description |
|---|---|---|
| SECRET_KEY | — | Flask session secret |
| DATABASE_URL | sqlite:///aidlms.db | PostgreSQL or SQLite URI |
| CLAUDE_API_KEY | — | Anthropic API key |
| MAX_BOOKING_DURATION_HOURS | 4 | Booking Agent limit |
| DAILY_BOOKING_LIMIT | 2 | Booking Agent daily cap |
| SOCKETIO_ASYNC_MODE | eventlet | SocketIO async driver |
