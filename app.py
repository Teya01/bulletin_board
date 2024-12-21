from flask import Flask, request, session, render_template, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from os import path
import sqlite3

password = "adminpassword"  # Ваш пароль
hashed_password = generate_password_hash(password)
print(hashed_password)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'секретно-секретный секрет')
app.config['DB_TYPE'] = os.getenv('DB_TYPE', 'postgres')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Подключение к базе данных
def db_connect():
    if app.config['DB_TYPE'] == 'postgres':
        conn = psycopg2.connect(
            host="127.0.0.1",
            port="5433",
            database="teya_adalinskaya_knowledge_base_second",
            user="teya_adalinskaya_knowledge_base",
            password="postgres"
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
    else:
        dir_path = path.dirname(path.realpath(__file__))
        db_path = path.join(dir_path, "database.db")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

    return conn, cur

def db_close(conn, cur):
    conn.commit()
    cur.close()
    conn.close()

# Проверка разрешённых файлов
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Формирование правильного плейсхолдера для запросов
def get_placeholder():
    return "%s" if app.config['DB_TYPE'] == 'postgres' else "?"

# Главная страница
@app.route("/")
def index():
    conn, cur = db_connect()
    placeholder = get_placeholder()
    cur.execute(f"""
        SELECT ads.id, ads.title, ads.content, users.username AS author, users.avatar, 
               CASE WHEN {placeholder} IS NOT NULL THEN users.email ELSE NULL END AS author_email
        FROM ads
        JOIN users ON ads.author_id = users.id;
    """, (session.get('user_id'),))
    ads = cur.fetchall()
    db_close(conn, cur)
    return render_template("index.html", ads=ads, user=session.get('username'), fio="Тэя Адалинская", group="ФБИ-24")

# Регистрация
@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        about = request.form.get('about', '')

        avatar_filename = None
        if 'avatar' in request.files:
            avatar = request.files['avatar']
            if avatar.filename != '' and allowed_file(avatar.filename):
                avatar_filename = secure_filename(avatar.filename)
                avatar.save(os.path.join(app.config['UPLOAD_FOLDER'], avatar_filename))

        hashed_password = generate_password_hash(password)

        conn, cur = db_connect()
        placeholder = get_placeholder()
        cur.execute(f"""
            INSERT INTO users (username, email, password, avatar, about) 
            VALUES ({placeholder}, {placeholder}, {placeholder}, {placeholder}, {placeholder});
        """, (username, email, hashed_password, avatar_filename, about))
        db_close(conn, cur)
        return redirect('/login')
    return render_template("register.html")

# Авторизация
@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn, cur = db_connect()
        placeholder = get_placeholder()
        cur.execute(f"SELECT * FROM users WHERE username = {placeholder};", (username,))
        user = cur.fetchone()
        db_close(conn, cur)

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']
            return redirect('/')
        return "Неверный логин или пароль"
    return render_template("login.html")

# Выход
@app.route("/logout")
def logout():
    session.clear()
    return redirect('/')

# Создание объявления
@app.route("/ads/create", methods=['GET', 'POST'])
def create_ad():
    if 'user_id' not in session:
        return redirect('/login')  # Перенаправление на страницу логина, если пользователь не авторизован

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        author_id = session['user_id']  # Получаем user_id из сессии

        if not title or not content:
            return "Заполните все поля."  # Проверка на пустые поля

        conn, cur = db_connect()
        placeholder = get_placeholder()
        
        # Выполняем запрос с использованием параметризированного запроса для предотвращения SQL инъекций
        cur.execute(f"""
            INSERT INTO ads (title, content, author_id)
            VALUES ({placeholder}, {placeholder}, {placeholder});
        """, (title, content, author_id))  # Передаем title, content и author_id
        db_close(conn, cur)
        return redirect('/')  # Перенаправление на главную страницу после успешного создания объявления

    return render_template("create_ad.html")


# Редактирование объявления
@app.route("/ads/edit/<int:ad_id>", methods=['GET', 'POST'])
def edit_ad(ad_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn, cur = db_connect()
    placeholder = get_placeholder()

    if request.method == 'GET':
        cur.execute(f"SELECT * FROM ads WHERE id = {placeholder} AND author_id = {placeholder};", (ad_id, session['user_id']))
        ad = cur.fetchone()
        db_close(conn, cur)
        if not ad:
            return "Объявление не найдено или у вас нет прав для редактирования"
        return render_template("edit_ad.html", ad=ad)

    title = request.form['title']
    content = request.form['content']
    cur.execute(f"""
        UPDATE ads SET title = {placeholder}, content = {placeholder} WHERE id = {placeholder} AND author_id = {placeholder};
    """, (title, content, ad_id, session['user_id']))
    db_close(conn, cur)
    return redirect('/')

# Удаление объявления
@app.route("/ads/delete/<int:ad_id>", methods=['POST'])
def delete_ad(ad_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn, cur = db_connect()
    placeholder = get_placeholder()
    cur.execute(f"DELETE FROM ads WHERE id = {placeholder} AND author_id = {placeholder};", (ad_id, session['user_id']))
    db_close(conn, cur)
    return redirect('/')

# JSON-RPC API для администрирования
@app.route("/api", methods=["POST"])
def api():
    data = request.json
    method = data.get("method")
    params = data.get("params", {})

    conn, cur = db_connect()
    placeholder = get_placeholder()

    if method == "delete_user" and session.get('is_admin'):
        cur.execute(f"DELETE FROM users WHERE id = {placeholder};", (params['user_id'],))
        db_close(conn, cur)
        return jsonify({"result": "User deleted successfully"})
    
    if method == "delete_ad" and session.get('is_admin'):
        cur.execute(f"DELETE FROM ads WHERE id = {placeholder};", (params['ad_id'],))
        db_close(conn, cur)
        return jsonify({"result": "Ad deleted successfully"})

    db_close(conn, cur)
    return jsonify({"error": "Unknown method"}), 400

if __name__ == "__main__":
    app.run(debug=True)

@app.route("/admin/users", methods=["GET", "POST"])
def manage_users():
    if not session.get('is_admin'):
        return redirect('/')

    conn, cur = db_connect()
    placeholder = get_placeholder()
    cur.execute(f"SELECT id, username, email FROM users WHERE NOT is_admin;")
    users = cur.fetchall()
    db_close(conn, cur)
    return render_template("manage_users.html", users=users)


import sqlite3

def modify_column():
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    # Создание новой таблицы с измененным столбцом
    cur.execute("""
        CREATE TABLE ads_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content VARCHAR(255),  -- Новый тип данных
            author_id INTEGER NOT NULL,
            FOREIGN KEY (author_id) REFERENCES users(id)
        );
    """)

    # Перенос данных из старой таблицы в новую
    cur.execute("""
        INSERT INTO ads_new (id, title, content, author_id)
        SELECT id, title, content, author_id FROM ads;
    """)

    # Удаление старой таблицы
    cur.execute("DROP TABLE ads;")

    # Переименование новой таблицы
    cur.execute("ALTER TABLE ads_new RENAME TO ads;")

    conn.commit()
    conn.close()

modify_column()
