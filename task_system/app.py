import os
from datetime import datetime
from flask import Flask, render_template, request, session, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "classroom-task-secret-key")
socketio = SocketIO(app, cors_allowed_origins="*")

TEACHER_PASSWORD = os.environ.get("TEACHER_PASSWORD", "admin123")

current_task = {"title": "", "active": False}
submissions = []  # [{"name": ..., "time": ..., "rank": ...}, ...]
cute_animals = [
    "🐱", "🐶", "🐰", "🦊", "🐼", "🐨", "🦁", "🐯", "🐸", "🐧",
    "🦄", "🐙", "🦋", "🐝", "🐬", "🦉", "🐳", "🦖", "🐹", "🐻",
    "🦝", "🦦", "🐿️", "🦜", "🐢", "🦩", "🐞", "🦔", "🦚", "🐲",
]


@app.route("/")
def index():
    return render_template("home.html")


# ---- Display page (for projector) ----
@app.route("/display")
def display():
    return render_template("display.html", task=current_task, submissions=submissions)


# ---- Student submit page ----
@app.route("/submit")
def submit_page():
    return render_template("submit.html", task=current_task)


# ---- Teacher control panel ----
@app.route("/teacher", methods=["GET", "POST"])
def teacher():
    if not session.get("is_teacher"):
        if request.method == "POST" and request.form.get("password") == TEACHER_PASSWORD:
            session["is_teacher"] = True
        else:
            return render_template("teacher_login.html")
    return render_template("teacher.html", task=current_task, submissions=submissions)


@app.route("/teacher/logout")
def teacher_logout():
    session.clear()
    return redirect(url_for("index"))


# ---- SocketIO events ----
@socketio.on("set_task")
def handle_set_task(data):
    global current_task, submissions
    current_task["title"] = data.get("title", "")
    current_task["active"] = True
    submissions = []
    emit("task_updated", {"title": current_task["title"], "active": True}, broadcast=True)
    emit("submissions_cleared", broadcast=True)


@socketio.on("close_task")
def handle_close_task():
    current_task["active"] = False
    emit("task_updated", {"title": current_task["title"], "active": False}, broadcast=True)


@socketio.on("clear_submissions")
def handle_clear():
    global submissions
    submissions = []
    emit("submissions_cleared", broadcast=True)


@socketio.on("student_submit")
def handle_submit(data):
    name = data.get("name", "").strip()
    if not name or not current_task["active"]:
        emit("submit_result", {"ok": False, "msg": "任务未开放或姓名为空"})
        return

    for s in submissions:
        if s["name"] == name:
            emit("submit_result", {"ok": False, "msg": "你已经提交过了"})
            return

    rank = len(submissions) + 1
    animal = cute_animals[(rank - 1) % len(cute_animals)]
    entry = {
        "name": name,
        "time": datetime.now().strftime("%H:%M:%S"),
        "rank": rank,
        "animal": animal,
    }
    submissions.append(entry)

    emit("submit_result", {"ok": True, "rank": rank, "animal": animal})
    emit("new_submission", entry, broadcast=True)


@socketio.on("toggle_music")
def handle_toggle_music():
    emit("music_toggle", broadcast=True)


@socketio.on("switch_music")
def handle_switch_music(data):
    track = data.get("track", 0)
    emit("music_switch", {"track": track}, broadcast=True)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True)
