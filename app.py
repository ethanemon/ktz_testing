import os
from flask import Flask, render_template, redirect, url_for
from flask_login import LoginManager, login_required, current_user
from dotenv import load_dotenv

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'ktz-secret-dev-key-2024')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ktz_testing.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # ── DB ──────────────────────────────────────────────
    from models import db
    db.init_app(app)

    # ── Auth ─────────────────────────────────────────────
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Для доступа необходимо войти в систему.'
    login_manager.login_message_category = 'warning'

    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ── Blueprints ────────────────────────────────────────
    from routes.auth import auth_bp
    from routes.admin import admin_bp
    from routes.tests import tests_bp
    from routes.taking import taking_bp
    from routes.analytics import analytics_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(tests_bp)
    app.register_blueprint(taking_bp)
    app.register_blueprint(analytics_bp)

    # ── Main dashboard ────────────────────────────────────
    @app.route('/')
    @login_required
    def index():
        return redirect(url_for('main.dashboard'))

    from flask import Blueprint
    main_bp = Blueprint('main', __name__)

    @main_bp.route('/dashboard')
    @login_required
    def dashboard():
        from models import Test, TestAttempt, User as UserModel
        from datetime import datetime, timedelta

        stats = {}
        if current_user.role in ('admin', 'hr'):
            stats['total_users'] = UserModel.query.filter_by(is_active=True).count()
            stats['total_tests'] = Test.query.count()
            stats['total_attempts'] = TestAttempt.query.filter(
                TestAttempt.finished_at.isnot(None)).count()
            since = datetime.utcnow() - timedelta(days=7)
            stats['recent_attempts'] = TestAttempt.query.filter(
                TestAttempt.finished_at >= since,
                TestAttempt.finished_at.isnot(None)
            ).count()

        # Тесты для прохождения
        available_tests = Test.query.filter_by(is_active=True).all()

        # История текущего пользователя
        my_attempts = TestAttempt.query.filter_by(user_id=current_user.id)\
            .filter(TestAttempt.finished_at.isnot(None))\
            .order_by(TestAttempt.finished_at.desc()).limit(5).all()

        # Тесты с оставшимися попытками
        for test in available_tests:
            used = TestAttempt.query.filter_by(
                user_id=current_user.id, test_id=test.id
            ).filter(TestAttempt.finished_at.isnot(None)).count()
            test._attempts_left = (test.max_attempts - used) if test.max_attempts > 0 else 999
            test._last_score = None
            last = TestAttempt.query.filter_by(
                user_id=current_user.id, test_id=test.id
            ).filter(TestAttempt.finished_at.isnot(None))\
             .order_by(TestAttempt.finished_at.desc()).first()
            if last:
                test._last_score = last.score
                test._last_passed = last.passed

        return render_template('dashboard.html',
                               stats=stats,
                               available_tests=available_tests,
                               my_attempts=my_attempts)

    app.register_blueprint(main_bp)

    # ── DB init ───────────────────────────────────────────
    with app.app_context():
        db.create_all()
        _seed_initial_data()

    return app


def _seed_initial_data():
    from models import db, User, Category

    # Создаём суперадмина если нет пользователей
    if User.query.count() == 0:
        admin = User(
            username='admin',
            email='admin@ktz.ru',
            full_name='Администратор системы',
            role='admin',
            department='ИТ-отдел',
            position='Системный администратор',
        )
        admin.set_password('admin123')

        hr = User(
            username='hr',
            email='hr@ktz.ru',
            full_name='Иванова Светлана Петровна',
            role='hr',
            department='Отдел кадров',
            position='HR-специалист',
        )
        hr.set_password('hr123456')

        emp = User(
            username='ivanov',
            email='ivanov@ktz.ru',
            full_name='Иванов Алексей Николаевич',
            role='employee',
            department='Цех №1 (профильные трубы)',
            position='Сварщик 5 разряда',
        )
        emp.set_password('emp123456')

        mgr = User(
            username='petrov',
            email='petrov@ktz.ru',
            full_name='Петров Дмитрий Сергеевич',
            role='manager',
            department='Цех №2 (круглые трубы)',
            position='Начальник цеха',
        )
        mgr.set_password('mgr123456')

        db.session.add_all([admin, hr, emp, mgr])
        db.session.commit()

    # Категории
    if Category.query.count() == 0:
        cats = [
            Category(name='Охрана труда и ПБ', description='Правила и нормы охраны труда, промышленная безопасность', color='#EF4444', icon='shield'),
            Category(name='Технологии производства', description='Технологические процессы производства электросварных труб', color='#3B82F6', icon='cog'),
            Category(name='Контроль качества', description='Методы контроля качества, ГОСТы, стандарты', color='#10B981', icon='check-circle'),
            Category(name='Работа с оборудованием', description='Правила эксплуатации и обслуживания оборудования', color='#F59E0B', icon='wrench'),
            Category(name='Экологическая безопасность', description='Требования экологической безопасности на производстве', color='#6366F1', icon='leaf'),
        ]
        db.session.add_all(cats)
        db.session.commit()


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5000)
