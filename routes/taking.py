from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, session
from flask_login import login_required, current_user
from models import db, Test, Question, AnswerOption, TestAttempt, UserAnswer, AuditLog
from ai_module import evaluate_text_answer
from datetime import datetime
import json
import random

taking_bp = Blueprint('taking', __name__, url_prefix='/take')


@taking_bp.route('/<int:test_id>/start')
@login_required
def start(test_id):
    test = Test.query.get_or_404(test_id)

    if not test.is_active:
        flash('Этот тест недоступен.', 'warning')
        return redirect(url_for('tests.list_tests'))

    prev_attempts = TestAttempt.query.filter_by(
        user_id=current_user.id, test_id=test_id
    ).filter(TestAttempt.finished_at.isnot(None)).count()

    if test.max_attempts > 0 and prev_attempts >= test.max_attempts:
        flash(f'Вы исчерпали все попытки ({test.max_attempts}).', 'warning')
        return redirect(url_for('tests.list_tests'))

    attempt = TestAttempt(
        user_id=current_user.id,
        test_id=test_id,
        attempt_number=prev_attempts + 1
    )
    db.session.add(attempt)
    db.session.commit()

    questions = list(test.questions)
    if test.shuffle_questions:
        random.shuffle(questions)
    session[f'attempt_{attempt.id}_qorder'] = [q.id for q in questions]

    log = AuditLog(user_id=current_user.id, action='start_test',
                   details=f'Тест: {test.title}, попытка #{attempt.attempt_number}')
    db.session.add(log)
    db.session.commit()

    return redirect(url_for('taking.take', attempt_id=attempt.id))


@taking_bp.route('/<int:attempt_id>')
@login_required
def take(attempt_id):
    attempt = TestAttempt.query.get_or_404(attempt_id)

    if attempt.user_id != current_user.id:
        flash('Нет доступа к этой попытке.', 'danger')
        return redirect(url_for('tests.list_tests'))

    if attempt.is_finished:
        return redirect(url_for('taking.result', attempt_id=attempt.id))

    test = attempt.test
    q_order = session.get(f'attempt_{attempt.id}_qorder', [q.id for q in test.questions])
    questions = []
    for qid in q_order:
        q = Question.query.get(qid)
        if q:
            questions.append(q)


    if test.shuffle_options:
        for q in questions:
            opts = list(q.options)
            random.shuffle(opts)
            q._shuffled_options = opts
    else:
        for q in questions:
            q._shuffled_options = sorted(q.options, key=lambda o: o.order)

    elapsed = int((datetime.utcnow() - attempt.started_at).total_seconds())
    time_limit_secs = test.time_limit * 60 if test.time_limit else 0

    return render_template('tests/take.html',
                           attempt=attempt, test=test, questions=questions,
                           elapsed=elapsed, time_limit_secs=time_limit_secs)


@taking_bp.route('/<int:attempt_id>/submit', methods=['POST'])
@login_required
def submit(attempt_id):
    attempt = TestAttempt.query.get_or_404(attempt_id)

    if attempt.user_id != current_user.id or attempt.is_finished:
        return jsonify({'error': 'Недопустимое действие'}), 400

    test = attempt.test
    data = request.get_json()
    answers_data = data.get('answers', {})

    total_points = 0
    earned_points = 0

    for question in test.questions:
        total_points += question.points
        ans_raw = answers_data.get(str(question.id))

        ua = UserAnswer(attempt_id=attempt.id, question_id=question.id)

        if question.question_type == 'text':
            text_ans = (ans_raw or '').strip()
            ua.text_answer = text_ans

            ref_option = next((o for o in question.options if o.is_correct), None)
            ref_text = ref_option.text if ref_option else ''

            eval_result = evaluate_text_answer(question.text, ref_text, text_ans)
            ua.ai_score = eval_result['score']
            ua.ai_feedback = eval_result['feedback']
            ua.is_correct = eval_result['is_correct']
            pts = question.points * eval_result['score'] / 100
            ua.points_earned = round(pts, 2)
            earned_points += ua.points_earned

        elif question.question_type in ('single', 'multiple'):
            if isinstance(ans_raw, list):
                selected_ids = [int(x) for x in ans_raw if str(x).isdigit()]
            elif ans_raw and str(ans_raw).isdigit():
                selected_ids = [int(ans_raw)]
            else:
                selected_ids = []

            ua.set_selected_ids(selected_ids)

            correct_ids = {o.id for o in question.options if o.is_correct}
            selected_set = set(selected_ids)

            if question.question_type == 'single':
                ua.is_correct = selected_set == correct_ids
                ua.points_earned = question.points if ua.is_correct else 0
            else:
        
                correct_selected = len(selected_set & correct_ids)
                wrong_selected = len(selected_set - correct_ids)
                if len(correct_ids) > 0:
                    ratio = max(0, correct_selected - wrong_selected) / len(correct_ids)
                    ua.points_earned = round(question.points * ratio, 2)
                else:
                    ua.points_earned = 0
                ua.is_correct = selected_set == correct_ids

            earned_points += ua.points_earned

        db.session.add(ua)

    attempt.points_earned = round(earned_points, 2)
    attempt.score = round(earned_points / total_points * 100, 1) if total_points > 0 else 0
    attempt.passed = attempt.score >= test.passing_score
    attempt.finished_at = datetime.utcnow()
    db.session.commit()

    log = AuditLog(user_id=current_user.id, action='finish_test',
                   details=f'Тест: {test.title}, балл: {attempt.score}%, '
                           f'{"сдан" if attempt.passed else "не сдан"}')
    db.session.add(log)
    db.session.commit()

    return jsonify({
        'redirect': url_for('taking.result', attempt_id=attempt.id)
    })


@taking_bp.route('/result/<int:attempt_id>')
@login_required
def result(attempt_id):
    attempt = TestAttempt.query.get_or_404(attempt_id)

    if attempt.user_id != current_user.id and \
       current_user.role not in ('admin', 'hr', 'manager'):
        flash('Нет доступа.', 'danger')
        return redirect(url_for('tests.list_tests'))

    if not attempt.is_finished:
        return redirect(url_for('taking.take', attempt_id=attempt.id))

    test = attempt.test

    answers_map = {ua.question_id: ua for ua in attempt.answers}
    questions_with_answers = []
    for q in test.questions:
        ua = answers_map.get(q.id)
        selected_ids = ua.get_selected_ids() if ua else []
        questions_with_answers.append({
            'question': q,
            'user_answer': ua,
            'selected_ids': selected_ids,
        })

    return render_template('tests/result.html',
                           attempt=attempt, test=test,
                           questions_with_answers=questions_with_answers)
