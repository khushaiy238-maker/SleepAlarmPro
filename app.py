from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from google import genai
import os
import sys
import subprocess
load_dotenv()

# ==========================================================
# LOAD ENVIRONMENT VARIABLES
# ==========================================================

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')


# ==========================================================

if not GEMINI_API_KEY:
    print("=" * 60)
    print("WARNING: GEMINI_API_KEY NOT FOUND")
    print("Check your .env file.")
    print("=" * 60)
    client = None
else:
    client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================================
# FLASK APP
# ==========================================================

app = Flask(__name__)

# ==========================================================
# SECRET KEY
# ==========================================================

app.config["SECRET_KEY"] = "sleepalarm123"

# ==========================================================
# DATABASE
# ==========================================================

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace(
        "postgres://",
        "postgresql://",
        1
    )

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ==========================================================
# AI STATUS
# ==========================================================

ai_status = "Ready"
camera_status = "OFF"
study_camera_process = None

# ==========================================================
# USER MODEL
# ==========================================================

class User(db.Model):

    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    fullname = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(255),
        nullable=False
    )


# ==========================================================
# STUDY SESSION MODEL
# ==========================================================

class StudySession(db.Model):

    __tablename__ = "study_sessions"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id")
    )

    study_time = db.Column(
        db.Integer,
        default=0
    )

    focus_score = db.Column(
        db.Integer,
        default=0
    )

    drowsiness_count = db.Column(
        db.Integer,
        default=0
    )

    session_date = db.Column(
        db.DateTime,
        server_default=db.func.now()
    )


# ==========================================================
# HOME
# ==========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# ==========================================================
# FEATURES
# ==========================================================

@app.route("/features")
def features():

    return render_template(
        "features.html"
    )


# ==========================================================
# LOGIN
# ==========================================================

@app.route(
    "/login",
    methods=["GET", "POST"]
)
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        user = User.query.filter_by(
            email=email,
            password=password
        ).first()

        if user:

            return redirect(
                url_for("dashboard")
            )

        return render_template(
            "login.html",
            error="Invalid Email or Password!"
        )

    return render_template(
        "login.html"
    )


# ==========================================================
# REGISTER
# ==========================================================

@app.route(
    "/register",
    methods=["GET", "POST"]
)
def register():

    if request.method == "POST":

        fullname = request.form.get(
            "fullname",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if not fullname or not email or not password:

            return render_template(
                "register.html",
                error="Please fill all fields."
            )

        if password != confirm_password:

            return render_template(
                "register.html",
                error="Passwords do not match!"
            )

        existing_user = User.query.filter_by(
            email=email
        ).first()

        if existing_user:

            return render_template(
                "register.html",
                error="Email already registered!"
            )

        new_user = User(
            fullname=fullname,
            email=email,
            password=password
        )

        db.session.add(new_user)
        db.session.commit()

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html"
    )


# ==========================================================
# DASHBOARD
# ==========================================================

@app.route("/dashboard")
def dashboard():

    global ai_status
    global camera_status

    user = User.query.first()

    latest_session = StudySession.query.order_by(
        StudySession.id.desc()
    ).first()

    sessions = StudySession.query.order_by(
        StudySession.id.desc()
    ).all()

    total_sessions = len(sessions)

    total_minutes = sum(
        (s.study_time or 0)
        for s in sessions
    )

    if total_sessions > 0:

        average_focus = round(
            sum(
                (s.focus_score or 0)
                for s in sessions
            ) / total_sessions
        )

        best_focus = max(
            (s.focus_score or 0)
            for s in sessions
        )

    else:

        average_focus = 0
        best_focus = 0

    return render_template(

        "dashboard.html",

        user=user,

        session=latest_session,

        sessions=sessions,

        total_sessions=total_sessions,

        total_minutes=total_minutes,

        average_focus=average_focus,

        best_focus=best_focus,

        ai_status=ai_status,

        camera_status=camera_status

    )


# ==========================================================
# PROFILE
# ==========================================================

@app.route("/profile")
def profile():

    user = User.query.first()

    return render_template(
        "profile.html",
        user=user
    )


# ==========================================================
# STUDY PAGE
# ==========================================================

@app.route("/study")
def study():

    return render_template(
        "study.html"
    )


# ==========================================================
# START STUDY SESSION
# ==========================================================

@app.route(
    "/start_study_session",
    methods=["POST"]
)
def start_study_session():

    global study_camera_process
    global ai_status
    global camera_status

    subject = request.form.get(
        "subject",
        ""
    ).strip()

    goal = request.form.get(
        "goal",
        ""
    ).strip()

    duration = request.form.get(
        "duration",
        "30"
    )

    try:
        duration = int(duration)
    except ValueError:
        duration = 30

    if duration < 1:
        duration = 30

    print("=" * 60)
    print("STARTING STUDY SESSION")
    print("Subject:", subject)
    print("Goal:", goal)
    print("Duration:", duration, "minutes")
    print("=" * 60)

    # Find your existing AI camera file
    ai_file = os.path.join(
        os.path.dirname(__file__),
        "camera",
        "blink_detection.py"
    )

    print("AI FILE:")
    print(ai_file)

    # Check that the file exists
    if not os.path.exists(ai_file):

        print("ERROR: blink_detection.py NOT FOUND")

        return (
            "Camera AI file was not found. "
            "Check camera/blink_detection.py"
        ), 500

    # Start your EXISTING AI camera
    try:

        if (
            study_camera_process is None
            or study_camera_process.poll() is not None
        ):

            study_camera_process = subprocess.Popen(
                [
                    sys.executable,
                    ai_file
                ],
                cwd=os.path.dirname(ai_file)
            )

            ai_status = "Running"
            camera_status = "ON"

            print("=" * 60)
            print("CAMERA AI STARTED")
            print("=" * 60)

        else:

            print("Camera AI is already running.")

    except Exception as e:

        print("=" * 60)
        print("CAMERA AI START ERROR")
        print(e)
        print("=" * 60)

        ai_status = "Error"
        camera_status = "OFF"

        return (
            "Could not start camera AI: "
            + str(e)
        ), 500

    # Open the study session page
    return render_template(
        "study_active.html",
        subject=subject,
        goal=goal,
        duration=duration
    )


# ==========================================================
# SAVE COMPLETED STUDY SESSION
# ==========================================================

@app.route(
    "/save_completed_session",
    methods=["POST"]
)
def save_completed_session():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        studied_minutes = int(
            data.get(
                "studied_minutes",
                1
            )
        )

        if studied_minutes < 1:
            studied_minutes = 1

        new_session = StudySession(

            user_id=1,

            study_time=studied_minutes,

            focus_score=100,

            drowsiness_count=0

        )

        db.session.add(
            new_session
        )

        db.session.commit()

        print("=" * 60)
        print("STUDY SESSION SAVED")
        print(
            "Study Time:",
            studied_minutes,
            "minutes"
        )
        print("=" * 60)

        return jsonify({

            "success": True,

            "message":
            "Study session saved successfully!"

        })

    except Exception as e:

        db.session.rollback()

        print("=" * 60)
        print("STUDY SESSION SAVE ERROR")
        print(e)
        print("=" * 60)

        return jsonify({

            "success": False,

            "message":
            "Could not save study session."

        }), 500


# ==========================================================
# ANALYTICS
# ==========================================================

@app.route("/analytics")
def analytics():

    sessions = StudySession.query.order_by(
        StudySession.session_date.desc()
    ).all()

    total_time = db.session.query(
        db.func.sum(
            StudySession.study_time
        )
    ).scalar()

    if total_time is None:
        total_time = 0

    avg_focus = db.session.query(
        db.func.avg(
            StudySession.focus_score
        )
    ).scalar()

    if avg_focus is None:
        avg_focus = 0

    total_drowsiness = db.session.query(
        db.func.sum(
            StudySession.drowsiness_count
        )
    ).scalar()

    if total_drowsiness is None:
        total_drowsiness = 0

    highest_focus = db.session.query(
        db.func.max(
            StudySession.focus_score
        )
    ).scalar()

    if highest_focus is None:
        highest_focus = 0

    total_sessions = StudySession.query.count()

    return render_template(

        "analytics.html",

        sessions=sessions,

        total_sessions=total_sessions,

        total_time=total_time,

        avg_focus=round(avg_focus),

        highest_focus=highest_focus,

        total_drowsiness=total_drowsiness

    )


# ==========================================================
# GAMES
# ==========================================================

@app.route("/games")
def games():

    return render_template(
        "games.html"
    )


# ==========================================================
# AI ASSISTANT PAGE
# ==========================================================

@app.route("/ai_assistant")
def ai_assistant():

    return render_template(
        "ai_assistant.html"
    )


# ==========================================================
# ASK AI
# ==========================================================

@app.route(
    "/ask_ai",
    methods=["POST"]
)
def ask_ai():

    try:

        # --------------------------------------------------
        # CHECK GEMINI CLIENT
        # --------------------------------------------------

        if client is None:

            return jsonify({

                "answer":
                "Gemini API key was not loaded. "
                "Please check your .env file."

            }), 500

        # --------------------------------------------------
        # GET QUESTION
        # --------------------------------------------------

        data = request.get_json(
            silent=True
        ) or {}

        question = data.get(
            "question",
            ""
        ).strip()

        # --------------------------------------------------
        # EMPTY QUESTION
        # --------------------------------------------------

        if not question:

            return jsonify({

                "answer":
                "Please enter a question."

            })

        # --------------------------------------------------
        # AI INSTRUCTIONS
        # --------------------------------------------------

        system_instruction = """
You are Sleep Alarm Pro AI Assistant.

You are a helpful, intelligent and friendly general-purpose AI assistant.

Answer the user's question regardless of whether it is:
- academic
- programming
- mathematics
- science
- technology
- career-related
- general knowledge
- writing
- explanations
- brainstorming
- everyday questions
- project development
- debugging
- or another safe topic.

Do not restrict yourself only to study questions.

Explain things clearly and naturally.

For programming questions:
- provide correct code when useful
- explain the important parts
- help debug errors

For difficult questions:
- break the answer into simple steps
- use examples when helpful

If the question is ambiguous, ask for clarification.

Be helpful, accurate and concise unless the user asks for more detail.
"""

        # --------------------------------------------------
        # GEMINI REQUEST
        # --------------------------------------------------

        response = client.models.generate_content(

            model="gemini-3.6-flash",

            contents=question,

            config={
                "system_instruction":
                system_instruction
            }

        )

        # --------------------------------------------------
        # GET RESPONSE TEXT
        # --------------------------------------------------

        answer = response.text

        if not answer:

            answer = (
                "I could not generate a response. "
                "Please try asking the question again."
            )

        return jsonify({

            "answer": answer

        })

    except Exception as e:

        print("=" * 60)
        print("AI ASSISTANT ERROR")
        print(e)
        print("=" * 60)

        return jsonify({

            "answer":
            "Sorry, I could not connect to the AI right now. "
            "Please check your Gemini API setup."

        }), 500


# ==========================================================
# MEMORY GAME
# ==========================================================

@app.route("/memory_game")
def memory_game():

    return render_template(
        "memory_games.html"
    )


# ==========================================================
# IT QUIZ
# ==========================================================

@app.route("/it_quiz")
def it_quiz():

    return render_template(
        "IT_quiz.html"
    )


# ==========================================================
# SUDOKU
# ==========================================================

@app.route("/sudoku")
def sudoku():

    return render_template(
        "sudoku.html"
    )


# ==========================================================
# WORD SCRAMBLE
# ==========================================================

@app.route("/word_scramble")
def word_scramble():

    return render_template(
        "word_scramble.html"
    )


# ==========================================================
# COLOR REFLEX
# ==========================================================

@app.route("/color_reflex")
def color_reflex():

    return render_template(
        "color_reflex.html"
    )


# ==========================================================
# SETTINGS
# ==========================================================

# ==========================================================
# SETTINGS
# ==========================================================

SETTINGS_FILE = os.path.join(
    os.path.dirname(__file__),
    "settings.json"
)


def load_settings():

    default_settings = {
        "alarm_sound": True,
        "ai_detection": True,
        "drowsiness_seconds": 3,
        "eye_sensitivity": "normal"
    }

    try:

        if not os.path.exists(SETTINGS_FILE):

            with open(
                SETTINGS_FILE,
                "w"
            ) as f:

                import json

                json.dump(
                    default_settings,
                    f,
                    indent=4
                )

            return default_settings

        import json

        with open(
            SETTINGS_FILE,
            "r"
        ) as f:

            settings_data = json.load(f)

        # Make sure missing settings get defaults
        for key, value in default_settings.items():

            if key not in settings_data:
                settings_data[key] = value

        return settings_data

    except Exception as e:

        print("Settings Load Error:", e)

        return default_settings


def save_settings(settings_data):

    import json

    try:

        with open(
            SETTINGS_FILE,
            "w"
        ) as f:

            json.dump(
                settings_data,
                f,
                indent=4
            )

        return True

    except Exception as e:

        print("Settings Save Error:", e)

        return False


@app.route(
    "/settings",
    methods=["GET", "POST"]
)
def settings():

    if request.method == "POST":

        alarm_sound = (
            request.form.get("alarm_sound")
            == "on"
        )

        ai_detection = (
            request.form.get("ai_detection")
            == "on"
        )

        drowsiness_seconds = request.form.get(
            "drowsiness_seconds",
            "3"
        )

        eye_sensitivity = request.form.get(
            "eye_sensitivity",
            "normal"
        )

        try:

            drowsiness_seconds = int(
                drowsiness_seconds
            )

        except ValueError:

            drowsiness_seconds = 3

        if drowsiness_seconds not in [2, 3, 4, 5]:

            drowsiness_seconds = 3

        if eye_sensitivity not in [
            "low",
            "normal",
            "sensitive"
        ]:

            eye_sensitivity = "normal"

        new_settings = {

            "alarm_sound": alarm_sound,

            "ai_detection": ai_detection,

            "drowsiness_seconds":
                drowsiness_seconds,

            "eye_sensitivity":
                eye_sensitivity

        }

        if save_settings(new_settings):

            return render_template(
                "settings.html",
                settings=new_settings,
                success="Settings saved successfully!"
            )

        return render_template(
            "settings.html",
            settings=new_settings,
            error="Could not save settings."
        )

    current_settings = load_settings()

    return render_template(
        "settings.html",
        settings=current_settings
    )


# ==========================================================
# START AI / CAMERA
# ==========================================================

@app.route("/start_ai")
def start_ai():

    global ai_status
    global camera_status

    ai_status = "Running"
    camera_status = "ON"

    print("=" * 50)
    print("START AI BUTTON CLICKED")
    print("=" * 50)

    ai_file = os.path.join(

        os.path.dirname(__file__),

        "camera",

        "blink_detection.py"

    )

    print("AI File Path:")
    print(ai_file)

    if not os.path.exists(ai_file):

        ai_status = "Error"
        camera_status = "OFF"

        return (
            "Error: blink_detection.py not found!"
        )

    try:

        subprocess.run(

            [
                sys.executable,
                ai_file
            ],

            check=True

        )

        print("=" * 50)
        print("AI Finished Successfully")
        print("=" * 50)

        ai_status = "Stopped"

    except Exception as e:

        print("=" * 50)
        print("AI ERROR")
        print(e)
        print("=" * 50)

        ai_status = "Error"

    finally:

        camera_status = "OFF"

    return redirect(
        url_for("dashboard")
    )


# ==========================================================
# OLD SAVE SESSION ROUTE
# ==========================================================

@app.route("/save_session")
def save_session():

    new_session = StudySession(

        user_id=1,

        study_time=1,

        focus_score=100,

        drowsiness_count=0

    )

    db.session.add(
        new_session
    )

    db.session.commit()

    return (
        "Study Session Saved Successfully!"
    )


# ==========================================================
# DELETE SESSION
# ==========================================================

@app.route(
    "/delete_session/<int:id>"
)
def delete_session(id):

    session = StudySession.query.get_or_404(
        id
    )

    db.session.delete(
        session
    )

    db.session.commit()

    return redirect(
        url_for("dashboard")
    )


# ==========================================================
# DATABASE INITIALIZATION
# ==========================================================

with app.app_context():

    db.create_all()


# ==========================================================
# RUN APPLICATION
# ==========================================================

if __name__ == "__main__":

    print("=" * 60)
    print("🚀 Sleep Alarm Pro Started Successfully")
    print("🌐 URL : http://127.0.0.1:5000")
    print("=" * 60)

    app.run(

        debug=True,

        host="0.0.0.0",

        port=5000

    )
