# AI-Powered Career Portal

A Flask-based recruitment platform with student registration/login, job
listings, resume upload, AI/ML-based resume analysis, and an ATS
(Applicant Tracking System) score, plus an admin/recruiter side for
posting jobs and managing applicants.

## Features

- **Student side**: register, log in, browse jobs, pay a one-time application
  fee via **Razorpay**, then upload a resume (PDF/DOCX) per job, view a
  personal dashboard with application status and ATS score.
- **Payment gate (Razorpay)**: before a resume can be submitted for a job,
  the student is routed through a Razorpay Checkout payment for a configurable
  application fee (default ₹50). The order is created server-side, the
  payment signature is verified server-side (HMAC-SHA256) before the
  application is accepted — the resume upload form is inaccessible until a
  valid, verified payment exists for that student + job.
- **Admin/recruiter side**: log in, post jobs with required skills, view all
  applicants for a job ranked by ATS score, update applicant status
  (Applied / Shortlisted / Rejected / Hired).
- **AI resume analysis / ATS scoring** (`resume_analysis.py`):
  1. Extracts raw text from the uploaded PDF/DOCX resume.
  2. Computes a **TF-IDF + cosine similarity** score between the resume
     and the job description (semantic match, via scikit-learn).
  3. Computes a **skill/keyword match score** — checks which of the job's
     required skills actually appear in the resume text.
  4. Combines both into a final weighted ATS score (0–100), along with
     lists of matched and missing skills, so both student and recruiter
     see exactly why a resume scored the way it did.

## Tech stack

- **Backend**: Python, Flask
- **Payments**: Razorpay Checkout + Orders API (test mode), server-side signature verification
- **Database**: SQLite (plain `sqlite3`, no ORM — see `db.py` / `schema.sql`)
- **Auth**: Flask sessions + Werkzeug password hashing (no third-party auth lib)
- **ML/NLP**: scikit-learn (TF-IDF, cosine similarity)
- **Resume parsing**: pdfplumber (PDF), python-docx (DOCX)
- **Frontend**: Jinja2 templates + plain CSS (no JS framework required)

## Project structure

```
career_portal/
├── app.py                # Flask app: routes for auth, student, admin
├── db.py                 # sqlite3 connection + query helpers
├── schema.sql             # Database schema (users, jobs, applications)
├── resume_analysis.py     # Resume text extraction + ATS scoring logic
├── config.py               # App configuration
├── requirements.txt
├── templates/              # Jinja2 HTML templates
├── static/
│   ├── css/style.css
│   └── uploads/            # Uploaded resumes are stored here
└── career_portal.db        # Created automatically on first run
```

## Setup

### 1. Get Razorpay test API keys

1. Sign up at [dashboard.razorpay.com](https://dashboard.razorpay.com) (free).
2. Make sure you're in **Test Mode** (toggle top-right of the dashboard).
3. Go to **Settings → API Keys → Generate Test Key** and copy the **Key Id**
   and **Key Secret**.
4. Set them as environment variables before running the app (recommended,
   don't commit real keys to code):

```bash
export RAZORPAY_KEY_ID="rzp_test_xxxxxxxxxxxx"
export RAZORPAY_KEY_SECRET="xxxxxxxxxxxxxxxxxxxxxxxx"
```

   Or just edit the defaults directly in `config.py` for a quick local demo.

   In **test mode**, use Razorpay's published test card
   `4111 1111 1111 1111`, any future expiry, any CVV, to simulate a
   successful payment — no real money moves.

### 2. Run the app

```bash
cd career_portal
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

The app will be available at `http://127.0.0.1:5000`.

On first run it automatically:
- Creates `career_portal.db` with the required tables.
- Seeds a demo admin/recruiter account:
  - **Email**: `admin@careerportal.com`
  - **Password**: `admin123`

## Typical demo flow

1. Log in as the admin (`admin@careerportal.com` / `admin123`) and post a
   job, e.g. title "Python Developer", required skills
   `Python, Flask, SQL, Machine Learning`.
2. Log out, click **Register**, and create a student account.
3. Browse jobs on the home page, open the job, and click **Apply Now**.
4. You'll be routed to the **application fee** page first — click
   **Pay ₹50 with Razorpay** and complete the test-mode checkout using the
   Razorpay test card above.
5. Once payment succeeds, you're redirected straight to the resume upload
   form — upload a resume (PDF or DOCX) and you'll instantly see an ATS score.
6. Check **My Dashboard** to see the application, ATS score, matched/missing
   skills, and status.
7. Log back in as admin → **Admin Dashboard** → **View Applicants** to see
   all candidates ranked by ATS score, with matched/missing skills, and
   change their status (Shortlisted / Rejected / Hired).

## Notes / next steps for extending this

- ATS scoring weights (60% skill match / 40% semantic similarity) are set
  in `resume_analysis.py::analyze_resume` and easy to tune.
- To move beyond SQLite (e.g. for production), swap out `db.py` for
  SQLAlchemy pointed at PostgreSQL/MySQL — the query shapes are simple
  enough to port directly.
- To add resend/forgot-password, email notifications, resume parsing for
  contact details/education, or a recruiter-facing search-by-skill, those
  are natural next modules to layer on top of this base.
