"""
ИИ-модуль: интеграция с Anthropic Claude API.
- Генерация вопросов по теме
- Оценка открытых ответов (семантическое сравнение)
"""
import os
import json
import re

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


def _get_client():
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key or not ANTHROPIC_AVAILABLE:
        return None
    return anthropic.Anthropic(api_key=api_key)


def generate_questions(topic: str, category: str, count: int = 5, difficulty: str = 'medium') -> list[dict]:
    """
    Генерирует список вопросов по теме для банка вопросов.
    Возвращает список словарей с полями:
      text, question_type, points, options [{text, is_correct}], explanation
    """
    client = _get_client()
    if not client:
        return _mock_questions(topic, count)

    difficulty_map = {
        'easy': 'базового уровня (для новых сотрудников)',
        'medium': 'среднего уровня (для опытных сотрудников)',
        'hard': 'повышенной сложности (для экспертов и аттестации)',
    }
    diff_label = difficulty_map.get(difficulty, 'среднего уровня')

    prompt = f"""Ты — эксперт по разработке корпоративных учебных тестов для металлургического предприятия ООО «Королёвский трубный завод» (производство электросварных труб).

Сгенерируй ровно {count} тестовых вопросов {diff_label} по теме: «{topic}» (категория: {category}).

Требования к формату ответа — строго JSON-массив без пояснений:
[
  {{
    "text": "Текст вопроса?",
    "question_type": "single",
    "points": 1,
    "explanation": "Краткое пояснение правильного ответа.",
    "options": [
      {{"text": "Вариант А", "is_correct": false}},
      {{"text": "Вариант Б", "is_correct": true}},
      {{"text": "Вариант В", "is_correct": false}},
      {{"text": "Вариант Г", "is_correct": false}}
    ]
  }}
]

Правила:
- question_type: "single" (один правильный ответ) или "multiple" (несколько правильных)
- Для "single": ровно 1 правильный вариант из 4
- Для "multiple": 2–3 правильных варианта из 5
- Вопросы должны быть практическими, с реальными техническими деталями
- Используй профессиональную терминологию (ГОСТ, СНиП, ОТ, ПБ, технологии сварки)
- НЕ нумеруй вопросы, НЕ добавляй комментарии вне JSON
- points: 1 для обычных, 2 для сложных вопросов

Верни ТОЛЬКО JSON-массив."""

    try:
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        content = message.content[0].text.strip()
        # Извлекаем JSON даже если есть лишний текст
        match = re.search(r'\[.*\]', content, re.DOTALL)
        if match:
            questions = json.loads(match.group())
            return questions[:count]
    except Exception as e:
        print(f"AI generation error: {e}")

    return _mock_questions(topic, count)


def evaluate_text_answer(question_text: str, correct_answer: str, user_answer: str) -> dict:
    """
    Оценивает открытый текстовый ответ сотрудника.
    Возвращает: {score: 0-100, feedback: str, is_correct: bool}
    """
    client = _get_client()
    if not client:
        return _mock_evaluate(user_answer, correct_answer)

    if not user_answer or not user_answer.strip():
        return {'score': 0, 'feedback': 'Ответ не предоставлен.', 'is_correct': False}

    prompt = f"""Ты — эксперт-оценщик ответов на вопросы по промышленной безопасности и технологиям производства труб.

Вопрос: {question_text}

Эталонный правильный ответ: {correct_answer}

Ответ сотрудника: {user_answer}

Оцени ответ сотрудника по шкале 0–100 и дай краткое объяснение (2–3 предложения на русском языке).

Критерии оценки:
- 90–100: полный и точный ответ, правильная терминология
- 70–89: ответ верный, но неполный или без ключевых деталей
- 50–69: частично правильный, есть существенные пробелы
- 30–49: ответ касается темы, но с серьёзными ошибками
- 0–29: неверный ответ или не по теме

Верни строго JSON без пояснений:
{{"score": 85, "feedback": "Объяснение оценки.", "is_correct": true}}

is_correct = true если score >= 70."""

    try:
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )
        content = message.content[0].text.strip()
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            result = json.loads(match.group())
            result['is_correct'] = result.get('score', 0) >= 70
            return result
    except Exception as e:
        print(f"AI evaluation error: {e}")

    return _mock_evaluate(user_answer, correct_answer)


def _mock_questions(topic: str, count: int) -> list[dict]:
    """Заглушка для работы без API-ключа."""
    questions = []
    for i in range(1, count + 1):
        questions.append({
            "text": f"[ИИ-вопрос #{i} по теме «{topic}»] Какое из следующих утверждений верно?",
            "question_type": "single",
            "points": 1,
            "explanation": "Это автоматически сгенерированный вопрос-заглушка. Установите ANTHROPIC_API_KEY для реальной генерации.",
            "options": [
                {"text": "Вариант А — правильный", "is_correct": True},
                {"text": "Вариант Б", "is_correct": False},
                {"text": "Вариант В", "is_correct": False},
                {"text": "Вариант Г", "is_correct": False},
            ]
        })
    return questions


def _mock_evaluate(user_answer: str, correct_answer: str) -> dict:
    """Простая оценка без ИИ по длине и совпадению слов."""
    if not user_answer or not user_answer.strip():
        return {'score': 0, 'feedback': 'Ответ не предоставлен.', 'is_correct': False}

    correct_words = set(correct_answer.lower().split())
    user_words = set(user_answer.lower().split())
    if not correct_words:
        score = 50
    else:
        overlap = len(correct_words & user_words) / len(correct_words)
        score = min(int(overlap * 100), 100)

    is_correct = score >= 70
    feedback = (
        "Ответ содержит ключевые понятия из эталонного ответа."
        if is_correct else
        "Ответ не содержит достаточного количества ключевых понятий. "
        "Установите ANTHROPIC_API_KEY для точной ИИ-оценки."
    )
    return {'score': score, 'feedback': feedback, 'is_correct': is_correct}
