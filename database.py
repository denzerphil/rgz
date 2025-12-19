import sqlite3
import os
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import random

def init_db():
    # Создаем папку instance, если её нет
    if not os.path.exists('instance'):
        os.makedirs('instance')
    
    conn = sqlite3.connect('instance/app.db')
    c = conn.cursor()

    # Создаем таблицы с IF NOT EXISTS
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS initiatives (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            author_id INTEGER NOT NULL,
            votes INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            initiative_id INTEGER NOT NULL,
            vote INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, initiative_id)
        )
    ''')
    
    # ... остальной код без изменений

    # Таблица голосов
    c.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            initiative_id INTEGER NOT NULL,
            vote INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, initiative_id),
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (initiative_id) REFERENCES initiatives (id)
        )
    ''')

    # Очистка старых данных
    c.execute("DELETE FROM votes")
    c.execute("DELETE FROM initiatives")
    c.execute("DELETE FROM users WHERE username != 'admin'")

    # Добавляем администратора
    admin_hash = generate_password_hash('Admin123!')
    c.execute("INSERT OR IGNORE INTO users (username, password, is_admin) VALUES (?, ?, ?)",
              ('admin', admin_hash, 1))

    # Добавляем тестовых пользователей (30+)
    user_ids = [1]  # ID администратора
    for i in range(2, 35):
        username = f'user{i}'
        password_hash = generate_password_hash('password123')
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)",
                  (username, password_hash))
        user_ids.append(i)

    # Добавляем тестовые инициативы (100+)
    initiative_titles = [
        "Внедрение гибкого графика работы",
        "Установка кулеров с водой на этажах",
        "Организация курсов английского языка",
        "Создание комнаты отдыха для сотрудников",
        "Внедрение системы удаленной работы",
        "Покупка новых ортопедических кресел",
        "Организация корпоративной библиотеки",
        "Введение дня здорового питания",
        "Установка велопарковки у офиса",
        "Создание программы наставничества"
    ]

    initiative_descriptions = [
        "Предлагаю внедрить гибкий график работы с 7:00 до 10:00 утра...",
        "Недостаток питьевой воды влияет на продуктивность сотрудников...",
        "Знание английского необходимо для работы с иностранными клиентами...",
        "Комната отдыха поможет сотрудникам восстанавливать силы...",
        "Удаленная работа повысит удовлетворенность сотрудников...",
        "Новые кресла улучшат осанку и снизят усталость...",
        "Корпоративная библиотека будет полезна для самообразования...",
        "День здорового питания улучшит культуру питания в коллективе...",
        "Велопарковка поощрит экологичный способ передвижения...",
        "Программа наставничества поможет новичкам быстрее адаптироваться..."
    ]

    # Генерируем 100+ инициатив
    for i in range(1, 105):
        title = f"{random.choice(initiative_titles)} #{i}"
        description = f"{random.choice(initiative_descriptions)} Это предложение номер {i}."
        author_id = random.choice(user_ids)
        votes = random.randint(-5, 25)
        
        # Создаем разную дату для каждой инициативы
        days_ago = random.randint(0, 180)
        created_at = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d %H:%M:%S')
        
        c.execute('''
            INSERT INTO initiatives (title, description, author_id, votes, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (title, description, author_id, votes, created_at))
        
        initiative_id = c.lastrowid
        
        # Добавляем голоса для этой инициативы
        voters = random.sample(user_ids, random.randint(5, 20))
        for voter_id in voters:
            if voter_id != author_id:  # Автор не голосует за свою инициативу
                vote_value = random.choice([1, -1])
                try:
                    c.execute('''
                        INSERT INTO votes (user_id, initiative_id, vote)
                        VALUES (?, ?, ?)
                    ''', (voter_id, initiative_id, vote_value))
                except sqlite3.IntegrityError:
                    pass  # Уже проголосовал

    conn.commit()
    conn.close()
    print("База данных инициализирована с тестовыми данными.")
    print("Папка instance создана, файл app.db создан.")
    print("Администратор: admin / Admin123!")
    print("Пользователи: user2-user34 / password123")

    

if __name__ == '__main__':
    init_db()

    