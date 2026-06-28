from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime
from models import db, User, AuditLog

auth_bp = Blueprint('auth', __name__)


def log_action(user_id, action, details='', ip=None):
    entry = AuditLog(user_id=user_id, action=action, details=details, ip_address=ip)
    db.session.add(entry)
    db.session.commit()


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=remember)
            user.last_login = datetime.utcnow()
            db.session.commit()
            log_action(user.id, 'login', f'Успешный вход', request.remote_addr)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.dashboard'))
        else:
            flash('Неверный логин или пароль.', 'danger')
            if user:
                log_action(user.id if user else None, 'login_failed', f'Неверный пароль для {username}', request.remote_addr)

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    log_action(current_user.id, 'logout', '', request.remote_addr)
    logout_user()
    return redirect(url_for('auth.login'))


@auth_bp.route('/profile')
@login_required
def profile():
    from models import TestAttempt
    attempts = TestAttempt.query.filter_by(user_id=current_user.id)\
        .filter(TestAttempt.finished_at.isnot(None))\
        .order_by(TestAttempt.finished_at.desc()).all()
    passed_count = sum(1 for a in attempts if a.passed)
    avg_score = round(sum(a.score for a in attempts) / len(attempts), 1) if attempts else 0
    return render_template('profile/index.html',
                           attempts=attempts,
                           passed_count=passed_count,
                           avg_score=avg_score)
