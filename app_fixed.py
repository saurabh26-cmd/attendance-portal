import os, sqlite3, calendar, io, csv
from datetime import date
from functools import wraps
from flask import Flask, request, redirect, session, send_file, render_template_string
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
      name TEXT NOT NULL, login_id TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'manager',
      location TEXT DEFAULT '', active INTEGER DEFAULT 1);

    CREATE TABLE IF NOT EXISTS employees(
      id INTEGER PRIMARY KEY AUTOINCREMENT, employee_code TEXT NOT NULL,
      name TEXT NOT NULL, designation TEXT NOT NULL,
      location TEXT NOT NULL, active INTEGER DEFAULT 1);

    CREATE TABLE IF NOT EXISTS attendance(
      employee_id INTEGER NOT NULL, att_date TEXT NOT NULL, status TEXT NOT NULL,
      PRIMARY KEY(employee_id,att_date));
    """)
    if not c.execute("SELECT 1 FROM users WHERE login_id='admin'").fetchone():
        c.execute(
            "INSERT INTO users(name,login_id,password_hash,role,location) VALUES(?,?,?,?,?)",
            ("Admin", "admin", generate_password_hash("Admin@123"), "admin", "ALL")
        )
    c.commit()
    c.close()

CSS = """<style>
*{box-sizing:border-box}
body{margin:0;font-family:Arial,sans-serif;background:#f3f5f9;color:#172033}
.nav{background:#111827;color:white;padding:15px 22px;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}
.nav a{color:white;text-decoration:none;margin-left:12px;font-size:14px}
.wrap{max-width:1400px;margin:24px auto;padding:0 16px}
.card{background:white;border:1px solid #e5e7eb;border-radius:12px;padding:18px;margin:14px 0;box-shadow:0 2px 10px #0000000b}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px}
input,select,button{padding:10px;border:1px solid #aeb7c4;border-radius:7px;font:inherit;width:100%;background:#fff;color:#172033}
select{color:#172033;background-color:#fff;appearance:auto;-webkit-appearance:auto}
select option{background:#fff;color:#172033;padding:8px}
button,.btn{background:#111827;color:white;border:0;cursor:pointer;padding:10px 14px;border-radius:7px;text-decoration:none;width:auto;display:inline-block}
.btn.success{background:#087f5b}.btn.secondary{background:#e9edf3;color:#172033}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border:1px solid #e2e6ec;padding:7px;text-align:center;white-space:nowrap}
th{background:#f7f8fa}
.scroll{overflow:auto}.emp{text-align:left;position:sticky;left:0;background:white;z-index:2}
.small{font-size:12px;color:#667085}
.login{max-width:420px;margin:70px auto}
.hero{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}
.actions{display:flex;gap:8px;flex-wrap:wrap}
.flash{background:#e7f7ef;padding:11px;border-radius:7px;margin-bottom:10px}
</style>"""

def html(title, body):
    nav = """<div class="nav"><b>📋 Monthly Attendance Portal</b><div>
    {% if session.get('uid') %}
    <span>{{session.get('name')}} · {{session.get('role')|title}}</span>
    <a href="/dashboard">Dashboard</a>
    {% if session.get('role')=='admin' %}<a href="/users">Managers</a><a href="/employees">Employees</a>{% endif %}
    <a href="/monthly">Attendance</a><a href="/report">Reports</a><a href="/logout">Logout</a>
    {% endif %}</div></div>"""
    return """<!doctype html><html><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>""" + title + """</title>""" + CSS + """</head><body>""" + nav + \
           """<div class="wrap">""" + body + """</div></body></html>"""

def render(t, **kw):
    return render_template_string(t, **kw)

def flash(msg):
    session.setdefault("flash", []).append(msg)

def page(title, body):
    msgs = session.pop("flash", [])
    return render(
        html(title, body.replace("{{FLASH}}",
        "".join("<div class='flash'>" + m + "</div>" for m in msgs)))
    )

def login_required(f):
    @wraps(f)
    def w(*a, **k):
        if "uid" not in session:
            return redirect("/")
        return f(*a, **k)
    return w

def admin_required(f):
    @wraps(f)
    def w(*a, **k):
        if session.get("role") != "admin":
            flash("Admin access required.")
            return redirect("/dashboard")
        return f(*a, **k)
    return w

def allowed_locations(c):
    if session.get("role") == "admin":
        return [r["location"] for r in c.execute(
            "SELECT DISTINCT location FROM employees WHERE location<>'' ORDER BY location"
        )]
    return [session.get("location")] if session.get("location") else []

@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        c = db()
        u = c.execute(
            "SELECT * FROM users WHERE login_id=? AND active=1",
            (request.form["login_id"].strip(),)
        ).fetchone()
        c.close()
        if u and check_password_hash(u["password_hash"], request.form["password"]):
            session.clear()
            session.update(uid=u["id"], name=u["name"], role=u["role"], location=u["location"])
            return redirect("/dashboard")
        flash("Invalid Login ID or Password.")

    body = """{{FLASH}}<div class="card login"><h2>Welcome 👋</h2>
    <p class="small">Monthly attendance management system</p>
    <form method="post">
    <label>Login ID<input name="login_id" required></label><br>
    <label>Password<input type="password" name="password" required></label><br>
    <button>Login</button></form>
    <p class="small">Admin: <b>admin</b> / <b>Admin@123</b></p></div>"""
    return page("Login", body)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/dashboard")
@login_required
def dashboard():
    c = db()
    if session["role"] == "admin":
        emp = c.execute("SELECT COUNT(*) n FROM employees WHERE active=1").fetchone()["n"]
        mgr = c.execute("SELECT COUNT(*) n FROM users WHERE role='manager' AND active=1").fetchone()["n"]
        loc = "All Locations"
    else:
        emp = c.execute(
            "SELECT COUNT(*) n FROM employees WHERE active=1 AND location=?",
            (session["location"],)
        ).fetchone()["n"]
        mgr = 0
        loc = session["location"]
    c.close()

    cards = f"""<div class="grid">
    <div class="card"><span class="small">Active Employees</span><h2>{emp}</h2></div>
    <div class="card"><span class="small">Managers</span><h2>{mgr}</h2></div>
    <div class="card"><span class="small">Location</span><h3>{loc}</h3></div></div>"""
    return page("Dashboard", f"""{{{{FLASH}}}}<div class="hero"><div><h1>Dashboard</h1>
    <p class="small">Welcome, {session['name']}.</p></div>
    <a class="btn" href="/monthly">➕ Fill Attendance</a></div>{cards}""")

@app.route("/users", methods=["GET","POST"])
@login_required
@admin_required
def users():
    c = db()
    if request.method == "POST":
        try:
            c.execute(
                """INSERT INTO users(name,login_id,password_hash,role,location)
                VALUES(?,?,?,?,?)""",
                (
                    request.form["name"].strip(),
                    request.form["login_id"].strip(),
                    generate_password_hash(request.form["password"]),
                    "manager",
                    request.form["location"].strip()
                )
            )
            c.commit()
            flash("Manager login created.")
        except sqlite3.IntegrityError:
            flash("Login ID already exists.")

    users = c.execute(
        "SELECT name,login_id,role,location,active FROM users ORDER BY name"
    ).fetchall()
    locs = c.execute(
        "SELECT DISTINCT location FROM employees WHERE location<>'' ORDER BY location"
    ).fetchall()
    c.close()

    opts = "".join(f"<option value='{x['location']}'>{x['location']}</option>" for x in locs)
    if not opts:
        opts = "<option value=''>Add employees/locations first</option>"

    rows = "".join(
        f"<tr><td>{u['name']}</td><td>{u['login_id']}</td><td>{u['role']}</td>"
        f"<td>{u['location']}</td><td>{'Active' if u['active'] else 'Inactive'}</td></tr>"
        for u in users
    )

    body = f"""{{{{FLASH}}}}<h1>Manager Accounts</h1>
    <div class="card"><form method="post" class="grid">
    <input name="name" placeholder="Manager name" required>
    <input name="login_id" placeholder="Login ID" required>
    <input name="password" placeholder="Password" required>
    <select name="location" required>{opts}</select>
    <button>Create Manager</button></form></div>
    <div class="card scroll"><table><tr><th>Name</th><th>Login ID</th><th>Role</th>
    <th>Location</th><th>Status</th></tr>{rows}</table></div>"""
    return page("Managers", body)

@app.route("/employees", methods=["GET","POST"])
@login_required
@admin_required
def employees():
    c = db()
    if request.method == "POST":
        c.execute(
            """INSERT INTO employees(employee_code,name,designation,location)
            VALUES(?,?,?,?)""",
            (
                request.form["code"].strip(),
                request.form["name"].strip(),
                request.form["designation"].strip(),
                request.form["location"].strip()
            )
        )
        c.commit()
        flash("Employee added.")

    emps = c.execute(
        "SELECT * FROM employees WHERE active=1 ORDER BY location,name"
    ).fetchall()
    c.close()

    rows = "".join(
        f"<tr><td>{e['employee_code']}</td><td>{e['name']}</td>"
        f"<td>{e['designation']}</td><td>{e['location']}</td></tr>"
        for e in emps
    )

    body = f"""{{{{FLASH}}}}<h1>Employee Master</h1>
    <div class="card"><form method="post" class="grid">
    <input name="code" placeholder="Employee ID" required>
    <input name="name" placeholder="Employee Name" required>
    <input name="designation" placeholder="Designation" required>
    <input name="location" placeholder="Warehouse / Location" required>
    <button>Add Employee</button></form></div>
    <div class="card scroll"><table><tr><th>Employee ID</th><th>Employee Name</th>
    <th>Designation</th><th>Location</th></tr>{rows}</table></div>"""
    return page("Employees", body)

@app.route("/monthly", methods=["GET","POST"])
@login_required
def monthly():
    c = db()
    locs = allowed_locations(c)

    if not locs:
        c.close()
        return page(
            "Attendance",
            """<div class='card'><h2>No locations available</h2>
            <p>Please go to <b>Employees</b> and add at least one employee with a warehouse/location.</p>
            </div>"""
        )

    location = request.args.get("location") or locs[0]
    if location not in locs:
        location = locs[0]

    year = int(request.args.get("year", date.today().year))
    month = int(request.args.get("month", date.today().month))
    if month < 1 or month > 12:
        month = date.today().month

    days = calendar.monthrange(year, month)[1]
    emps = c.execute(
        "SELECT * FROM employees WHERE active=1 AND location=? ORDER BY name",
        (location,)
    ).fetchall()

    if request.method == "POST":
        for e in emps:
            for d in range(1, days + 1):
                s = request.form.get(f"a_{e['id']}_{d}", "")
                if s:
                    c.execute(
                        """INSERT INTO attendance(employee_id,att_date,status)
                        VALUES(?,?,?)
                        ON CONFLICT(employee_id,att_date)
                        DO UPDATE SET status=excluded.status""",
                        (e["id"], f"{year:04d}-{month:02d}-{d:02d}", s)
                    )
        c.commit()
        c.close()
        flash(f"Attendance saved for {calendar.month_name[month]} {year}.")
        return redirect(f"/monthly?location={location}&year={year}&month={month}")

    start = f"{year:04d}-{month:02d}-01"
    end = f"{year:04d}-{month:02d}-{days:02d}"
    data = {}

    for e in emps:
        data[e["id"]] = {
            r["att_date"]: r["status"]
            for r in c.execute(
                "SELECT att_date,status FROM attendance WHERE employee_id=? AND att_date BETWEEN ? AND ?",
                (e["id"], start, end)
            )
        }
    c.close()

    opts_loc = "".join(
        f"<option value='{x}' {'selected' if x == location else ''}>{x}</option>"
        for x in locs
    )
    heads = "".join(f"<th>{d}</th>" for d in range(1, days + 1))
    rows = ""

    for e in emps:
        cells = ""
        for d in range(1, days + 1):
            cur = data[e["id"]].get(f"{year:04d}-{month:02d}-{d:02d}", "")
            opts = "<option value=''>-</option>" + "".join(
                f"<option value='{s}' {'selected' if cur == s else ''}>{s}</option>"
                for s in ["P", "A", "L", "WO"]
            )
            cells += f"<td><select name='a_{e['id']}_{d}' style='width:62px'>{opts}</select></td>"

        rows += (
            f"<tr><td class='emp'><b>{e['employee_code']}</b><br>{e['name']}"
            f"<br><span class='small'>{e['designation']}</span></td>{cells}</tr>"
        )

    body = f"""{{{{FLASH}}}}<div class="hero"><div><h1>Monthly Attendance</h1>
    <p class="small">{calendar.month_name[month]} {year} · {location}</p></div>
    <div class="actions">
    <a class="btn secondary" href="/report?location={location}&year={year}&month={month}">Report</a>
    <a class="btn success" href="/export?location={location}&year={year}&month={month}">Export CSV</a>
    </div></div>

    <form method="get" class="card grid">
    <label>Warehouse<select name="location">{opts_loc}</select></label>
    <label>Year<input type="number" name="year" value="{year}"></label>
    <label>Month<input type="number" name="month" value="{month}" min="1" max="12"></label>
    <button>Load Month</button></form>

    <form method="post"><div class="card scroll"><table>
    <tr><th class="emp">Employee</th>{heads}</tr>{rows}</table></div>
    <button class="btn success" type="submit">💾 Save Full Month Attendance</button></form>
    <p class="small">P = Present · A = Absent · L = Leave · WO = Weekly Off</p>"""
    return page("Monthly Attendance", body)

@app.route("/report")
@login_required
def report():
    c = db()
    locs = allowed_locations(c)
    if not locs:
        c.close()
        return page("Report", "<div class='card'>No location assigned.</div>")

    location = request.args.get("location") or locs[0]
    if location not in locs:
        location = locs[0]

    year = int(request.args.get("year", date.today().year))
    month = int(request.args.get("month", date.today().month))
    days = calendar.monthrange(year, month)[1]

    emps = c.execute(
        "SELECT * FROM employees WHERE active=1 AND location=? ORDER BY name",
        (location,)
    ).fetchall()

    rows = ""
    for e in emps:
        cnt = {s: 0 for s in ["P", "A", "L", "WO"]}
        for r in c.execute(
            "SELECT status FROM attendance WHERE employee_id=? AND att_date BETWEEN ? AND ?",
            (e["id"], f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{days:02d}")
        ):
            if r["status"] in cnt:
                cnt[r["status"]] += 1
        rows += (
            f"<tr><td>{e['employee_code']}</td><td>{e['name']}</td>"
            f"<td>{e['designation']}</td><td>{cnt['P']}</td><td>{cnt['A']}</td>"
            f"<td>{cnt['L']}</td><td>{cnt['WO']}</td><td>{sum(cnt.values())}</td></tr>"
        )

    c.close()
    body = f"""<div class="hero"><div><h1>Attendance Report</h1>
    <p class="small">{calendar.month_name[month]} {year} · {location}</p></div>
    <a class="btn success" href="/export?location={location}&year={year}&month={month}">⬇ Download CSV</a></div>
    <div class="card scroll"><table><tr><th>Employee ID</th><th>Name</th><th>Designation</th>
    <th>Present</th><th>Absent</th><th>Leave</th><th>Weekly Off</th><th>Total</th></tr>{rows}</table></div>"""
    return page("Report", body)

@app.route("/export")
@login_required
def export():
    c = db()
    locs = allowed_locations(c)
    if not locs:
        c.close()
        return "No location assigned", 400

    location = request.args.get("location") or locs[0]
    if location not in locs:
        location = locs[0]

    year = int(request.args.get("year", date.today().year))
    month = int(request.args.get("month", date.today().month))
    days = calendar.monthrange(year, month)[1]

    emps = c.execute(
        "SELECT * FROM employees WHERE active=1 AND location=? ORDER BY name",
        (location,)
    ).fetchall()

    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(
        ["Employee ID","Name","Designation","Location"] +
        [str(d) for d in range(1, days + 1)] +
        ["Present","Absent","Leave","WO"]
    )

    for e in emps:
        sts = []
        cnt = {s: 0 for s in ["P", "A", "L", "WO"]}
        for d in range(1, days + 1):
            r = c.execute(
                "SELECT status FROM attendance WHERE employee_id=? AND att_date=?",
                (e["id"], f"{year:04d}-{month:02d}-{d:02d}")
            ).fetchone()
            s = r["status"] if r else ""
            sts.append(s)
            if s in cnt:
                cnt[s] += 1

        w.writerow(
            [e["employee_code"], e["name"], e["designation"], e["location"]] +
            sts + [cnt["P"], cnt["A"], cnt["L"], cnt["WO"]]
        )

    c.close()
    out.seek(0)
    return send_file(
        io.BytesIO(out.getvalue().encode("utf-8-sig")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"attendance_{year}_{month:02d}.csv"
    )

init()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
