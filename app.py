from flask import Flask, request, render_template, redirect, url_for
import sqlite3, uuid, datetime, os

app = Flask(__name__)
DB = os.path.join(os.path.dirname(__file__), "data.db")

def db_conn():
    return sqlite3.connect(DB, check_same_thread=False)

def init_db():
    with db_conn() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS transactions(
            id TEXT PRIMARY KEY,
            date TEXT,
            month TEXT,
            type TEXT CHECK(type IN ('credit','debit')),
            amount REAL,
            description TEXT
        )
        """)
init_db()

def month_key(dt=None):
    dt = dt or datetime.date.today()
    return f"{dt.year}-{dt.month:02d}"

@app.route("/", methods=["GET"])
def home():
    m = request.args.get("month") or month_key()
    with db_conn() as con:
        rows = con.execute(
            "SELECT id,date,month,type,amount,description FROM transactions WHERE month=? ORDER BY date DESC, rowid DESC",
            (m,)
        ).fetchall()
        sums = con.execute("""
          SELECT
            SUM(CASE WHEN type='credit' THEN amount ELSE 0 END) AS total_credit,
            SUM(CASE WHEN type='debit'  THEN amount ELSE 0 END) AS total_debit
          FROM transactions WHERE month=?
        """, (m,)).fetchone()
        total_credit = sums[0] or 0.0
        total_debit  = sums[1] or 0.0
        available = total_credit - total_debit
    return render_template("index.html", month=m, transactions=rows,
                           total_credit=total_credit, total_debit=total_debit, available=available)

@app.route("/credit", methods=["POST"])
def credit():
    amount = float(request.form["amount"])
    desc = request.form.get("description","").strip()
    dt = datetime.date.today()
    with db_conn() as con:
        con.execute("INSERT INTO transactions(id,date,month,type,amount,description) VALUES(?,?,?,?,?,?)",
                    (str(uuid.uuid4()), dt.isoformat(), month_key(dt), "credit", amount, desc))
    return redirect(url_for("home", month=request.form.get("month") or month_key()))

@app.route("/debit", methods=["POST"])
def debit():
    amount = float(request.form["amount"])
    desc = request.form.get("description","").strip()
    dt = datetime.date.today()
    with db_conn() as con:
        con.execute("INSERT INTO transactions(id,date,month,type,amount,description) VALUES(?,?,?,?,?,?)",
                    (str(uuid.uuid4()), dt.isoformat(), month_key(dt), "debit", amount, desc))
    return redirect(url_for("home", month=request.form.get("month") or month_key()))

@app.route("/set-month", methods=["POST"])
def set_month():
    m = request.form.get("month") or month_key()
    return redirect(url_for("home", month=m))

@app.route("/delete/<tid>", methods=["POST"])
def delete_txn(tid):
    with db_conn() as con:
        con.execute("DELETE FROM transactions WHERE id=?", (tid,))
    return redirect(url_for("home", month=request.form.get("month") or month_key()))

if __name__ == "__main__":
    # For same-WiFi sharing, change to: app.run(host="0.0.0.0", port=5000, debug=True)
    app.run(debug=True)
