from app import create_app
from app.extensions import socketio

app = create_app()
@app.route("/")
def home():
    return render_template("index.html")

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, use_reloader=False)