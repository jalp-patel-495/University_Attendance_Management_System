from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
# from datetime import date

import json
from fpdf import FPDF

app = Flask(__name__)
app.config.from_object('config.Config')

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# Database Models
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # admin, teacher, student
    full_name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    teacher_subjects = db.relationship('TeacherSubject', backref='teacher', lazy=True, cascade="all, delete-orphan")
    student_classes = db.relationship('StudentClass', backref='student', lazy=True, cascade="all, delete-orphan")
    attendance = db.relationship('Attendance', backref='student_user', lazy=True, foreign_keys='Attendance.student_id', cascade="all, delete-orphan")

class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    course_code = db.Column(db.String(50), unique=True, nullable=False)
    course_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    subjects = db.relationship('Subject', backref='course', lazy=True, cascade="all, delete-orphan")
    classes = db.relationship('Class', backref='course', lazy=True, cascade="all, delete-orphan")

class Subject(db.Model):
    __tablename__ = 'subjects'
    id = db.Column(db.Integer, primary_key=True)
    subject_code = db.Column(db.String(50), unique=True, nullable=False)
    subject_name = db.Column(db.String(100), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    teacher_subjects = db.relationship('TeacherSubject', backref='subject', lazy=True, cascade="all, delete-orphan")
    attendance = db.relationship('Attendance', backref='subject_att', lazy=True, cascade="all, delete-orphan")

class Class(db.Model):
    __tablename__ = 'classes'
    id = db.Column(db.Integer, primary_key=True)
    class_code = db.Column(db.String(50), unique=True, nullable=False)
    class_name = db.Column(db.String(100), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    academic_year = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    student_classes = db.relationship('StudentClass', backref='class_info', lazy=True, cascade="all, delete-orphan")
    teacher_subjects = db.relationship('TeacherSubject', backref='class_info', lazy=True, cascade="all, delete-orphan")

class TeacherSubject(db.Model):
    __tablename__ = 'teacher_subjects'
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    assigned_date = db.Column(db.DateTime, default=datetime.utcnow)

class StudentClass(db.Model):
    __tablename__ = 'student_classes'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    enrollment_date = db.Column(db.DateTime, default=datetime.utcnow)

class Attendance(db.Model):
    __tablename__ = 'attendance'
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(10), nullable=False)  # Present, Absent, Late
    marked_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    marked_at = db.Column(db.DateTime, default=datetime.utcnow)

class Schedule(db.Model):
    __tablename__ = 'schedules'
    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    day_of_week = db.Column(db.String(15), nullable=False) # Monday, Tuesday...
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    room = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    class_info = db.relationship('Class', backref=db.backref('schedules', cascade='all, delete-orphan'), lazy=True)
    subject = db.relationship('Subject', backref=db.backref('schedules', cascade='all, delete-orphan'), lazy=True)

# ================= DSA TOPIC: STACK IMPLEMENTATION =================
class AttendanceStack:
    def __init__(self):
        self.stack = []

    def push(self, item):
        self.stack.append(item)

    def pop(self):
        if not self.is_empty():
            return self.stack.pop()
        return None

    def peek(self):
        if not self.is_empty():
            return self.stack[-1]
        return None

    def is_empty(self):
        return len(self.stack) == 0

    def size(self):
        return len(self.stack)


# Global stack object
attendance_stack = AttendanceStack()
# ===================================================================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_context():
    if not current_user.is_authenticated:
        return dict()
    
    context = {}
    if current_user.role == 'student':
        student_class = StudentClass.query.filter_by(student_id=current_user.id).first()
        context['student_class'] = student_class
        
    return context

# Authentication Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif current_user.role == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        else:
            return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Login successful!', 'success')
            
            # Redirect based on role
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'teacher':
                return redirect(url_for('teacher_dashboard'))
            else:
                return redirect(url_for('student_dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('auth/login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Admin Routes
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
    
    stats = {
        'total_students': User.query.filter_by(role='student').count(),
        'total_teachers': User.query.filter_by(role='teacher').count(),
        'total_courses': Course.query.count(),
        'total_classes': Class.query.count()
    }
    
    return render_template('admin/dashboard.html', stats=stats)

@app.route('/admin/courses', methods=['GET', 'POST'])
@login_required
def manage_courses():
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        course_code = request.form.get('course_code')
        course_name = request.form.get('course_name')
        description = request.form.get('description')
        
        course = Course(course_code=course_code, course_name=course_name, description=description)
        db.session.add(course)
        db.session.commit()
        flash('Course added successfully!', 'success')
        return redirect(url_for('manage_courses'))
    
    courses = Course.query.all()
    return render_template('admin/courses.html', courses=courses)

@app.route('/admin/course/edit/<int:id>', methods=['POST'])
@login_required
def edit_course(id):
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
    
    course = Course.query.get_or_404(id)
    course.course_code = request.form.get('course_code')
    course.course_name = request.form.get('course_name')
    course.description = request.form.get('description')
    
    db.session.commit()
    flash('Course updated successfully!', 'success')
    return redirect(url_for('manage_courses'))



@app.route('/admin/subjects', methods=['GET', 'POST'])
@login_required
def manage_subjects():
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        subject_code = request.form.get('subject_code')
        subject_name = request.form.get('subject_name')
        course_id = request.form.get('course_id')
        
        subject = Subject(subject_code=subject_code, subject_name=subject_name, course_id=course_id)
        db.session.add(subject)
        db.session.commit()
        flash('Subject added successfully!', 'success')
        return redirect(url_for('manage_subjects'))
    
    subjects = Subject.query.all()
    courses = Course.query.all()
    return render_template('admin/subjects.html', subjects=subjects, courses=courses)

@app.route('/admin/subject/edit/<int:id>', methods=['POST'])
@login_required
def edit_subject(id):
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
    
    subject = Subject.query.get_or_404(id)
    subject.subject_code = request.form.get('subject_code')
    subject.subject_name = request.form.get('subject_name')
    subject.course_id = request.form.get('course_id')
    
    db.session.commit()
    flash('Subject updated successfully!', 'success')
    return redirect(url_for('manage_subjects'))



@app.route('/admin/classes', methods=['GET', 'POST'])
@login_required
def manage_classes():
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        class_code = request.form.get('class_code')
        class_name = request.form.get('class_name')
        course_id = request.form.get('course_id')
        academic_year = request.form.get('academic_year')
        
        class_obj = Class(class_code=class_code, class_name=class_name, 
                         course_id=course_id, academic_year=academic_year)
        db.session.add(class_obj)
        db.session.commit()
        flash('Class added successfully!', 'success')
        return redirect(url_for('manage_classes'))
    
    classes = Class.query.all()
    courses = Course.query.all()
    return render_template('admin/classes.html', classes=classes, courses=courses)

@app.route('/admin/class/edit/<int:id>', methods=['POST'])
@login_required
def edit_class(id):
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
    
    class_obj = Class.query.get_or_404(id)
    class_obj.class_code = request.form.get('class_code')
    class_obj.class_name = request.form.get('class_name')
    class_obj.course_id = request.form.get('course_id')
    class_obj.academic_year = request.form.get('academic_year')
    
    db.session.commit()
    flash('Class updated successfully!', 'success')
    return redirect(url_for('manage_classes'))



@app.route('/admin/users', methods=['GET', 'POST'])
@login_required
def manage_users():
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        full_name = request.form.get('full_name')
        role = request.form.get('role')
        
        hashed_password = generate_password_hash(password)
        user = User(username=username, email=email, password=hashed_password, 
                   full_name=full_name, role=role)
        db.session.add(user)
        db.session.commit()
        flash('User added successfully!', 'success')
        return redirect(url_for('manage_users'))
    
    role_filter = request.args.get('role')
    if role_filter and role_filter != 'all':
        users = User.query.filter_by(role=role_filter).all()
    else:
        users = User.query.all()
    
    classes = Class.query.all()
    return render_template('admin/users.html', users=users, classes=classes)

@app.route('/admin/user/edit/<int:id>', methods=['POST'])
@login_required
def edit_user(id):
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
    
    user = User.query.get_or_404(id)
    user.username = request.form.get('username')
    user.email = request.form.get('email')
    user.full_name = request.form.get('full_name')
    user.role = request.form.get('role')
    
    password = request.form.get('password')
    if password:
        user.password = generate_password_hash(password)
        
    try:
        db.session.commit()
        flash('User updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Error updating user. Username or email might already exist.', 'danger')
        
    return redirect(url_for('manage_users'))

@app.route('/admin/assign-class/<int:student_id>', methods=['POST'])
@login_required
def assign_student_class(student_id):
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
        
    class_id = request.form.get('class_id')
    
    # Check if assignment already exists
    exists = StudentClass.query.filter_by(student_id=student_id, class_id=class_id).first()
    if not exists:
        assignment = StudentClass(student_id=student_id, class_id=class_id)
        db.session.add(assignment)
        db.session.commit()
        flash('Class assigned successfully!', 'success')
    else:
        flash('Student is already assigned to this class.', 'warning')
        
    return redirect(url_for('manage_users'))

@app.route('/admin/assign-teachers', methods=['GET', 'POST'])
@login_required
def assign_teachers():
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        teacher_id = request.form.get('teacher_id')
        subject_id = request.form.get('subject_id')
        class_id = request.form.get('class_id')
        
        assignment = TeacherSubject(teacher_id=teacher_id, subject_id=subject_id, class_id=class_id)
        db.session.add(assignment)
        db.session.commit()
        flash('Teacher assigned successfully!', 'success')
        return redirect(url_for('assign_teachers'))
    
    teachers = User.query.filter_by(role='teacher').all()
    subjects = Subject.query.all()
    classes = Class.query.all()
    assignments = TeacherSubject.query.all()
    
    return render_template('admin/assign_teachers.html', 
                          teachers=teachers, subjects=subjects, 
                          classes=classes, assignments=assignments)

# Teacher Routes
@app.route('/teacher/dashboard')
@login_required
def teacher_dashboard():
    if current_user.role != 'teacher':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
    
    # Get teacher's assigned subjects
    assignments = TeacherSubject.query.filter_by(teacher_id=current_user.id).all()
    
    stats = {
        'assigned_subjects': len(assignments),
        'total_classes': len(set([a.class_id for a in assignments])),
        'today_attendance': Attendance.query.filter(
            Attendance.marked_by == current_user.id,
            Attendance.date == date.today()
        ).count()
    }
    
    return render_template('teacher/dashboard.html', stats=stats, assignments=assignments)

@app.route('/teacher/attendance/<int:subject_id>/<int:class_id>', methods=['GET', 'POST'])
@login_required
def take_attendance(subject_id, class_id):
    if current_user.role != 'teacher':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
    
    # Check if teacher is assigned to this subject and class
    assignment = TeacherSubject.query.filter_by(
        teacher_id=current_user.id,
        subject_id=subject_id,
        class_id=class_id
    ).first()
    
    if not assignment:
        flash('You are not assigned to this subject/class', 'danger')
        return redirect(url_for('teacher_dashboard'))
    
    if request.method == 'POST':
        data = request.json
        attendance_date = data.get('date')
        
        for record in data.get('attendance', []):
            attendance_record_date = datetime.strptime(attendance_date, '%Y-%m-%d').date()
            
            # Check if attendance already exists
            existing_attendance = Attendance.query.filter_by(
                student_id=record['student_id'],
                subject_id=subject_id,
                class_id=class_id,
                date=attendance_record_date
            ).first()
            
            if existing_attendance:
                # Update existing record
                existing_attendance.status = record['status']
                existing_attendance.marked_by = current_user.id
                existing_attendance.marked_at = datetime.utcnow()
            else:
                # Create new record
                attendance = Attendance(
                    student_id=record['student_id'],
                    subject_id=subject_id,
                    class_id=class_id,
                    date=attendance_record_date,
                    status=record['status'],
                    marked_by=current_user.id
                )
                db.session.add(attendance)
        
        db.session.commit()
                # ================= STACK USAGE =================
        log_message = f"Teacher {current_user.full_name} marked attendance for Subject {subject_id}, Class {class_id} on {attendance_date}"
        attendance_stack.push(log_message)

        print("Stack Size:", attendance_stack.size())
        print("Last Operation:", attendance_stack.peek())
        # =================================================

        return jsonify({'success': True, 'message': 'Attendance saved successfully!'})
    
    # Get students in this class
    student_classes = StudentClass.query.filter_by(class_id=class_id).all()
    students = [sc.student for sc in student_classes]
    
    subject = Subject.query.get(subject_id)
    class_info = Class.query.get(class_id)
    
    return render_template('teacher/attendance.html', 
                          students=students, 
                          subject=subject, 
                          class_info=class_info)

@app.route('/teacher/view-attendance')
@login_required
def view_attendance():
    current_date = date.today()
    subjects = TeacherSubject.query.filter_by(
        teacher_id=current_user.id
    ).all()

    # Attendance records (you already have this logic or empty list)
    assignments = [] 
    if current_user.role != 'teacher':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
    
    assignments = TeacherSubject.query.filter_by(teacher_id=current_user.id).all()
    
    # Extract unique classes and subjects for filters
    classes = {}
    subjects = {}
    
    for assignment in assignments:
        if assignment.class_id not in classes:
            classes[assignment.class_id] = assignment.class_info
        if assignment.subject_id not in subjects:
            subjects[assignment.subject_id] = assignment.subject
            
    return render_template('teacher/view_attendance.html', 
                          assignments=assignments, 
                          classes=classes.values(),
                          subjects=subjects.values(),
                          current_date=current_date)

@app.context_processor
def inject_current_date():
    return {'current_date': date.today()}

@app.route('/teacher/reports')
@login_required
def teacher_reports():
    if current_user.role != 'teacher':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
    
    # Get attendance data for teacher's subjects
    assignments = TeacherSubject.query.filter_by(teacher_id=current_user.id).all()
    return render_template('teacher/reports.html', assignments=assignments,current_date=date.today())

# Student Routes
@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'student':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
    
    # Get student's class
    student_class = StudentClass.query.filter_by(student_id=current_user.id).first()
    
    # Get today's attendance
    today_attendance = Attendance.query.filter_by(
        student_id=current_user.id,
        date=date.today()
    ).all()
    
    # Calculate overall attendance percentage
    total_records = Attendance.query.filter_by(student_id=current_user.id).count()
    present_records = Attendance.query.filter_by(
        student_id=current_user.id,
        status='Present'
    ).count()
    
    percentage = (present_records / total_records * 100) if total_records > 0 else 0
    
    # Get total subjects for the class
    total_subjects_count = 0
    if student_class:
        # Count unique subjects assigned to the student's class
        total_subjects_count = db.session.query(TeacherSubject.subject_id)\
            .filter_by(class_id=student_class.class_id)\
            .distinct().count()

    stats = {
        'total_subjects': total_subjects_count,
        'present_today': len([a for a in today_attendance if a.status == 'Present']),
        'attendance_percentage': round(percentage, 2)
    }
    
    return render_template('student/dashboard.html', stats=stats, student_class=student_class, current_date=date.today())

@app.route('/student/attendance')
@login_required
def student_attendance():
    current_date = date.today()
    if current_user.role != 'student':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
    
    # Get attendance records for the student
    attendance_records = Attendance.query.filter_by(student_id=current_user.id).all()
    
    # Group by date
    attendance_by_date = {}
    for record in attendance_records:
        date_str = record.date.strftime('%Y-%m-%d')
        if date_str not in attendance_by_date:
            attendance_by_date[date_str] = []
        attendance_by_date[date_str].append(record)
    
    # return render_template('student/attendance_view.html', 
    #                       attendance_by_date=attendance_by_date
    #                       current_date=current_date )
    return render_template(
    'student/attendance_view.html',
    attendance_records=attendance_records,
    current_date=current_date,
    attendance_by_date=attendance_by_date)

@app.route('/api/teacher/reports')
@login_required
def get_teacher_reports():
    if current_user.role != 'teacher':
        return jsonify({'error': 'Access denied'}), 403
        
    report_type = request.args.get('type', 'monthly')
    month_str = request.args.get('month')
    subject_id = request.args.get('subject_id')
    
    # Parse month
    try:
        year, month = map(int, month_str.split('-'))
    except (ValueError, AttributeError):
        today = date.today()
        year, month = today.year, today.month

    # Base query
    query = Attendance.query.join(Subject).join(Class).join(StudentClass, Attendance.student_id == StudentClass.student_id)
    
    # Filter by teacher's subjects
    teacher_assignments = TeacherSubject.query.filter_by(teacher_id=current_user.id).all()
    allowed_subject_ids = [a.subject_id for a in teacher_assignments]
    
    if subject_id and int(subject_id) in allowed_subject_ids:
        query = query.filter(Attendance.subject_id == subject_id)
    else:
        query = query.filter(Attendance.subject_id.in_(allowed_subject_ids))
        
    # Filter by month
    query = query.filter(
        db.extract('year', Attendance.date) == year,
        db.extract('month', Attendance.date) == month
    )
    
    records = query.all()
    
    # Calculate Stats
    total_days = db.session.query(db.func.count(db.distinct(Attendance.date))).filter(
        db.extract('year', Attendance.date) == year,
        db.extract('month', Attendance.date) == month,
        Attendance.subject_id.in_(allowed_subject_ids)
    ).scalar() or 0

    total_records = len(records)
    present_count = len([r for r in records if r.status == 'Present'])
    absent_count = len([r for r in records if r.status == 'Absent'])
    late_count = len([r for r in records if r.status == 'Late'])
    
    avg_percentage = (present_count / total_records * 100) if total_records > 0 else 0
    
    # Get unique students count
    total_students = len(set(r.student_id for r in records))

    # Best attendance day
    from sqlalchemy import func
    best_day_query = db.session.query(
        Attendance.date, 
        func.count(Attendance.id).label('count')
    ).filter(
        Attendance.status == 'Present',
        db.extract('year', Attendance.date) == year,
        db.extract('month', Attendance.date) == month,
        Attendance.subject_id.in_(allowed_subject_ids)
    ).group_by(Attendance.date).order_by(db.desc('count')).first()
    
    best_day = best_day_query[0].strftime('%Y-%m-%d') if best_day_query else 'N/A'

    stats = {
        'total_days': total_days,
        'avg_percentage': round(avg_percentage, 1),
        'total_students': total_students,
        'best_day': best_day
    }
    
    # Charts Data
    # 1. Trend (Attendance % per day)
    trend_data = {}
    for r in records:
        d = r.date.strftime('%Y-%m-%d')
        if d not in trend_data:
            trend_data[d] = {'total': 0, 'present': 0}
        trend_data[d]['total'] += 1
        if r.status == 'Present':
            trend_data[d]['present'] += 1
            
    trend_labels = sorted(trend_data.keys())
    trend_values = []
    for d in trend_labels:
        total = trend_data[d]['total']
        present = trend_data[d]['present']
        pct = (present / total * 100) if total > 0 else 0
        trend_values.append(round(pct, 1))

    # 2. Distribution
    distribution = [present_count, absent_count, late_count]
    
    charts = {
        'trend': {'labels': trend_labels, 'data': trend_values},
        'distribution': distribution
    }
    
    # Table Data
    table_headers = ['Date', 'Student', 'Subject', 'Class', 'Status', 'Time']
    table_rows = []
    
    # Allow filtering/sorting for table if needed, for now just list latest
    sorted_records = sorted(records, key=lambda x: x.date, reverse=True)
    
    count = 0
    for r in sorted_records:
        if count >= 100: break # Limit rows
        
        student = User.query.get(r.student_id)
        subject = Subject.query.get(r.subject_id)
        class_obj = Class.query.get(r.class_id)
        
        # Determine badge class
        status_badge = f'<span class="badge bg-secondary">{r.status}</span>'
        if r.status == 'Present':
            status_badge = '<span class="badge bg-success">Present</span>'
        elif r.status == 'Absent':
            status_badge = '<span class="badge bg-danger">Absent</span>'
        elif r.status == 'Late':
            status_badge = '<span class="badge bg-warning">Late</span>'

        table_rows.append([
            r.date.strftime('%Y-%m-%d'),
            student.full_name if student else 'Unknown',
            subject.subject_name if subject else 'Unknown',
            class_obj.class_name if class_obj else 'Unknown',
            status_badge,
            r.marked_at.strftime('%H:%M') if r.marked_at else '-'
        ])
        count += 1
        
    return jsonify({
        'stats': stats,
        'charts': charts,
        'table': {'headers': table_headers, 'rows': table_rows}
    })

@app.route('/teacher/students')
@login_required
def view_students():
    if current_user.role != 'teacher':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
        
    # Get teacher's classes
    teacher_assignments = TeacherSubject.query.filter_by(teacher_id=current_user.id).all()
    class_ids = [t.class_id for t in teacher_assignments]
    
    # Get students in these classes
    student_classes = StudentClass.query.filter(StudentClass.class_id.in_(class_ids)).all()
    
    students_data = []
    seen_students = set()
    
    for sc in student_classes:
        # Avoid duplicate students if they are in multiple classes taught by same teacher?
        # Or show them per class? Let's show per class entry or distinctive?
        # Let's show unique students and list their classes
        if sc.student_id not in seen_students:
            student = User.query.get(sc.student_id)
            # Find all classes this student is in that are also taught by this teacher
            s_classes = StudentClass.query.filter_by(student_id=student.id).all()
            my_classes = [c.class_info.class_name for c in s_classes if c.class_id in class_ids]
            
            students_data.append({
                'id': student.id,
                'username': student.username,
                'email': student.email,
                'full_name': student.full_name,
                'class_name': ', '.join(my_classes)
            })
            seen_students.add(sc.student_id)

    # Get unique classes for the "Add Student" modal dropdown
    my_classes_objects = {}
    for ta in teacher_assignments:
        if ta.class_id not in my_classes_objects:
            my_classes_objects[ta.class_id] = ta.class_info

    return render_template('teacher/students.html', students=students_data, classes=my_classes_objects.values())

@app.route('/teacher/add_student', methods=['POST'])
@login_required
def add_student():
    if current_user.role != 'teacher':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
        
    username = request.form.get('username')
    email = request.form.get('email')
    full_name = request.form.get('full_name')
    password = request.form.get('password')
    class_id = request.form.get('class_id')
    
    # Check if user exists
    user = User.query.filter((User.username == username) | (User.email == email)).first()
    if user:
        if user.role != 'student':
             flash('User exists but is not a student.', 'danger')
             return redirect(url_for('view_students'))
             
        # Assign to class if not already assigned
        exists = StudentClass.query.filter_by(student_id=user.id, class_id=class_id).first()
        if not exists:
            sc = StudentClass(student_id=user.id, class_id=class_id)
            db.session.add(sc)
            db.session.commit()
            flash('Existing student assigned to class successfully!', 'success')
        else:
            flash('Student already in this class.', 'warning')
    else:
        # Create new user
        hashed_password = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_password, full_name=full_name, role='student')
        db.session.add(new_user)
        db.session.commit()
        
        # Assign to class
        sc = StudentClass(student_id=new_user.id, class_id=class_id)
        db.session.add(sc)
        db.session.commit()
        flash('New student created and assigned successfully!', 'success')
        
    return redirect(url_for('view_students'))


@app.route('/student/reports')
@login_required
def student_reports():
    if current_user.role != 'student':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
    
    # Get student's class for teacher lookup
    student_class = StudentClass.query.filter_by(student_id=current_user.id).first()
    
    import calendar
    from datetime import datetime
    
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    # Get all attendance for the current year (for trend)
    year_attendance = Attendance.query.filter(
        Attendance.student_id == current_user.id,
        db.extract('year', Attendance.date) == current_year
    ).all()
    
    # Calculate monthly trend for the current year
    monthly_trend = []
    for m in range(1, 13):
        m_attendance = [r for r in year_attendance if r.date.month == m]
        if not m_attendance:
            monthly_trend.append(0)
            continue
        
        m_present = len([r for r in m_attendance if r.status == 'Present'])
        m_pct = (m_present / len(m_attendance)) * 100
        monthly_trend.append(round(m_pct, 2))
    
    # Calculate distribution (based on all-time attendance)
    all_attendance = Attendance.query.filter_by(student_id=current_user.id).all()
    distribution = {
        'Present': len([r for r in all_attendance if r.status == 'Present']),
        'Absent': len([r for r in all_attendance if r.status == 'Absent']),
        'Late': len([r for r in all_attendance if r.status == 'Late'])
    }
    
    # Get attendance for current month (original logic for subject-wise table)
    month_attendance = [r for r in year_attendance if r.date.month == current_month]
    
    # Calculate subject-wise percentage for current month
    subjects = {}
    for record in month_attendance:
        if record.subject_id not in subjects:
            subject = Subject.query.get(record.subject_id)
            
            # Find teacher
            teacher_name = 'N/A'
            if student_class:
                ts = TeacherSubject.query.filter_by(
                    subject_id=record.subject_id, 
                    class_id=student_class.class_id
                ).first()
                if ts and ts.teacher:
                    teacher_name = ts.teacher.full_name

            subjects[record.subject_id] = {
                'id': subject.id,
                'name': subject.subject_name,
                'code': subject.subject_code,
                'teacher': teacher_name,
                'total': 0,
                'present': 0,
                'absent': 0,
                'late': 0
            }
        
        subjects[record.subject_id]['total'] += 1
        if record.status == 'Present':
            subjects[record.subject_id]['present'] += 1
        elif record.status == 'Absent':
            subjects[record.subject_id]['absent'] += 1
        elif record.status == 'Late':
            subjects[record.subject_id]['late'] += 1
    
    # Calculate subject percentages
    for sub_id in subjects:
        if subjects[sub_id]['total'] > 0:
            subjects[sub_id]['percentage'] = round(
                (subjects[sub_id]['present'] / subjects[sub_id]['total']) * 100, 2
            )
        else:
            subjects[sub_id]['percentage'] = 0
    
    # Calculate overall stats
    total_records = len(all_attendance)
    present_records = distribution['Present']
    overall_percentage = (present_records / total_records * 100) if total_records > 0 else 0
    
    stats = {
        'attendance_percentage': round(overall_percentage, 2)
    }

    return render_template('student/reports.html', 
                          subjects=list(subjects.values()),
                          month=calendar.month_name[current_month],
                          stats=stats,
                          current_date=datetime.now(),
                          monthly_trend=monthly_trend,
                          distribution=distribution)

@app.route('/api/student/detailed-report')
@login_required
def student_detailed_report():
    if current_user.role != 'student':
        return jsonify([])
    
    month = request.args.get('month')
    subject_id = request.args.get('subject_id')
    
    query = Attendance.query.filter_by(student_id=current_user.id)
    
    if month:
        year, month_num = map(int, month.split('-'))
        query = query.filter(
            db.extract('year', Attendance.date) == year,
            db.extract('month', Attendance.date) == month_num
        )
    
    if subject_id:
        query = query.filter_by(subject_id=subject_id)
        
    records = query.order_by(Attendance.date.desc()).all()
    
    result = []
    for record in records:
        subject = Subject.query.get(record.subject_id)
        result.append({
            'date': record.date.strftime('%Y-%m-%d'),
            'day': record.date.strftime('%A'),
            'subject': subject.subject_name if subject else 'N/A',
            'status': record.status,
            'time': record.marked_at.strftime('%H:%M') if record.marked_at else '-',
            'remarks': record.remarks if hasattr(record, 'remarks') else ''
        })
        
    return jsonify(result)

@app.route('/student/schedule')
@login_required
def student_schedule():
    if current_user.role != 'student':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
        
    # Get student's class
    student_class_record = StudentClass.query.filter_by(student_id=current_user.id).first()
    
    schedule_data = {}
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    class_name = "Not Assigned"
    
    if student_class_record:
        class_obj = Class.query.get(student_class_record.class_id)
        class_name = class_obj.class_name
        
        # Get schedules for this class
        schedules = Schedule.query.filter_by(class_id=student_class_record.class_id).all()
        
        # Organize by day
        for day in days_order:
            day_schedules = [s for s in schedules if s.day_of_week == day]
            day_schedules.sort(key=lambda x: x.start_time)
            if day_schedules:
                formatted_schedules = []
                for s in day_schedules:
                    formatted_schedules.append({
                        'subject': s.subject.subject_name,
                        'time': f"{s.start_time.strftime('%H:%M')} - {s.end_time.strftime('%H:%M')}",
                        'room': s.room
                    })
                schedule_data[day] = formatted_schedules
                
    return render_template('student/schedule.html', schedule=schedule_data, days=days_order, class_name=class_name)

@app.route('/api/student/export-report/<month>/')
@app.route('/api/student/export-report/<month>/<subject_id>')
@login_required
def export_student_report(month, subject_id=None):
    if current_user.role != 'student':
        flash('Access denied!', 'danger')
        return redirect(url_for('student_reports'))
        
    # Build query
    query = Attendance.query.filter_by(student_id=current_user.id)
    
    if month:
        try:
            year, month_num = map(int, month.split('-'))
            query = query.filter(
                db.extract('year', Attendance.date) == year,
                db.extract('month', Attendance.date) == month_num
            )
        except ValueError:
            pass
            
    if subject_id and subject_id not in ['null', 'undefined', '']:
        query = query.filter_by(subject_id=subject_id)
        
    records = query.order_by(Attendance.date.desc()).all()
    
    # Generate PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=16)
    pdf.cell(200, 10, txt="Attendance Report", ln=1, align="C")
    
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Student: {current_user.full_name} ({current_user.username})", ln=1, align="L")
    pdf.cell(200, 10, txt=f"Month: {month}", ln=1, align="L")
    pdf.ln(10)
    
    # Table Header
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(40, 10, "Date", 1)
    pdf.cell(70, 10, "Subject", 1)
    pdf.cell(30, 10, "Status", 1)
    pdf.cell(50, 10, "Teacher", 1)
    pdf.ln()
    
    # Table Content
    pdf.set_font("Arial", size=10)
    for record in records:
        subject = Subject.query.get(record.subject_id)
        teacher = User.query.get(record.marked_by) if record.marked_by else None
        
        pdf.cell(40, 10, str(record.date), 1)
        pdf.cell(70, 10, subject.subject_name if subject else 'N/A', 1)
        
        status = record.status
        pdf.cell(30, 10, status, 1)
        pdf.cell(50, 10, teacher.full_name if teacher else 'N/A', 1)
        pdf.ln()
        
    response = make_response(pdf.output(dest='S').encode('latin-1'))
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=attendance_report_{month}.pdf'
    
    return response

@app.route('/teacher/students')
@login_required
def teacher_students():
    # load all classes / students for this teacher
    return render_template('teacher/students.html')


# API Routes for AJAX
@app.route('/api/get-class-students/<int:class_id>')
@login_required
def get_class_students(class_id):
    student_classes = StudentClass.query.filter_by(class_id=class_id).all()
    students = []
    
    for sc in student_classes:
        students.append({
            'id': sc.student.id,
            'name': sc.student.full_name,
            'username': sc.student.username
        })
    
    return jsonify(students)

@app.route('/api/get-attendance/<int:subject_id>/<int:class_id>/<date>')
@login_required
def get_attendance(subject_id, class_id, date):
    attendance_date = datetime.strptime(date, '%Y-%m-%d').date()
    records = Attendance.query.filter_by(
        subject_id=subject_id,
        class_id=class_id,
        date=attendance_date
    ).all()
    
    attendance_data = {}
    for record in records:
        attendance_data[record.student_id] = record.status
    
    return jsonify(attendance_data)

# Create tables
with app.app_context():
    db.create_all()
    
    # Create admin user if not exists
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        hashed_password = generate_password_hash('admin123')
        admin = User(
            username='admin',
            email='admin@school.com',
            password=hashed_password,
            full_name='Administrator',
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()

# Additional API Routes
@app.route('/api/teacher/attendance-records')
@login_required
def teacher_attendance_records():
    if current_user.role != 'teacher':
        return jsonify([])
    
    subject_id = request.args.get('subject_id')
    class_id = request.args.get('class_id')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    # Query attendance records based on filters
    query = db.session.query(
        Attendance.date,
        Subject.subject_name,
        Class.class_name,
        db.func.count(Attendance.id).label('total_students'),
        db.func.sum(db.case((Attendance.status == 'Present', 1), else_=0)).label('present'),
        db.func.sum(db.case((Attendance.status == 'Absent', 1), else_=0)).label('absent'),
        db.func.sum(db.case((Attendance.status == 'Late', 1), else_=0)).label('late'),
        Subject.id.label('subject_id'),
        Class.id.label('class_id')
    ).join(Subject, Attendance.subject_id == Subject.id)\
     .join(Class, Attendance.class_id == Class.id)\
     .join(TeacherSubject, db.and_(
         TeacherSubject.subject_id == Subject.id,
         TeacherSubject.class_id == Class.id
     ))\
     .filter(TeacherSubject.teacher_id == current_user.id)\
     .group_by(Attendance.date, Subject.id, Class.id)
    
    if subject_id:
        query = query.filter(Attendance.subject_id == subject_id)
    if class_id:
        query = query.filter(Attendance.class_id == class_id)
    if date_from:
        query = query.filter(Attendance.date >= date_from)
    if date_to:
        query = query.filter(Attendance.date <= date_to)
    
    records = query.order_by(Attendance.date.desc()).all()
    
    result = []
    for record in records:
        result.append({
            'date': record.date.strftime('%Y-%m-%d'),
            'subject_name': record.subject_name,
            'class_name': record.class_name,
            'total_students': record.total_students,
            'present': record.present,
            'absent': record.absent,
            'late': record.late,
            'subject_id': record.subject_id,
            'class_id': record.class_id
        })
    
    return jsonify(result)

@app.route('/api/attendance-details/<int:subject_id>/<int:class_id>/<date>')
@login_required
def attendance_details(subject_id, class_id, date):
    attendance_date = datetime.strptime(date, '%Y-%m-%d').date()
    
    records = db.session.query(
        Attendance,
        User.username.label('student_username'),
        User.full_name.label('student_name')
    ).join(User, Attendance.student_id == User.id)\
     .filter(Attendance.subject_id == subject_id,
             Attendance.class_id == class_id,
             Attendance.date == attendance_date)\
     .all()
    
    result = []
    for attendance, username, full_name in records:
        result.append({
            'student_username': username,
            'student_name': full_name,
            'status': attendance.status,
            'marked_time': attendance.marked_at.strftime('%H:%M') if attendance.marked_at else '-',
            'remarks': attendance.remarks if hasattr(attendance, 'remarks') else None
        })
    
    return jsonify(result)

# Teacher Export Routes
@app.route('/api/export-report/<report_type>/<month>/')
@app.route('/api/export-report/<report_type>/<month>/<subject_id>')
@login_required
def export_teacher_report(report_type, month, subject_id=None):
    if current_user.role != 'teacher':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
        
    try:
        year, month_num = map(int, month.split('-'))
    except (ValueError, AttributeError):
        today = date.today()
        year, month_num = today.year, today.month

    query = Attendance.query.join(Subject).join(Class)
    teacher_assignments = TeacherSubject.query.filter_by(teacher_id=current_user.id).all()
    allowed_subject_ids = [a.subject_id for a in teacher_assignments]
    
    if subject_id and subject_id not in ['null', 'undefined', '']:
        if int(subject_id) in allowed_subject_ids:
            query = query.filter(Attendance.subject_id == subject_id)
        else:
            return "Unauthorized subject", 403
    else:
        query = query.filter(Attendance.subject_id.in_(allowed_subject_ids))
        
    query = query.filter(
        db.extract('year', Attendance.date) == year,
        db.extract('month', Attendance.date) == month_num
    )
    
    records = query.order_by(Attendance.date.desc()).all()
    
    import csv
    from io import StringIO
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Date', 'Student Name', 'Subject', 'Class', 'Status', 'Marked At'])
    
    for r in records:
        student = User.query.get(r.student_id)
        subject = Subject.query.get(r.subject_id)
        class_obj = Class.query.get(r.class_id)
        cw.writerow([
            r.date.strftime('%Y-%m-%d'),
            student.full_name if student else 'Unknown',
            subject.subject_name if subject else 'Unknown',
            class_obj.class_name if class_obj else 'Unknown',
            r.status,
            r.marked_at.strftime('%H:%M:%S') if r.marked_at else '-'
        ])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=attendance_report_{month}.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/api/export-attendance')
@login_required
def export_teacher_attendance_all():
    if current_user.role != 'teacher':
        return jsonify({'error': 'Access denied'}), 403
        
    subject_id = request.args.get('subject_id')
    class_id = request.args.get('class_id')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    query = Attendance.query.join(Subject).join(Class)
    teacher_assignments = TeacherSubject.query.filter_by(teacher_id=current_user.id).all()
    allowed_subject_ids = [a.subject_id for a in teacher_assignments]
    
    if subject_id:
        query = query.filter(Attendance.subject_id == subject_id)
    else:
        query = query.filter(Attendance.subject_id.in_(allowed_subject_ids))
        
    if class_id:
        query = query.filter(Attendance.class_id == class_id)
    if date_from:
        query = query.filter(Attendance.date >= date_from)
    if date_to:
        query = query.filter(Attendance.date <= date_to)
        
    records = query.order_by(Attendance.date.desc()).all()
    
    import csv
    from io import StringIO
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Date', 'Student', 'Subject', 'Class', 'Status', 'Time'])
    
    for r in records:
        student = User.query.get(r.student_id)
        subject = Subject.query.get(r.subject_id)
        class_obj = Class.query.get(r.class_id)
        cw.writerow([
            r.date.strftime('%Y-%m-%d'),
            student.full_name if student else 'Unknown',
            subject.subject_name if subject else 'Unknown',
            class_obj.class_name if class_obj else 'Unknown',
            r.status,
            r.marked_at.strftime('%H:%M') if r.marked_at else '-'
        ])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=attendance_all_export.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/api/export-daily-attendance/<int:subject_id>/<int:class_id>/<date_str>')
@login_required
def export_daily_attendance(subject_id, class_id, date_str):
    if current_user.role != 'teacher':
        return jsonify({'error': 'Access denied'}), 403
        
    attendance_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    
    # Check authorization
    assignment = TeacherSubject.query.filter_by(
        teacher_id=current_user.id,
        subject_id=subject_id,
        class_id=class_id
    ).first()
    
    if not assignment:
        return "Unauthorized", 403
        
    records = Attendance.query.filter_by(
        subject_id=subject_id,
        class_id=class_id,
        date=attendance_date
    ).all()
    
    import csv
    from io import StringIO
    si = StringIO()
    cw = csv.writer(si)
    
    subject = Subject.query.get(subject_id)
    class_obj = Class.query.get(class_id)
    
    cw.writerow(['Attendance Report'])
    cw.writerow([f'Date: {date_str}'])
    cw.writerow([f'Subject: {subject.subject_name if subject else "N/A"}'])
    cw.writerow([f'Class: {class_obj.class_name if class_obj else "N/A"}'])
    cw.writerow([])
    cw.writerow(['Student ID', 'Student Name', 'Status', 'Time', 'Remarks'])
    
    for r in records:
        student = User.query.get(r.student_id)
        cw.writerow([
            student.username if student else 'Unknown',
            student.full_name if student else 'Unknown',
            r.status,
            r.marked_at.strftime('%H:%M') if r.marked_at else '-',
            r.remarks if hasattr(r, 'remarks') else '-'
        ])
        
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=attendance_{date_str}.csv"
    output.headers["Content-type"] = "text/csv"
    return output


# Student API Routes
@app.route('/api/student/subjects')
@login_required
def get_student_subjects_api():
    if current_user.role != 'student':
        return jsonify([])
    
    student_class = StudentClass.query.filter_by(student_id=current_user.id).first()
    if not student_class:
        return jsonify([])
        
    # Get distinct subjects for this class
    assignments = TeacherSubject.query.filter_by(class_id=student_class.class_id).all()
    subjects = []
    seen_subjects = set()
    
    for assign in assignments:
        if assign.subject_id not in seen_subjects:
            subjects.append({
                'id': assign.subject.id,
                'name': assign.subject.subject_name
            })
            seen_subjects.add(assign.subject_id)
            
    return jsonify(subjects)

@app.route('/api/student/export-attendance')
@login_required
def export_student_attendance_api():
    if current_user.role != 'student':
        return jsonify({'error': 'Access denied'})
        
    import csv
    from io import StringIO
    from flask import make_response
    
    month = request.args.get('month')
    subject_id = request.args.get('subject_id')
    status = request.args.get('status')
    
    # Build query
    query = Attendance.query.filter_by(student_id=current_user.id)
    
    if month:
        year, month_num = map(int, month.split('-'))
        query = query.filter(
            db.extract('year', Attendance.date) == year,
            db.extract('month', Attendance.date) == month_num
        )
    
    if subject_id:
        query = query.filter_by(subject_id=subject_id)
    
    if status:
        query = query.filter_by(status=status)
        
    records = query.order_by(Attendance.date.desc()).all()
    
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Date', 'Subject', 'Status', 'Time', 'Teacher'])
    
    for record in records:
        subject = Subject.query.get(record.subject_id)
        teacher = User.query.get(record.marked_by) if record.marked_by else None
        
        cw.writerow([
            record.date.strftime('%Y-%m-%d'),
            subject.subject_name if subject else 'N/A',
            record.status,
            record.marked_at.strftime('%H:%M') if record.marked_at else '-',
            teacher.full_name if teacher else 'N/A'
        ])
        
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=attendance_report.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/api/student/today-classes')
@login_required
def student_today_classes():
    if current_user.role != 'student':
        return jsonify([])
    
    # Get student's class
    student_class = StudentClass.query.filter_by(student_id=current_user.id).first()
    if not student_class:
        return jsonify([])
    
    # Get today's date
    today = date.today()
    
    # Get subjects for today (this is simplified - you might want to add a schedule table)
    assignments = TeacherSubject.query.filter_by(class_id=student_class.class_id).all()
    
    result = []
    for assignment in assignments:
        # Check attendance for today
        attendance = Attendance.query.filter_by(
            student_id=current_user.id,
            subject_id=assignment.subject_id,
            class_id=assignment.class_id,
            date=today
        ).first()
        
        result.append({
            'subject_id': assignment.subject_id,
            'subject_name': assignment.subject.subject_name,
            'teacher_name': assignment.teacher.full_name if assignment.teacher else 'N/A',
            'time': '10:00 AM',  # This should come from a schedule table
            'room': 'Room 101',   # This should come from a schedule table
            'attendance_status': attendance.status if attendance else 'Not Marked'
        })
    
    return jsonify(result)

@app.route('/api/student/recent-attendance')
@login_required
def student_recent_attendance():
    if current_user.role != 'student':
        return jsonify([])
    
    attendance = Attendance.query.filter_by(student_id=current_user.id)\
        .order_by(Attendance.date.desc())\
        .limit(10)\
        .all()
    
    result = []
    for record in attendance:
        subject = Subject.query.get(record.subject_id)
        teacher = User.query.get(record.marked_by) if record.marked_by else None
        
        result.append({
            'date': record.date.strftime('%Y-%m-%d'),
            'subject_name': subject.subject_name if subject else 'N/A',
            'status': record.status,
            'teacher_name': teacher.full_name if teacher else 'N/A',
            'time': record.marked_at.strftime('%H:%M') if record.marked_at else '-'
        })
    
    return jsonify(result)

@app.route('/api/student/attendance-data')
@login_required
def student_attendance_data():
    if current_user.role != 'student':
        return jsonify({})
    
    month = request.args.get('month')
    subject_id = request.args.get('subject_id')
    status = request.args.get('status')
    
    # Build query
    query = Attendance.query.filter_by(student_id=current_user.id)
    
    if month:
        year, month_num = map(int, month.split('-'))
        query = query.filter(
            db.extract('year', Attendance.date) == year,
            db.extract('month', Attendance.date) == month_num
        )
    
    if subject_id:
        query = query.filter_by(subject_id=subject_id)
    
    if status:
        query = query.filter_by(status=status)
    
    attendance = query.order_by(Attendance.date.desc()).all()
    
    # Prepare summary
    summary = {
        'present': len([a for a in attendance if a.status == 'Present']),
        'absent': len([a for a in attendance if a.status == 'Absent']),
        'late': len([a for a in attendance if a.status == 'Late']),
        'total': len(attendance)
    }
    
    # Prepare calendar events
    calendar_events = []
    for record in attendance:
        subject = Subject.query.get(record.subject_id)
        calendar_events.append({
            'title': subject.subject_name if subject else 'Class',
            'start': record.date.isoformat(),
            'status': record.status
        })
    
    # Prepare table data
    table_data = []
    for record in attendance:
        subject = Subject.query.get(record.subject_id)
        teacher = User.query.get(record.marked_by) if record.marked_by else None
        
        table_data.append({
            'date': record.date.strftime('%Y-%m-%d'),
            'day': record.date.strftime('%A'),
            'subject': subject.subject_name if subject else 'N/A',
            'status': record.status,
            'time': record.marked_at.strftime('%H:%M') if record.marked_at else '-',
            'teacher': teacher.full_name if teacher else 'N/A'
        })
    
    # Prepare chart data (monthly trend)
    chart_data = {
        'labels': ['Week 1', 'Week 2', 'Week 3', 'Week 4'],
        'data': [85, 88, 92, 90]  # This should be calculated from actual data
    }
    
    return jsonify({
        'summary': summary,
        'calendar_events': calendar_events,
        'table_data': table_data,
        'chart_data': chart_data
    })

# Delete routes
@app.route('/admin/delete/course/<int:id>', methods=['DELETE'])
@login_required
def delete_course(id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'})
    
    course = Course.query.get_or_404(id)
    
    # Check if course has subjects
    # Cascade delete handles subjects automatically
    
    db.session.delete(course)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Course deleted successfully'})

@app.route('/admin/delete/subject/<int:id>', methods=['DELETE'])
@login_required
def delete_subject(id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'})
    
    subject = Subject.query.get_or_404(id)
    
    # Check if subject has attendance records
    # Cascade delete handles attendance automatically
    
    db.session.delete(subject)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Subject deleted successfully'})

@app.route('/admin/delete/class/<int:id>', methods=['DELETE'])
@login_required
def delete_class(id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'})
    
    class_obj = Class.query.get_or_404(id)
    
    # Check if class has students
    # Cascade delete handles student_classes automatically
    
    db.session.delete(class_obj)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Class deleted successfully'})

@app.route('/admin/delete/user/<int:id>', methods=['DELETE'])
@login_required
def delete_user(id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'})
    
    if id == current_user.id:
        return jsonify({'success': False, 'message': 'Cannot delete your own account'})
    
    user = User.query.get_or_404(id)
    
    try:
        # Avoid foreign key constraint on marked_by
        if user.role == 'teacher' or user.role == 'admin':
            Attendance.query.filter_by(marked_by=user.id).update({'marked_by': None})
            
        db.session.delete(user)
        db.session.commit()
        return jsonify({'success': True, 'message': 'User deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/admin/delete/assignment/<int:id>', methods=['DELETE'])
@login_required
def delete_assignment(id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'})
    
    assignment = TeacherSubject.query.get_or_404(id)
    
    db.session.delete(assignment)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Assignment deleted successfully'})

@app.route('/admin/schedule', methods=['GET', 'POST'])
@login_required
def manage_schedule():
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        class_id = request.form.get('class_id')
        subject_id = request.form.get('subject_id')
        day_of_week = request.form.get('day_of_week')
        start_time_str = request.form.get('start_time')
        end_time_str = request.form.get('end_time')
        room = request.form.get('room')
        
        try:
            # Parse time "HH:MM"
            start_time = datetime.strptime(start_time_str, '%H:%M').time()
            end_time = datetime.strptime(end_time_str, '%H:%M').time()
            
            schedule = Schedule(
                class_id=class_id,
                subject_id=subject_id,
                day_of_week=day_of_week,
                start_time=start_time,
                end_time=end_time,
                room=room
            )
            db.session.add(schedule)
            db.session.commit()
            flash('Schedule added successfully!', 'success')
        except ValueError:
             flash('Invalid time format.', 'danger')
        except Exception as e:
             db.session.rollback()
             flash(f'Error adding schedule: {str(e)}', 'danger')
             
        return redirect(url_for('manage_schedule'))
    
    classes = Class.query.order_by(Class.class_name).all()
    subjects = Subject.query.order_by(Subject.subject_name).all()
    
    # Get all schedules with related data
    schedules = Schedule.query.join(Class).join(Subject).order_by(
        Class.class_name, 
        Schedule.day_of_week, 
        Schedule.start_time
    ).all()
    
    # Helper to sort days
    days_order = {
        'Monday': 1, 'Tuesday': 2, 'Wednesday': 3, 'Thursday': 4, 
        'Friday': 5, 'Saturday': 6, 'Sunday': 7
    }
    schedules.sort(key=lambda x: (x.class_info.class_name, days_order.get(x.day_of_week, 8), x.start_time))
    
    return render_template('admin/schedule.html', classes=classes, subjects=subjects, schedules=schedules)

@app.route('/admin/schedule/delete/<int:id>', methods=['DELETE'])
@login_required
def delete_schedule(id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied'})
    
    schedule = Schedule.query.get_or_404(id)
    try:
        db.session.delete(schedule)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Schedule deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)})
    
if __name__ == '__main__':
    app.run(debug=True)