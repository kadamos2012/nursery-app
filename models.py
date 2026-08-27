from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ---------- Core entities ----------

class Nursery(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    classes = db.relationship("SchoolClass", backref="nursery", lazy=True)
    teachers = db.relationship("Teacher", backref="nursery", lazy=True)


class SchoolClass(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nursery_id = db.Column(db.Integer, db.ForeignKey("nursery.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # e.g. "الفراشات"
    children = db.relationship("Child", backref="school_class", lazy=True)


class Teacher(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nursery_id = db.Column(db.Integer, db.ForeignKey("nursery.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(30), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("school_class.id"), nullable=True)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    def get_id(self):
        return f"teacher:{self.id}"


class Parent(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(30), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    def get_id(self):
        return f"parent:{self.id}"


class Child(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey("school_class.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    birth_date = db.Column(db.Date, nullable=True)
    photo_url = db.Column(db.String(255), nullable=True)
    photo_data = db.Column(db.Text, nullable=True)   # base64-encoded image
    photo_mime = db.Column(db.String(50), nullable=True)
    medical_notes = db.Column(db.Text, nullable=True)  # allergies / chronic conditions

    subscription_type = db.Column(db.String(20), nullable=False, default="full_time")  # "full_time" | "part_time"
    monthly_fee = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    discount_type = db.Column(db.String(10), nullable=False, default="none")  # "none" | "fixed" | "percent"
    discount_value = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    archived = db.Column(db.Boolean, nullable=False, default=False)

    parents = db.relationship("ParentChild", backref="child", lazy=True)
    daily_logs = db.relationship("DailyLog", backref="child", lazy=True, order_by="DailyLog.date.desc()")
    attendance = db.relationship("AttendanceRecord", backref="child", lazy=True)
    payments = db.relationship("Payment", backref="child", lazy=True)
    messages = db.relationship("Message", backref="child", lazy=True, order_by="Message.timestamp")
    addons = db.relationship("ChildAddon", backref="child", lazy=True)


class ParentChild(db.Model):
    """Links a parent account to one or more children (siblings supported)."""
    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("parent.id"), nullable=False)
    child_id = db.Column(db.Integer, db.ForeignKey("child.id"), nullable=False)


# ---------- Daily activity ----------

class DailyLog(db.Model):
    """One entry per child per day, filled in by the teacher during the day."""
    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey("child.id"), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)

    arrival_time = db.Column(db.Time, nullable=True)
    departure_time = db.Column(db.Time, nullable=True)

    meal_status = db.Column(db.String(50), nullable=True)   # "اتاكلت كلها" / "نص الوجبة" / "رفض الأكل"
    nap_minutes = db.Column(db.Integer, nullable=True)
    mood = db.Column(db.String(20), nullable=True)           # emoji or short label

    note = db.Column(db.Text, nullable=True)
    photo_url = db.Column(db.String(255), nullable=True)

    created_by_teacher_id = db.Column(db.Integer, db.ForeignKey("teacher.id"), nullable=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("child_id", "date", name="uq_child_date"),)


class AttendanceRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey("child.id"), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    present = db.Column(db.Boolean, default=True)

    __table_args__ = (db.UniqueConstraint("child_id", "date", name="uq_attendance_child_date"),)


class PaymentMethod(db.Model):
    """Catalog of collection/disbursement methods (cash, bank transfer, mobile wallet, etc.)."""
    id = db.Column(db.Integer, primary_key=True)
    nursery_id = db.Column(db.Integer, db.ForeignKey("nursery.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    active = db.Column(db.Boolean, default=True)


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey("child.id"), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    paid = db.Column(db.Boolean, default=False)
    paid_date = db.Column(db.Date, nullable=True)
    payment_method_id = db.Column(db.Integer, db.ForeignKey("payment_method.id"), nullable=True)

    payment_method = db.relationship("PaymentMethod", foreign_keys=[payment_method_id])


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey("child.id"), nullable=False)
    sender_type = db.Column(db.String(10), nullable=False)  # "parent" or "teacher"
    sender_id = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class PushSubscription(db.Model):
    """A parent's browser push subscription (Web Push API)."""
    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("parent.id"), nullable=False)
    endpoint = db.Column(db.String(512), nullable=False, unique=True)
    p256dh = db.Column(db.String(255), nullable=False)
    auth = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------- Owner / back-office (accounting) ----------

class Owner(UserMixin, db.Model):
    """The nursery owner: full access to accounting, staff, classes, and activities."""
    id = db.Column(db.Integer, primary_key=True)
    nursery_id = db.Column(db.Integer, db.ForeignKey("nursery.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(30), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)

    def get_id(self):
        return f"owner:{self.id}"


class Employee(db.Model):
    """Staff member (teacher, warehouse keeper, admin, etc.) with a monthly salary."""
    id = db.Column(db.Integer, primary_key=True)
    nursery_id = db.Column(db.Integer, db.ForeignKey("nursery.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(100), nullable=True)  # job title, e.g. "معلمة", "إدارية"
    phone = db.Column(db.String(30), nullable=True)
    monthly_salary = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    hire_date = db.Column(db.Date, nullable=True)
    active = db.Column(db.Boolean, default=True)

    salary_payments = db.relationship("SalaryPayment", backref="employee", lazy=True)


class SalaryPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    paid = db.Column(db.Boolean, default=False)
    paid_date = db.Column(db.Date, nullable=True)
    payment_method_id = db.Column(db.Integer, db.ForeignKey("payment_method.id"), nullable=True)

    payment_method = db.relationship("PaymentMethod", foreign_keys=[payment_method_id])

    __table_args__ = (db.UniqueConstraint("employee_id", "month", "year", name="uq_salary_emp_month_year"),)


class Advance(db.Model):
    """A salary advance (سلفة) given to an employee, deducted from a future salary payment."""
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    note = db.Column(db.String(255), nullable=True)
    deducted = db.Column(db.Boolean, default=False)


class Trip(db.Model):
    """A planned trip/outing with cost estimation and a suggested subscription price."""
    id = db.Column(db.Integer, primary_key=True)
    nursery_id = db.Column(db.Integer, db.ForeignKey("nursery.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    date = db.Column(db.Date, nullable=True)
    estimated_students = db.Column(db.Integer, nullable=False, default=1)
    profit_margin_percent = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    final_price = db.Column(db.Numeric(10, 2), nullable=True)
    status = db.Column(db.String(20), nullable=False, default="draft")  # "draft" | "published"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    cost_items = db.relationship("TripCostItem", backref="trip", lazy=True, cascade="all, delete-orphan")
    eligible_classes = db.relationship("TripClass", backref="trip", lazy=True, cascade="all, delete-orphan")
    registrations = db.relationship("TripRegistration", backref="trip", lazy=True, cascade="all, delete-orphan")


class TripCostItem(db.Model):
    """A single cost line for a trip. cost_type is 'total' (split across estimated_students)
    or 'per_child' (already a per-child amount)."""
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    cost_type = db.Column(db.String(10), nullable=False, default="total")  # "total" | "per_child"


class TripClass(db.Model):
    """Which classes are eligible to subscribe to a trip."""
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("school_class.id"), nullable=False)

    school_class = db.relationship("SchoolClass")


class TripRegistration(db.Model):
    """A child subscribed to a trip, either by the parent directly or registered by the owner."""
    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey("trip.id"), nullable=False)
    child_id = db.Column(db.Integer, db.ForeignKey("child.id"), nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    paid = db.Column(db.Boolean, default=False)
    paid_date = db.Column(db.Date, nullable=True)
    payment_method_id = db.Column(db.Integer, db.ForeignKey("payment_method.id"), nullable=True)
    requested_by = db.Column(db.String(10), nullable=False, default="parent")  # "parent" | "owner"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    child = db.relationship("Child")
    payment_method = db.relationship("PaymentMethod")

    __table_args__ = (db.UniqueConstraint("trip_id", "child_id", name="uq_trip_child"),)


class Announcement(db.Model):
    """A notice posted by the owner, shown to parents of a specific class or the whole nursery."""
    id = db.Column(db.Integer, primary_key=True)
    nursery_id = db.Column(db.Integer, db.ForeignKey("nursery.id"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("school_class.id"), nullable=True)  # None = whole nursery
    title = db.Column(db.String(150), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_owner_id = db.Column(db.Integer, db.ForeignKey("owner.id"), nullable=True)

    school_class = db.relationship("SchoolClass")


class ExpenseCategory(db.Model):
    """Editable catalog of expense line items (rent, bills, supplies, etc.)."""
    id = db.Column(db.Integer, primary_key=True)
    nursery_id = db.Column(db.Integer, db.ForeignKey("nursery.id"), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    active = db.Column(db.Boolean, default=True)


class Expense(db.Model):
    """A general nursery expense (rent, supplies, utilities, maintenance, etc.)."""
    id = db.Column(db.Integer, primary_key=True)
    nursery_id = db.Column(db.Integer, db.ForeignKey("nursery.id"), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    created_by_owner_id = db.Column(db.Integer, db.ForeignKey("owner.id"), nullable=True)
    payment_method_id = db.Column(db.Integer, db.ForeignKey("payment_method.id"), nullable=True)

    payment_method = db.relationship("PaymentMethod", foreign_keys=[payment_method_id])


class Activity(db.Model):
    """A nursery activity (trip, party, workshop) with an associated cost."""
    id = db.Column(db.Integer, primary_key=True)
    nursery_id = db.Column(db.Integer, db.ForeignKey("nursery.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    date = db.Column(db.Date, nullable=True)
    cost = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    notes = db.Column(db.Text, nullable=True)


class Addon(db.Model):
    """Catalog of additional/optional subscriptions on top of the base plan
    (e.g. transport bus, extra meal, extended hours)."""
    id = db.Column(db.Integer, primary_key=True)
    nursery_id = db.Column(db.Integer, db.ForeignKey("nursery.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False)
    monthly_fee = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    active = db.Column(db.Boolean, default=True)


class ChildAddon(db.Model):
    """Which additional subscriptions a specific child is enrolled in."""
    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey("child.id"), nullable=False)
    addon_id = db.Column(db.Integer, db.ForeignKey("addon.id"), nullable=False)

    addon = db.relationship("Addon")

    __table_args__ = (db.UniqueConstraint("child_id", "addon_id", name="uq_child_addon"),)
