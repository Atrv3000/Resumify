from datetime import datetime
import os
import requests
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import FREE_TEMPLATES
from forms import LoginForm, RegisterForm
from models import db, User, Resume, Purchase
# ==============================
# 🔧 App Setup
# ==============================
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or "dev_key"
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///Resumify.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
db.init_app(app)

# ==============================
# 🔐 Login Manager
# ==============================
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==============================
# 🤖 AI Utility
# ==============================
def get_ai_response(prompt, system_prompt, temperature=0.7, max_tokens=150):
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5000",
        "X-Title": "Resumify"
    }
    payload = {
        "model": "deepseek/deepseek-chat-v3-0324:free",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    try:
        res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=10)
        if res.status_code == 200:
            return res.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print("[AI ERROR]", e)
    return None

def generate_bio(name, profession, skills):
    prompt = (
        f"Write a first-person 2–3 sentence summary for a resume. "
        f"The person is named {name}, a {profession}, skilled in {skills}. "
        f"The tone should be confident, creative, and slightly poetic—like a personal brand pitch. "
        f"Begin with 'I am' or 'I'm'. Mention how their skills come together to create functional and meaningful work."
    )
    system = "You are a professional copywriter for personal branding. Avoid generic fluff. Keep it human and inspired."
    return get_ai_response(prompt, system) or (
        f"I'm {name}, a {profession} skilled in {skills}, blending creativity and logic to craft meaningful work."
    )

# ==============================
# 🌐 Routes
# ==============================

@app.route('/')
def index():
    return render_template("index.html")


@app.route('/start')
@login_required
def start():
    return render_template("start.html")


@app.route('/generate', methods=['POST'])
@login_required
def generate():
    # --- Step 1: Refresh tokens if needed ---
    current_user.reset_tokens_if_needed()
    db.session.commit()

    form = request.form
    template = form.get('template', 'classic')

    # --- Step 2: Premium template check ---
    is_premium = template not in FREE_TEMPLATES
    if is_premium and not (current_user.is_pro_user() or current_user.is_ultimate_user()):
        flash("This template is only available for Pro or Ultimate users.", "error")
        return redirect(url_for('pricing'))

    # --- Step 3: Token availability check ---
    if not current_user.has_tokens():
        flash("You're out of tokens. Please buy more or wait for your daily reset.", "error")
        return redirect(url_for('pricing'))

    # --- Step 4: Profile picture handling ---
    pic_url = None
    if 'profile_pic' in request.files:
        pic = request.files['profile_pic']
        if pic and pic.filename:
            filename = secure_filename(pic.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            pic.save(filepath)
            pic_url = f"/static/uploads/{filename}"

    # --- Step 5: Bio generation (fallback to AI if empty) ---
    skills = [s.strip() for s in form.get('skills', '').split(',') if s.strip()]
    bio = form.get('bio', '').strip() or generate_bio(
        form['name'], 
        form['profession'], 
        ', '.join(skills)
    )

    # --- Step 6: Save Resume to DB ---
    resume = Resume(
        user_id=current_user.id,
        name=form['name'],
        profession=form['profession'],
        email=form.get('email', ''),
        phone=form.get('phone', ''),
        linkedin=form.get('linkedin', ''),
        bio=bio,
        skills=','.join(skills),
        job_title=form.get('job_title', ''),
        company=form.get('company', ''),
        job_desc=form.get('job_desc', ''),
        degree=form.get('degree', ''),
        institute=form.get('institute', ''),
        grad_year=form.get('grad_year', ''),
        profile_pic_url=pic_url,
        template=template
    )
    db.session.add(resume)

    # --- Step 7: Deduct token & commit ---
    current_user.deduct_token()
    current_user.last_generated = datetime.utcnow()
    db.session.commit()

    # --- Step 8: Render resume directly ---
    context = {
        'name': resume.name,
        'profession': resume.profession,
        'email': resume.email,
        'phone': resume.phone,
        'linkedin': resume.linkedin,
        'bio': resume.bio,
        'skills': skills,
        'job_title': resume.job_title,
        'company': resume.company,
        'job_desc': resume.job_desc,
        'degree': resume.degree,
        'institute': resume.institute,
        'grad_year': resume.grad_year,
        'profile_pic_url': resume.profile_pic_url
    }

    flash("Resume generated successfully!", "success")
    return render_template(f"resume_{template}.html", **context)


@app.route('/my-resumes')
@login_required
def my_resumes():
    resumes = Resume.query.filter_by(user_id=current_user.id).order_by(Resume.timestamp.desc()).all()
    return render_template('my_resumes.html', resumes=resumes)

@app.route('/resume/<int:resume_id>')
@login_required
def view_resume(resume_id):
    resume = Resume.query.filter_by(id=resume_id, user_id=current_user.id).first_or_404()
    context = {
        'name': resume.name,
        'profession': resume.profession,
        'email': resume.email,
        'phone': resume.phone,
        'linkedin': resume.linkedin,
        'bio': resume.bio,
        'skills': [s.strip() for s in resume.skills.split(',')],
        'job_title': resume.job_title,
        'company': resume.company,
        'job_desc': resume.job_desc,
        'degree': resume.degree,
        'institute': resume.institute,
        'grad_year': resume.grad_year,
        'profile_pic_url': resume.profile_pic_url
    }
    return render_template(f"resume_{resume.template}.html", **context)

@app.route('/delete_resume/<int:resume_id>', methods=['POST'])
@login_required
def delete_resume(resume_id):
    print(f"[DEBUG] Delete resume called with ID: {resume_id}")
    print(f"[DEBUG] Current user ID: {current_user.id}")
    
    resume = Resume.query.get_or_404(resume_id)
    print(f"[DEBUG] Found resume: {resume.name} owned by user {resume.user_id}")
    
    if resume.user_id != current_user.id:
        flash("Unauthorized", "error")
        return redirect(url_for('start'))

    db.session.delete(resume)
    db.session.commit()
    flash("Resume deleted successfully!", "success")
    print(f"[DEBUG] Resume {resume_id} deleted successfully")
    return redirect(url_for('my_resumes'))


@app.route('/resume/<int:resume_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_resume(resume_id):
    original = Resume.query.filter_by(id=resume_id, user_id=current_user.id).first_or_404()

    if request.args.get('duplicate') == '1':
        duplicate = Resume(
            user_id=current_user.id,
            name=original.name,
            profession=original.profession,
            email=original.email,
            phone=original.phone,
            linkedin=original.linkedin,
            bio=original.bio,
            skills=original.skills,
            job_title=original.job_title,
            company=original.company,
            job_desc=original.job_desc,
            degree=original.degree,
            institute=original.institute,
            grad_year=original.grad_year,
            profile_pic_url=original.profile_pic_url,
            template=original.template
        )
        db.session.add(duplicate)
        db.session.commit()
        flash("Resume duplicated. You can now edit it.", "info")
        return redirect(url_for('edit_resume', resume_id=duplicate.id))

    if request.method == 'POST':
        form = request.form
        original.name = form['name']
        original.profession = form['profession']
        original.email = form.get('email', '')
        original.phone = form.get('phone', '')
        original.linkedin = form.get('linkedin', '')
        original.bio = form.get('bio', '')
        original.skills = form.get('skills', '')
        original.job_title = form.get('job_title', '')
        original.company = form.get('company', '')
        original.job_desc = form.get('job_desc', '')
        original.degree = form.get('degree', '')
        original.institute = form.get('institute', '')
        original.grad_year = form.get('grad_year', '')
        original.template = form.get('template', 'classic')

        if 'profile_pic' in request.files:
            pic = request.files['profile_pic']
            if pic and pic.filename:
                filename = secure_filename(pic.filename)
                path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                pic.save(path)
                original.profile_pic_url = f"/static/uploads/{filename}"

        db.session.commit()
        flash("Resume updated successfully!", "success")
        return redirect(url_for('my_resumes'))

    return render_template('edit_resume.html', resume=original)

@app.route('/buy_token/<int:count>')
@login_required
def buy_token(count):
    price_map = {1: 50, 5: 100}
    amount = price_map.get(count, 0)
    if amount == 0:
        flash("Invalid token pack selected.", "error")
        return redirect(url_for('pricing'))

    current_user.tokens += count
    purchase = Purchase(user_id=current_user.id, amount=amount, description=f"{count} Token Pack")
    db.session.add(purchase)
    db.session.commit()

    flash(f"{count} token{'s' if count > 1 else ''} purchased successfully.", "success")
    return redirect(url_for('pricing'))

@app.route('/upgrade/<string:plan>')
@login_required
def upgrade(plan):
    if plan == 'pro':
        current_user.tokens += 15
        current_user.plan = 'pro'
        purchase = Purchase(user_id=current_user.id, amount=199, description='Pro Pack')
        flash("Upgraded to Pro Pack. 15 tokens added + Premium templates unlocked.", "success")
    elif plan == 'ultimate':
        current_user.tokens = 9999
        current_user.plan = 'ultimate'
        purchase = Purchase(user_id=current_user.id, amount=499, description='Ultimate Pack')
        flash("Welcome to Ultimate Pack. Unlimited tokens + all templates unlocked.", "success")
    else:
        flash("Invalid upgrade option.", "error")
        return redirect(url_for('pricing'))

    db.session.add(purchase)
    db.session.commit()
    return redirect(url_for('my_resumes'))

@app.route('/pricing')
def pricing():
    return render_template('pricing.html')

@app.route('/regen/bio', methods=['POST'])
@login_required
def regenerate_bio():
    data = request.get_json()
    bio = generate_bio(data.get('name'), data.get('profession'), data.get('skills'))
    return jsonify({"bio": bio})

@app.route('/resume/<int:resume_id>/download', methods=['POST'])
@login_required
def download_resume(resume_id):
    resume = Resume.query.get_or_404(resume_id)
    if resume.user_id != current_user.id:
        flash("Access denied.", "error")
        return redirect(url_for('my_resumes'))

    context = {
        'name': resume.name,
        'profession': resume.profession,
        'email': resume.email,
        'phone': resume.phone,
        'linkedin': resume.linkedin,
        'bio': resume.bio,
        'skills': [s.strip() for s in resume.skills.split(',')],
        'job_title': resume.job_title,
        'company': resume.company,
        'job_desc': resume.job_desc,
        'degree': resume.degree,
        'institute': resume.institute,
        'grad_year': resume.grad_year,
        'profile_pic_url': resume.profile_pic_url
    }

    html = render_template(f"resume_{resume.template}.html", **context)
    folder = f"temp_resume_{resume_id}"
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, "resume.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    return "Resume HTML saved."  # Optional response

# ==============================
# 🔐 Auth Routes
# ==============================

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash("Email already registered.", "error")
            return redirect(url_for('register'))

        username = f"{form.first_name.data.lower()}.{form.last_name.data.lower()}"
        hashed_pw = generate_password_hash(form.password.data)

        new_user = User(
            username=username,
            first_name=form.first_name.data,
            last_name=form.last_name.data,
            email=form.email.data,
            password=hashed_pw,
            tokens=3,
            plan='free'
        )

        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        flash("Account created successfully!", "success")
        return redirect(url_for('index'))

    return render_template("register.html", form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and check_password_hash(user.password, form.password.data):
            login_user(user)
            flash('Logged in successfully.', 'success')
            return redirect(url_for('index'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Logged out successfully.", "success")
    return redirect(url_for('login'))

# ==============================
# 🚀 Run Server
# ==============================
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
