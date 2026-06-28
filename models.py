from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    full_name = db.Column(db.String(200))
    role = db.Column(db.String(20), default='employee')  # admin, hr, employee, manager
    department = db.Column(db.String(100))
    position = db.Column(db.String(150))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    attempts = db.relationship('TestAttempt', backref='user', lazy=True)
    audit_logs = db.relationship('AuditLog', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def role_display(self):
        roles = {
            'admin': 'Администратор',
            'hr': 'HR-специалист',
            'employee': 'Сотрудник',
            'manager': 'Руководитель подразделения',
        }
        return roles.get(self.role, self.role)

    @property
    def role_badge_class(self):
        classes = {
            'admin': 'badge-admin',
            'hr': 'badge-hr',
            'employee': 'badge-employee',
            'manager': 'badge-manager',
        }
        return classes.get(self.role, 'badge-employee')

    def can(self, permission):
        perms = {
            'admin': ['manage_users', 'manage_tests', 'view_analytics', 'take_tests', 'view_all_results'],
            'hr': ['manage_tests', 'view_analytics', 'take_tests', 'view_all_results'],
            'manager': ['view_analytics', 'take_tests', 'view_dept_results'],
            'employee': ['take_tests'],
        }
        return permission in perms.get(self.role, [])


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(7), default='#3B82F6')
    icon = db.Column(db.String(50), default='folder')
    tests = db.relationship('Test', backref='category', lazy=True)


class Test(db.Model):
    __tablename__ = 'tests'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    time_limit = db.Column(db.Integer, default=30)          # minutes, 0 = unlimited
    passing_score = db.Column(db.Integer, default=70)       # percent
    max_attempts = db.Column(db.Integer, default=3)
    shuffle_questions = db.Column(db.Boolean, default=False)
    shuffle_options = db.Column(db.Boolean, default=False)
    show_results = db.Column(db.Boolean, default=True)      # show correct answers after
    is_active = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    questions = db.relationship('Question', backref='test', lazy=True,
                                cascade='all, delete-orphan', order_by='Question.order')
    attempts = db.relationship('TestAttempt', backref='test', lazy=True)
    creator = db.relationship('User', foreign_keys=[created_by], lazy=True)

    @property
    def question_count(self):
        return len(self.questions)

    @property
    def total_points(self):
        return sum(q.points for q in self.questions) or 0

    @property
    def avg_score(self):
        finished = [a for a in self.attempts if a.finished_at]
        if not finished:
            return None
        return round(sum(a.score for a in finished) / len(finished), 1)

    @property
    def pass_rate(self):
        finished = [a for a in self.attempts if a.finished_at]
        if not finished:
            return None
        passed = sum(1 for a in finished if a.passed)
        return round(passed / len(finished) * 100, 1)


class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('tests.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    # single, multiple, text, sequence
    question_type = db.Column(db.String(20), default='single')
    order = db.Column(db.Integer, default=0)
    points = db.Column(db.Integer, default=1)
    explanation = db.Column(db.Text)          # shown after test
    image_url = db.Column(db.String(500))
    ai_generated = db.Column(db.Boolean, default=False)

    options = db.relationship('AnswerOption', backref='question', lazy=True,
                              cascade='all, delete-orphan', order_by='AnswerOption.order')

    @property
    def type_display(self):
        types = {
            'single': 'Один ответ',
            'multiple': 'Несколько ответов',
            'text': 'Открытый ответ',
            'sequence': 'Последовательность',
        }
        return types.get(self.question_type, self.question_type)

    @property
    def correct_options(self):
        return [o for o in self.options if o.is_correct]


class AnswerOption(db.Model):
    __tablename__ = 'answer_options'
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    is_correct = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer, default=0)
    correct_position = db.Column(db.Integer)  # for sequence questions


class TestAttempt(db.Model):
    __tablename__ = 'test_attempts'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('tests.id'), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    finished_at = db.Column(db.DateTime)
    score = db.Column(db.Float, default=0)           # percent 0-100
    points_earned = db.Column(db.Float, default=0)
    passed = db.Column(db.Boolean, default=False)
    attempt_number = db.Column(db.Integer, default=1)

    answers = db.relationship('UserAnswer', backref='attempt', lazy=True)

    @property
    def duration_minutes(self):
        if self.finished_at and self.started_at:
            delta = self.finished_at - self.started_at
            return round(delta.total_seconds() / 60, 1)
        return None

    @property
    def is_finished(self):
        return self.finished_at is not None


class UserAnswer(db.Model):
    __tablename__ = 'user_answers'
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('test_attempts.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    selected_options = db.Column(db.Text, default='[]')   # JSON list of option IDs
    text_answer = db.Column(db.Text)
    is_correct = db.Column(db.Boolean)
    points_earned = db.Column(db.Float, default=0)
    ai_score = db.Column(db.Float)            # 0-100 from AI evaluation
    ai_feedback = db.Column(db.Text)

    question = db.relationship('Question', lazy=True)

    def get_selected_ids(self):
        try:
            return json.loads(self.selected_options or '[]')
        except Exception:
            return []

    def set_selected_ids(self, ids):
        self.selected_options = json.dumps(ids)


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(100))
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
