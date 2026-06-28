from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from functools import wraps
from models import db, Test, Question, AnswerOption, Category, AuditLog
import json

tests_bp = Blueprint('tests', __name__, url_prefix='/tests')


def hr_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role not in ('admin', 'hr'):
            flash('Только HR-специалисты и администраторы могут управлять тестами.', 'danger')
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated


@tests_bp.route('/')
@login_required
def list_tests():
    from flask_login import current_user
    from models import TestAttempt
    if current_user.role in ('admin', 'hr'):
        tests = Test.query.order_by(Test.created_at.desc()).all()
    else:
        tests = Test.query.filter_by(is_active=True).order_by(Test.title).all()
    categories = Category.query.order_by(Category.name).all()
    cat_filter = request.args.get('category', type=int)
    if cat_filter:
        tests = [t for t in tests if t.category_id == cat_filter]
    for test in tests:
        used = TestAttempt.query.filter_by(
            user_id=current_user.id, test_id=test.id
        ).filter(TestAttempt.finished_at.isnot(None)).count()
        test._attempts_left = (test.max_attempts - used) if test.max_attempts > 0 else 999
        last = TestAttempt.query.filter_by(
            user_id=current_user.id, test_id=test.id
        ).filter(TestAttempt.finished_at.isnot(None))         .order_by(TestAttempt.finished_at.desc()).first()
        test._last_score = last.score if last else None
        test._last_passed = last.passed if last else False
    return render_template('tests/list.html', tests=tests, categories=categories, cat_filter=cat_filter)


@tests_bp.route('/create', methods=['GET', 'POST'])
@login_required
@hr_required
def create_test():
    categories = Category.query.order_by(Category.name).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        category_id = request.form.get('category_id', type=int)
        time_limit = request.form.get('time_limit', 30, type=int)
        passing_score = request.form.get('passing_score', 70, type=int)
        max_attempts = request.form.get('max_attempts', 3, type=int)
        shuffle_questions = bool(request.form.get('shuffle_questions'))
        shuffle_options = bool(request.form.get('shuffle_options'))
        show_results = bool(request.form.get('show_results'))

        if not title:
            flash('Введите название теста.', 'danger')
        else:
            test = Test(
                title=title, description=description, category_id=category_id,
                time_limit=time_limit, passing_score=passing_score,
                max_attempts=max_attempts, shuffle_questions=shuffle_questions,
                shuffle_options=shuffle_options, show_results=show_results,
                created_by=current_user.id
            )
            db.session.add(test)
            db.session.commit()
            log = AuditLog(user_id=current_user.id, action='create_test',
                           details=f'Создан тест: {title}')
            db.session.add(log)
            db.session.commit()
            flash(f'Тест «{title}» создан. Добавьте вопросы.', 'success')
            return redirect(url_for('tests.edit_questions', test_id=test.id))

    return render_template('tests/create.html', categories=categories, test=None)


@tests_bp.route('/<int:test_id>/edit', methods=['GET', 'POST'])
@login_required
@hr_required
def edit_test(test_id):
    test = Test.query.get_or_404(test_id)
    categories = Category.query.order_by(Category.name).all()

    if request.method == 'POST':
        test.title = request.form.get('title', '').strip()
        test.description = request.form.get('description', '').strip()
        test.category_id = request.form.get('category_id', type=int)
        test.time_limit = request.form.get('time_limit', 30, type=int)
        test.passing_score = request.form.get('passing_score', 70, type=int)
        test.max_attempts = request.form.get('max_attempts', 3, type=int)
        test.shuffle_questions = bool(request.form.get('shuffle_questions'))
        test.shuffle_options = bool(request.form.get('shuffle_options'))
        test.show_results = bool(request.form.get('show_results'))
        test.is_active = bool(request.form.get('is_active'))
        db.session.commit()
        flash('Тест обновлён.', 'success')
        return redirect(url_for('tests.edit_questions', test_id=test.id))

    return render_template('tests/create.html', categories=categories, test=test)


@tests_bp.route('/<int:test_id>/questions', methods=['GET'])
@login_required
@hr_required
def edit_questions(test_id):
    test = Test.query.get_or_404(test_id)
    return render_template('tests/questions.html', test=test)


@tests_bp.route('/<int:test_id>/questions/add', methods=['POST'])
@login_required
@hr_required
def add_question(test_id):
    test = Test.query.get_or_404(test_id)
    data = request.get_json()

    q = Question(
        test_id=test.id,
        text=data.get('text', '').strip(),
        question_type=data.get('question_type', 'single'),
        points=data.get('points', 1),
        explanation=data.get('explanation', '').strip(),
        order=len(test.questions),
        ai_generated=data.get('ai_generated', False)
    )
    db.session.add(q)
    db.session.flush()

    for i, opt in enumerate(data.get('options', [])):
        ao = AnswerOption(
            question_id=q.id,
            text=opt.get('text', '').strip(),
            is_correct=opt.get('is_correct', False),
            order=i
        )
        db.session.add(ao)

    db.session.commit()
    return jsonify({'id': q.id, 'text': q.text, 'type': q.question_type})


@tests_bp.route('/questions/<int:q_id>/delete', methods=['POST'])
@login_required
@hr_required
def delete_question(q_id):
    q = Question.query.get_or_404(q_id)
    db.session.delete(q)
    db.session.commit()
    return jsonify({'ok': True})


@tests_bp.route('/<int:test_id>/delete', methods=['POST'])
@login_required
@hr_required
def delete_test(test_id):
    test = Test.query.get_or_404(test_id)
    title = test.title
    db.session.delete(test)
    db.session.commit()
    flash(f'Тест «{title}» удалён.', 'success')
    return redirect(url_for('tests.list_tests'))