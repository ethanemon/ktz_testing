from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from functools import wraps
from models import db, User, AuditLog
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Недостаточно прав доступа.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated


def hr_or_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ('admin', 'hr'):
            flash('Недостаточно прав доступа.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/users')
@login_required
@admin_required
def users():
    users_list = User.query.order_by(User.full_name).all()
    return render_template('admin/users.html', users=users_list)


@admin_bp.route('/users/create', methods=['GET', 'POST'])
@login_required
@admin_required
def create_user():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        full_name = request.form.get('full_name', '').strip()
        role = request.form.get('role', 'employee')
        department = request.form.get('department', '').strip()
        position = request.form.get('position', '').strip()
        password = request.form.get('password', '')

        if User.query.filter_by(username=username).first():
            flash('Пользователь с таким логином уже существует.', 'danger')
        elif User.query.filter_by(email=email).first():
            flash('Email уже используется.', 'danger')
        elif len(password) < 6:
            flash('Пароль должен быть не менее 6 символов.', 'danger')
        else:
            user = User(
                username=username, email=email, full_name=full_name,
                role=role, department=department, position=position
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            log = AuditLog(user_id=current_user.id, action='create_user',
                           details=f'Создан пользователь {username} ({role})')
            db.session.add(log)
            db.session.commit()
            flash(f'Пользователь «{full_name}» успешно создан.', 'success')
            return redirect(url_for('admin.users'))

    return render_template('admin/user_form.html', user=None)


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        user.full_name = request.form.get('full_name', '').strip()
        user.email = request.form.get('email', '').strip()
        user.role = request.form.get('role', 'employee')
        user.department = request.form.get('department', '').strip()
        user.position = request.form.get('position', '').strip()
        user.is_active = bool(request.form.get('is_active'))
        new_password = request.form.get('password', '').strip()
        if new_password:
            if len(new_password) < 6:
                flash('Пароль должен быть не менее 6 символов.', 'danger')
                return render_template('admin/user_form.html', user=user)
            user.set_password(new_password)

        db.session.commit()
        flash(f'Данные пользователя «{user.full_name}» обновлены.', 'success')
        return redirect(url_for('admin.users'))

    return render_template('admin/user_form.html', user=user)


@admin_bp.route('/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify({'error': 'Нельзя деактивировать себя'}), 400
    user.is_active = not user.is_active
    db.session.commit()
    return jsonify({'active': user.is_active, 'name': user.full_name})


@admin_bp.route('/logs')
@login_required
@admin_required
def audit_logs():
    page = request.args.get('page', 1, type=int)
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=50)
    return render_template('admin/logs.html', logs=logs)
