import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "career_portal.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    ALLOWED_EXTENSIONS = {"pdf", "docx", "doc"}
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB max resume size

    # --- Razorpay (test mode) ---
    # Get these from https://dashboard.razorpay.com/app/keys (use the TEST keys, not live)
    RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "rzp_test_TGvrPyEBB2xjKj")
    RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "1xIT498U7V9CTjIjQKnrs0Px")
    APPLICATION_FEE_PAISE = 5000  # ₹50.00 — Razorpay amounts are in paise (smallest unit)
    APPLICATION_FEE_DISPLAY = "₹50"
