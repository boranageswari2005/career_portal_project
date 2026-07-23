import os
from functools import wraps
from datetime import datetime
import razorpay
from flask import Flask, render_template, redirect, url_for, flash, request, abort, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

from config import Config
import db as dbmod
from resume_analysis import analyze_resume


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    dbmod.init_app(app)

    razorpay_client = razorpay.Client(
        auth=(app.config["RAZORPAY_KEY_ID"], app.config["RAZORPAY_KEY_SECRET"])
    )

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    if not os.path.exists(dbmod.DB_PATH):
        dbmod.init_db()

    @app.template_filter("format_date")
    def format_date(value):
        if not value:
            return "-"
        try:
            dt = datetime.strptime(value.split(".")[0], "%Y-%m-%d %H:%M:%S")
            return dt.strftime("%d %b %Y")
        except (ValueError, AttributeError):
            return value

    def allowed_file(filename):
        return (
            "." in filename
            and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]
        )

    # ---------- Auth helpers ----------

    @app.before_request
    def load_logged_in_user():
        user_id = session.get("user_id")
        g.user = None
        if user_id is not None:
            g.user = dbmod.query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)

    @app.context_processor
    def inject_user():
        return dict(current_user=g.user)

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                flash("Please log in to continue.", "info")
                return redirect(url_for("login"))
            return view(*args, **kwargs)
        return wrapped

    def admin_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                flash("Please log in to continue.", "info")
                return redirect(url_for("login"))
            if g.user["role"] != "admin":
                abort(403)
            return view(*args, **kwargs)
        return wrapped

    # ---------- Public routes ----------

    @app.route("/")
    def index():
        jobs = dbmod.query_db(
            "SELECT * FROM jobs WHERE is_active = 1 ORDER BY created_at DESC"
        )
        return render_template("index.html", jobs=jobs)

    @app.route("/jobs/<int:job_id>")
    def job_detail(job_id):
        job = dbmod.query_db("SELECT * FROM jobs WHERE id = ?", (job_id,), one=True)
        if job is None:
            abort(404)
        already_applied = False
        if g.user and g.user["role"] == "student":
            existing = dbmod.query_db(
                "SELECT 1 FROM applications WHERE student_id = ? AND job_id = ?",
                (g.user["id"], job_id), one=True
            )
            already_applied = existing is not None
        return render_template("job_detail.html", job=job, already_applied=already_applied)

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if g.user:
            return redirect(url_for("index"))
        if request.method == "POST":
            name = request.form.get("name", "").strip()
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            phone = request.form.get("phone", "").strip()
            skills = request.form.get("skills", "").strip()

            if not name or not email or not password:
                flash("Name, email and password are required.", "danger")
                return redirect(url_for("register"))

            existing = dbmod.query_db("SELECT 1 FROM users WHERE email = ?", (email,), one=True)
            if existing:
                flash("An account with that email already exists.", "danger")
                return redirect(url_for("register"))

            password_hash = generate_password_hash(password)
            dbmod.execute_db(
                "INSERT INTO users (name, email, password_hash, role, phone, skills) "
                "VALUES (?, ?, ?, 'student', ?, ?)",
                (name, email, password_hash, phone, skills)
            )
            flash("Registration successful. Please log in.", "success")
            return redirect(url_for("login"))

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.user:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            user = dbmod.query_db("SELECT * FROM users WHERE email = ?", (email,), one=True)
            if user and check_password_hash(user["password_hash"], password):
                session.clear()
                session["user_id"] = user["id"]
                flash(f"Welcome back, {user['name']}!", "success")
                return redirect(url_for("dashboard"))
            flash("Invalid email or password.", "danger")
        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        session.clear()
        flash("You have been logged out.", "info")
        return redirect(url_for("index"))

    # ---------- Shared dashboard router ----------

    @app.route("/dashboard")
    @login_required
    def dashboard():
        if g.user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("student_dashboard"))

    # ---------- Student routes ----------

    @app.route("/student/dashboard")
    @login_required
    def student_dashboard():
        if g.user["role"] == "admin":
            return redirect(url_for("admin_dashboard"))
        applications = dbmod.query_db(
            """SELECT a.*, j.title AS job_title, j.company AS job_company
               FROM applications a JOIN jobs j ON a.job_id = j.id
               WHERE a.student_id = ? ORDER BY a.applied_at DESC""",
            (g.user["id"],)
        )
        return render_template("student_dashboard.html", applications=applications)

    @app.route("/jobs/<int:job_id>/apply", methods=["GET", "POST"])
    @login_required
    def apply_job(job_id):
        if g.user["role"] == "admin":
            abort(403)
        job = dbmod.query_db("SELECT * FROM jobs WHERE id = ?", (job_id,), one=True)
        if job is None:
            abort(404)

        existing = dbmod.query_db(
            "SELECT 1 FROM applications WHERE student_id = ? AND job_id = ?",
            (g.user["id"], job_id), one=True
        )
        if existing:
            flash("You have already applied to this job.", "info")
            return redirect(url_for("student_dashboard"))

        payment = dbmod.query_db(
            "SELECT * FROM payments WHERE student_id = ? AND job_id = ?",
            (g.user["id"], job_id), one=True
        )
        if payment is None or payment["status"] != "paid":
            flash(f"Please pay the {app.config['APPLICATION_FEE_DISPLAY']} application fee to continue.", "info")
            return redirect(url_for("pay_for_job", job_id=job_id))

        if request.method == "POST":
            file = request.files.get("resume")
            if not file or file.filename == "":
                flash("Please select a resume file to upload.", "danger")
                return redirect(url_for("apply_job", job_id=job_id))

            if not allowed_file(file.filename):
                flash("Only PDF or DOCX files are allowed.", "danger")
                return redirect(url_for("apply_job", job_id=job_id))

            filename = secure_filename(
                f"{g.user['id']}_{job_id}_{int(datetime.utcnow().timestamp())}_{file.filename}"
            )
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(filepath)

            try:
                result = analyze_resume(filepath, job["description"], job["required_skills"])
            except Exception as exc:
                flash(f"Could not analyze resume: {exc}", "danger")
                return redirect(url_for("apply_job", job_id=job_id))

            dbmod.execute_db(
                """INSERT INTO applications
                   (student_id, job_id, resume_filename, resume_text, ats_score,
                    similarity_score, skill_match_score, matched_skills, missing_skills, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Applied')""",
                (
                    g.user["id"], job_id, filename, result["resume_text"][:5000],
                    result["ats_score"], result["similarity_score"], result["skill_match_score"],
                    ", ".join(result["matched_skills"]), ", ".join(result["missing_skills"])
                )
            )

            flash(f"Application submitted! Your ATS score: {result['ats_score']}%", "success")
            return redirect(url_for("student_dashboard"))

        return render_template("apply_job.html", job=job)

    # ---------- Payment routes (Razorpay) ----------

    @app.route("/jobs/<int:job_id>/pay")
    @login_required
    def pay_for_job(job_id):
        if g.user["role"] == "admin":
            abort(403)
        job = dbmod.query_db("SELECT * FROM jobs WHERE id = ?", (job_id,), one=True)
        if job is None:
            abort(404)

        existing_application = dbmod.query_db(
            "SELECT 1 FROM applications WHERE student_id = ? AND job_id = ?",
            (g.user["id"], job_id), one=True
        )
        if existing_application:
            flash("You have already applied to this job.", "info")
            return redirect(url_for("student_dashboard"))

        payment = dbmod.query_db(
            "SELECT * FROM payments WHERE student_id = ? AND job_id = ?",
            (g.user["id"], job_id), one=True
        )
        if payment and payment["status"] == "paid":
            return redirect(url_for("apply_job", job_id=job_id))

        amount = app.config["APPLICATION_FEE_PAISE"]

        if payment is None:
            try:
                order = razorpay_client.order.create({
                    "amount": amount,
                    "currency": "INR",
                    "receipt": f"job{job_id}_student{g.user['id']}",
                    "payment_capture": 1,
                })
            except Exception as exc:
                flash(f"Could not initiate payment: {exc}", "danger")
                return redirect(url_for("job_detail", job_id=job_id))

            dbmod.execute_db(
                """INSERT INTO payments (student_id, job_id, razorpay_order_id, amount, status)
                   VALUES (?, ?, ?, ?, 'created')""",
                (g.user["id"], job_id, order["id"], amount)
            )
            order_id = order["id"]
        else:
            order_id = payment["razorpay_order_id"]

        return render_template(
            "payment.html", job=job, order_id=order_id, amount=amount,
            amount_display=app.config["APPLICATION_FEE_DISPLAY"],
            razorpay_key_id=app.config["RAZORPAY_KEY_ID"]
        )

    @app.route("/jobs/<int:job_id>/verify-payment", methods=["POST"])
    @login_required
    def verify_payment(job_id):
        if g.user["role"] == "admin":
            abort(403)

        payment_id = request.form.get("razorpay_payment_id")
        order_id = request.form.get("razorpay_order_id")
        signature = request.form.get("razorpay_signature")

        payment = dbmod.query_db(
            "SELECT * FROM payments WHERE student_id = ? AND job_id = ?",
            (g.user["id"], job_id), one=True
        )
        if payment is None or payment["razorpay_order_id"] != order_id:
            flash("Payment record not found. Please try again.", "danger")
            return redirect(url_for("pay_for_job", job_id=job_id))

        try:
            razorpay_client.utility.verify_payment_signature({
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature,
            })
        except razorpay.errors.SignatureVerificationError:
            dbmod.execute_db(
                "UPDATE payments SET status = 'failed', razorpay_payment_id = ? WHERE id = ?",
                (payment_id, payment["id"])
            )
            flash("Payment verification failed. Please try again.", "danger")
            return redirect(url_for("pay_for_job", job_id=job_id))

        dbmod.execute_db(
            """UPDATE payments SET status = 'paid', razorpay_payment_id = ?, razorpay_signature = ?
               WHERE id = ?""",
            (payment_id, signature, payment["id"])
        )
        flash(f"Payment successful! You can now submit your application.", "success")
        return redirect(url_for("apply_job", job_id=job_id))

    @app.route("/jobs/<int:job_id>/payment-failed", methods=["POST"])
    @login_required
    def payment_failed(job_id):
        payment = dbmod.query_db(
            "SELECT * FROM payments WHERE student_id = ? AND job_id = ?",
            (g.user["id"], job_id), one=True
        )
        if payment:
            dbmod.execute_db("UPDATE payments SET status = 'failed' WHERE id = ?", (payment["id"],))
        flash("Payment was not completed. Please try again.", "danger")
        return redirect(url_for("pay_for_job", job_id=job_id))

    # ---------- Admin routes ----------

    @app.route("/admin/dashboard")
    @admin_required
    def admin_dashboard():
        jobs = dbmod.query_db(
            """SELECT j.*, (SELECT COUNT(*) FROM applications a WHERE a.job_id = j.id) AS applicant_count
               FROM jobs j WHERE posted_by = ? ORDER BY created_at DESC""",
            (g.user["id"],)
        )
        total_applications = dbmod.query_db(
            """SELECT COUNT(*) AS cnt FROM applications a
               JOIN jobs j ON a.job_id = j.id WHERE j.posted_by = ?""",
            (g.user["id"],), one=True
        )["cnt"]
        return render_template("admin_dashboard.html", jobs=jobs, total_applications=total_applications)

    @app.route("/admin/jobs/new", methods=["GET", "POST"])
    @admin_required
    def new_job():
        if request.method == "POST":
            title = request.form.get("title", "").strip()
            company = request.form.get("company", "").strip() or "Our Company"
            description = request.form.get("description", "").strip()
            required_skills = request.form.get("required_skills", "").strip()
            location = request.form.get("location", "").strip()
            job_type = request.form.get("job_type", "Full-time")

            if not title or not description or not required_skills:
                flash("Title, description and required skills are required.", "danger")
                return redirect(url_for("new_job"))

            dbmod.execute_db(
                """INSERT INTO jobs (title, company, description, required_skills,
                                      location, job_type, posted_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (title, company, description, required_skills, location, job_type, g.user["id"])
            )
            flash("Job posted successfully.", "success")
            return redirect(url_for("admin_dashboard"))

        return render_template("new_job.html")

    @app.route("/admin/jobs/<int:job_id>/applicants")
    @admin_required
    def view_applicants(job_id):
        job = dbmod.query_db("SELECT * FROM jobs WHERE id = ?", (job_id,), one=True)
        if job is None:
            abort(404)
        if job["posted_by"] != g.user["id"]:
            abort(403)
        applicants = dbmod.query_db(
            """SELECT a.*, u.name AS student_name, u.email AS student_email
               FROM applications a JOIN users u ON a.student_id = u.id
               WHERE a.job_id = ? ORDER BY a.ats_score DESC""",
            (job_id,)
        )
        return render_template("applicants.html", job=job, applicants=applicants)

    @app.route("/admin/applications/<int:app_id>/status", methods=["POST"])
    @admin_required
    def update_status(app_id):
        application = dbmod.query_db(
            """SELECT a.*, j.posted_by AS job_owner FROM applications a
               JOIN jobs j ON a.job_id = j.id WHERE a.id = ?""",
            (app_id,), one=True
        )
        if application is None:
            abort(404)
        if application["job_owner"] != g.user["id"]:
            abort(403)
        new_status = request.form.get("status")
        if new_status in ("Applied", "Shortlisted", "Rejected", "Hired"):
            dbmod.execute_db("UPDATE applications SET status = ? WHERE id = ?", (new_status, app_id))
            flash("Applicant status updated.", "success")
        return redirect(url_for("view_applicants", job_id=application["job_id"]))

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("error.html", code=403, message="Access forbidden."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("error.html", code=404, message="Page not found."), 404

    return app


app = create_app()


def seed_admin():
    with app.app_context():
        existing = dbmod.query_db(
            "SELECT 1 FROM users WHERE email = 'admin@careerportal.com'", one=True
        )
        if not existing:
            password_hash = generate_password_hash("admin123")
            dbmod.execute_db(
                "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, 'admin')",
                ("Admin", "admin@careerportal.com", password_hash)
            )
            print("Seeded default admin -> email: admin@careerportal.com / password: admin123")


if __name__ == "__main__":
    seed_admin()
    app.run(host="0.0.0.0", port=5000)
