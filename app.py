from flask import Flask, request, render_template, redirect, session, jsonify, url_for
import mysql.connector
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "your_secret_key"
CORS(app)

# Database Connection
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="bank_system"
        )
        return conn
    except mysql.connector.Error as e:
        print(f"Database connection error: {e}")
        return None

# Home Page


@app.route("/")

def home():
    if "user_id" in session:
        return redirect("/dashboard")
    elif "admin" in session:
        return redirect("/admin_dashboard")
    return render_template("index.html")

# User Registration
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
            conn.commit()
            return redirect("/login")
        except mysql.connector.IntegrityError:
            return "User already exists!"
        finally:
            cursor.close()
            conn.close()
    return render_template("register.html")

# User Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user[1], password):
            session["user_id"] = user[0]
            return redirect("/dashboard")
        return "Invalid credentials!"
    return render_template("login.html")

# User Dashboard
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch user balance
    cursor.execute("SELECT balance FROM users WHERE id=%s", (session["user_id"],))
    balance = cursor.fetchone()["balance"]

    # Fetch loan status
    cursor.execute("SELECT amount, status FROM loans WHERE user_id=%s ORDER BY id DESC LIMIT 1", (session["user_id"],))
    loan = cursor.fetchone()

    cursor.close()
    conn.close()

    loan_status = None
    loan_amount = None
    if loan:
        loan_status = loan["status"]
        loan_amount = loan["amount"]

    return render_template("dashboard.html", balance=balance, loan_status=loan_status, loan_amount=loan_amount)


# Admin Login
@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admins WHERE username=%s", (username,))
        admin = cursor.fetchone()
        cursor.close()
        conn.close()

        # Check if the password field is empty or missing
        if not admin or not admin.get("password"):
            return "Invalid credentials! Admin password is missing or incorrect."

        if check_password_hash(admin["password"], password):
            session["admin"] = admin["username"]
            return redirect("/admin_dashboard")
        
        return "Invalid credentials!"
    
    return render_template("admin_login.html")

# Admin Dashboard
@app.route("/admin_dashboard")
def admin_dashboard():
    if "admin" not in session:
        return redirect("/admin_login")
    return render_template("admin_dashboard.html")

# Admin - Manage Users
@app.route("/admin/users")
def admin_users():
    if "admin" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("admin_users.html", users=users)

# Admin - Delete User
@app.route("/admin/delete_user/<int:user_id>")
def admin_delete_user(user_id):
    if "admin" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect("/admin/users")

# Admin - View Transactions
@app.route("/admin/transactions")
def admin_transactions():
    if "admin" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # ✅ Ensure we select the `timestamp` column explicitly
    cursor.execute("SELECT transactions.id, transactions.amount, transactions.transaction_type, transactions.timestamp, users.username FROM transactions JOIN users ON transactions.user_id = users.id")
    
    transactions = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("admin_transactions.html", transactions=transactions)


# Admin - Manage Loans
@app.route("/admin/loans")
def admin_loans():
    if "admin" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT loans.*, users.username FROM loans JOIN users ON loans.user_id = users.id")
    loans = cursor.fetchall()
    cursor.close()
    conn.close()

    return render_template("admin_loans.html", loans=loans)

# Admin - Approve Loan
@app.route("/admin/approve_loan/<int:loan_id>")
def admin_approve_loan(loan_id):
    if "admin" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE loans SET status='approved' WHERE id=%s", (loan_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect("/admin/loans")

# Admin - Reject Loan
@app.route("/admin/reject_loan/<int:loan_id>")
def admin_reject_loan(loan_id):
    if "admin" not in session:
        return redirect("/admin_login")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE loans SET status='rejected' WHERE id=%s", (loan_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect("/admin/loans")

# Deposit Money
@app.route("/deposit", methods=["POST"])
def deposit():
    if "user_id" not in session:
        return redirect("/login")

    amount = float(request.form["amount"])
    
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Check current balance before updating
        cursor.execute("SELECT balance FROM users WHERE id = %s", (session["user_id"],))
        current_balance = cursor.fetchone()
        
        if current_balance is None:
            return "User not found!", 400

        # Ensure balance is numeric
        current_balance = float(current_balance[0]) if current_balance[0] else 0

        # Update balance
        new_balance = current_balance + amount
        cursor.execute("UPDATE users SET balance = %s WHERE id = %s", (new_balance, session["user_id"]))

        # Insert transaction
        cursor.execute("INSERT INTO transactions (user_id, transaction_type, amount) VALUES (%s, 'deposit', %s)", (session["user_id"], amount))

        conn.commit()

    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")  # ✅ Debugging step

    finally:
        cursor.close()
        conn.close()
    
    return redirect("/dashboard")


# Apply for Loan
@app.route("/apply_loan", methods=["POST"])
def apply_loan():
    if "user_id" not in session:
        return redirect("/login")

    amount = float(request.form["amount"])
    interest_rate = 5.0
    duration = int(request.form["duration"])

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO loans (user_id, amount, interest_rate, duration, status) VALUES (%s, %s, %s, %s, 'pending')",
                   (session["user_id"], amount, interest_rate, duration))
    conn.commit()
    cursor.close()
    conn.close()
    
    return redirect("/dashboard")



# Logout
@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("admin", None)
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True, port=5000)
