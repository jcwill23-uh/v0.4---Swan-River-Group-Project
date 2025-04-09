import os
import urllib.parse
import logging
from flask import Flask, redirect, url_for, session, request, render_template, jsonify, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from functools import wraps
import msal
import requests
import pyodbc
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from datetime import datetime
import subprocess
from werkzeug.security import generate_password_hash, check_password_hash #Password hashing


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__, template_folder='docs', static_folder='docs')
#app.secret_key = os.getenv('SECRET_KEY')
app.config['SECRET_KEY']= 'sWanRiver'

# Configure session storage
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_FILE_DIR'] = '/tmp/flask_session'
app.config['SESSION_FILE_THRESHOLD'] = 100
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Ensure session directory exists
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

# Azure SQL Database setup
params = urllib.parse.quote_plus(
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=tcp:swan-river-user-information.database.windows.net,1433;"
    "DATABASE=UserDatabase;"
    "UID=jcwill23@cougarnet.uh.edu@swan-river-user-information;"
    "PWD=H1ghLander;"
    "Encrypt=yes;"
    "TrustServerCertificate=no;"
    "Connection Timeout=30"
)

# Configure SQLAlchemy engine
engine = create_engine(
    f"mssql+pyodbc:///?odbc_connect={params}",
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=5,
    max_overflow=10
)

# Bind engine to SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = engine.url
db = SQLAlchemy(app)

# Azure Blob Storage Configuration - USER'S SIGNATURE PHOTO
SIGNATURE_STORAGE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=usersignatures;AccountKey=rGwYQGqikAfq0XDTasLRbd5HTQkbVW2s8NClGZ9NGdCknqdp8MBGEo8/WEdd/GO205SYcwyOz+cL+ASt/PQdPQ==;EndpointSuffix=core.windows.net"
SIGNATURE_CONTAINER_NAME = "signatures"
STORAGE_ACCOUNT_NAME = "usersignatures"

# Azure Blob Storage Configuration - PDF's
PDF_STORAGE_CONNECTION_STRING = "DefaultEndpointsProtocol=https;AccountName=swanriverpdfs;AccountKey=ngToSF78m/0QeZVrW6cgw4xbRfhC+5AsuLJzB0vXoLroL7diVT59uvpIiklgcpc7UqyVHjVH9k5q+AStzdWBMw==;EndpointSuffix=core.windows.net"
PDF_CONTAINER_NAME = "releaseforms"

# Initialize Azure Blob Clients
signature_blob_service = BlobServiceClient.from_connection_string(SIGNATURE_STORAGE_CONNECTION_STRING)
pdf_blob_service = BlobServiceClient.from_connection_string(PDF_STORAGE_CONNECTION_STRING)

# Container Clients
signature_container_client = signature_blob_service.get_container_client(SIGNATURE_CONTAINER_NAME)
pdf_container_client = pdf_blob_service.get_container_client(PDF_CONTAINER_NAME)

# ---- Database Models ----

# User Model
class User(db.Model):
    __tablename__ = 'User'
    
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(50), nullable=False)
    middle_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(150), nullable=False) #for creating accounts
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), default="basicuser")
    status = db.Column(db.String(20), default="active")
    signature_url = db.Column(db.String(255), nullable=True)
    pdf_url = db.Column(db.String(255), nullable=True)


# Form Request Model
class ReleaseFormRequest(db.Model):
    __tablename__ = "release_form_request"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    
    # General Student Information
    student_name = db.Column(db.String(255), nullable=False)
    peoplesoft_id = db.Column(db.String(7), nullable=False)
    user_email = db.Column(db.String(255), nullable=False)
    user_id = db.Column(db.Integer, nullable=False)

    # Release Form-Specific Fields
    password = db.Column(db.String(10), nullable=True)  # 10-character max password
    campus = db.Column(db.String(50), nullable=True)  # Selected UH campus
    categories = db.Column(db.String(255), nullable=True)  # List of selected categories
    specific_info = db.Column(db.String(255), nullable=True)  # Information to be released
    release_to = db.Column(db.String(255), nullable=True)  # Names of individuals receiving info
    purpose = db.Column(db.String(255), nullable=True)  # Purpose of information release
    other_category_text = db.Column(db.String(255), nullable=True)  # If "Other" category is chosen
    other_info_text = db.Column(db.String(255), nullable=True)  # If "Other" info is chosen
    other_purpose_text = db.Column(db.String(255), nullable=True)  # If "Other" purpose is chosen

    # SSN Form-Specific Fields
    toChange = db.Column(db.String(20), nullable=True)  # Tracks whether 'name' or 'ssn' is updated
    name_change_reason = db.Column(db.String(50), nullable=True)
    ssn_change_reason = db.Column(db.String(50), nullable=True)

    # Name Change Fields (Old & New)
    old_first_name = db.Column(db.String(50), nullable=True)
    old_middle_name = db.Column(db.String(50), nullable=True)
    old_last_name = db.Column(db.String(50), nullable=True)
    old_suffix = db.Column(db.String(10), nullable=True)
    new_first_name = db.Column(db.String(50), nullable=True)
    new_middle_name = db.Column(db.String(50), nullable=True)
    new_last_name = db.Column(db.String(50), nullable=True)
    new_suffix = db.Column(db.String(10), nullable=True)

    # SSN Change Fields (Stored in XXX-XX-XXXX format)
    old_ssn = db.Column(db.String(11), nullable=True)
    new_ssn = db.Column(db.String(11), nullable=True)

    #RCL Form fields
    rcl_reason = db.Column(db.String(50))
    academic_subreason = db.Column(db.String(50))
    iai_explanation = db.Column(db.Text)
    icl_class1 = db.Column(db.String(255))
    icl_prof1 = db.Column(db.String(255))
    icl_sign1 = db.Column(db.String(255))
    icl_date1 = db.Column(db.String(255))
    icl_class2 = db.Column(db.String(255))
    icl_prof2 = db.Column(db.String(255))
    icl_sign2 = db.Column(db.String(255))
    icl_date2 = db.Column(db.String(255))
    medical_subreason = db.Column(db.String(50))
    final_hours = db.Column(db.String(10))
    uh_hours = db.Column(db.String(10))
    other_hours = db.Column(db.String(10))
    other_school = db.Column(db.String(255))
    rcl_term = db.Column(db.String(10))
    rcl_term_year_fall = db.Column(db.String(4))
    rcl_term_year_spring = db.Column(db.String(4))
    drop_class_1 = db.Column(db.String(255))
    drop_class_2 = db.Column(db.String(255))
    drop_class_3 = db.Column(db.String(255))
    hours_after_drop = db.Column(db.String(10))
    hours_term = db.Column(db.String(10))
    hours_year_fall = db.Column(db.String(4))
    hours_year_spring = db.Column(db.String(4))

    # Signature & PDF Storage
    signature_url = db.Column(db.String(255), nullable=True)
    pdf_url = db.Column(db.String(255), nullable=True)

    # Approval Workflow & Status
    approval_status = db.Column(db.String(20), nullable=False, default="pending")  # Values: pending, approved, returned, rejected
    submitted_at = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)

    # Form name
    form_name = db.Column(db.String(255))
    
    comments = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<ReleaseFormRequest {self.id} - {self.student_name} - {self.peoplesoft_id}>"


# ---- API Routes ----

# Route to handle form submission
@app.route('/submit_course_load', methods=['POST'])
def submit_course_load():
    try:
        data = request.form
        is_final_submission = data.get("final_submission") == "true"
        form_id = data.get("form_id")

        # Extract and format names
        student_name = (data.get('first_name') or "").strip() + " " + (data.get('middle_name') or "").strip() + " " + (data.get('last_name') or "").strip()
        uhid = data.get("peoplesoft_id", "").strip()
        user_email = session["user"]["email"]
        user = User.query.filter_by(email=user_email).first()
        if not user:
            return jsonify({"error": "User not found"}), 404
        user_id = user.id
        signature_url = data.get('signature_url', None)

        approval_status = "pending" if is_final_submission else "draft"
        form_name = "RCL"

        form_instance = None

        if form_id:
            existing_request = ReleaseFormRequest.query.get(form_id)

            if existing_request:
                existing_request.student_name = student_name
                existing_request.peoplesoft_id = uhid
                existing_request.user_email = user_email
                existing_request.user_id = user_id
                existing_request.rcl_reason = data.get("rcl_reason")
                existing_request.academic_subreason = data.get("academic_subreason")
                existing_request.iai_explanation = data.get("iai_explanation")
                existing_request.icl_class1 = data.get("icl_class1")
                existing_request.icl_prof1 = data.get("icl_prof1")
                existing_request.icl_sign1 = data.get("icl_sign1")
                existing_request.icl_date1 = data.get("icl_date1")
                existing_request.icl_class2 = data.get("icl_class2")
                existing_request.icl_prof2 = data.get("icl_prof2")
                existing_request.icl_sign2 = data.get("icl_sign2")
                existing_request.icl_date2 = data.get("icl_date2")
                existing_request.medical_subreason = data.get("medical_subreason")
                existing_request.final_hours = data.get("final_hours")
                existing_request.uh_hours = data.get("uh_hours")
                existing_request.other_hours = data.get("other_hours")
                existing_request.other_school = data.get("other_school")
                existing_request.rcl_term = data.get("rcl_term")
                existing_request.rcl_term_year_fall = data.get("rcl_term_year_fall")
                existing_request.rcl_term_year_spring = data.get("rcl_term_year_spring")
                existing_request.drop_class_1 = data.get("drop_class_1")
                existing_request.drop_class_2 = data.get("drop_class_2")
                existing_request.drop_class_3 = data.get("drop_class_3")
                existing_request.hours_after_drop = data.get("hours_after_drop")
                existing_request.hours_term = data.get("hours_term")
                existing_request.hours_year_fall = data.get("hours_year_fall")
                existing_request.hours_year_spring = data.get("hours_year_spring")
                existing_request.signature_url = signature_url
                existing_request.approval_status = approval_status
                existing_request.submitted_at = datetime.utcnow() if is_final_submission else None
                existing_request.form_name = form_name
                db.session.commit()
                form_instance = existing_request
            else:
                return jsonify({"error": "Draft not found."}), 404

        else:
            new_request = ReleaseFormRequest(
                student_name=student_name,
                peoplesoft_id=uhid,
                user_email=user_email,
                user_id=user_id,
                rcl_reason=data.get("rcl_reason"),
                academic_subreason=data.get("academic_subreason"),
                iai_explanation=data.get("iai_explanation"),
                icl_class1=data.get("icl_class1"),
                icl_prof1=data.get("icl_prof1"),
                icl_sign1=data.get("icl_sign1"),
                icl_date1=data.get("icl_date1"),
                icl_class2=data.get("icl_class2"),
                icl_prof2=data.get("icl_prof2"),
                icl_sign2=data.get("icl_sign2"),
                icl_date2=data.get("icl_date2"),
                medical_subreason=data.get("medical_subreason"),
                final_hours=data.get("final_hours"),
                uh_hours=data.get("uh_hours"),
                other_hours=data.get("other_hours"),
                other_school=data.get("other_school"),
                rcl_term=data.get("rcl_term"),
                rcl_term_year_fall=data.get("rcl_term_year_fall"),
                rcl_term_year_spring=data.get("rcl_term_year_spring"),
                drop_class_1=data.get("drop_class_1"),
                drop_class_2=data.get("drop_class_2"),
                drop_class_3=data.get("drop_class_3"),
                hours_after_drop=data.get("hours_after_drop"),
                hours_term=data.get("hours_term"),
                hours_year_fall=data.get("hours_year_fall"),
                hours_year_spring=data.get("hours_year_spring"),
                signature_url=signature_url,
                approval_status=approval_status,
                form_name=form_name,
                submitted_at=datetime.utcnow() if is_final_submission else None
            )
            db.session.add(new_request)
            db.session.commit()
            form_instance = new_request

        if not form_instance:
            return jsonify({"error": "Failed to process form."}), 500
        
        # Fetch user object before PDF generation
        user = User.query.filter_by(email=session["user"]["email"]).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Generate PDF
        pdf_dir = "/mnt/data"
        os.makedirs(pdf_dir, exist_ok=True)

        tex_file_path = os.path.join(pdf_dir, f"form_{form_instance.id}.tex")
        pdf_file_path = os.path.join(pdf_dir, f"form_{form_instance.id}.pdf")

        with open(tex_file_path, "w") as tex_file:
            tex_file.write(generate_course_load_pdf(form_instance, user))

        try:
            pdflatex_path = "pdflatex"
            os.environ["PATH"] += os.pathsep + os.path.dirname(pdflatex_path)

            if not os.path.exists(tex_file_path):
                logger.error("LaTeX file was not created.")
                return jsonify({"error": "LaTeX file was not created."}), 500

            result = subprocess.run(
                [pdflatex_path, "-output-directory", pdf_dir, tex_file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )

            logger.info(f"pdflatex STDOUT:\n{result.stdout.decode()}")
            logger.info(f"pdflatex STDERR:\n{result.stderr.decode()}")

        except subprocess.CalledProcessError as e:
            stderr_output = e.stderr.decode("utf-8", errors="replace")
            stdout_output = e.stdout.decode("utf-8", errors="replace")
            logger.error("PDF generation failed with CalledProcessError")
            logger.error(f"STDOUT:\n{stdout_output}")
            logger.error(f"STDERR:\n{stderr_output}")
            return jsonify({"error": f"PDF generation failed. See logs."}), 500

        
        except FileNotFoundError:
            return jsonify({"error": "pdflatex not found"}), 500

        blob_name = f"release_forms/form_{form_instance.id}.pdf"
        blob_client = pdf_container_client.get_blob_client(blob_name)

        with open(pdf_file_path, "rb") as data:
            if not os.path.exists(pdf_file_path):
                return jsonify({"error": "PDF file was not created successfully."}), 500
            blob_client.upload_blob(data, overwrite=True)

        # Store PDF URL in the database
        pdf_url = f"https://{pdf_blob_service.account_name}.blob.core.windows.net/{PDF_CONTAINER_NAME}/{blob_name}"
        form_instance.pdf_url = pdf_url
        db.session.commit()

        if not is_final_submission:
            return jsonify({"message": "Draft saved successfully."}), 200

        return jsonify({"message": "Form saved successfully", "pdf_url": pdf_url}), 200


    except Exception as e:
        return jsonify({"error": str(e)}), 500

    
#RCL Form PDF Generation
def generate_course_load_pdf(form, user):
    import re

    def latex_escape(text):
        return re.sub(r'([&_{}%$#])', r'\\\1', text) if text else ""

    def safe_value(val, fallback=r"\hspace{3cm}"):
        return latex_escape(val) if val else fallback

    signature_path = download_signature(user.signature_url, user.id) if user.signature_url else "default-signature.png"

    academic_subreason_checkbox = "X" if form.academic_subreason == 'IAI' else ""
    iclp_checkbox = "X" if form.academic_subreason == 'ICLP' else ""
    medical_checkbox = "X" if form.medical_subreason else ""
    final_checkbox = "X" if form.final_hours else ""
    concurrent_checkbox = "X" if form.uh_hours or form.other_hours else ""
    rcl_fall_checkbox = "X" if form.rcl_term == 'fall' else ""
    rcl_spring_checkbox = "X" if form.rcl_term == 'spring' else ""
    fall_hours_check = "X" if form.hours_term == 'fall' else ""
    spring_hours_check = "X" if form.hours_term == 'spring' else ""

    student_name = latex_escape(form.student_name)
    ps_id = latex_escape(form.peoplesoft_id)
    submitted_date = form.submitted_at.strftime('%m/%d/%Y') if form.submitted_at else ""
    iai_explanation = safe_value(form.iai_explanation)
    icl_class1 = safe_value(form.icl_class1)
    icl_prof1 = safe_value(form.icl_prof1)
    icl_sign1 = safe_value(form.icl_sign1)
    icl_date1 = safe_value(form.icl_date1)
    icl_class2 = safe_value(form.icl_class2)
    icl_prof2 = safe_value(form.icl_prof2)
    icl_sign2 = safe_value(form.icl_sign2)
    icl_date2 = safe_value(form.icl_date2)
    final_hours = safe_value(form.final_hours)
    uh_hours = safe_value(form.uh_hours)
    other_hours = safe_value(form.other_hours)
    other_school = safe_value(form.other_school)
    rcl_year_fall = safe_value(form.rcl_term_year_fall)
    rcl_year_spring = safe_value(form.rcl_term_year_spring)
    drop_class_1 = safe_value(form.drop_class_1)
    drop_class_2 = safe_value(form.drop_class_2)
    drop_class_3 = safe_value(form.drop_class_3)
    hours_after_drop = safe_value(form.hours_after_drop)
    hours_year_fall = safe_value(form.hours_year_fall)
    hours_year_spring = safe_value(form.hours_year_spring)

    return rf"""\documentclass[8pt]{{article}}
\usepackage[top=0.25in, bottom=0.75in, left=0.5in, right=0.5in]{{geometry}}
\usepackage{{amsmath,amssymb,graphicx,enumitem,array,booktabs,multirow,tikz,hyperref,ulem}}
\usepackage{{setspace}}
\setstretch{{0.1}}
\setlength\parindent{{0pt}}
\pagestyle{{empty}}

\newcommand{{\checkbox}}[1]{{\tikz[scale=0.5] \draw[thick] (0,0) rectangle (0.3,0.3) node[pos=.5] {{#1}};}}
\newcommand{{\customline}}{{\rule{{6cm}}{{0.4pt}}}}

\begin{{document}}
\begin{{center}}
    \includegraphics[width=5.5cm]{{RCL_Form_logo.png}}
\end{{center}}
\small
{{\footnotesize\textbf{{
Student Center North, N203, Houston, TX 77204-3024 \quad Phone:(713)743-5065 \quad Email:isssohlp@central.uh.edu \quad \underline{{\href{{http://uh.edu/oiss}}{{http://uh.edu/oisss}}}}
}}}}

\begin{{center}}
    \LARGE \textbf{{Reduced Course Load (RCL) Form for Undergraduates}}
\end{{center}}

F-1 students are required to maintain full-time enrollment while studying in the U.S. Undergraduate and post-baccalaureate students are expected to complete a minimum of 12 hours of course work during the fall and spring semesters. Classes during the summer are optional unless it is the first semester at UH; then an F-1 student has to complete 6 hours. The following form must be completed before dropping below full-time hours after start of classes. \\
\textbf{{Note:}} Dropping below full course load may involve the loss of resident tuition based on a scholarship, grant, or on-campus employment. \\\\
\underline{{Please complete the form below by selecting one of the options:}} \\\\

\vspace{{0.5em}}
\textbf{{1. ACADEMIC DIFFICULTY \underline{{(FIRST SEMESTER ONLY)}}}} \\
RCL for valid academic difficulties is allowed \underline{{once}} and \underline{{only in the first semester}} when starting a new degree program. A minimum of 6hrs will still have to be completed. This option cannot be used prior to ORD. \\

\vspace{{0.5em}}
\textbf{{Initial Adjustment Issues (IAI)}} \\
\checkbox{{{academic_subreason_checkbox}}} I am having initial difficulties with English, reading, or unfamiliarity with American teaching methods. \\
Please explain: \underline{{{iai_explanation}}} \\

\vspace{{0.5em}}
\textbf{{Improper Course Level Placement (ICLP)}} \\
\checkbox{{{iclp_checkbox}}} I am having difficulty with my class(es) due to improper course level placement which may include not having the prerequisites or insufficient background to complete the course at this time. For example, an international student taking U.S. History for the first time (e.g. no previous exposure, insufficient background) or a philosophy course that is based on a worldview that clashes with the student's own culture. \\

\begin{{center}} \textbf{{ICLP CERTIFYING SIGNATURE BY PROFESSOR}} \end{{center}}
I \textit{{recommend that this student be allowed to drop the following course(s) due to improper course level placement as defined above.}} \\
\begin{{tabular}}{{@{{}}l p{{2.7cm}} l p{{2.7cm}} l p{{3cm}} l p{{3cm}}@{{}}}}
    Class& \underline{{{icl_class1}}} & Professor& \underline{{{icl_prof1}}} & Signature& \underline{{{icl_sign1}}} & Date& \underline{{{icl_date1}}} \\
    Class& \underline{{{icl_class2}}} & Professor& \underline{{{icl_prof2}}} & Signature& \underline{{{icl_sign2}}} & Date& \underline{{{icl_date2}}}
\end{{tabular}} 

\vspace{{0.5em}}
\textbf{{2. MEDICAL REASON}} \\
\vspace{{0.5em}}
\checkbox{{{medical_checkbox}}} Valid medical reason must be proven with a supporting letter from a licensed medical doctor, clinical psychologist, or doctor of osteopathy. \underline{{The letter has to contain the following information:}} written in English on a letterhead, signed in ink, the recommended credit hours of enrollment, when the below hours should begin and end (if known), details of when student first saw the doctor, and when they advised the student withdraw from course(s). Medical excuses must be renewed each semester. You are only allowed to accumulate 12 months of reduced course load for medical reasons during any given degree level. \textbf{{Zero hours are allowed under this provision of the law only if it is clearly recommended by the licensed medical professional.}} \\

\vspace{{0.5em}}
\textbf{{3. FINAL SEMESTER}} \\
\vspace{{0.5em}}
\checkbox{{{final_checkbox}}} This is my final semester and I only need \underline{{{final_hours}}} hours of course work to complete my degree. I understand that if I am granted a reduced course load and fail to complete my degree as planned, I may be in violation of my legal status and will need to apply for reinstatement. (If you need only one course to finish your program of study, it cannot be taken through onlin/distance education). \\

\vspace{{0.5em}}
\textbf{{4. CONCURRENTLY ENROLLED}} \\
\vspace{{0.5em}}
\checkbox{{{concurrent_checkbox}}} I am taking courses at another college/University and want to drop a course at UH. I will still have 12 hours of enrollment between both schools. After the drop, I will have \underline{{{uh_hours}}} hours at UH and \underline{{{other_hours}}} at \underline{{{other_school}}} (school name). Attach proof of concurrent enrollment. Academic advisor signature is not required for this option, only ISSSO counselor. \\

\vspace{{0.5em}}
\sloppy
\noindent\fbox{{%
  \parbox{{0.97\textwidth}}{{%
    \hspace*{{0.5em}}%
    I am applying for a reduced course load for the \checkbox{{{rcl_fall_checkbox}}} Fall 20\underline{{{rcl_year_fall}}} \quad \checkbox{{{rcl_spring_checkbox}}} Spring 20\underline{{{rcl_year_spring}}}

    I want to drop the following class(es): \underline{{{drop_class_1}}}; \underline{{{drop_class_2}}}; \underline{{{drop_class_3}}} (course number). After the drop, I will have a total of \underline{{{hours_after_drop}}} (at UH) for the: \checkbox{{{fall_hours_check}}} Fall 20\underline{{{hours_year_fall}}} \quad \checkbox{{{spring_hours_check}}} Spring 20\underline{{{hours_year_spring}}}

    \small
    {{\footnotesize{{
    You must submit a copy of this form to Office of the University Registrar (located in the Welcome Center) if you are requesting the drop after the 1st day of the semester. The approval signature from your Academic Advisor and ISSSO are required to drop a course. You may still be responsible for the tuition and fee charges to the dropped course(s) after passing the deadline.
    }}}} \\[1ex]
    \textbf{{Student Name:}} \underline{{{student_name}}} \quad
    \textbf{{PS ID:}} \underline{{{ps_id}}} \quad
    \textbf{{Date:}} \underline{{{submitted_date}}} \quad
    \textbf{{Signature:}} \IfFileExists{{{signature_path}}}{{\includegraphics[width=1.5in]{{{signature_path}}}}}{{(Not Available)}}
    \hspace*{{0.5em}}%
  }}
}}

\vspace{{0.5em}}

\begin{{center}}
    APPROVAL SIGNATURE FROM ACADEMIC ADVISOR
\end{{center}}

\begin{{tabular}}{{@{{}}l l l l l l@{{}}}}
Name: & \rule{{4cm}}{{0.4pt}} & 
Signature: & \rule{{4cm}}{{0.4pt}} &
Date: & \rule{{4cm}}{{0.4pt}} \\
\end{{tabular}}

\vspace{{0.5em}}

\begin{{tabular}}{{@{{}}l l l l l l@{{}}}}
Name: & \rule{{4cm}}{{0.4pt}} & 
Signature: & \rule{{4cm}}{{0.4pt}} &
Date: & \rule{{4cm}}{{0.4pt}} \\
\end{{tabular}}
\end{{document}}
"""

@app.route('/submit_release_form', methods=['POST'])
def submit_release_form():
    try:
        data = request.form
        is_final_submission = data.get("final_submission") == "true"
        form_id = data.get("form_id")  # Get form ID (if editing a draft)

        student_name = (data.get('first_name') or "").strip() + " " + (data.get('middle_name') or "").strip() + " " + (data.get('last_name') or "").strip()
        peoplesoft_id = (data.get('peoplesoftID') or "").strip()
        password = (data.get('password') or "").strip()
        campus = (data.get('campus') or "").strip()
        categories = [c.strip() for c in request.form.getlist('categories') if c]
        specific_info = [s.strip() for s in request.form.getlist('info') if s]
        purpose = [p.strip() for p in request.form.getlist('purpose') if p]

        # Handle "Other" fields
        other_category_text = request.form.get("hiddenOtherCategoryText", "").strip()
        other_info_text = request.form.get("hiddenOtherInfoText", "").strip()
        other_purpose_text = request.form.get("hiddenOtherPurposeText", "").strip()

        # Replace "Other" selection with user input
        categories = [c if c != "Other" else f"Other: {other_category_text}" for c in categories]
        specific_info = [s if s != "Other" else f"Other: {other_info_text}" for s in specific_info]
        purpose = [p if p != "Other" else f"Other: {other_purpose_text}" for p in purpose]

        # Convert lists to comma-separated strings
        categories = ", ".join(categories)
        specific_info = ", ".join(specific_info)
        purpose = ", ".join(purpose)

        release_to = (data.get('releaseTo') or "").strip()
        signature_url = data.get('signature_url', None)

        approval_status = "pending" if is_final_submission else "draft"
        form_name = "Release Records"

        form_instance = None

        # Check if form_id exists (Updating a draft)
        if form_id:
            existing_request = ReleaseFormRequest.query.get(form_id)

            if existing_request:
                existing_request.student_name = student_name
                existing_request.password = password
                existing_request.campus = campus
                existing_request.categories = categories
                existing_request.specific_info = specific_info
                existing_request.purpose = purpose
                existing_request.release_to = release_to
                existing_request.signature_url = signature_url
                existing_request.approval_status = approval_status
                existing_request.submitted_at = datetime.utcnow() if is_final_submission else None
                existing_request.other_category_text = other_category_text
                existing_request.other_info_text = other_info_text
                existing_request.other_purpose_text = other_purpose_text
                existing_request.form_name = form_name
                db.session.commit()
                form_instance = existing_request
            else:
                return jsonify({"error": "Draft not found."}), 404
        else:
            # Creating a new form if no form_id is provided
            new_request = ReleaseFormRequest(
                student_name=student_name,
                peoplesoft_id=peoplesoft_id,
                password=password,
                campus=campus,
                categories=categories,
                specific_info=specific_info,
                release_to=release_to,
                purpose=purpose,
                signature_url=signature_url,
                submitted_at=datetime.utcnow() if is_final_submission else None,
                approval_status=approval_status,
                other_category_text=other_category_text,
                other_info_text=other_info_text,
                other_purpose_text=other_purpose_text,
                form_name=form_name
            )
            db.session.add(new_request)
            db.session.commit()
            form_instance = new_request

        if not form_instance:
            return jsonify({"error": "Failed to process form."}), 500

        # Fetch user object before PDF generation
        user = User.query.filter_by(email=session["user"]["email"]).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Generate PDF
        pdf_dir = "/mnt/data"
        os.makedirs(pdf_dir, exist_ok=True)

        tex_file_path = os.path.join(pdf_dir, f"form_{form_instance.id}.tex")
        pdf_file_path = os.path.join(pdf_dir, f"form_{form_instance.id}.pdf")

        with open(tex_file_path, "w") as tex_file:
            tex_file.write(generate_latex_content(form_instance, user))

        try:
            pdflatex_path = "pdflatex"
            os.environ["PATH"] += os.pathsep + os.path.dirname(pdflatex_path)

            if not os.path.exists(tex_file_path):
                return jsonify({"error": "LaTeX file was not created."}), 500

            subprocess.run([pdflatex_path, "-output-directory", pdf_dir, tex_file_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except subprocess.CalledProcessError as e:
            return jsonify({"error": f"PDF generation failed: {e.stderr.decode()}"}), 500
        except FileNotFoundError:
            return jsonify({"error": "pdflatex not found"}), 500

        # Upload PDF to Azure Blob Storage
        blob_name = f"release_forms/form_{form_instance.id}.pdf"
        blob_client = pdf_container_client.get_blob_client(blob_name)

        with open(pdf_file_path, "rb") as data:
            if not os.path.exists(pdf_file_path):
                return jsonify({"error": "PDF file was not created successfully."}), 500
            blob_client.upload_blob(data, overwrite=True)

        # Store PDF URL in the database
        pdf_url = f"https://{pdf_blob_service.account_name}.blob.core.windows.net/{PDF_CONTAINER_NAME}/{blob_name}"
        form_instance.pdf_url = pdf_url
        db.session.commit()

        return jsonify({"message": "Form saved successfully", "pdf_url": pdf_url}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Route to edit a form that was saved for later
@app.route('/edit_draft/<int:form_id>', methods=['GET'])
def edit_draft_form(form_id):
    try:
        print(f"Attempting to load draft with ID: {form_id}")  # Debugging

        form = ReleaseFormRequest.query.get(form_id)

        if not form:
            print(f"Error: No form found with ID {form_id}")  # Log missing form error
            flash("Error: Draft not found.", "error")
            return redirect(url_for('basic_user_form_status'))

        user = User.query.filter_by(email=session["user"]["email"]).first()
        if form.approval_status != "draft":
            print(f"Error: Form {form_id} is not a draft, current status: {form.approval_status}")  # Log status issue
            flash("Error: This form is no longer a draft.", "error")
            return redirect(url_for('basic_user_form_status'))

        signature_url = user.signature_url if user else None

        # Check if the form is for SSN or Name Change
        # Check if the form is for SSN or Name Change
        to_change_lower = form.toChange.lower() if form.toChange else ""
        if "ssn" in to_change_lower or "name" in to_change_lower:
            template = "basic_user_ssn.html"  # Load the SSN/Name Change Form

        campus = form.campus.lower() if form.campus else ""
        if "clear lake" in campus or "downtown" in campus or "main" in campus or "victoria" in campus:
            template = "basic_user_release.html" # Load the Release Form

        rcl_reason = form.rcl_reason.lower() if form.rcl_reason else ""
        if "academic_difficulty" in rcl_reason or "medical_reason" in rcl_reason or "final_semester" in rcl_reason or "concurrent_enrollment" in rcl_reason:
            template = "basic_user_course_load.html" # Load reduce course load form

        print(f"Draft {form_id} loaded successfully, rendering {template}")  # Confirm successful retrieval
        return render_template(template, form=form, user=user)

    except Exception as e:
        print(f"Unexpected error while loading draft {form_id}: {str(e)}")  # Log full error message
        flash("An unexpected error occurred while loading the draft.", "error")
        return redirect(url_for('basic_user_form_status'))

# Route to handle form submission
@app.route('/submit_ssn_form', methods=['POST'])
def submit_ssn_form():
    try:
        data = request.form
        is_final_submission = data.get("final_submission") == "true"
        form_id = data.get("form_id")
        form_name = "Name/SSN Change"

        # Extract and format names
        student_name = f"{data.get('first_name', '').strip()} {data.get('middle_name', '').strip()} {data.get('last_name', '').strip()}"
        uhid = data.get("peoplesoft_id", "").strip()
        user_email = data.get("user_email", "").strip()
        user = User.query.filter_by(email=user_email).first()
        if not user:
            return jsonify({"error": "User not found"}), 404
        user_id = user.id  # Assign correct user ID

        # Process checkboxes for changes
        to_update = ",".join([u.strip() for u in data.getlist("toChange") if u])
        name_change_reason = data.get("name_change_reason", "").strip()
        ssn_change_reason = data.get("ssn_change_reason", "").strip()

        # Process name change fields
        old_first_name = data.get("old_first_name", "").strip()
        old_middle_name = data.get("old_middle_name", "").strip()
        old_last_name = data.get("old_last_name", "").strip()
        old_suffix = data.get("old_suffix", "").strip()
        new_first_name = data.get("new_first_name", "").strip()
        new_middle_name = data.get("new_middle_name", "").strip()
        new_last_name = data.get("new_last_name", "").strip()
        new_suffix = data.get("new_suffix", "").strip()

        # Process SSN change fields
        old_ssn = "-".join([
            data.get("old_ssn_1", "").strip(),
            data.get("old_ssn_2", "").strip(),
            data.get("old_ssn_3", "").strip()
        ])
        new_ssn = "-".join([
            data.get("new_ssn_1", "").strip(),
            data.get("new_ssn_2", "").strip(),
            data.get("new_ssn_3", "").strip()
        ])

        # Process signature
        signature_url = data.get("signature_url", None)

        approval_status = "pending" if is_final_submission else "draft"

        form_instance = None

        # Check if form_id exists (Updating a draft)
        if form_id:
            existing_request = ReleaseFormRequest.query.get(form_id)

            if existing_request:
                existing_request.student_name = student_name
                existing_request.peoplesoft_id = uhid
                existing_request.user_email = user_email
                existing_request.user_id = user_id
                existing_request.toChange = to_update
                existing_request.name_change_reason = name_change_reason
                existing_request.ssn_change_reason = ssn_change_reason
                existing_request.old_first_name = old_first_name
                existing_request.old_middle_name = old_middle_name
                existing_request.old_last_name = old_last_name
                existing_request.old_suffix = old_suffix
                existing_request.new_first_name = new_first_name
                existing_request.new_middle_name = new_middle_name
                existing_request.new_last_name = new_last_name
                existing_request.new_suffix = new_suffix
                existing_request.old_ssn = old_ssn
                existing_request.new_ssn = new_ssn
                existing_request.signature_url = signature_url
                existing_request.approval_status = "draft" if not is_final_submission else "pending"
                existing_request.form_name = form_name
                db.session.commit()
                form_instance = existing_request
            else:
                return jsonify({"error": "Draft not found."}), 404
                
            if not is_final_submission:
                return jsonify({"message": "Draft saved successfully."}), 200

        else:
            # Store form request in database
            new_request = ReleaseFormRequest(
                student_name=student_name,
                peoplesoft_id=uhid,
                user_email=user_email,
                user_id=user_id,
                toChange=to_update,
                name_change_reason=name_change_reason,
                ssn_change_reason=ssn_change_reason,
                old_first_name=old_first_name,
                old_middle_name=old_middle_name,
                old_last_name=old_last_name,
                old_suffix=old_suffix,
                new_first_name=new_first_name,
                new_middle_name=new_middle_name,
                new_last_name=new_last_name,
                new_suffix=new_suffix,
                old_ssn=old_ssn,
                new_ssn=new_ssn,
                signature_url=signature_url,
                form_name=form_name,
                approval_status="draft" if not is_final_submission else "pending",
                submitted_at=datetime.utcnow() if is_final_submission else None
            )
            db.session.add(new_request)
            db.session.commit()
            form_instance = new_request
            if not is_final_submission:
                return jsonify({"message": "Draft saved successfully."}), 200

        if not form_instance:
            return jsonify({"error": "Failed to process form."}), 500

        # Fetch user object before PDF generation
        user = User.query.filter_by(email=session["user"]["email"]).first()
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Generate PDF
        pdf_dir = "/mnt/data"
        os.makedirs(pdf_dir, exist_ok=True)

        tex_file_path = os.path.join(pdf_dir, f"form_{form_instance.id}.tex")
        pdf_file_path = os.path.join(pdf_dir, f"form_{form_instance.id}.pdf")

        with open(tex_file_path, "w") as tex_file:
            tex_file.write(generate_ssn_form(form_instance, user))

        try:
            pdflatex_path = "pdflatex"
            os.environ["PATH"] += os.pathsep + os.path.dirname(pdflatex_path)

            if not os.path.exists(tex_file_path):
                return jsonify({"error": "LaTeX file was not created."}), 500

            subprocess.run([pdflatex_path, "-output-directory", pdf_dir, tex_file_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        except subprocess.CalledProcessError as e:
            return jsonify({"error": f"PDF generation failed: {e.stderr.decode()}"}), 500
        except FileNotFoundError:
            return jsonify({"error": "pdflatex not found"}), 500

        # Upload PDF to Azure Blob Storage
        blob_name = f"release_forms/form_{form_instance.id}.pdf"
        blob_client = pdf_container_client.get_blob_client(blob_name)

        with open(pdf_file_path, "rb") as data:
            if not os.path.exists(pdf_file_path):
                return jsonify({"error": "PDF file was not created successfully."}), 500
            blob_client.upload_blob(data, overwrite=True)

        # Store PDF URL in the database
        pdf_url = f"https://{pdf_blob_service.account_name}.blob.core.windows.net/{PDF_CONTAINER_NAME}/{blob_name}"
        form_instance.pdf_url = pdf_url
        db.session.commit()

        return jsonify({"message": "Form saved successfully", "pdf_url": pdf_url}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Azure AD Configuration
CLIENT_ID = "7fbeba40-e221-4797-8f8a-dc364de519c7"
CLIENT_SECRET = "x2T8Q~yVzAOoC~r6FYtzK6sqCJQR_~RCVH5-dcw8"
TENANT_ID = "170bbabd-a2f0-4c90-ad4b-0e8f0f0c4259"
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
#REDIRECT_URI = "https://swan-river-group-project.azurewebsites.net/auth/callback"
REDIRECT_URI = "http://localhost:8000/auth/callback"
SCOPE = ['User.Read']

# Authentication Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/azure_login')
def azure_login():
    session['state'] = 'random_state'
    auth_url = _build_auth_url(scopes=SCOPE, state=session['state'])
    return redirect(auth_url)

@app.route('/auth/callback')
def authorized():
    try:
        code = request.args.get('code')
        if not code:
            return redirect(url_for('index'))
        
        token = _get_token_from_code(code)
        user_info = _get_user_info(token)
        email = user_info.get('mail') or user_info.get('userPrincipalName')

        logger.info(f"User attempting login: {email}")

        # Fetch user from database
        user = User.query.filter_by(email=email).first()

        if not user:
            logger.info(f"User {email} not found. Creating new basic user.")
            user = User(
                first_name=user_info.get('givenName', 'Unknown'),
                middle_name=None,
                last_name=user_info.get('surname', 'Unknown'),
                email=email,
                role='basicuser',
                status='active'
            )
            db.session.add(user)
            db.session.commit()
            db.session.refresh(user)  # Ensure role and status are fresh

        else:
            logger.info(f"User {email} found in database with role: {user.role} and status: {user.status}")

        db.session.refresh(user)  # Refresh to get the latest role and status

        # Check if the user is suspended
        if user.status.lower() != "active":
            logger.warning(f"User {email} is suspended. Redirecting to login.")
            flash("Account suspended. Please contact support.", "error")
            return redirect(url_for('login'))

        # Store user details properly in session
        session['user'] = {
            'first_name': user.first_name,
            'middle_name': user.middle_name if user.middle_name else '',
            'last_name': user.last_name,
            'email': user.email,
            'role': user.role.strip().lower(),
            'status': user.status
        }

        logger.info(f"User {user.email} logged in with role: {session['user']['role']} and status: {session['user']['status']}")

         # Debug before role check
        logger.info(f"Checking role for {user.email}: session['user']['role'] = {session['user']['role']}")

        # Redirect based on role
        if session.get('user', {}).get('role', '').strip().lower() == "admin":
            logger.info(f"Admin {user.email} is being redirected to admin_home")
            return redirect(url_for('admin_home'))
        else:
            return redirect(url_for('basic_user_home'))

    except Exception as e:
        logger.error(f"Internal Server Error: {str(e)}", exc_info=True)
        flash("An error occurred while logging in. Please try again.", "error")
        return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# Basic User Routes
@app.route('/basic_user_home')
def basic_user_home():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template(
        'basic_user_home.html',
        user_name=f"{session['user']['first_name']} {session['user'].get('middle_name', '').strip()} {session['user']['last_name']}".strip()
    )

@app.route('/basic_user_view')
def basic_user_view():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template("basic_user_view.html", user=session['user'])

@app.route('/basic_user_edit')
def basic_user_edit():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template("basic_user_edit.html", user=session['user'])

@app.route('/basic_user_forms')
def basic_user_forms():
    if 'user' not in session:
        return redirect(url_for('index'))
    # Fetch user's signature from the database
    email = session['user']['email']
    user = User.query.filter_by(email=email).first()
    # Get the signature URL (if exists)
    signature_url = user.signature_url if user and user.signature_url else ""
    return render_template("basic_user_forms.html", user=session['user'])

@app.route('/basic_user_course_load')
def basic_user_course_load():
    if 'user' not in session:
        return redirect(url_for('index'))
    # Fetch user's signature from the database
    email = session['user']['email']
    user = User.query.filter_by(email=email).first()
    # Get the signature URL (if exists)
    signature_url = user.signature_url if user and user.signature_url else ""
    return render_template("basic_user_course_load.html", user=session['user'], signature_url=signature_url)

@app.route('/basic_user_release')
def basic_user_release():
    if 'user' not in session:
        return redirect(url_for('index'))
    # Fetch user's signature from the database
    email = session['user']['email']
    user = User.query.filter_by(email=email).first()
    # Get the signature URL (if exists)
    signature_url = user.signature_url if user and user.signature_url else ""
    return render_template("basic_user_release.html", user=session['user'], signature_url=signature_url)

@app.route('/basic_user_ssn')
def basic_user_ssn():
    if 'user' not in session:
        return redirect(url_for('index'))
    # Fetch user's signature from the database
    email = session['user']['email']
    user = User.query.filter_by(email=email).first()
    # Get the signature URL (if exists)
    signature_url = user.signature_url if user and user.signature_url else ""
    return render_template("basic_user_ssn.html", user=session['user'], signature_url=signature_url)

@app.route('/basic_user_form_status')
def basic_user_form_status():
    if 'user' not in session:
        return redirect(url_for('index'))
    
    # Fetch user's email from session
    email = session['user']['email']
    user = User.query.filter_by(email=email).first()

    # Fetch all forms (Drafts + Submitted Forms)
    user_full_name = f"{user.first_name} {user.middle_name or ''} {user.last_name}".strip()
    requests = ReleaseFormRequest.query.filter(
        ReleaseFormRequest.student_name.like(f"%{user_full_name}%")
    ).all()
    
    return render_template("basic_user_form_status.html", user=session['user'], requests=requests)

def download_signature(signature_url, user_id):
    """
    Downloads the user's signature from Azure Blob Storage and saves it locally.
    Returns the local file path to be used in LaTeX.
    """
    local_path = f"/mnt/data/signature_{user_id}.png"
    if signature_url and signature_url.startswith("http"):
        try:
            response = requests.get(signature_url, stream=True)
            if response.status_code == 200:
                with open(local_path, "wb") as file:
                    for chunk in response.iter_content(1024):
                        file.write(chunk)
                return local_path
        except Exception as e:
            print(f"Error downloading signature: {e}")
    return "/mnt/data/default-signature.png"  # Fallback if the download fails

def generate_ssn_form(form, user):
    """
    Generates a LaTeX document for the SSN Change Form.
    """
    import re

    # Escape LaTeX special characters in user inputs
    def latex_escape(text):
        return re.sub(r'([&_{}%$#])', r'\\\1', text) if text else ""

    # Download signature if available
    signature_path = download_signature(user.signature_url, user.id) if user.signature_url else "/mnt/data/default-signature.png"

    # Define checkbox formatting
    def latex_checkbox(condition):
        return r"$\boxtimes$" if condition else r"$\square$"

    # Process checkboxes for changes
    to_change = [t.strip() for t in form.toChange.split(",") if t] if form.toChange else []

    # Split SSN into sections safely
    old_ssn_parts = form.old_ssn.split("-") if form.old_ssn else ["", "", ""]
    new_ssn_parts = form.new_ssn.split("-") if form.new_ssn else ["", "", ""]

    # Escape input fields to prevent LaTeX errors
    user_first_name = latex_escape(user.first_name if user.first_name else "")
    user_middle_name = latex_escape(user.middle_name if user.middle_name else "")
    user_last_name = latex_escape(user.last_name if user.last_name else "")
    peoplesoft_id = latex_escape(form.peoplesoft_id)
    name_change_reason = latex_escape(form.name_change_reason)
    ssn_change_reason = latex_escape(form.ssn_change_reason)

    old_first_name = latex_escape(form.old_first_name)
    old_middle_name = latex_escape(form.old_middle_name)
    old_last_name = latex_escape(form.old_last_name)
    old_suffix = latex_escape(form.old_suffix)

    new_first_name = latex_escape(form.new_first_name)
    new_middle_name = latex_escape(form.new_middle_name)
    new_last_name = latex_escape(form.new_last_name)
    new_suffix = latex_escape(form.new_suffix)

    latex_content = f"""
    \\documentclass[10pt]{{article}}
    \\usepackage[a4paper, margin=0.75in]{{geometry}}
    \\usepackage{{graphicx}}
    \\usepackage{{array}}
    \\usepackage{{titlesec}}
    \\usepackage{{setspace}}
    \\usepackage{{lmodern}}
    \\usepackage{{amssymb}}
    \\usepackage{{multicol}}
    \\usepackage{{ragged2e}}
    \\usepackage{{xcolor}}

    % Define checkbox formatting
    \\newcommand{{\\checkbox}}[1]{{\\hspace{{1em}} #1}}

    % Define custom colors
    \\definecolor{{uhgray}}{{rgb}}{{0.3,0.3,0.3}} % Dark Gray
    \\definecolor{{uhred}}{{rgb}}{{0.8,0.0,0.0}}  % Red

    % Remove default footer and page number
    \\pagestyle{{empty}}

    \\begin{{document}}

    \\begin{{center}}
    {{\\huge \\textcolor{{uhgray}}{{\\textbf{{UNIVERSITY of }}}}\\textcolor{{uhred}}{{\\textbf{{HOUSTON}}}}}} \\\\
    {{\\Large \\textcolor{{uhgray}}{{OFFICE OF THE UNIVERSITY REGISTRAR}}}} \\\\
    \\vspace{{0.5em}}
    {{\\large Name and/or Social Security Number Change}} \\\\
    {{\\small University of Houston | Office of the University Registrar}} \\\\
    {{\\small Houston, Texas 77204-2027 | (713) 743-1010, option 7}} 
    \\end{{center}}

    \\hrulefill
    \\vspace{{0.5em}}

    \\textbf{{Student Name (as listed on university record)}}

    \\vspace{{0.5em}}

    \\begin{{tabular}}{{@{{}}p{{1.8in}} p{{1.8in}} p{{1.8in}}@{{}}}}
    First Name & Middle Name & Last Name \\\\
    \\textbf{{\\underline{{{user_first_name}}}}} & \\textbf{{\\underline{{{user_middle_name}}}}} & \\textbf{{\\underline{{{user_last_name}}}}} \\\\
    \\end{{tabular}}

    \\vspace{{1em}}

    \\begin{{tabular}}{{@{{}}p{{2.8in}} p{{3in}}@{{}}}}
    \\textbf{{myUH ID Number}} & \\textbf{{What are you requesting to add or update?}} \\\\
    \\textbf{{\\underline{{{peoplesoft_id}}}}} & 
    \\checkbox{{{latex_checkbox('name' in to_change)}}}~Update Name (Complete Section A) \\\\
    & \\checkbox{{{latex_checkbox('ssn' in to_change)}}}~Update/Add Social Security Number \\\\
    & \\hspace{{2em}} (Complete Section B) \\\\
    \\end{{tabular}}

    \\hrulefill
    \\vspace{{0.5em}}

    \\textbf{{\\fontsize{{13}}{{13}}\\selectfont \\underline{{Section A: Student Name Change}}}} \\\\
    \\\\
    \\indent The University of Houston record of your name was originally taken from your application for admission
    \\indent and may be changed if:

    \\begin{{enumerate}}
        \\item You have married, remarried, or divorced (a copy of marriage license or portion of divorce decree indicating new name must be provided).
        \\item You have changed your name by court order (a copy of the court order must be provided).
        \\item Your legal name is listed incorrectly and satisfactory evidence exists for its correction (driver license, state ID, birth certificate, valid passport, etc., must be provided).
    \\end{{enumerate}}

    \\textbf{{Check reason for name change request:}} \\\\
    \\checkbox{{{latex_checkbox(name_change_reason == 'Marriage/Divorce')}}}~Marriage/Divorce 
    \\checkbox{{{latex_checkbox(name_change_reason == 'Court Order')}}}~Court Order 
    \\checkbox{{{latex_checkbox(name_change_reason == 'Correction of Error')}}}~Correction of Error 

    \\hrulefill
    \\vspace{{0.5em}}

    \\textbf{{\\fontsize{{13}}{{13}}\\selectfont \\underline{{Section B: Student Social Security Number Change}}}} \\\\\\\\
    The University of Houston record of your Social Security Number was originally taken from your application for admission and may be changed only if the student has obtained a new social security number or an error was made. In either case, the student must provide a copy of the Social Security Card. The Social Security card must include the student's signature and must be submitted with a valid government-issued photo ID. \\\\

    \\textbf{{Check reason for Social Security Number change request:}} \\\\
    \\checkbox{{{latex_checkbox(ssn_change_reason == 'Correction of Error')}}}~Correction of Error
    \\checkbox{{{latex_checkbox(ssn_change_reason == 'Addition')}}}~Addition of SSN to university records 

    \\vspace{{1em}}

    \\begin{{tabular}}{{@{{}}p{{2.5in}} p{{2.5in}}@{{}}}}
    \\textbf{{FROM:}} {old_ssn_parts[0]}-{old_ssn_parts[1]}-{old_ssn_parts[2]} & \\textbf{{TO:}} {new_ssn_parts[0]}-{new_ssn_parts[1]}-{new_ssn_parts[2]} \\\\
    \\end{{tabular}}

    \\hrulefill
    \\vspace{{0.5em}}

    \\textbf{{SIGNATURE (REQUIRED):}} \\includegraphics[height=1cm]{{{signature_path}}} \\hspace{{4em}} \\textbf{{Date:}} \\underline{{\\today}}
    
    \\vfill
    \\noindent
    {{\\tiny
    State law requires that you be informed of the following: (1) with few exceptions, you are entitled on request to be informed about the information the
    University collects about you by use of this form; (2) you are entitled to receive and review the information; and (3) you are entitled to have the University correct incorrect information.
    }}
        
    \\end{{document}}
    """
    return latex_content
    
# Update generate_latex_content function
def generate_latex_content(form, user):
    """
    Generates a one-page LaTeX document for the authorization form.
    """
    # Download signature locally if it's a URL
    signature_path = download_signature(user.signature_url, user.id) if user.signature_url else "/mnt/data/default-signature.png"

    # Define LaTeX checkbox symbols
    def latex_checkbox(condition):
        return r"$\boxtimes$" if condition else r"$\square$"

    # Process selected checkboxes
    categories = [c.strip() for c in form.categories.split(",") if c] if form.categories else []
    specific_info = [s.strip() for s in form.specific_info.split(",") if s] if form.specific_info else []
    purpose = [p.strip() for p in form.purpose.split(",") if p] if form.purpose else []

    latex_content = f"""
    \\documentclass[10pt]{{article}}
    \\usepackage[a4paper, margin=0.75in]{{geometry}}
    \\usepackage{{graphicx}}
    \\usepackage{{array}}
    \\usepackage{{titlesec}}
    \\usepackage{{setspace}}
    \\usepackage{{lmodern}}
    \\usepackage{{amssymb}}
    \\usepackage{{multicol}}
    \\usepackage{{ragged2e}}

    % Define checkbox formatting
    \\newcommand{{\\checkbox}}[1]{{\\hspace{{2em}} #1}}

    % Remove default footer and page number
    \\pagestyle{{empty}}

    \\begin{{document}}

    % Form Number at the Top Left
    \\noindent
    {{\\small \\textbf{{Form No. OGC-SF-2006-02}}}}

    \\begin{{center}}
        {{\\textbf{{AUTHORIZATION TO RELEASE EDUCATIONAL RECORDS}}}} \\\\
        {{\\textbf{{Family Educational Rights and Privacy Act of 1974 as Amended (FERPA)}}}}
    \\end{{center}}

    \\vspace{{0.2em}}

    \\noindent
    I \\textbf{{({form.student_name})}} hereby voluntarily authorize officials in the University of Houston - \\textbf{{({form.campus})}} identified below to disclose personally identifiable information from my educational records. (Please check the box or boxes that apply):

    \\begin{{flushleft}}
        \\checkbox{{{latex_checkbox('Registrar' in categories)}}} Office of the University Registrar \\\\
        \\checkbox{{{latex_checkbox('Financial Aid' in categories)}}} Scholarships and Financial Aid \\\\
        \\checkbox{{{latex_checkbox('Student Financial Services' in categories)}}} Student Financial Services \\\\
        \\checkbox{{{latex_checkbox('Undergraduate Scholars' in categories)}}} Undergraduate Scholars @ UH \\\\
        \\checkbox{{{latex_checkbox('Advancement' in categories)}}} University Advancement \\\\
        \\checkbox{{{latex_checkbox('Dean of Students' in categories)}}} Dean of Students Office \\\\
        \\checkbox{{{latex_checkbox(any('Other:' in c for c in categories))}}} Other (Please Specify): \\textbf{{\\underline{{{form.other_category_text}}}}}
    \\end{{flushleft}}

    \\noindent
    Specifically, I authorize disclosure of the following information or category of information. (Please check the box or boxes that apply):
    \\begin{{flushleft}}
        \\checkbox{{{latex_checkbox('Advising' in specific_info)}}} Academic Advising Profile/Information \\\\
        \\checkbox{{{latex_checkbox('Academic Records' in specific_info)}}} Academic Records \\\\
        \\checkbox{{{latex_checkbox('All Records' in specific_info)}}} All University Records \\\\
        \\checkbox{{{latex_checkbox('Billing' in specific_info)}}} Billing/Financial Aid \\\\
        \\checkbox{{{latex_checkbox('Disciplinary' in specific_info)}}} Disciplinary \\\\
        \\checkbox{{{latex_checkbox('Grades' in specific_info)}}} Grades/Transcripts \\\\
        \\checkbox{{{latex_checkbox('Housing' in specific_info)}}} Housing \\\\
        \\checkbox{{{latex_checkbox('Photos' in specific_info)}}} Photos \\\\
        \\checkbox{{{latex_checkbox('Scholarships' in specific_info)}}} Scholarship and/or Honors \\\\
        \\checkbox{{{latex_checkbox(any('Other:' in s for s in specific_info))}}} Other (Please Specify): \\textbf{{\\underline{{{form.other_info_text}}}}}
    \\end{{flushleft}}

    \\noindent
    This information may be released to: \\textbf{{({form.release_to})}} for the purpose of informing:

    \\begin{{flushleft}}
        \\checkbox{{{latex_checkbox('Family' in purpose)}}} Family \\\\
        \\checkbox{{{latex_checkbox('Educational Institution' in purpose)}}} Educational Institution \\\\
        \\checkbox{{{latex_checkbox('Honor or Award' in purpose)}}} Honor or Award \\\\
        \\checkbox{{{latex_checkbox('Employer' in purpose)}}} Employer/Prospective Employer \\\\
        \\checkbox{{{latex_checkbox('Public/Media' in purpose)}}} Public or Media of Scholarship \\\\
        \\checkbox{{{latex_checkbox(any('Other:' in p for p in purpose))}}} Other (Please Specify): \\textbf{{\\underline{{{form.other_purpose_text}}}}}
    \\end{{flushleft}}

    \\noindent
    Please provide a password to obtain information via the phone: \\textbf{{({form.password})}}. The password should not contain more than ten (10) letters. You must provide the password to the individuals or agencies listed above. The University will not release information to the caller if the caller does not have the password. A new form must be completed to change your password. \\\\
    
    \\noindent
    \\textbf{{This is to attest that I am the student signing this form. I understand the information may be released orally or in the form of copies of written records, as preferred by the requester. This authorization will remain in effect from the date it is executed until revoked by me, in writing, and delivered to Department(s) identified above.}} \\\\

    \\vfill

    % Student Information Section
    \\noindent
    \\noindent
    \\begin{{tabular}}{{ p{{3in}} p{{3in}} }}
        \\textbf{{\\underline{{{form.student_name}}}}} & \\textbf{{\\underline{{{form.peoplesoft_id}}}}} \\\\
        \\textbf{{Student Name [Please Print]}} & \\textbf{{PeopleSoft I.D. Number}} \\\\[1.5em]

        % Signature and Date row
        \\begin{{minipage}}{{3in}}
            
            \\IfFileExists{{{signature_path}}}
                {{\\includegraphics[width=2in]{{{signature_path}}}}}
                {{\\textbf{{No signature on file.}}}}
        \\end{{minipage}} 
        & 
        \\begin{{minipage}}{{3in}}
            
            \\textbf{{\\underline{{\\today}}}}
        \\end{{minipage}} \\\\
        
        \\textbf{{Student Signature}} & \\textbf{{Date:}} \\\\
    \\end{{tabular}} \\\\

    \\vfill

    % Bottom Section
    \\noindent
    \\begin{{tabular}}{{ p{{3in}} p{{3in}} }}
        \\textbf{{Please Retain a Copy for your Records}} & \\\\
        \\textbf{{Document may be Submitted to Registrar's Office}} & \\\\
        FERPA Authorization Form & \\\\
        OGC-SF-2006-02 Revised 11.10.2022 & \\textbf{{Note: Modification of this Form requires approval of OGC}} \\\\
        Page 1 of 1 & \\\\
    \\end{{tabular}}

    \\end{{document}}
    """
    return latex_content

#--------------------------------------------------------------------------------------------------------------------------------------
#sign in
@app.route('/sign_in', methods=['POST'])
def sign_in():
    email = request.form['email']
    password = request.form['password']

    # Query the database for the user
    user = User.query.filter_by(email=email).first()

    if user:
        logger.info(f"User {user.email} found in database.")

        # If the password is None (e.g., OAuth users), allow login
        if not user.password or check_password_hash(user.password, password):
             # Split the full name into first, middle, and last names
            name_parts = user.name.split()
            first_name = name_parts[0]  # First name is the first part
            middle_name = " ".join(name_parts[1:-1]) if len(name_parts) > 2 else ""  # Middle name, if present
            last_name = name_parts[-1] if len(name_parts) > 1 else ""  # Last name

            session['user'] = {
                'first_name': first_name,
                'middle_name': middle_name,
                'last_name': last_name,
                'email': user.email,
                'role': user.role.strip().lower(),
                'status': user.status.strip().lower()
            }

            logger.info(f"User {user.email} logged in with role: {session['user']['role']} and status: {session['user']['status']}")

            # Redirect based on role
            logger.info(f"Checking role for {user.email}: session['user']['role'] = {session['user']['role']}")
            if session['user']['role'] == "admin":
                logger.info(f"Admin {user.email} is being redirected to admin_home.")
                return redirect(url_for('admin_home'))
            else:
                logger.info(f"Basic user {user.email} is being redirected to basic_user_home.")
                return redirect(url_for('basic_user_home'))
        else:
            # Invalid password
            logger.warning(f"Password mismatch for {user.email}.")
            return render_template('login.html', error="Invalid password. Please try again.")
    else:
        # User not found
        logger.warning(f"No account found for email: {email}.")
        return render_template('login.html', error="No account found with this email.")

#create account
@app.route('/create_account', methods=['GET', 'POST'])
def create_account():
    if request.method == 'POST':
        # Collect form data
        first_name = request.form['first_name']
        middle_name = request.form.get('middle_name', '').strip()  # Optional, defaults to empty
        last_name = request.form['last_name']
        email = request.form['email'].lower()  # Normalize email
        password = request.form['password']

        # Concatenate name (first + middle + last)
        name = f"{first_name} {middle_name} {last_name}".strip()  # Remove extra spaces if middle_name is empty

        # Hash the password securely
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        # Check if the email is already in use
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            return "Error: Email already in use. Please try another email."

        # Create a new User instance
        new_user = User(
            first_name=first_name,
            middle_name=middle_name if middle_name else None,  # Handle optional middle name
            last_name=last_name,
            name=name,
            email=email,
            password=hashed_password,  # Store the hashed password
            role="basicuser",  # Default role for manual accounts
            status="active",   # Default status for new users
            signature_url=None,  # Optional fields
            pdf_url=None,        # Optional fields
        )
        try:
            # Insert concatenated name into the database directly using raw SQL or ORM logic
            db.session.add(new_user)
            db.session.commit()

            # Update the name field manually if needed
            new_user.name = name
            db.session.commit()

            # Redirect to basic user home after account creation
            return redirect(url_for('basic_user_home'))

        except Exception as e:
            # Log the error for debugging purposes
            logger.error(f"Database Error: {str(e)}", exc_info=True)
            return f"Error: An issue occurred while creating the account. {str(e)}"

    # Render the form
    return render_template('login.html')

#---------------------------------------------------------------------------------------------------------------------------

# Admin Routes
@app.route('/admin_home')
def admin_home():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template(
        'admin.html',
        user_name=f"{session['user']['first_name']} {session['user'].get('middle_name', '').strip()} {session['user']['last_name']}".strip()
    )

@app.route('/admin_create_user')
def admin_create_user():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('admin-create-user.html')

@app.route('/admin_delete_user')
def admin_delete_user():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('admin-delete-user.html')

@app.route('/admin_edit_profile')
def admin_edit_profile():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('admin-edit-profile.html', user=session['user'])

@app.route('/admin_update_user')
def admin_update_user():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('admin-update-user.html')

@app.route('/admin_view_profile')
def admin_view_profile():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('admin-view-profile.html', user=session['user'])

@app.route('/admin_view_users')
def admin_view_users():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('admin-view-user.html')

@app.route('/admin_user_forms')
def admin_user_forms():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('admin-user-forms.html')

@app.route('/admin_request_forms')
def admin_request_forms():
    if 'user' not in session:
        return redirect(url_for('index'))

    # Fetch all submitted forms
    requests = ReleaseFormRequest.query.all()
    return render_template('admin-request-forms.html', requests=requests)

@app.route('/admin_previous_forms')
def admin_previous_forms():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('admin-previous-forms.html')

# Update user profile
@app.route('/user/profile/update', methods=['PUT'])
def update_user_profile():
    if "user" not in session:
        return jsonify({"error": "User not logged in"}), 401

    user = User.query.filter_by(email=session['user']['email']).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    user.first_name = data.get("first_name", user.first_name).strip()
    user.middle_name = data.get("middle_name", user.middle_name).strip() if "middle_name" in data else user.middle_name
    user.last_name = data.get("last_name", user.last_name).strip()
    
    db.session.commit()
    
    session['user'] = {
        'first_name': user.first_name,
        'middle_name': user.middle_name if user.middle_name else '',
        'last_name': user.last_name,
        'email': user.email,
        'role': user.role,
        'status': user.status
    }
    
    return jsonify({"message": "Profile updated successfully!"})

@app.route('/admin/create_user', methods=['POST'])
def create_user():
    if "user" not in session or session["user"]["role"] != "admin":
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    role = data.get("role", "basicuser").strip().lower()
    status = data.get("status", "active").strip().lower()

    if not name or not email:
        return jsonify({"error": "Name and email are required"}), 400

    # Check if the email already exists
    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        return jsonify({"error": "User with this email already exists"}), 400

    # Create new user
    new_user = User(name=name, email=email, role=role, status=status)
    db.session.add(new_user)
    db.session.commit()

    logger.info(f"Admin {session['user']['email']} created new user {email} with role {role}")

    return jsonify({"message": "User created successfully!"}), 201

# Update user information in database
@app.route('/admin/update_user/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    if "user" not in session or session["user"]["role"] != "admin":
        return jsonify({"error": "Unauthorized"}), 403

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Invalid JSON received"}), 400  # New check to prevent JSON errors

        # Validate required fields
        required_fields = ["first_name", "last_name", "role", "status"]
        for field in required_fields:
            if field not in data or not isinstance(data[field], str) or not data[field].strip():
                return jsonify({"error": f"Missing or invalid field: {field}"}), 400

        user.first_name = data["first_name"].strip()
        user.middle_name = data.get("middle_name", "").strip()  # Handle optional middle name
        user.last_name = data["last_name"].strip()
        user.role = data["role"].strip().lower()
        user.status = data["status"].strip().lower()

        db.session.commit()

        logger.info(f"Admin {session['user']['email']} updated user {user.email}")

        return jsonify({"message": "User updated successfully!"}), 200

    except Exception as e:
        db.session.rollback()
        logger.error(f"Database error: {str(e)}")
        return jsonify({"error": "Database error, could not update user"}), 500


# Suspend user's account
@app.route('/admin/deactivate_user/<int:user_id>', methods=['PUT'])
def deactivate_user(user_id):
    if "user" not in session or session["user"]["role"] != "admin":
        return jsonify({"error": "Unauthorized"}), 403

    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json()
    new_status = data.get("status", "deactivated").strip().lower()

    # Ensure the status is valid
    if new_status not in ["active", "deactivated"]:
        return jsonify({"error": "Invalid status value"}), 400

    user.status = new_status
    db.session.commit()

    logger.info(f"Admin {session['user']['email']} suspended user {user.email}")

    return jsonify({"message": "User suspended successfully!"}), 200

# Fetch all users in database
@app.route('/admin/all_users')
def all_users():
    users = User.query.all()
    return jsonify([
        {
            "id": user.id,
            "first_name": user.first_name if user.first_name else "",
            "middle_name": user.middle_name if user.middle_name else "",
            "last_name": user.last_name if user.last_name else "",
            "email": user.email,
            "role": user.role,
            "status": user.status
        }
        for user in users
    ])

# Admin retrieve submitted PDF's
@app.route('/admin_get_pdf/<int:form_id>', methods=['GET'])
def admin_get_pdf(form_id):
    form = ReleaseFormRequest.query.get(form_id)
    if not form or not form.pdf_url:
        return jsonify({"error": "PDF not found"}), 404
    return redirect(form.pdf_url)

# Upload user signature to Azure Blob Storage
@app.route('/upload_signature', methods=['POST'])
def upload_user_signature():
    if "user" not in session:
        return jsonify({"error": "User not logged in"}), 401

    email = session["user"]["email"]
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    if "signature" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["signature"]
    
    try:
        # Ensure file type is allowed
        if file.filename == "":
            return jsonify({"error": "Invalid file name"}), 400
        
        allowed_extensions = {"png", "jpg", "jpeg"}
        if file.filename.split(".")[-1].lower() not in allowed_extensions:
            return jsonify({"error": "Invalid file format. Only PNG, JPG, and JPEG are allowed."}), 400

        blob_name = f"signatures/user_{user.id}.png"
        blob_client = signature_container_client.get_blob_client(blob_name)

        # Delete old signature if exists
        blob_list = signature_container_client.list_blobs(name_starts_with=blob_name)
        if any(blob_list):
            blob_client.delete_blob()

        # Upload new signature
        blob_client.upload_blob(file.read(), overwrite=True)

        # Generate the URL
        signature_url = f"https://{STORAGE_ACCOUNT_NAME}.blob.core.windows.net/{SIGNATURE_CONTAINER_NAME}/{blob_name}"

        # Update database
        user.signature_url = signature_url
        db.session.commit()

        return jsonify({"message": "Signature uploaded successfully!", "signature_url": signature_url})

    except Exception as e:
        logging.error(f"Error uploading signature: {str(e)}")
        return jsonify({"error": f"Error uploading signature: {str(e)}"}), 500

@app.route('/approve_request/<int:request_id>', methods=['POST'])
def approve_request(request_id):
    request = ReleaseFormRequest.query.get(request_id)
    if request:
        request.approval_status = "approved"
        db.session.commit()
        return jsonify({"message": "Request approved successfully"}), 200
    return jsonify({"error": "Request not found"}), 404

@app.route('/decline_request/<int:request_id>', methods=['POST'])
def decline_request(request_id):
    request = ReleaseFormRequest.query.get(request_id)
    if request:
        request.approval_status = "declined"
        db.session.commit()
        return jsonify({"message": "Request declined successfully"}), 200
    return jsonify({"error": "Request not found"}), 404

# Save comments
@app.route('/update_comment/<int:request_id>', methods=['POST'])
def update_comment(request_id):
    data = request.get_json() 
    release_form_request = ReleaseFormRequest.query.get(request_id)  

    if release_form_request:
        release_form_request.comments = data['comments']  
        db.session.commit()  
        return jsonify({"message": "Comment saved successfully"}), 200
    return jsonify({"error": "Request not found"}), 404 
    
# Helper functions
def _build_auth_url(scopes=None, state=None):
    return msal.PublicClientApplication(CLIENT_ID, authority=AUTHORITY).get_authorization_request_url(
        scopes, state=state, redirect_uri=REDIRECT_URI)

def _get_token_from_code(code):
    client = msal.ConfidentialClientApplication(CLIENT_ID, authority=AUTHORITY, client_credential=CLIENT_SECRET)
    result = client.acquire_token_by_authorization_code(code, scopes=SCOPE, redirect_uri=REDIRECT_URI)
    return result.get("access_token")

def _get_user_info(token):
    return requests.get('https://graph.microsoft.com/v1.0/me', headers={'Authorization': 'Bearer ' + token}).json()

# Run Flask App
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=8000, debug=True)
    #app.run(host='localhost', port=5000, debug=True) 
