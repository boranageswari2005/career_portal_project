CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'student',
    phone TEXT,
    skills TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    company TEXT DEFAULT 'Our Company',
    description TEXT NOT NULL,
    required_skills TEXT NOT NULL,
    location TEXT,
    job_type TEXT DEFAULT 'Full-time',
    posted_by INTEGER NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (posted_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    job_id INTEGER NOT NULL,
    resume_filename TEXT NOT NULL,
    resume_text TEXT,
    ats_score REAL DEFAULT 0,
    similarity_score REAL DEFAULT 0,
    skill_match_score REAL DEFAULT 0,
    matched_skills TEXT,
    missing_skills TEXT,
    status TEXT DEFAULT 'Applied',
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, job_id),
    FOREIGN KEY (student_id) REFERENCES users(id),
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    job_id INTEGER NOT NULL,
    razorpay_order_id TEXT NOT NULL,
    razorpay_payment_id TEXT,
    razorpay_signature TEXT,
    amount INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'created',  -- created, paid, failed
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, job_id),
    FOREIGN KEY (student_id) REFERENCES users(id),
    FOREIGN KEY (job_id) REFERENCES jobs(id)
);
