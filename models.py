from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # Auth Info
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    # Optional Identity Details
    first_name = db.Column(db.String(30))
    last_name = db.Column(db.String(30))

    # Plan & Token Logic
    plan = db.Column(db.String(20), default="free")   # free, pro, ultimate
    tokens = db.Column(db.Integer, default=3)         # current available tokens
    last_token_reset = db.Column(db.DateTime, default=datetime.utcnow)
    last_generated = db.Column(db.DateTime, nullable=True)

    # Relationships
    resumes = db.relationship("Resume", backref="user", lazy=True)
    purchases = db.relationship("Purchase", backref="user", lazy=True)

    # --- Plan Helpers ---
    def is_free_user(self):
        return self.plan == "free"

    def is_pro_user(self):
        return self.plan == "pro"

    def is_ultimate_user(self):
        return self.plan == "ultimate"

    # --- Token Logic ---
    def has_tokens(self):
        """Check if user has tokens or unlimited plan."""
        return self.tokens > 0 or self.is_ultimate_user()

    def deduct_token(self):
        """Deduct a token unless ultimate user."""
        if not self.is_ultimate_user():
            self.tokens = max(0, self.tokens - 1)

    def reset_tokens_if_needed(self):
        """Reset daily tokens based on plan type (runs once every 24h)."""
        now = datetime.utcnow()
        if not self.last_token_reset or (now - self.last_token_reset).days >= 1:
            if self.is_free_user():
                self.tokens = 3
            elif self.is_pro_user():
                self.tokens = 15
            # Ultimate users don’t need tokens
            self.last_token_reset = now


class Resume(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # Resume Fields
    name = db.Column(db.String(100))
    profession = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    linkedin = db.Column(db.String(150))
    bio = db.Column(db.Text)
    skills = db.Column(db.Text)

    # Work
    job_title = db.Column(db.String(100))
    company = db.Column(db.String(100))
    job_desc = db.Column(db.Text)

    # Education
    degree = db.Column(db.String(100))
    institute = db.Column(db.String(150))
    grad_year = db.Column(db.String(10))

    # Meta
    profile_pic_url = db.Column(db.String(300))
    template = db.Column(db.String(50), default="classic")
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class Purchase(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    amount = db.Column(db.Integer)          # Amount in INR
    description = db.Column(db.String(100)) # e.g. "Pro Pack", "1 Token"
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
