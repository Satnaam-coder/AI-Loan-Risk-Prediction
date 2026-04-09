from flask import Flask, render_template, request, redirect
from werkzeug.security import generate_password_hash, check_password_hash
import joblib
import numpy as np
import sqlite3

app = Flask(__name__)

# Load model
model = joblib.load('loan_model.pkl')
scaler = joblib.load('scaler.pkl')

# Create DB table
conn = sqlite3.connect('database.db')
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS loans (
    income REAL,
    credit REAL,
    annuity REAL,
    goods_price REAL,
    days_employed REAL,
    days_birth REAL,
    family_members REAL,
    gender INTEGER,
    car INTEGER,
    realty INTEGER,
    risk TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)''')

conn.commit()
conn.close()

conn = sqlite3.connect('database.db')
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    password TEXT,
    role TEXT
)''')

conn.commit()
conn.close()

# Home
@app.route('/')
def home():
    return redirect('/login')

# Prediction
@app.route('/predict', methods=['POST'])
def predict():
    try:
    
        data = [
            float(request.form['income']),
            float(request.form['credit']),
            float(request.form['annuity']),
            float(request.form['goods_price']),
            float(request.form['days_employed']),
            float(request.form['days_birth']),
            float(request.form['family_members']),
            float(request.form['gender']),
            0, 0, 0, 0,   # simplified for now
            float(request.form['car']),
            float(request.form['realty'])
        ]

        data_scaled = scaler.transform([data])

        prob = model.predict_proba(data_scaled)[0][1]
        risk_score = round(prob * 100, 2)
        
        # ✅ VALIDATION

        if float(data[0]) <= 0:
         return render_template('index.html', error="Income must be positive")

        if float(data[1]) <= 0:
         return render_template('index.html', error="Credit must be positive")

        if float(data[6]) <= 0:
         return render_template('index.html', error="Family members must be valid")


        # 🔥 ADVANCED RISK SYSTEM
        if prob > 0.7:
            result = f"🚨 High Risk ({risk_score}%)- Loan may default due to high burden"
        elif prob > 0.4:
            result = f"⚠️ Medium Risk ({risk_score}%) - Needs review"
        else:
            result = f"✅ Low Risk ({risk_score}%)- Safe applicant"
    
            
        # Save to DB
        conn = sqlite3.connect('database.db')
        c = conn.cursor()

        c.execute(""" INSERT INTO loans (
                      income, credit, annuity, goods_price,
                      days_employed, days_birth, family_members,
                      gender, car, realty, risk )VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
                      data[0], data[1], data[2], data[3],
                      data[4], data[5], data[6],
                      data[7], data[12], data[13],
                      result))

        conn.commit()
        conn.close()

        return render_template('index.html', prediction_text=result)

    except Exception as e:
        return render_template('index.html', prediction_text="Something went wrong!")

# History Page
@app.route('/history')
def history():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute("SELECT * FROM loans")
    data = c.fetchall()
    conn.close()

    return render_template('history.html', data=data)

@app.route('/dashboard')
def dashboard():

    conn = sqlite3.connect('database.db')
    c = conn.cursor()

    total = c.execute("SELECT COUNT(*) FROM loans").fetchone()[0]
    high = c.execute("SELECT COUNT(*) FROM loans WHERE risk LIKE '%High%'").fetchone()[0]
    medium = c.execute("SELECT COUNT(*) FROM loans WHERE risk LIKE '%Medium%'").fetchone()[0]
    low = c.execute("SELECT COUNT(*) FROM loans WHERE risk LIKE '%Low%'").fetchone()[0]

    conn.close()

    return render_template('dashboard.html',
                           total=total,
                           high=high,
                           medium=medium,
                           low=low)

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']


        conn = sqlite3.connect('database.db')
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE username=?", (user,))
        result = c.fetchone()

        conn.close()

        if result and check_password_hash(result[2], pwd):
            if result[3] == "admin":
                return redirect('/dashboard')
            else:
             return redirect('/home')
        else:
            return render_template('login.html', error="Invalid username or password")

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']

        hashed_pwd = generate_password_hash(pwd)

        conn = sqlite3.connect('database.db')
        c = conn.cursor()

        # check if user exists
        c.execute("SELECT * FROM users WHERE username=?", (user,))
        if c.fetchone():
            return render_template('signup.html', error="Username already exists")

        c.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (user, hashed_pwd, "user"))
        conn.commit()
        conn.close()

        return redirect('/login')

    return render_template('signup.html')

@app.route('/home')
def main_home():
    return render_template('index.html')

@app.route('/logout')
def logout():
    return redirect('/login')

import csv
from flask import Response

@app.route('/download')
def download():
    import sqlite3

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    cur.execute("SELECT * FROM predictions")
    data = cur.fetchall()

    conn.close()

    def generate():
        yield "Income,Loan,Result\n"
        for row in data:
            yield f"{row[0]},{row[1]},{row[-1]}\n"

    return Response(generate(),
        mimetype='text/csv',
        headers={"Content-Disposition": "attachment;filename=data.csv"})

if __name__ == "__main__":
    app.run(debug=True)