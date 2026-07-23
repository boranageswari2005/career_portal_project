"""
AI-based resume analysis and ATS scoring.

Approach:
1. Extract raw text from the uploaded resume (PDF / DOCX).
2. Clean and normalize both the resume text and the job description.
3. Compute a semantic similarity score using TF-IDF + cosine similarity
   (scikit-learn) between resume and job description.
4. Compute a keyword/skill match score by checking which required skills
   for the job actually appear in the resume text.
5. Combine both signals into a final ATS score (0-100) plus a
   human-readable breakdown of matched / missing skills.
"""

import re
import pdfplumber
import docx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def extract_text_from_resume(filepath):
    """Extract raw text from a PDF or DOCX resume file."""
    text = ""
    if filepath.lower().endswith(".pdf"):
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    elif filepath.lower().endswith((".docx", ".doc")):
        document = docx.Document(filepath)
        text = "\n".join(p.text for p in document.paragraphs)
    return text.strip()


def _clean_text(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s+#./-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tfidf_similarity(resume_text, job_text):
    """Cosine similarity between resume and job description using TF-IDF."""
    if not resume_text.strip() or not job_text.strip():
        return 0.0
    vectorizer = TfidfVectorizer(stop_words="english")
    try:
        tfidf_matrix = vectorizer.fit_transform([resume_text, job_text])
    except ValueError:
        return 0.0
    similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
    return round(float(similarity) * 100, 2)


def _skill_match(resume_text, required_skills):
    """Check which required skills (comma-separated) appear in the resume."""
    skills = [s.strip().lower() for s in required_skills.split(",") if s.strip()]
    if not skills:
        return 0.0, [], []

    matched, missing = [], []
    for skill in skills:
        # word-boundary-ish match so "java" doesn't match "javascript" falsely
        pattern = r"(?<!\w)" + re.escape(skill) + r"(?!\w)"
        if re.search(pattern, resume_text):
            matched.append(skill)
        else:
            missing.append(skill)

    match_pct = round((len(matched) / len(skills)) * 100, 2) if skills else 0.0
    return match_pct, matched, missing


def analyze_resume(resume_filepath, job_description, required_skills):
    """
    Run full ATS analysis. Returns a dict with:
      - ats_score: float (0-100)
      - similarity_score: float (semantic match to job description)
      - skill_match_score: float (% of required skills found)
      - matched_skills / missing_skills: lists
      - resume_text: extracted raw text (stored for later reference)
    """
    raw_text = extract_text_from_resume(resume_filepath)
    cleaned_resume = _clean_text(raw_text)
    cleaned_job = _clean_text(job_description)

    similarity_score = _tfidf_similarity(cleaned_resume, cleaned_job)
    skill_match_score, matched, missing = _skill_match(cleaned_resume, required_skills)

    # Weighted final score: skill match matters more for ATS-style screening
    ats_score = round((0.6 * skill_match_score) + (0.4 * similarity_score), 2)
    ats_score = min(ats_score, 100.0)

    return {
        "ats_score": ats_score,
        "similarity_score": similarity_score,
        "skill_match_score": skill_match_score,
        "matched_skills": matched,
        "missing_skills": missing,
        "resume_text": raw_text,
    }
