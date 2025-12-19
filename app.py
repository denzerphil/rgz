from flask import Flask, render_template, request, jsonify, session, redirect, url_for, g
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_secret_key_here_change_this_in_production'
DATABASE = '/home/denzerphil/rgz/app.db'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Главная страница
@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    limit = 20
    offset = (page - 1) * limit

    db = get_db()
    initiatives = db.execute('''
        SELECT i.*, u.username FROM initiatives i
        JOIN users u ON i.author_id = u.id
        ORDER BY i.created_at DESC
        LIMIT ? OFFSET ?
    ''', (limit, offset)).fetchall()

    total = db.execute('SELECT COUNT(*) FROM initiatives').fetchone()[0]

    return render_template('index.html',
                           initiatives=initiatives,
                           page=page,
                           total=total,
                           limit=limit,
                           user=session.get('user'))

# API для голосования
@app.route('/api/vote', methods=['POST'])
def api_vote():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Не авторизован'})

    data = request.json
    initiative_id = data.get('initiative_id')
    vote_value = data.get('vote')  # 1 или -1

    if not initiative_id or vote_value not in [1, -1]:
        return jsonify({'success': False, 'message': 'Неверные данные'})

    db = get_db()
    user_id = session['user_id']

    # Проверяем, не голосовал ли уже
    existing = db.execute('SELECT * FROM votes WHERE user_id = ? AND initiative_id = ?',
                          (user_id, initiative_id)).fetchone()

    if existing:
        db.execute('DELETE FROM votes WHERE id = ?', (existing['id'],))
        # Отменяем предыдущий голос
        db.execute('UPDATE initiatives SET votes = votes - ? WHERE id = ?',
                   (existing['vote'], initiative_id))

    # Добавляем новый голос
    db.execute('INSERT INTO votes (user_id, initiative_id, vote) VALUES (?, ?, ?)',
               (user_id, initiative_id, vote_value))
    db.execute('UPDATE initiatives SET votes = votes + ? WHERE id = ?',
               (vote_value, initiative_id))

    # Проверяем, не упали ли голоса ниже -10
    initiative = db.execute('SELECT * FROM initiatives WHERE id = ?', (initiative_id,)).fetchone()
    if initiative and initiative['votes'] < -10:
        db.execute('DELETE FROM initiatives WHERE id = ?', (initiative_id,))
        db.execute('DELETE FROM votes WHERE initiative_id = ?', (initiative_id,))

    db.commit()
    return jsonify({'success': True})

# API для добавления инициативы
@app.route('/api/add', methods=['POST'])
def api_add_initiative():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Не авторизован'})

    data = request.json
    title = data.get('title')
    description = data.get('description')

    if not title or not description:
        return jsonify({'success': False, 'message': 'Заполните все поля'})

    db = get_db()
    db.execute('INSERT INTO initiatives (title, description, author_id) VALUES (?, ?, ?)',
               (title, description, session['user_id']))
    db.commit()

    return jsonify({'success': True})

# Авторизация
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        db = get_db()
        user = db.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user'] = user['username']
            return redirect(url_for('index'))
        else:
            return render_template('login.html', error='Неверный логин или пароль')

    return render_template('login.html')

# Регистрация
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not username or not password:
            return render_template('register.html', error='Заполните все поля')

        db = get_db()
        hash_pass = generate_password_hash(password)

        try:
            db.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hash_pass))
            db.commit()
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            return render_template('register.html', error='Пользователь уже существует')

    return render_template('register.html')

# Выход
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Страница добавления инициативы
@app.route('/add_initiative')
def add_initiative_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('add_initiative.html', user=session.get('user'))

# Профиль пользователя
@app.route('/profile')
def profile_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    user_id = session['user_id']
    
    try:
        # Получаем данные пользователя
        user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        
        if not user:
            session.clear()
            return redirect(url_for('login'))
        
        # Статистика пользователя
        stats = {
            'initiatives_count': db.execute(
                'SELECT COUNT(*) FROM initiatives WHERE author_id = ?', 
                (user_id,)
            ).fetchone()[0] or 0,
            'total_votes': db.execute('''
                SELECT COALESCE(SUM(vote), 0) FROM votes 
                WHERE user_id = ?
            ''', (user_id,)).fetchone()[0] or 0,
            'positive_votes': db.execute(
                'SELECT COUNT(*) FROM votes WHERE user_id = ? AND vote = 1', 
                (user_id,)
            ).fetchone()[0] or 0,
            'negative_votes': db.execute(
                'SELECT COUNT(*) FROM votes WHERE user_id = ? AND vote = -1', 
                (user_id,)
            ).fetchone()[0] or 0,
            'initiatives_votes': db.execute('''
                SELECT COALESCE(SUM(votes), 0) FROM initiatives 
                WHERE author_id = ?
            ''', (user_id,)).fetchone()[0] or 0
        }
        
        return render_template('profile.html', 
                             user=dict(user),  # Преобразуем Row в dict для безопасности
                             stats=stats,
                             session_user=session.get('user'))
    except Exception as e:
        print(f"Ошибка в профиле: {str(e)}")
        return f"Ошибка сервера: {str(e)}", 500
# Мои инициативы
@app.route('/my_initiatives')
def my_initiatives_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    initiatives = db.execute('''
        SELECT * FROM initiatives 
        WHERE author_id = ? 
        ORDER BY created_at DESC
    ''', (session['user_id'],)).fetchall()
    
    return render_template('my_initiatives.html', 
                           initiatives=initiatives, 
                           user=session.get('user'))

# Админ-панель
@app.route('/admin')
def admin_panel_page():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    
    # Проверка прав администратора
    user = db.execute('SELECT is_admin FROM users WHERE id = ?', 
                      (session['user_id'],)).fetchone()
    if not user or not user['is_admin']:
        return redirect(url_for('index'))
    
    # Данные для админки
    users = db.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
    
    stats = {
        'total_users': db.execute('SELECT COUNT(*) FROM users').fetchone()[0],
        'total_initiatives': db.execute('SELECT COUNT(*) FROM initiatives').fetchone()[0],
        'active_initiatives': db.execute('SELECT COUNT(*) FROM initiatives WHERE votes > -10').fetchone()[0],
        'deleted_initiatives': db.execute('SELECT COUNT(*) FROM initiatives WHERE votes <= -10').fetchone()[0]
    }
    
    return render_template('admin.html', 
                           users=users, 
                           stats=stats, 
                           user=session.get('user'))

# API для поиска инициатив (админка)
@app.route('/api/admin/search')
def api_admin_search():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Не авторизован'})
    
    # Проверка прав администратора
    db = get_db()
    admin_check = db.execute('SELECT is_admin FROM users WHERE id = ?', 
                             (session['user_id'],)).fetchone()
    if not admin_check or not admin_check['is_admin']:
        return jsonify({'success': False, 'message': 'Нет прав администратора'})
    
    query = request.args.get('q', '')
    if not query:
        return jsonify({'initiatives': []})
    
    # Поиск по названию и автору
    initiatives = db.execute('''
        SELECT i.*, u.username as author 
        FROM initiatives i
        JOIN users u ON i.author_id = u.id
        WHERE i.title LIKE ? OR u.username LIKE ?
        ORDER BY i.created_at DESC
        LIMIT 20
    ''', (f'%{query}%', f'%{query}%')).fetchall()
    
    result = []
    for init in initiatives:
        result.append({
            'id': init['id'],
            'title': init['title'],
            'author': init['author'],
            'votes': init['votes'],
            'created_at': init['created_at'][:10]
        })
    
    return jsonify({'initiatives': result})

# API для удаления инициативы
@app.route('/api/initiative/<int:initiative_id>', methods=['DELETE'])
def api_delete_initiative(initiative_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Не авторизован'})
    
    db = get_db()
    
    # Получаем инициативу
    initiative = db.execute('SELECT * FROM initiatives WHERE id = ?', 
                            (initiative_id,)).fetchone()
    
    if not initiative:
        return jsonify({'success': False, 'message': 'Инициатива не найдена'})
    
    # Проверяем права: автор или администратор
    user = db.execute('SELECT is_admin FROM users WHERE id = ?', 
                      (session['user_id'],)).fetchone()
    
    is_author = initiative['author_id'] == session['user_id']
    is_admin = user and user['is_admin']
    
    if not (is_author or is_admin):
        return jsonify({'success': False, 'message': 'Нет прав на удаление'})
    
    # Удаляем голоса и инициативу
    try:
        db.execute('DELETE FROM votes WHERE initiative_id = ?', (initiative_id,))
        db.execute('DELETE FROM initiatives WHERE id = ?', (initiative_id,))
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# API для админки - переключение статуса администратора
@app.route('/api/admin/toggle/<int:user_id>', methods=['POST'])
def api_admin_toggle(user_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Не авторизован'})
    
    db = get_db()
    
    # Проверяем, является ли текущий пользователь администратором
    admin_check = db.execute('SELECT is_admin FROM users WHERE id = ?', 
                             (session['user_id'],)).fetchone()
    if not admin_check or not admin_check['is_admin']:
        return jsonify({'success': False, 'message': 'Нет прав администратора'})
    
    # Меняем статус пользователя
    target_user = db.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not target_user:
        return jsonify({'success': False, 'message': 'Пользователь не найден'})
    
    new_status = 0 if target_user['is_admin'] else 1
    db.execute('UPDATE users SET is_admin = ? WHERE id = ?', (new_status, user_id))
    db.commit()
    
    return jsonify({'success': True})

# API для админки - удаление пользователя
@app.route('/api/admin/delete/user/<int:user_id>', methods=['DELETE'])
def api_admin_delete_user(user_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Не авторизован'})
    
    if session['user_id'] == user_id:
        return jsonify({'success': False, 'message': 'Нельзя удалить себя'})
    
    db = get_db()
    
    # Проверка прав администратора
    admin_check = db.execute('SELECT is_admin FROM users WHERE id = ?', 
                             (session['user_id'],)).fetchone()
    if not admin_check or not admin_check['is_admin']:
        return jsonify({'success': False, 'message': 'Нет прав администратора'})
    
    # Удаляем пользователя и его инициативы
    try:
        db.execute('DELETE FROM votes WHERE user_id = ?', (user_id,))
        db.execute('DELETE FROM initiatives WHERE author_id = ?', (user_id,))
        db.execute('DELETE FROM users WHERE id = ?', (user_id,))
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# Обработка 404 ошибок
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    # Проверяем и создаем БД при первом запуске
    if not os.path.exists('instance'):
        os.makedirs('instance')
    
    if not os.path.exists(DATABASE):
        from database import init_db
        init_db()
        print("База данных создана. Администратор: admin / Admin123!")
    
    app.run(debug=True, port=5000)

    # Функция для проверки и восстановления базы данных
def check_and_repair_db():
    if not os.path.exists('instance'):
        os.makedirs('instance')
    
    db_path = DATABASE
    needs_repair = False
    
    if os.path.exists(db_path):
        try:
            test_conn = sqlite3.connect(db_path)
            test_cursor = test_conn.cursor()
            # Пробуем выполнить простой запрос
            test_cursor.execute("SELECT 1")
            test_conn.close()
        except sqlite3.Error:
            needs_repair = True
            print("Обнаружена поврежденная база данных, пересоздаю...")
            os.remove(db_path)
    
    if not os.path.exists(db_path) or needs_repair:
        print("Создание новой базы данных...")
        from database import init_db
        init_db()

if __name__ == '__main__':
    # Проверяем и восстанавливаем БД при запуске
    check_and_repair_db()
    
    app.run(debug=True, port=5000)