import os
import sqlite3
import uuid
import hashlib
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_from_directory, g, jsonify
)
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "task-system-secret-key-change-in-production")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "tasks.db")
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
ALLOWED_EXTENSIONS = {
    "txt", "pdf", "png", "jpg", "jpeg", "gif", "doc", "docx",
    "xls", "xlsx", "ppt", "pptx", "zip", "rar", "7z", "py",
    "java", "c", "cpp", "h", "md", "csv", "json",
}
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    db.executescript("""
    CREATE TABLE IF NOT EXISTS teacher (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        username    TEXT UNIQUE NOT NULL,
        password    TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS task (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        title       TEXT NOT NULL,
        description TEXT NOT NULL,
        created_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        deadline    TEXT,
        status      TEXT NOT NULL DEFAULT 'open'  -- open / closed
    );

    CREATE TABLE IF NOT EXISTS submission (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id     INTEGER NOT NULL REFERENCES task(id),
        student_name TEXT NOT NULL,
        content     TEXT,
        file_path   TEXT,
        file_name   TEXT,
        submitted_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
        review_status TEXT NOT NULL DEFAULT 'pending',  -- pending / approved / rejected
        review_comment TEXT
    );
    """)

    # seed a default teacher account if none exists
    cur = db.execute("SELECT COUNT(*) FROM teacher")
    if cur.fetchone()[0] == 0:
        hashed = hashlib.sha256("admin123".encode()).hexdigest()
        db.execute("INSERT INTO teacher (username, password) VALUES (?, ?)",
                   ("teacher", hashed))
    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def teacher_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_teacher"):
            flash("请先以教师身份登录", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def student_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("student_name"):
            flash("请先输入你的姓名", "warning")
            return redirect(url_for("student_login"))
        return f(*args, **kwargs)
    return decorated


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ---------------------------------------------------------------------------
# Routes – public
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Routes – teacher auth
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        hashed = hashlib.sha256(password.encode()).hexdigest()

        db = get_db()
        teacher = db.execute(
            "SELECT * FROM teacher WHERE username=? AND password=?",
            (username, hashed),
        ).fetchone()

        if teacher:
            session["is_teacher"] = True
            session["teacher_name"] = username
            flash("登录成功", "success")
            return redirect(url_for("teacher_dashboard"))
        flash("用户名或密码错误", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("已退出登录", "info")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Routes – teacher dashboard
# ---------------------------------------------------------------------------

@app.route("/teacher")
@teacher_required
def teacher_dashboard():
    db = get_db()
    tasks = db.execute("SELECT * FROM task ORDER BY created_at DESC").fetchall()
    return render_template("teacher_dashboard.html", tasks=tasks)


@app.route("/teacher/task/new", methods=["GET", "POST"])
@teacher_required
def create_task():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        deadline = request.form.get("deadline", "").strip() or None

        if not title or not description:
            flash("标题和描述不能为空", "danger")
            return redirect(url_for("create_task"))

        db = get_db()
        db.execute(
            "INSERT INTO task (title, description, deadline) VALUES (?, ?, ?)",
            (title, description, deadline),
        )
        db.commit()
        flash("任务创建成功", "success")
        return redirect(url_for("teacher_dashboard"))
    return render_template("create_task.html")


@app.route("/teacher/task/<int:task_id>/toggle", methods=["POST"])
@teacher_required
def toggle_task(task_id):
    db = get_db()
    task = db.execute("SELECT * FROM task WHERE id=?", (task_id,)).fetchone()
    if not task:
        flash("任务不存在", "danger")
        return redirect(url_for("teacher_dashboard"))
    new_status = "closed" if task["status"] == "open" else "open"
    db.execute("UPDATE task SET status=? WHERE id=?", (new_status, task_id))
    db.commit()
    flash(f"任务已{'关闭' if new_status == 'closed' else '重新开放'}", "info")
    return redirect(url_for("teacher_dashboard"))


@app.route("/teacher/task/<int:task_id>/delete", methods=["POST"])
@teacher_required
def delete_task(task_id):
    db = get_db()
    db.execute("DELETE FROM submission WHERE task_id=?", (task_id,))
    db.execute("DELETE FROM task WHERE id=?", (task_id,))
    db.commit()
    flash("任务已删除", "info")
    return redirect(url_for("teacher_dashboard"))


@app.route("/teacher/task/<int:task_id>/submissions")
@teacher_required
def view_submissions(task_id):
    db = get_db()
    task = db.execute("SELECT * FROM task WHERE id=?", (task_id,)).fetchone()
    if not task:
        flash("任务不存在", "danger")
        return redirect(url_for("teacher_dashboard"))
    submissions = db.execute(
        "SELECT * FROM submission WHERE task_id=? ORDER BY submitted_at DESC",
        (task_id,),
    ).fetchall()
    return render_template("view_submissions.html", task=task, submissions=submissions)


@app.route("/teacher/submission/<int:sub_id>/review", methods=["POST"])
@teacher_required
def review_submission(sub_id):
    status = request.form.get("review_status", "pending")
    comment = request.form.get("review_comment", "").strip()

    db = get_db()
    db.execute(
        "UPDATE submission SET review_status=?, review_comment=? WHERE id=?",
        (status, comment, sub_id),
    )
    db.commit()

    sub = db.execute("SELECT task_id FROM submission WHERE id=?", (sub_id,)).fetchone()
    flash("评审已保存", "success")
    return redirect(url_for("view_submissions", task_id=sub["task_id"]))


@app.route("/teacher/settings", methods=["GET", "POST"])
@teacher_required
def teacher_settings():
    if request.method == "POST":
        old_pw = request.form.get("old_password", "").strip()
        new_pw = request.form.get("new_password", "").strip()
        confirm_pw = request.form.get("confirm_password", "").strip()

        if new_pw != confirm_pw:
            flash("两次输入的新密码不一致", "danger")
            return redirect(url_for("teacher_settings"))

        old_hash = hashlib.sha256(old_pw.encode()).hexdigest()
        db = get_db()
        teacher = db.execute(
            "SELECT * FROM teacher WHERE username=? AND password=?",
            (session["teacher_name"], old_hash),
        ).fetchone()

        if not teacher:
            flash("旧密码不正确", "danger")
            return redirect(url_for("teacher_settings"))

        new_hash = hashlib.sha256(new_pw.encode()).hexdigest()
        db.execute("UPDATE teacher SET password=? WHERE username=?",
                   (new_hash, session["teacher_name"]))
        db.commit()
        flash("密码修改成功", "success")
        return redirect(url_for("teacher_dashboard"))

    return render_template("teacher_settings.html")


# ---------------------------------------------------------------------------
# Routes – student
# ---------------------------------------------------------------------------

@app.route("/student/login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        name = request.form.get("student_name", "").strip()
        if not name:
            flash("请输入你的姓名", "warning")
            return redirect(url_for("student_login"))
        session["student_name"] = name
        flash(f"欢迎，{name}！", "success")
        return redirect(url_for("student_tasks"))
    return render_template("student_login.html")


@app.route("/student/tasks")
@student_required
def student_tasks():
    db = get_db()
    tasks = db.execute(
        "SELECT * FROM task WHERE status='open' ORDER BY created_at DESC"
    ).fetchall()

    student_name = session["student_name"]
    submitted_ids = set()
    rows = db.execute(
        "SELECT task_id FROM submission WHERE student_name=?", (student_name,)
    ).fetchall()
    for r in rows:
        submitted_ids.add(r["task_id"])

    return render_template("student_tasks.html", tasks=tasks, submitted_ids=submitted_ids)


@app.route("/student/task/<int:task_id>/submit", methods=["GET", "POST"])
@student_required
def submit_task(task_id):
    db = get_db()
    task = db.execute("SELECT * FROM task WHERE id=?", (task_id,)).fetchone()
    if not task:
        flash("任务不存在", "danger")
        return redirect(url_for("student_tasks"))
    if task["status"] != "open":
        flash("该任务已关闭，无法提交", "warning")
        return redirect(url_for("student_tasks"))

    if request.method == "POST":
        content = request.form.get("content", "").strip()
        file = request.files.get("file")
        file_path = None
        file_name = None

        if file and file.filename and allowed_file(file.filename):
            original_name = secure_filename(file.filename)
            unique_name = f"{uuid.uuid4().hex}_{original_name}"
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
            file.save(file_path)
            file_name = original_name

        if not content and not file_path:
            flash("请填写提交内容或上传文件", "warning")
            return redirect(url_for("submit_task", task_id=task_id))

        student_name = session["student_name"]
        db.execute(
            "INSERT INTO submission (task_id, student_name, content, file_path, file_name) "
            "VALUES (?, ?, ?, ?, ?)",
            (task_id, student_name, content, file_path, file_name),
        )
        db.commit()
        flash("提交成功！", "success")
        return redirect(url_for("student_tasks"))

    return render_template("submit_task.html", task=task)


@app.route("/student/my-submissions")
@student_required
def my_submissions():
    db = get_db()
    student_name = session["student_name"]
    rows = db.execute("""
        SELECT s.*, t.title as task_title
        FROM submission s JOIN task t ON s.task_id = t.id
        WHERE s.student_name = ?
        ORDER BY s.submitted_at DESC
    """, (student_name,)).fetchall()
    return render_template("my_submissions.html", submissions=rows)


# ---------------------------------------------------------------------------
# File download
# ---------------------------------------------------------------------------

@app.route("/download/<int:sub_id>")
def download_file(sub_id):
    db = get_db()
    sub = db.execute("SELECT * FROM submission WHERE id=?", (sub_id,)).fetchone()
    if not sub or not sub["file_path"]:
        flash("文件不存在", "danger")
        return redirect(url_for("index"))
    directory = os.path.dirname(sub["file_path"])
    filename = os.path.basename(sub["file_path"])
    return send_from_directory(directory, filename, as_attachment=True,
                               download_name=sub["file_name"])


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
