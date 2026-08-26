import os
from datetime import datetime, date, time as dtime

from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from flask_cors import CORS

from models import (
    db, Nursery, SchoolClass, Teacher, Parent, Child, ParentChild,
    DailyLog, AttendanceRecord, Payment, Message, PushSubscription
)
from pywebpush import webpush, WebPushException
import json as json_lib

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

db_url = os.environ.get("DATABASE_URL", "sqlite:///nursery.db")
# Render's Postgres URLs start with "postgres://"; SQLAlchemy needs "postgresql://"
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_CLAIMS = {"sub": os.environ.get("VAPID_CONTACT_EMAIL", "mailto:admin@example.com")}

# Needed so the browser-based frontend (a different origin) can send the
# session cookie back on each request once this is deployed.
app.config["SESSION_COOKIE_SAMESITE"] = "None"
app.config["SESSION_COOKIE_SECURE"] = True

db.init_app(app)

# Allow the mobile web app (served from a different domain, e.g. claude.ai
# artifacts or your own frontend host) to call this API with cookies.
CORS(app, supports_credentials=True, origins=os.environ.get("ALLOWED_ORIGIN", "*"))

login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    kind, raw_id = user_id.split(":")
    if kind == "teacher":
        return Teacher.query.get(int(raw_id))
    if kind == "parent":
        return Parent.query.get(int(raw_id))
    return None


def current_role():
    if not current_user.is_authenticated:
        return None
    return "teacher" if isinstance(current_user, Teacher) else "parent"


def child_belongs_to_parent(child_id, parent_id):
    return ParentChild.query.filter_by(child_id=child_id, parent_id=parent_id).first() is not None


def notify_child_parents(child_id, title, body):
    """Sends a Web Push notification to every parent linked to this child."""
    if not VAPID_PRIVATE_KEY:
        return  # push not configured yet

    links = ParentChild.query.filter_by(child_id=child_id).all()
    parent_ids = [l.parent_id for l in links]
    subs = PushSubscription.query.filter(PushSubscription.parent_id.in_(parent_ids)).all()

    for sub in subs:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=json_lib.dumps({"title": title, "body": body}),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims=dict(VAPID_CLAIMS),
            )
        except WebPushException:
            # subscription likely expired/revoked — remove it
            db.session.delete(sub)
    db.session.commit()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.route("/api/auth/login", methods=["POST"])
def api_login():
    """
    Body: { "role": "parent" | "teacher", "phone": "...", "password": "..." }
    """
    data = request.get_json(force=True)
    role = data.get("role")
    phone = data.get("phone", "").strip()
    password = data.get("password", "")

    model = Teacher if role == "teacher" else Parent
    user = model.query.filter_by(phone=phone).first()

    if not user or not user.check_password(password):
        return jsonify({"error": "رقم الهاتف أو كلمة المرور غير صحيحة"}), 401

    login_user(user)
    return jsonify({"ok": True, "role": role, "name": user.name, "id": user.id})


@app.route("/api/auth/logout", methods=["POST"])
@login_required
def api_logout():
    logout_user()
    return jsonify({"ok": True})


@app.route("/api/auth/me")
def api_me():
    if not current_user.is_authenticated:
        return jsonify({"authenticated": False})
    return jsonify({
        "authenticated": True,
        "role": current_role(),
        "id": current_user.id,
        "name": current_user.name,
    })


# ---------------------------------------------------------------------------
# Parent-facing API (consumed by the mobile web app)
# ---------------------------------------------------------------------------

@app.route("/api/parent/children")
@login_required
def parent_children():
    if current_role() != "parent":
        return jsonify({"error": "غير مصرح"}), 403

    links = ParentChild.query.filter_by(parent_id=current_user.id).all()
    children = []
    for link in links:
        c = Child.query.get(link.child_id)
        children.append({
            "id": c.id,
            "name": c.name,
            "class_name": c.school_class.name,
            "photo_url": c.photo_url,
        })
    return jsonify(children)


@app.route("/api/child/<int:child_id>/today")
@login_required
def child_today(child_id):
    if current_role() == "parent" and not child_belongs_to_parent(child_id, current_user.id):
        return jsonify({"error": "غير مصرح"}), 403

    log = DailyLog.query.filter_by(child_id=child_id, date=date.today()).first()
    if not log:
        return jsonify({"exists": False})

    return jsonify({
        "exists": True,
        "date": log.date.isoformat(),
        "arrival_time": log.arrival_time.isoformat() if log.arrival_time else None,
        "departure_time": log.departure_time.isoformat() if log.departure_time else None,
        "meal_status": log.meal_status,
        "nap_minutes": log.nap_minutes,
        "mood": log.mood,
        "note": log.note,
        "photo_url": log.photo_url,
    })


@app.route("/api/child/<int:child_id>/logs")
@login_required
def child_logs(child_id):
    """History of daily logs, most recent first. ?limit=30"""
    if current_role() == "parent" and not child_belongs_to_parent(child_id, current_user.id):
        return jsonify({"error": "غير مصرح"}), 403

    limit = int(request.args.get("limit", 30))
    logs = (DailyLog.query.filter_by(child_id=child_id)
            .order_by(DailyLog.date.desc()).limit(limit).all())

    return jsonify([{
        "date": l.date.isoformat(),
        "meal_status": l.meal_status,
        "nap_minutes": l.nap_minutes,
        "mood": l.mood,
        "note": l.note,
        "photo_url": l.photo_url,
    } for l in logs])


@app.route("/api/child/<int:child_id>/attendance")
@login_required
def child_attendance(child_id):
    """?year=2026&month=8"""
    if current_role() == "parent" and not child_belongs_to_parent(child_id, current_user.id):
        return jsonify({"error": "غير مصرح"}), 403

    year = int(request.args.get("year", date.today().year))
    month = int(request.args.get("month", date.today().month))

    records = AttendanceRecord.query.filter(
        AttendanceRecord.child_id == child_id,
        db.extract("year", AttendanceRecord.date) == year,
        db.extract("month", AttendanceRecord.date) == month,
    ).all()

    return jsonify([{"date": r.date.isoformat(), "present": r.present} for r in records])


@app.route("/api/child/<int:child_id>/payments")
@login_required
def child_payments(child_id):
    if current_role() == "parent" and not child_belongs_to_parent(child_id, current_user.id):
        return jsonify({"error": "غير مصرح"}), 403

    payments = Payment.query.filter_by(child_id=child_id).order_by(
        Payment.year.desc(), Payment.month.desc()
    ).all()

    return jsonify([{
        "month": p.month, "year": p.year, "amount": str(p.amount),
        "paid": p.paid, "paid_date": p.paid_date.isoformat() if p.paid_date else None,
    } for p in payments])


@app.route("/api/child/<int:child_id>/messages", methods=["GET", "POST"])
@login_required
def child_messages(child_id):
    if current_role() == "parent" and not child_belongs_to_parent(child_id, current_user.id):
        return jsonify({"error": "غير مصرح"}), 403

    if request.method == "POST":
        data = request.get_json(force=True)
        msg = Message(
            child_id=child_id,
            sender_type=current_role(),
            sender_id=current_user.id,
            text=data.get("text", "").strip(),
        )
        db.session.add(msg)
        db.session.commit()

        if current_role() == "teacher":
            child = Child.query.get(child_id)
            notify_child_parents(child_id, f"رسالة جديدة عن {child.name}", msg.text[:100])

        return jsonify({"ok": True, "id": msg.id})

    msgs = Message.query.filter_by(child_id=child_id).order_by(Message.timestamp).all()
    return jsonify([{
        "sender_type": m.sender_type,
        "text": m.text,
        "timestamp": m.timestamp.isoformat(),
    } for m in msgs])


# ---------------------------------------------------------------------------
# Push notifications (Web Push API)
# ---------------------------------------------------------------------------

@app.route("/api/push/vapid-public-key")
def push_public_key():
    return jsonify({"publicKey": VAPID_PUBLIC_KEY})


@app.route("/api/push/subscribe", methods=["POST"])
@login_required
def push_subscribe():
    if current_role() != "parent":
        return jsonify({"error": "غير مصرح"}), 403

    data = request.get_json(force=True)
    endpoint = data.get("endpoint")
    keys = data.get("keys", {})

    existing = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if existing:
        existing.p256dh = keys.get("p256dh")
        existing.auth = keys.get("auth")
    else:
        db.session.add(PushSubscription(
            parent_id=current_user.id, endpoint=endpoint,
            p256dh=keys.get("p256dh"), auth=keys.get("auth"),
        ))
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/push/unsubscribe", methods=["POST"])
@login_required
def push_unsubscribe():
    data = request.get_json(force=True)
    PushSubscription.query.filter_by(endpoint=data.get("endpoint")).delete()
    db.session.commit()
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Teacher-facing quick-entry pages (server-rendered, built for speed on a phone)
# ---------------------------------------------------------------------------

@app.route("/teacher/login", methods=["GET", "POST"])
def teacher_login():
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        teacher = Teacher.query.filter_by(phone=phone).first()
        if teacher and teacher.check_password(password):
            login_user(teacher)
            return redirect(url_for("teacher_dashboard"))
        return render_template("teacher_login.html", error="رقم الهاتف أو كلمة المرور غير صحيحة")
    return render_template("teacher_login.html", error=None)


@app.route("/teacher")
@login_required
def teacher_dashboard():
    if current_role() != "teacher":
        return redirect(url_for("teacher_login"))
    children = Child.query.filter_by(class_id=current_user.class_id).all() if current_user.class_id else Child.query.all()

    today = date.today()
    logs_today = {l.child_id: l for l in DailyLog.query.filter_by(date=today).all()}

    return render_template("teacher_dashboard.html", children=children, logs_today=logs_today, today=today)


@app.route("/teacher/child/<int:child_id>/log", methods=["GET", "POST"])
@login_required
def teacher_child_log(child_id):
    if current_role() != "teacher":
        return redirect(url_for("teacher_login"))

    child = Child.query.get_or_404(child_id)
    today = date.today()
    log = DailyLog.query.filter_by(child_id=child_id, date=today).first()
    if not log:
        log = DailyLog(child_id=child_id, date=today, created_by_teacher_id=current_user.id)
        db.session.add(log)

    if request.method == "POST":
        log.meal_status = request.form.get("meal_status") or log.meal_status
        log.mood = request.form.get("mood") or log.mood
        note = request.form.get("note")
        if note:
            log.note = note
        nap = request.form.get("nap_minutes")
        if nap:
            log.nap_minutes = int(nap)
        log.updated_at = datetime.utcnow()
        db.session.commit()
        notify_child_parents(child_id, f"تحديث جديد لـ {child.name}", "المعلمة حدّثت يوميات طفلك — افتحي التطبيق للتفاصيل")
        return redirect(url_for("teacher_dashboard"))

    return render_template("teacher_child_log.html", child=child, log=log)


# ---------------------------------------------------------------------------
# CLI helper: seed demo data
# ---------------------------------------------------------------------------

@app.cli.command("db-init")
def db_init():
    """Creates tables without wiping existing data. Safe to run on every deploy."""
    with app.app_context():
        db.create_all()
    print("تم التأكد من وجود الجداول.")


@app.cli.command("seed")
def seed():
    """Run with: flask --app app.py seed"""
    db.drop_all()
    db.create_all()

    nursery = Nursery(name="حضانة البراعم الصغيرة")
    db.session.add(nursery)
    db.session.flush()

    school_class = SchoolClass(nursery_id=nursery.id, name="الفراشات")
    db.session.add(school_class)
    db.session.flush()

    teacher = Teacher(nursery_id=nursery.id, name="مروة أحمد", phone="01000000001", class_id=school_class.id)
    teacher.set_password("teacher123")
    db.session.add(teacher)

    parent = Parent(name="ولية أمر يوسف", phone="01000000002")
    parent.set_password("parent123")
    db.session.add(parent)
    db.session.flush()

    child = Child(class_id=school_class.id, name="يوسف أحمد")
    db.session.add(child)
    db.session.flush()

    db.session.add(ParentChild(parent_id=parent.id, child_id=child.id))

    db.session.add(DailyLog(
        child_id=child.id, date=date.today(),
        meal_status="اتاكلت كلها", nap_minutes=120, mood="😊",
        note="رسم لوحة جميلة وقال إنها هدية لماما",
        created_by_teacher_id=teacher.id,
    ))
    db.session.add(AttendanceRecord(child_id=child.id, date=date.today(), present=True))
    db.session.add(Payment(child_id=child.id, month=date.today().month, year=date.today().year, amount=2500, paid=True))

    db.session.commit()
    print("تم إنشاء بيانات تجريبية:")
    print("  معلمة: 01000000001 / teacher123")
    print("  ولية أمر: 01000000002 / parent123")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, host="0.0.0.0", port=5000)
