"""
Точка запуска приложения КТЗ — Система тестирования знаний.

Запуск:
    python run.py

Первый запуск создаёт базу данных и демо-аккаунты:
    admin / admin123
    hr    / hr123456
    ivanov / emp123456
    petrov / mgr123456
"""
from app import create_app

app = create_app()

if __name__ == '__main__':
    print("\n" + "="*55)
    print("  КТЗ — Система тестирования знаний сотрудников")
    print("  ООО «Королёвский трубный завод»")
    print("="*55)
    print("  URL:  http://127.0.0.1:5001")
    print("  Логин: admin | Пароль: admin123")
    print("="*55 + "\n")
    app.run(debug=True, port=5001, host='0.0.0.0')
