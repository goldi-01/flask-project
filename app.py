from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from datetime import datetime, timedelta
import sqlite3, uuid, random, string
app = Flask(__name__)
app.secret_key = 'demo-secret'
DB_FILE = "company.db"


# ---------------------- DB INIT ----------------------

def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                mobile TEXT,
                email TEXT UNIQUE,
                password TEXT,
                amount TEXT,
                signup_time TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS licenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT,
                email TEXT,
                client_id TEXT UNIQUE,
                transaction_id TEXT,
                duration INTEGER,
                machine_id TEXT,
                password TEXT,
                last_payment TEXT,
                valid_until TEXT,
                is_active INTEGER DEFAULT 1
            )
        """)

        conn.commit()
        conn.close()
        print("✅ Tables created successfully in company.db")

    except Exception as e:
        print("❌ Error creating tables:", e)

init_db()

# ---------------------- API LOGIN ----------------------

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"message": "Email and password required"}), 400

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT client_id, valid_until, is_active FROM licenses WHERE email=? AND password=?", (email, password))
    row = cursor.fetchone()
    conn.close()

    if row:
        client_id, valid_until, is_active = row
        today = datetime.now().date()
        valid_date = datetime.strptime(valid_until, "%Y-%m-%d").date()

        if not is_active or today > valid_date:
            return jsonify({"message": "License expired"}), 403

        return jsonify({"message": "Login successful", "client_id": client_id}), 200

    return jsonify({"message": "Invalid credentials"}), 401

# ---------------------- ROUTES ----------------------

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        mobile = request.form['mobile']
        email = request.form['email']
        password = request.form['password']
        amount = request.form['amount']
        signup_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email = ?", (email,))
        if c.fetchone():
            flash("Email already exists!", "danger")
            return redirect(url_for('signup'))

        c.execute("""
            INSERT INTO users (name, mobile, email, password, amount, signup_time)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, mobile, email, password, amount, signup_time))
        conn.commit()
        conn.close()

        session['email'] = email
        flash("Signup successful!", "success")
        return redirect(url_for('welcome'))

    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, password))
        user = c.fetchone()
        conn.close()

        if user:
            session['email'] = email
            flash("Login successful!", "success")
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid email or password!", "danger")
            return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/welcome')
def welcome():
    if 'email' not in session:
        flash("Please login or signup first", "warning")
        return redirect(url_for('login'))
    return render_template('welcome.html', email=session['email'])

@app.route('/admin')
def admin_dashboard():
    if 'email' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM licenses")
    rows = c.fetchall()
    conn.close()

    licenses = []
    today = datetime.today()

    for row in rows:
        try:
            valid_until = datetime.strptime(row["valid_until"], "%Y-%m-%d")
            status = "Valid" if row["is_active"] == 1 and today <= valid_until else "Expired"
        except:
            status = "Invalid Date"

        licenses.append({
            "client_id": row["client_id"],
            "client_name": row["client_name"],
            "email": row["email"],
            "machine_id": row["machine_id"],
            "last_payment": row["last_payment"],
            "valid_until": row["valid_until"],
            "status": status
        })

    return render_template("dashboard.html", licenses=licenses)

@app.route('/activate', methods=["GET", "POST"])
def activate():
    if 'email' not in session:
        flash("Please login first.", "warning")
        return redirect(url_for('login'))

    if request.method == "POST":
        client_name = request.form.get('client_name')
        email = request.form.get('email')
        client_id = request.form.get('client_id')     
        transaction_id = request.form.get('transaction_id')
        duration = int(request.form.get('duration'))

        today = datetime.today()
        valid_until = today + timedelta(days=duration)
        machine_id = str(uuid.uuid4())
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()

        c.execute("SELECT * FROM licenses WHERE client_id = ?", (client_id,))
        existing = c.fetchone()

        if existing:
            c.execute("""
                UPDATE licenses 
                SET transaction_id=?, last_payment=?, valid_until=?, is_active=1 
                WHERE client_id=?
            """, (transaction_id, today.strftime("%Y-%m-%d"), valid_until.strftime("%Y-%m-%d"), client_id))
            flash(f"License updated for {client_name}.", "info")
        else:
            c.execute("""
                INSERT INTO licenses (
                    client_name, email, client_id, transaction_id, duration, 
                    machine_id, password, last_payment, valid_until, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                client_name, email, client_id, transaction_id, duration,
                machine_id, password, today.strftime("%Y-%m-%d"), valid_until.strftime("%Y-%m-%d")
            ))
            flash(f"New license activated for {client_name}. Password: {password}", "success")

        conn.commit()
        conn.close()
        return redirect(url_for("admin_dashboard"))

    return render_template("activate.html")

@app.route('/deactivate/<client_id>')
def deactivate(client_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE licenses SET is_active = 0 WHERE client_id = ?", (client_id,))
    conn.commit()
    conn.close()
    flash(f"Client {client_id} deactivated.", "warning")
    return redirect(url_for("admin_dashboard"))

@app.route('/activate/<client_id>')
def reactivate(client_id):
    today = datetime.today()
    valid_until = today + timedelta(days=30)

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        UPDATE licenses SET is_active = 1, last_payment=?, valid_until=? 
        WHERE client_id=?
    """, (today.strftime("%Y-%m-%d"), valid_until.strftime("%Y-%m-%d"), client_id))
    conn.commit()
    conn.close()

    flash(f"Client {client_id} reactivated for 30 days.", "success")
    return redirect(url_for("admin_dashboard"))

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, host="0.0.0.0", port=5000)
