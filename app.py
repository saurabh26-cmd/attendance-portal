import os, sqlite3, calendar
from datetime import date
from functools import wraps
from flask import Flask, request, redirect, url_for, session, flash, render_template_string
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret")
DB = os.environ.get("DB_FILE", "attendance.db")

def db():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def init():
    c = db()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      login_id TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL DEFAULT 'manager',
      location TEXT DEFAULT '',
      active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS employees(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      employee_code TEXT NOT NULL,
      name TEXT NOT NULL,
      designation TEXT NOT NULL,
      location TEXT NOT NULL,
      active INTEGER DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS attendance(
      employee_id INTEGER NOT NULL,
      att_date TEXT NOT NULL,
      status TEXT NOT NULL,
      PRIMARY KEY(employee_id, att_date)
    );
    """)
    if not c.execute("SELECT 1 FROM users WHERE login_id='admin'").fetchone():
        c.execute(
            "INSERT INTO users(name,login_id,password_hash,role,location) VALUES(?,?,?,?,?)",
            ("Admin", "admin", generate_password_hash("Admin@123"), "admin", "ALL")
        )
    if not c.execute("SELECT 1 FROM employees").fetchone():
        c.executemany(
            "INSERT INTO employees(employee_code,name,designation,location) VALUES(?,?,?,?)",
            [
                ("FK001", "Rahul", "Picker/Packer", "Noida STC"),
                ("FK002", "Amit", "Picker/Packer", "Noida STC"),
                ("FK003", "Ravi", "Inward Executive", "Noida STC"),
                ("FK004", "Suresh", "Picker/Packer", "Ghaziabad")
            ]
        )
    c.commit()
    c.close()

CSS = """
<style>
body{font-family:Arial,sans-serif;margin:0;background:#f4f6f8;color:#17202a}
.nav{background:#111827;color:#fff;padding:14px 18px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
.nav a{color:#fff;margin-left:14px;text-decoration:none}
.wrap{max-width:1200px;margin:22px auto;padding:0 14px}
.card{background:#fff;border-radius:10px;padding:16px;margin-bottom:16px;box-shadow:0 2px 8px #0001}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
input,select,button{padding:9px;border:1px solid #ccd3da;border-radius:6px;box-sizing:border-box}
input,select{width:100%}
button{background:#111827;color:#fff;cursor:pointer}
.scroll{overflow:auto}
table{border-collapse:collapse;width:100%}
th,td{border:1px solid #ddd;padding:6px;text-align:center;white-space:nowrap}
.emp{text-align:left;position:sticky;left:0;background:#fff}
.flash{padding:10px;border-radius:6px;margin-bottom:10px;background:#dcfce7}
.small{font-size:13px;color:#667085}
a.button{display:inline-block;background:#111827;color:#fff;padding:10px 14px;border-radius:6px;text-decoration:none}
</style>
"""

NAV = """
<div class="nav">
  <b>Monthly Attendance Portal</b>
  <div>
  {% if session.get('uid') %}
    {{ session.get('name') }} ({{ session.get('role') }})
    <a href="/dashboard">Dashboard</a>
    {% if session.get('role') == 'admin' %}
      <a href="/users">Users</a>
      <a href="/employees">Employees</a>
    {% endif %}
    <a href="/monthly">Attendance</a>
    <a href="/report">Report</a>
    <a href="/logout">Logout</a>
  {% endif %}
  </div>
</div>
"""

def page(body):
    flashes = "".join(
        f"<div class='flash'>{m}</div>" for m in session.pop("_flashes", [])
    )
    return CSS + NAV + f"<div class='wrap'>{flashes}{body}</div>"

def msg(text):
    session.setdefault("_flashes", []).append(text)

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "uid" not in session:
            return redirect("/")
        return f(*args, **kwargs)
    return wrapper

def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            msg("Admin access required.")
            return redirect("/dashboard")
        return f(*args, **kwargs)
    return wrapper

def allowed_locations(c):
    if session.get("role") == "admin":
        return [r["location"] for r in c.execute(
            "SELECT DISTINCT location FROM employees WHERE location<>'' ORDER BY location"
        ).fetchall()]
    return [session.get("location")] if session.get("location") else []

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        c = db()
        u = c.execute(
            "SELECT * FROM users WHERE login_id=? AND active=1",
            (request.form.get("login_id", "").strip(),)
        ).fetchone()
        c.close()
        if u and check_password_hash(u["password_hash"], request.form.get("password", "")):
            session.clear()
            session.update(uid=u["id"], name=u["name"], role=u["role"], location=u["location"])
            return redirect("/dashboard")
        msg("Invalid Login ID or Password.")
    return page("""
    <div class="card" style="max-width:420px;margin:70px auto">
      <h2>Monthly Attendance Portal</h2>
      <p class="small">Admin creates manager IDs and assigns warehouses.</p>
      <form method="post">
        <p>Login ID<br><input name="login_id" required></p>
        <p>Password<br><input name="password" type="password" required></p>
        <button type="submit">Login</button>
      </form>
      <p class="small">Demo Admin: <b>admin</b> / <b>Admin@123</b></p>
    </div>
    """)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/dashboard")
@login_required
def dashboard():
    c = db()
    if session["role"] == "admin":
        n = c.execute("SELECT COUNT(*) n FROM employees WHERE active=1").fetchone()["n"]
    else:
        n = c.execute(
            "SELECT COUNT(*) n FROM employees WHERE active=1 AND location=?",
            (session["location"],)
        ).fetchone()["n"]
    locs = allowed_locations(c)
    c.close()
    return page(f"""
      <h2>Dashboard</h2>
      <div class="grid">
        <div class="card"><span class="small">Active Employees</span><h1>{n}</h1></div>
        <div class="card"><span class="small">Location(s)</span><h3>{', '.join(locs)}</h3></div>
      </div>
      <div class="card">
        <a class="button" href="/monthly">Fill Monthly Attendance</a>
      </div>
    """)

@app.route("/users", methods=["GET", "POST"])
@login_required
@admin_required
def users():
    c = db()
    if request.method == "POST":
        try:
            c.execute(
                "INSERT INTO users(name,login_id,password_hash,role,location) VALUES(?,?,?,?,?)",
                (
                    request.form["name"].strip(),
                    request.form["login_id"].strip(),
                    generate_password_hash(request.form["password"]),
                    "manager",
                    request.form["location"].strip()
                )
            )
            c.commit()
            msg("Manager login created.")
        except sqlite3.IntegrityError:
            msg("Login ID already exists.")
    users = c.execute(
        "SELECT name,login_id,role,location,active FROM users ORDER BY name"
    ).fetchall()
    locs = c.execute(
        "SELECT DISTINCT location FROM employees WHERE location<>'' ORDER BY location"
    ).fetchall()
    c.close()

    options = "".join(f"<option>{r['location']}</option>" for r in locs)
    rows = "".join(
        f"<tr><td>{u['name']}</td><td>{u['login_id']}</td><td>{u['role']}</td><td>{u['location']}</td></tr>"
        for u in users
    )
    return page(f"""
    <h2>Admin — Create Manager Login</h2>
    <div class="card">
      <form method="post" class="grid">
        <input name="name" placeholder="Manager Name" required>
        <input name="login_id" placeholder="Login ID" required>
        <input name="password" type="password" placeholder="Password" required>
        <select name="location" required>{options}</select>
        <button>Create Login</button>
      </form>
    </div>
    <div class="card scroll">
      <table><tr><th>Name</th><th>Login ID</th><th>Role</th><th>Location</th></tr>{rows}</table>
    </div>
    """)

@app.route("/employees", methods=["GET", "POST"])
@login_required
@admin_required
def employees():
    c = db()
    if request.method == "POST":
        c.execute(
            "INSERT INTO employees(employee_code,name,designation,location) VALUES(?,?,?,?)",
            (
                request.form["code"].strip(),
                request.form["name"].strip(),
                request.form["designation"].strip(),
                request.form["location"].strip()
            )
        )
        c.commit()
        msg("Employee added.")
    emps = c.execute(
        "SELECT employee_code,name,designation,location FROM employees ORDER BY location,name"
    ).fetchall()
    c.close()
    rows = "".join(
        f"<tr><td>{e['employee_code']}</td><td>{e['name']}</td><td>{e['designation']}</td><td>{e['location']}</td></tr>"
        for e in emps
    )
    return page(f"""
    <h2>Employee Master</h2>
    <div class="card">
      <form method="post" class="grid">
        <input name="code" placeholder="Employee ID" required>
        <input name="name" placeholder="Employee Name" required>
        <input name="designation" placeholder="Designation" required>
        <input name="location" placeholder="Warehouse / Location" required>
        <button>Add Employee</button>
      </form>
    </div>
    <div class="card scroll"><table>
      <tr><th>Employee ID</th><th>Name</th><th>Designation</th><th>Location</th></tr>{rows}
    </table></div>
    """)

@app.route("/monthly", methods=["GET", "POST"])
@login_required
def monthly():
    c = db()
    locs = allowed_locations(c)
    if not locs:
        c.close()
        return page("<div class='card'><h3>No location assigned.</h3></div>")

    location = request.args.get("location") or locs[0]
    if location not in locs:
        location = locs[0]

    year = int(request.args.get("year", date.today().year))
    month = int(request.args.get("month", date.today().month))
    days = calendar.monthrange(year, month)[1]

    employees = c.execute(
        "SELECT * FROM employees WHERE active=1 AND location=? ORDER BY name",
        (location,)
    ).fetchall()

    if request.method == "POST":
        for e in employees:
            for d in range(1, days + 1):
                status = request.form.get(f"a_{e['id']}_{d}", "")
                if status:
                    ad = f"{year:04d}-{month:02d}-{d:02d}"
                    c.execute("""
                        INSERT INTO attendance(employee_id,att_date,status)
                        VALUES(?,?,?)
                        ON CONFLICT(employee_id,att_date)
                        DO UPDATE SET status=excluded.status
                    """, (e["id"], ad, status))
        c.commit()
        c.close()
        msg(f"{calendar.month_name[month]} {year} attendance saved.")
        return redirect(f"/monthly?location={location}&year={year}&month={month}")

    data = {}
    start = f"{year:04d}-{month:02d}-01"
    end = f"{year:04d}-{month:02d}-{days:02d}"
    for e in employees:
        data[e["id"]] = {
            r["att_date"]: r["status"] for r in c.execute(
                "SELECT att_date,status FROM attendance WHERE employee_id=? AND att_date BETWEEN ? AND ?",
                (e["id"], start, end)
            ).fetchall()
        }
    c.close()

    headers = "".join(f"<th>{d}</th>" for d in range(1, days + 1))
    rows = ""
    for e in employees:
        cells = ""
        for d in range(1, days + 1):
            ds = f"{year:04d}-{month:02d}-{d:02d}"
            current = data[e["id"]].get(ds, "")
            opts = "<option value=''></option>" + "".join(
                f"<option value='{s}' {'selected' if current == s else ''}>{s}</option>"
                for s in ["P", "A", "L", "WO"]
            )
            cells += f"<td><select name='a_{e['id']}_{d}' style='width:58px'>{opts}</select></td>"
        rows += f"""
        <tr>
          <td class='emp'><b>{e['employee_code']}</b><br>{e['name']}<br>
          <span class='small'>{e['designation']}</span></td>{cells}
        </tr>
        """

    loc_options = "".join(
        f"<option {'selected' if l == location else ''}>{l}</option>" for l in locs
    )
    return page(f"""
    <h2>Monthly Attendance — {calendar.month_name[month]} {year}</h2>
    <form method="get" class="card grid">
      <label>Warehouse<select name="location">{loc_options}</select></label>
      <label>Year<input type="number" name="year" value="{year}"></label>
      <label>Month<input type="number" name="month" value="{month}" min="1" max="12"></label>
      <button>Load Month</button>
    </form>
    <form method="post">
      <div class="card scroll">
        <table><tr><th class="emp">Employee</th>{headers}</tr>{rows}</table>
      </div>
      <button type="submit">Save Full Month Attendance</button>
    </form>
    <p class="small">P = Present · A = Absent · L = Leave · WO = Weekly Off</p>
    """)

@app.route("/report")
@login_required
def report():
    c = db()
    locs = allowed_locations(c)
    if not locs:
        c.close()
        return page("<div class='card'><h3>No location assigned.</h3></div>")
    location = request.args.get("location") or locs[0]
    if location not in locs:
        location = locs[0]
    year = int(request.args.get("year", date.today().year))
    month = int(request.args.get("month", date.today().month))
    days = calendar.monthrange(year, month)[1]
    start = f"{year:04d}-{month:02d}-01"
    end = f"{year:04d}-{month:02d}-{days:02d}"
    emps = c.execute(
        "SELECT * FROM employees WHERE active=1 AND location=? ORDER BY name",
        (location,)
    ).fetchall()
    rows = ""
    for e in emps:
        counts = {s: 0 for s in ["P", "A", "L", "WO"]}
        for r in c.execute(
            "SELECT status FROM attendance WHERE employee_id=? AND att_date BETWEEN ? AND ?",
            (e["id"], start, end)
        ).fetchall():
            if r["status"] in counts:
                counts[r["status"]] += 1
        rows += f"<tr><td>{e['employee_code']}</td><td>{e['name']}</td><td>{e['designation']}</td><td>{counts['P']}</td><td>{counts['A']}</td><td>{counts['L']}</td><td>{counts['WO']}</td></tr>"
    c.close()
    return page(f"""
    <h2>{calendar.month_name[month]} {year} Summary — {location}</h2>
    <div class="card scroll"><table>
      <tr><th>Employee ID</th><th>Name</th><th>Designation</th><th>Present</th><th>Absent</th><th>Leave</th><th>Weekly Off</th></tr>
      {rows}
    </table></div>
    """)

# Initialize DB during Gunicorn import as well as local execution.
init()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
