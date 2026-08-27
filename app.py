import os
from datetime import datetime, date, time as dtime

from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from flask_cors import CORS

from models import (
    db, Nursery, SchoolClass, Teacher, Parent, Child, ParentChild,
    DailyLog, AttendanceRecord, Payment, Message, PushSubscription,
    Owner, Employee, SalaryPayment, Expense, Activity, Addon, ChildAddon,
    PaymentMethod, Advance
)
from pywebpush import webpush, WebPushException
import json as json_lib
import base64

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
    if kind == "owner":
        return Owner.query.get(int(raw_id))
    return None


def current_role():
    if not current_user.is_authenticated:
        return None
    if isinstance(current_user, Teacher):
        return "teacher"
    if isinstance(current_user, Owner):
        return "owner"
    return "parent"


def compute_child_expected_fee(child):
    addons_total = sum(float(ca.addon.monthly_fee) for ca in ChildAddon.query.filter_by(child_id=child.id).all())
    subtotal = float(child.monthly_fee) + addons_total
    if child.discount_type == "fixed":
        discount = float(child.discount_value)
    elif child.discount_type == "percent":
        discount = subtotal * float(child.discount_value) / 100
    else:
        discount = 0
    return max(subtotal - discount, 0)


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

FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://nursery-app-frontend-i3jq.onrender.com")


@app.route("/")
def index():
    return redirect(url_for("unified_login"))


@app.route("/login", methods=["GET", "POST"])
def unified_login():
    if request.method == "POST":
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        owner = Owner.query.filter_by(phone=phone).first()
        if owner and owner.check_password(password):
            login_user(owner)
            return redirect(url_for("owner_dashboard"))

        teacher = Teacher.query.filter_by(phone=phone).first()
        if teacher and teacher.check_password(password):
            login_user(teacher)
            return redirect(url_for("teacher_dashboard"))

        parent = Parent.query.filter_by(phone=phone).first()
        if parent and parent.check_password(password):
            login_user(parent)
            return redirect(FRONTEND_URL)

        return render_template("login.html", error="رقم الهاتف أو كلمة المرور غير صحيحة")

    return render_template("login.html", error=None)


@app.route("/teacher")
@login_required
def teacher_dashboard():
    if current_role() != "teacher":
        return redirect(url_for("unified_login"))
    children = Child.query.filter_by(class_id=current_user.class_id).all() if current_user.class_id else Child.query.all()

    today = date.today()
    logs_today = {l.child_id: l for l in DailyLog.query.filter_by(date=today).all()}

    return render_template("teacher_dashboard.html", children=children, logs_today=logs_today, today=today)


@app.route("/teacher/child/<int:child_id>/log", methods=["GET", "POST"])
@login_required
def teacher_child_log(child_id):
    if current_role() != "teacher":
        return redirect(url_for("unified_login"))

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
# Owner-facing pages: accounting, classes, students, activities, staff
# ---------------------------------------------------------------------------

def require_owner():
    return current_role() == "owner"


@app.route("/owner")
@login_required
def owner_dashboard():
    if not require_owner():
        return redirect(url_for("unified_login"))

    today = date.today()
    month, year = today.month, today.year

    tuition_paid = db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0)).filter(
        Payment.month == month, Payment.year == year, Payment.paid.is_(True)
    ).scalar()
    tuition_due = db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0)).filter(
        Payment.month == month, Payment.year == year, Payment.paid.is_(False)
    ).scalar()
    expenses_total = db.session.query(db.func.coalesce(db.func.sum(Expense.amount), 0)).filter(
        db.extract("month", Expense.date) == month, db.extract("year", Expense.date) == year
    ).scalar()
    salaries_total = db.session.query(db.func.coalesce(db.func.sum(SalaryPayment.amount), 0)).filter(
        SalaryPayment.month == month, SalaryPayment.year == year
    ).scalar()
    activities_cost = db.session.query(db.func.coalesce(db.func.sum(Activity.cost), 0)).filter(
        db.extract("month", Activity.date) == month, db.extract("year", Activity.date) == year
    ).scalar()

    net = float(tuition_paid) - float(expenses_total) - float(salaries_total) - float(activities_cost)

    classes_count = SchoolClass.query.count()
    students_count = Child.query.count()
    staff_count = Employee.query.filter_by(active=True).count()

    return render_template(
        "owner_dashboard.html", month=month, year=year,
        tuition_paid=tuition_paid, tuition_due=tuition_due, expenses_total=expenses_total,
        salaries_total=salaries_total, activities_cost=activities_cost, net=net,
        classes_count=classes_count, students_count=students_count, staff_count=staff_count,
    )


@app.route("/owner/classes", methods=["GET", "POST"])
@login_required
def owner_classes():
    if not require_owner():
        return redirect(url_for("unified_login"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            db.session.add(SchoolClass(nursery_id=current_user.nursery_id, name=name))
            db.session.commit()
        return redirect(url_for("owner_classes"))

    classes = SchoolClass.query.all()
    counts = {c.id: Child.query.filter_by(class_id=c.id).count() for c in classes}
    return render_template("owner_classes.html", classes=classes, counts=counts)


@app.route("/owner/classes/<int:class_id>/students", methods=["GET", "POST"])
@login_required
def owner_class_students(class_id):
    if not require_owner():
        return redirect(url_for("unified_login"))

    school_class = SchoolClass.query.get_or_404(class_id)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        birth_date = request.form.get("birth_date") or None
        subscription_type = request.form.get("subscription_type", "full_time")
        monthly_fee = request.form.get("monthly_fee") or 0
        if name:
            db.session.add(Child(
                class_id=class_id, name=name, birth_date=birth_date,
                subscription_type=subscription_type, monthly_fee=monthly_fee,
            ))
            db.session.commit()
        return redirect(url_for("owner_class_students", class_id=class_id))

    students = Child.query.filter_by(class_id=class_id).all()
    parents_by_child = {}
    addons_by_child = {}
    total_due_by_child = {}
    for s in students:
        links = ParentChild.query.filter_by(child_id=s.id).all()
        parents_by_child[s.id] = [Parent.query.get(l.parent_id) for l in links]
        child_addons = ChildAddon.query.filter_by(child_id=s.id).all()
        addons_by_child[s.id] = [ca.addon for ca in child_addons]
        total_due_by_child[s.id] = compute_child_expected_fee(s)

    return render_template(
        "owner_students.html", school_class=school_class, students=students,
        parents_by_child=parents_by_child, addons_by_child=addons_by_child,
        total_due_by_child=total_due_by_child, today=date.today(),
    )


@app.route("/owner/activities", methods=["GET", "POST"])
@login_required
def owner_activities():
    if not require_owner():
        return redirect(url_for("unified_login"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        cost = request.form.get("cost") or 0
        activity_date = request.form.get("date") or None
        notes = request.form.get("notes", "").strip()
        if name:
            db.session.add(Activity(
                nursery_id=current_user.nursery_id, name=name, cost=cost,
                date=activity_date or None, notes=notes,
            ))
            db.session.commit()
        return redirect(url_for("owner_activities"))

    activities = Activity.query.order_by(Activity.date.desc()).all()
    total_cost = sum(float(a.cost) for a in activities)
    return render_template("owner_activities.html", activities=activities, total_cost=total_cost)


@app.route("/owner/staff", methods=["GET", "POST"])
@login_required
def owner_staff():
    if not require_owner():
        return redirect(url_for("unified_login"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        role = request.form.get("role", "").strip()
        phone = request.form.get("phone", "").strip()
        salary = request.form.get("monthly_salary") or 0
        if name:
            db.session.add(Employee(
                nursery_id=current_user.nursery_id, name=name, role=role,
                phone=phone, monthly_salary=salary, hire_date=date.today(),
            ))
            db.session.commit()
        return redirect(url_for("owner_staff"))

    employees = Employee.query.filter_by(active=True).all()
    today = date.today()
    paid_status = {
        sp.employee_id: sp.paid for sp in
        SalaryPayment.query.filter_by(month=today.month, year=today.year).all()
    }
    methods = PaymentMethod.query.filter_by(active=True).all()

    advances_by_employee = {}
    for e in employees:
        outstanding = Advance.query.filter_by(employee_id=e.id, deducted=False).all()
        advances_by_employee[e.id] = {
            "items": outstanding,
            "total": sum(float(a.amount) for a in outstanding),
        }

    return render_template(
        "owner_staff.html", employees=employees, paid_status=paid_status,
        today=today, methods=methods, advances_by_employee=advances_by_employee,
    )


@app.route("/owner/staff/<int:employee_id>/pay-salary", methods=["POST"])
@login_required
def owner_pay_salary(employee_id):
    if not require_owner():
        return redirect(url_for("unified_login"))

    employee = Employee.query.get_or_404(employee_id)
    today = date.today()
    method_id = request.form.get("payment_method_id") or None

    outstanding_advances = Advance.query.filter_by(employee_id=employee_id, deducted=False).all()
    advances_total = sum(float(a.amount) for a in outstanding_advances)
    net_amount = max(float(employee.monthly_salary) - advances_total, 0)

    payment = SalaryPayment.query.filter_by(employee_id=employee_id, month=today.month, year=today.year).first()
    if not payment:
        payment = SalaryPayment(employee_id=employee_id, month=today.month, year=today.year, amount=net_amount)
        db.session.add(payment)
    payment.amount = net_amount
    payment.paid = True
    payment.paid_date = today
    payment.payment_method_id = method_id

    for adv in outstanding_advances:
        adv.deducted = True

    db.session.commit()
    return redirect(url_for("owner_staff"))


@app.route("/owner/staff/<int:employee_id>/advance", methods=["POST"])
@login_required
def owner_add_advance(employee_id):
    if not require_owner():
        return redirect(url_for("unified_login"))

    amount = request.form.get("amount")
    note = request.form.get("note", "").strip()
    if amount and float(amount) > 0:
        db.session.add(Advance(employee_id=employee_id, amount=amount, note=note))
        db.session.commit()
    return redirect(url_for("owner_staff"))


@app.route("/owner/parents", methods=["GET", "POST"])
@login_required
def owner_parents():
    if not require_owner():
        return redirect(url_for("unified_login"))

    if request.method == "POST":
        form_type = request.form.get("form_type")

        if form_type == "new_parent":
            name = request.form.get("name", "").strip()
            phone = request.form.get("phone", "").strip()
            password = request.form.get("password", "").strip()
            child_id = request.form.get("child_id")
            if name and phone and password:
                existing = Parent.query.filter_by(phone=phone).first()
                if existing:
                    return render_template_owner_parents_error("رقم الهاتف ده مسجل قبل كده لولي أمر تاني")
                new_parent = Parent(name=name, phone=phone)
                new_parent.set_password(password)
                db.session.add(new_parent)
                db.session.flush()
                if child_id:
                    db.session.add(ParentChild(parent_id=new_parent.id, child_id=int(child_id)))
                db.session.commit()

        elif form_type == "link_existing":
            parent_id = request.form.get("parent_id")
            child_id = request.form.get("child_id")
            if parent_id and child_id:
                exists = ParentChild.query.filter_by(parent_id=parent_id, child_id=child_id).first()
                if not exists:
                    db.session.add(ParentChild(parent_id=parent_id, child_id=child_id))
                    db.session.commit()

        return redirect(url_for("owner_parents"))

    parents = Parent.query.all()
    children = Child.query.all()
    links_by_parent = {}
    for p in parents:
        links = ParentChild.query.filter_by(parent_id=p.id).all()
        links_by_parent[p.id] = [Child.query.get(l.child_id) for l in links]

    return render_template("owner_parents.html", parents=parents, children=children, links_by_parent=links_by_parent)


def render_template_owner_parents_error(message):
    parents = Parent.query.all()
    children = Child.query.all()
    links_by_parent = {}
    for p in parents:
        links = ParentChild.query.filter_by(parent_id=p.id).all()
        links_by_parent[p.id] = [Child.query.get(l.child_id) for l in links]
    return render_template("owner_parents.html", parents=parents, children=children, links_by_parent=links_by_parent, error=message)


@app.route("/owner/addons", methods=["GET", "POST"])
@login_required
def owner_addons():
    if not require_owner():
        return redirect(url_for("unified_login"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        monthly_fee = request.form.get("monthly_fee") or 0
        if name:
            db.session.add(Addon(nursery_id=current_user.nursery_id, name=name, monthly_fee=monthly_fee))
            db.session.commit()
        return redirect(url_for("owner_addons"))

    addons = Addon.query.filter_by(active=True).all()
    subscriber_counts = {a.id: ChildAddon.query.filter_by(addon_id=a.id).count() for a in addons}
    return render_template("owner_addons.html", addons=addons, subscriber_counts=subscriber_counts)


@app.route("/owner/child/<int:child_id>/addons", methods=["GET", "POST"])
@login_required
def owner_child_addons(child_id):
    if not require_owner():
        return redirect(url_for("unified_login"))

    child = Child.query.get_or_404(child_id)

    if request.method == "POST":
        selected_ids = set(int(x) for x in request.form.getlist("addon_ids"))
        current_links = ChildAddon.query.filter_by(child_id=child_id).all()
        current_ids = {link.addon_id for link in current_links}

        for link in current_links:
            if link.addon_id not in selected_ids:
                db.session.delete(link)
        for addon_id in selected_ids - current_ids:
            db.session.add(ChildAddon(child_id=child_id, addon_id=addon_id))

        db.session.commit()
        return redirect(url_for("owner_class_students", class_id=child.class_id))

    all_addons = Addon.query.filter_by(active=True).all()
    active_ids = {ca.addon_id for ca in ChildAddon.query.filter_by(child_id=child_id).all()}
    return render_template("owner_child_addons.html", child=child, all_addons=all_addons, active_ids=active_ids)


@app.route("/owner/child/<int:child_id>/profile", methods=["GET", "POST"])
@login_required
def owner_child_profile(child_id):
    if not require_owner():
        return redirect(url_for("unified_login"))

    child = Child.query.get_or_404(child_id)

    if request.method == "POST":
        child.medical_notes = request.form.get("medical_notes", "").strip()
        child.discount_type = request.form.get("discount_type", "none")
        child.discount_value = request.form.get("discount_value") or 0

        photo_file = request.files.get("photo")
        if photo_file and photo_file.filename:
            raw = photo_file.read()
            if len(raw) > 3 * 1024 * 1024:
                return render_template("owner_child_profile.html", child=child, error="حجم الصورة كبير أوي، اختاري صورة أصغر من 3 ميجا")
            child.photo_data = base64.b64encode(raw).decode("ascii")
            child.photo_mime = photo_file.mimetype or "image/jpeg"

        db.session.commit()
        return redirect(url_for("owner_class_students", class_id=child.class_id))

    return render_template("owner_child_profile.html", child=child, error=None)


@app.route("/child/<int:child_id>/photo")
@login_required
def child_photo(child_id):
    child = Child.query.get_or_404(child_id)

    if current_role() == "parent" and not child_belongs_to_parent(child_id, current_user.id):
        return "غير مصرح", 403

    if not child.photo_data:
        return "", 404

    raw = base64.b64decode(child.photo_data)
    return app.response_class(raw, mimetype=child.photo_mime or "image/jpeg")


@app.route("/owner/payment-methods", methods=["GET", "POST"])
@login_required
def owner_payment_methods():
    if not require_owner():
        return redirect(url_for("unified_login"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            db.session.add(PaymentMethod(nursery_id=current_user.nursery_id, name=name))
            db.session.commit()
        return redirect(url_for("owner_payment_methods"))

    methods = PaymentMethod.query.filter_by(active=True).all()
    return render_template("owner_payment_methods.html", methods=methods)


@app.route("/owner/payment-methods/statement")
@login_required
def owner_payment_methods_statement():
    if not require_owner():
        return redirect(url_for("unified_login"))

    today = date.today()
    start = request.args.get("start") or today.replace(day=1).isoformat()
    end = request.args.get("end") or today.isoformat()

    methods = PaymentMethod.query.filter_by(active=True).all()
    summary = {m.id: {"name": m.name, "in": 0.0, "out": 0.0} for m in methods}
    summary["none"] = {"name": "بدون طريقة محددة", "in": 0.0, "out": 0.0}

    transactions = []

    tuition_payments = Payment.query.filter(
        Payment.paid.is_(True), Payment.paid_date >= start, Payment.paid_date <= end
    ).all()
    for p in tuition_payments:
        key = p.payment_method_id or "none"
        summary.setdefault(key, {"name": p.payment_method.name if p.payment_method else "بدون طريقة محددة", "in": 0.0, "out": 0.0})
        summary[key]["in"] += float(p.amount)
        transactions.append({
            "date": p.paid_date, "type": "تحصيل اشتراك", "detail": p.child.name,
            "amount": float(p.amount), "direction": "in",
            "method": p.payment_method.name if p.payment_method else "—",
        })

    expenses = Expense.query.filter(Expense.date >= start, Expense.date <= end).all()
    for e in expenses:
        key = e.payment_method_id or "none"
        summary.setdefault(key, {"name": e.payment_method.name if e.payment_method else "بدون طريقة محددة", "in": 0.0, "out": 0.0})
        summary[key]["out"] += float(e.amount)
        transactions.append({
            "date": e.date, "type": f"مصروف — {e.category}", "detail": e.description or "",
            "amount": float(e.amount), "direction": "out",
            "method": e.payment_method.name if e.payment_method else "—",
        })

    salary_payments = SalaryPayment.query.filter(
        SalaryPayment.paid.is_(True), SalaryPayment.paid_date >= start, SalaryPayment.paid_date <= end
    ).all()
    for sp in salary_payments:
        key = sp.payment_method_id or "none"
        summary.setdefault(key, {"name": sp.payment_method.name if sp.payment_method else "بدون طريقة محددة", "in": 0.0, "out": 0.0})
        summary[key]["out"] += float(sp.amount)
        transactions.append({
            "date": sp.paid_date, "type": "مرتب", "detail": sp.employee.name,
            "amount": float(sp.amount), "direction": "out",
            "method": sp.payment_method.name if sp.payment_method else "—",
        })

    transactions.sort(key=lambda t: t["date"], reverse=True)
    summary_rows = [v for k, v in summary.items() if v["in"] > 0 or v["out"] > 0]

    return render_template(
        "owner_payment_statement.html", start=start, end=end,
        summary_rows=summary_rows, transactions=transactions,
    )


@app.route("/owner/tuition", methods=["GET", "POST"])
@login_required
def owner_tuition():
    if not require_owner():
        return redirect(url_for("unified_login"))

    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))

    if request.method == "POST":
        child_id = int(request.form.get("child_id"))
        amount = request.form.get("amount")
        method_id = request.form.get("payment_method_id") or None

        payment = Payment.query.filter_by(child_id=child_id, month=month, year=year).first()
        if not payment:
            payment = Payment(child_id=child_id, month=month, year=year, amount=amount)
            db.session.add(payment)
        payment.amount = amount
        payment.paid = True
        payment.paid_date = date.today()
        payment.payment_method_id = method_id
        db.session.commit()
        return redirect(url_for("owner_tuition", month=month, year=year))

    children = Child.query.all()
    existing_payments = {
        p.child_id: p for p in Payment.query.filter_by(month=month, year=year).all()
    }
    methods = PaymentMethod.query.filter_by(active=True).all()

    rows = []
    for c in children:
        expected = compute_child_expected_fee(c)
        rows.append({
            "child": c,
            "expected": expected,
            "payment": existing_payments.get(c.id),
        })

    return render_template("owner_tuition.html", rows=rows, methods=methods, month=month, year=year)


@app.route("/owner/expenses", methods=["GET", "POST"])
@login_required
def owner_expenses():
    if not require_owner():
        return redirect(url_for("unified_login"))

    if request.method == "POST":
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        amount = request.form.get("amount") or 0
        expense_date = request.form.get("date") or date.today().isoformat()
        method_id = request.form.get("payment_method_id") or None
        if category and float(amount) > 0:
            db.session.add(Expense(
                nursery_id=current_user.nursery_id, category=category, description=description,
                amount=amount, date=expense_date, created_by_owner_id=current_user.id,
                payment_method_id=method_id,
            ))
            db.session.commit()
        return redirect(url_for("owner_expenses"))

    expenses = Expense.query.order_by(Expense.date.desc()).all()
    total = sum(float(e.amount) for e in expenses)
    methods = PaymentMethod.query.filter_by(active=True).all()
    return render_template("owner_expenses.html", expenses=expenses, total=total, methods=methods)


@app.route("/owner/reports")
@login_required
def owner_reports():
    if not require_owner():
        return redirect(url_for("unified_login"))

    month = int(request.args.get("month", date.today().month))
    year = int(request.args.get("year", date.today().year))

    tuition_paid = db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0)).filter(
        Payment.month == month, Payment.year == year, Payment.paid.is_(True)
    ).scalar()
    tuition_due = db.session.query(db.func.coalesce(db.func.sum(Payment.amount), 0)).filter(
        Payment.month == month, Payment.year == year, Payment.paid.is_(False)
    ).scalar()

    expenses = Expense.query.filter(
        db.extract("month", Expense.date) == month, db.extract("year", Expense.date) == year
    ).all()
    expenses_by_category = {}
    for e in expenses:
        expenses_by_category[e.category] = expenses_by_category.get(e.category, 0) + float(e.amount)
    expenses_total = sum(expenses_by_category.values())

    salaries_total = db.session.query(db.func.coalesce(db.func.sum(SalaryPayment.amount), 0)).filter(
        SalaryPayment.month == month, SalaryPayment.year == year, SalaryPayment.paid.is_(True)
    ).scalar()

    activities = Activity.query.filter(
        db.extract("month", Activity.date) == month, db.extract("year", Activity.date) == year
    ).all()
    activities_cost = sum(float(a.cost) for a in activities)

    net = float(tuition_paid) - expenses_total - float(salaries_total) - activities_cost

    return render_template(
        "owner_reports.html", month=month, year=year,
        tuition_paid=tuition_paid, tuition_due=tuition_due,
        expenses_by_category=expenses_by_category, expenses_total=expenses_total,
        salaries_total=salaries_total, activities_cost=activities_cost, net=net,
    )


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

    owner = Owner(nursery_id=nursery.id, name="مالكة الحضانة", phone="01000000009")
    owner.set_password("owner123")
    db.session.add(owner)

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
