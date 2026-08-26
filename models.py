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

    parents = db.relationship("ParentChild", backref="child", lazy=True)
    daily_logs = db.relationship("DailyLog", backref="child", lazy=True, order_by="DailyLog.date.desc()")
    attendance = db.relationship("AttendanceRecord", backref="child", lazy=True)
    payments = db.relationship("Payment", backref="child", lazy=True)
    messages = db.relationship("Message", backref="child", lazy=True, order_by="Message.timestamp")


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


class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey("child.id"), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    paid = db.Column(db.Boolean, default=False)
    paid_date = db.Column(db.Date, nullable=True)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    child_id = db.Column(db.Integer, db.ForeignKey("child.id"), nullable=False)
    sender_type = db.Column(db.String(10), nullable=False)  # "parent" or "teacher"
    sender_id = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
