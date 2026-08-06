import os, calendar, sqlite3
from datetime import date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app=Flask(__name__)
app.secret_key=os.environ.get("SECRET_KEY","change-this-secret")

# For quick testing this uses SQLite. For cloud deployment, point DATABASE_URL
# to a PostgreSQL database and replace the db() function with a PostgreSQL adapter.
DB=os.environ.get("DB_FILE","attendance.db")

def db():
    c=sqlite3.connect(DB)
    c.row_factory=sqlite3.Row
    return c

def init():
    c=db()
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
      PRIMARY KEY(employee_id,att_date)
    );
    """)
    if not c.execute("SELECT 1 FROM users WHERE login_id='admin'").fetchone():
        c.execute("INSERT INTO users(name,login_id,password_hash,role,location) VALUES(?,?,?,?,?)",
                  ("Admin","admin",generate_password_hash("Admin@123"),"admin","ALL"))
    if not c.execute("SELECT 1 FROM employees").fetchone():
        sample=[
          ("FK001","Rahul","Picker/Packer","Noida STC"),
          ("FK002","Amit","Picker/Packer","Noida STC"),
          ("FK003","Ravi","Inward Executive","Noida STC"),
          ("FK004","Suresh","Picker/Packer","Ghaziabad")
        ]
        c.executemany("INSERT INTO employees(employee_code,name,designation,location) VALUES(?,?,?,?)",sample)
    c.commit(); c.close()

def login_required(f):
    @wraps(f)
    def w(*a,**kw):
        if "uid" not in session: return redirect(url_for("login"))
        return f(*a,**kw)
    return w

def admin_required(f):
    @wraps(f)
    def w(*a,**kw):
        if session.get("role")!="admin":
            flash("Admin access required.","danger"); return redirect(url_for("dashboard"))
        return f(*a,**kw)
    return w

@app.route("/",methods=["GET","POST"])
def login():
    if request.method=="POST":
        lid=request.form["login_id"].strip()
        c=db(); u=c.execute("SELECT * FROM users WHERE login_id=? AND active=1",(lid,)).fetchone(); c.close()
        if u and check_password_hash(u["password_hash"],request.form["password"]):
            session.update(uid=u["id"],name=u["name"],role=u["role"],location=u["location"])
            return redirect(url_for("dashboard"))
        flash("Invalid Login ID or Password.","danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear(); return redirect(url_for("login"))

def locations_for_user(c):
    if session["role"]=="admin":
        rows=c.execute("SELECT DISTINCT location FROM employees WHERE location<>'' ORDER BY location").fetchall()
        return [x["location"] for x in rows]
    return [session["location"]] if session["location"] else []

@app.route("/dashboard")
@login_required
def dashboard():
    c=db()
    locs=locations_for_user(c)
    if session["role"]=="admin":
        employees=c.execute("SELECT COUNT(*) n FROM employees WHERE active=1").fetchone()["n"]
    else:
        employees=c.execute("SELECT COUNT(*) n FROM employees WHERE active=1 AND location=?",(session["location"],)).fetchone()["n"]
    c.close()
    return render_template("dashboard.html",employees=employees,locations=locs)

@app.route("/monthly",methods=["GET","POST"])
@login_required
def monthly():
    c=db()
    locs=locations_for_user(c)
    location=request.args.get("location") or (locs[0] if locs else "")
    year=int(request.args.get("year",date.today().year))
    month=int(request.args.get("month",date.today().month))
    if location not in locs:
        location=locs[0] if locs else ""
    days=calendar.monthrange(year,month)[1]
    dates=[f"{year:04d}-{month:02d}-{d:02d}" for d in range(1,days+1)]
    employees=c.execute("SELECT * FROM employees WHERE active=1 AND location=? ORDER BY name",(location,)).fetchall()
    if request.method=="POST":
        for e in employees:
            for d in range(1,days+1):
                key=f"a_{e['id']}_{d}"
                status=request.form.get(key,"")
                if status:
                    ad=f"{year:04d}-{month:02d}-{d:02d}"
                    c.execute("""INSERT INTO attendance(employee_id,att_date,status) VALUES(?,?,?)
                                 ON CONFLICT(employee_id,att_date) DO UPDATE SET status=excluded.status""",
                              (e["id"],ad,status))
        c.commit(); c.close()
        flash(f"{calendar.month_name[month]} {year} attendance saved.","success")
        return redirect(url_for("monthly",location=location,year=year,month=month))
    data={}
    for e in employees:
        data[e["id"]]={r["att_date"]:r["status"] for r in c.execute(
            "SELECT att_date,status FROM attendance WHERE employee_id=? AND att_date BETWEEN ? AND ?",
            (e["id"],dates[0],dates[-1])).fetchall()}
    c.close()
    return render_template("monthly.html",locations=locs,location=location,year=year,month=month,
                           month_name=calendar.month_name[month],days=range(1,days+1),
                           employees=employees,data=data)

@app.route("/admin/users",methods=["GET","POST"])
@login_required
@admin_required
def users():
    c=db()
    if request.method=="POST":
        try:
            c.execute("""INSERT INTO users(name,login_id,password_hash,role,location)
                         VALUES(?,?,?,?,?)""",
                      (request.form["name"],request.form["login_id"].strip(),
                       generate_password_hash(request.form["password"]),
                       "manager",request.form["location"]))
            c.commit(); flash("Manager login created.","success")
        except sqlite3.IntegrityError: flash("Login ID already exists.","danger")
    users=c.execute("SELECT id,name,login_id,role,location,active FROM users ORDER BY name").fetchall()
    locations=c.execute("SELECT DISTINCT location FROM employees WHERE location<>'' ORDER BY location").fetchall()
    c.close(); return render_template("users.html",users=users,locations=locations)

@app.route("/admin/employees",methods=["GET","POST"])
@login_required
@admin_required
def employees():
    c=db()
    if request.method=="POST":
        c.execute("INSERT INTO employees(employee_code,name,designation,location) VALUES(?,?,?,?)",
                  (request.form["code"],request.form["name"],request.form["designation"],request.form["location"]))
        c.commit(); flash("Employee added.","success")
    emps=c.execute("SELECT * FROM employees ORDER BY location,name").fetchall()
    locs=c.execute("SELECT DISTINCT location FROM employees WHERE location<>'' ORDER BY location").fetchall()
    c.close(); return render_template("employees.html",employees=emps,locations=locs)

@app.route("/report")
@login_required
def report():
    c=db()
    locs=locations_for_user(c)
    location=request.args.get("location") or (locs[0] if locs else "")
    year=int(request.args.get("year",date.today().year)); month=int(request.args.get("month",date.today().month))
    days=calendar.monthrange(year,month)[1]
    start=f"{year:04d}-{month:02d}-01"; end=f"{year:04d}-{month:02d}-{days:02d}"
    emps=c.execute("SELECT * FROM employees WHERE active=1 AND location=? ORDER BY name",(location,)).fetchall()
    report=[]
    for e in emps:
        rows=c.execute("SELECT status FROM attendance WHERE employee_id=? AND att_date BETWEEN ? AND ?",(e["id"],start,end)).fetchall()
        counts={s:0 for s in ["P","A","L","WO"]}
        for r in rows:
            if r["status"] in counts: counts[r["status"]]+=1
        report.append((e,counts))
    c.close()
    return render_template("report.html",locations=locs,location=location,year=year,month=month,month_name=calendar.month_name[month],report=report)

init()

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=True)
