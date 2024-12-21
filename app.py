from flask import Flask, request, session, render_template, redirect, url_for, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from werkzeug.security import generate_password_hash

password = "adminpassword"  # Ваш пароль
hashed_password = generate_password_hash(password)
print(hashed_password)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'super_secret_key'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Подключение к базе данных
def db_connect():
    conn = psycopg2.connect(
        host="127.0.0.1",
        port="5433",
        database="teya_adalinskaya_knowledge_base_second",
        user="teya_adalinskaya_knowledge_base",
        password="postgres"
    )
    cur = conn.cursor(cursor_factory=RealDictCursor)
    return conn, cur

def db_close(conn, cur):
    conn.commit()
    cur.close()
    conn.close()

# Проверка разрешённых файлов
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Главная страница
@app.route("/")
def index():
    conn, cur = db_connect()
    cur.execute("""
        SELECT ads.id, ads.title, ads.content, users.username AS author, users.avatar, 
               CASE WHEN %s IS NOT NULL THEN users.email ELSE NULL END AS author_email
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
        cur.execute("""
            INSERT INTO users (username, email, password, avatar, about) 
            VALUES (%s, %s, %s, %s, %s);
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
        cur.execute("SELECT * FROM users WHERE username = %s;", (username,))
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
        return redirect('/login')

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

        conn, cur = db_connect()
        cur.execute("""
            INSERT INTO ads (title, content, author_id)
            VALUES (%s, %s, %s);
        """, (title, content, session['user_id']))
        db_close(conn, cur)
        return redirect('/')
    return render_template("create_ad.html")

# Редактирование объявления
@app.route("/ads/edit/<int:ad_id>", methods=['GET', 'POST'])
def edit_ad(ad_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn, cur = db_connect()

    if request.method == 'GET':
        cur.execute("SELECT * FROM ads WHERE id = %s AND author_id = %s;", (ad_id, session['user_id']))
        ad = cur.fetchone()
        db_close(conn, cur)
        if not ad:
            return "Объявление не найдено или у вас нет прав для редактирования"
        return render_template("edit_ad.html", ad=ad)

    title = request.form['title']
    content = request.form['content']
    cur.execute("""
        UPDATE ads SET title = %s, content = %s WHERE id = %s AND author_id = %s;
    """, (title, content, ad_id, session['user_id']))
    db_close(conn, cur)
    return redirect('/')

# Удаление объявления
@app.route("/ads/delete/<int:ad_id>", methods=['POST'])
def delete_ad(ad_id):
    if 'user_id' not in session:
        return redirect('/login')

    conn, cur = db_connect()
    cur.execute("DELETE FROM ads WHERE id = %s AND author_id = %s;", (ad_id, session['user_id']))
    db_close(conn, cur)
    return redirect('/')

# JSON-RPC API для администрирования
@app.route("/api", methods=["POST"])
def api():
    data = request.json
    method = data.get("method")
    params = data.get("params", {})

    conn, cur = db_connect()

    if method == "delete_user" and session.get('is_admin'):
        cur.execute("DELETE FROM users WHERE id = %s;", (params['user_id'],))
        db_close(conn, cur)
        return jsonify({"result": "User deleted successfully"})
    
    if method == "delete_ad" and session.get('is_admin'):
        cur.execute("DELETE FROM ads WHERE id = %s;", (params['ad_id'],))
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
    cur.execute("SELECT id, username, email FROM users WHERE NOT is_admin;")
    users = cur.fetchall()
    db_close(conn, cur)
    return render_template("manage_users.html", users=users)
