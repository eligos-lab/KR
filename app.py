from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os

# Инициализация приложения
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Инициализация расширений
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Декоратор для проверки прав администратора
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.group != 'admin':
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# Модели данных
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    group = db.Column(db.String(20), nullable=False, default='student')
    password_hash = db.Column(db.String(120), nullable=False)
    grades = db.relationship('Grade', backref='user', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.username}>'

class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    grades = db.relationship('Grade', backref='subject', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Subject {self.title}>'

class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subject.id'), nullable=False)

    def __repr__(self):
        return f'<Grade {self.value} for user {self.user_id} in subject {self.subject_id}>'

# Загрузчик пользователя
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Обработчики маршрутов
@app.route('/')
def index():
    subjects = Subject.query.order_by(Subject.title).all()
    return render_template('index.html', subjects=subjects)

@app.route('/subject/<int:subject_id>')
@login_required
def subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    
    if current_user.group == 'admin':
        grades = Grade.query.filter_by(subject_id=subject_id).join(User).order_by(User.username).all()
        users = User.query.filter(User.group != 'admin').order_by(User.username).all()
    else:
        grades = Grade.query.filter_by(subject_id=subject_id, user_id=current_user.id).all()
        users = []
    
    return render_template('subject.html', subject=subject, grades=grades, users=users)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        
        flash('Неверное имя пользователя или пароль', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/add_grade/<int:subject_id>', methods=['POST'])
@login_required
@admin_required
def add_grade(subject_id):
    try:
        user_id = request.form.get('user_id')
        value = float(request.form.get('value'))
        
        if not (0 <= value <= 100):
            raise ValueError("Оценка должна быть между 0 и 100")
        
        grade = Grade(value=value, user_id=user_id, subject_id=subject_id)
        db.session.add(grade)
        db.session.commit()
        flash('Оценка успешно добавлена', 'success')
    except ValueError as e:
        flash(str(e), 'danger')
    except Exception:
        flash('Произошла ошибка при добавлении оценки', 'danger')
        db.session.rollback()
    
    return redirect(url_for('subject', subject_id=subject_id))

@app.route('/add_subject', methods=['GET', 'POST'])
@login_required
@admin_required
def add_subject():
    if request.method == 'POST':
        title = request.form.get('title').strip()
        description = request.form.get('description').strip()
        
        if not title:
            flash('Название предмета обязательно', 'danger')
        else:
            subject = Subject(title=title, description=description)
            db.session.add(subject)
            db.session.commit()
            flash('Предмет успешно добавлен', 'success')
            return redirect(url_for('index'))
    
    return render_template('add_subject.html')

@app.route('/edit_subject/<int:subject_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    
    if request.method == 'POST':
        title = request.form.get('title').strip()
        description = request.form.get('description').strip()
        
        if not title:
            flash('Название предмета обязательно', 'danger')
        else:
            subject.title = title
            subject.description = description
            db.session.commit()
            flash('Предмет успешно обновлен', 'success')
            return redirect(url_for('index'))
    
    return render_template('edit_subject.html', subject=subject)

@app.route('/delete_subject/<int:subject_id>', methods=['POST'])
@login_required
@admin_required
def delete_subject(subject_id):
    subject = Subject.query.get_or_404(subject_id)
    db.session.delete(subject)
    db.session.commit()
    flash('Предмет успешно удален', 'success')
    return redirect(url_for('index'))

@app.route('/users')
@login_required
@admin_required
def users():
    users_list = User.query.filter(User.group != 'admin').order_by(User.username).all()
    return render_template('users.html', users=users_list)

@app.route('/add_user', methods=['GET', 'POST'])
@login_required
@admin_required
def add_user():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        group = request.form.get('group')
        
        if not username or not password:
            flash('Имя пользователя и пароль обязательны', 'danger')
        elif User.query.filter_by(username=username).first():
            flash('Пользователь с таким именем уже существует', 'danger')
        else:
            user = User(
                username=username,
                group=group,
                password_hash=generate_password_hash(password)
            )
            db.session.add(user)
            db.session.commit()
            flash('Пользователь успешно добавлен', 'success')
            return redirect(url_for('users'))
    
    return render_template('add_user.html')

@app.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.group == 'admin':
        flash('Нельзя редактировать администратора', 'danger')
        return redirect(url_for('users'))
    
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        group = request.form.get('group')
        
        if not username:
            flash('Имя пользователя обязательно', 'danger')
        else:
            user.username = username
            if password:
                user.password_hash = generate_password_hash(password)
            user.group = group
            db.session.commit()
            flash('Пользователь успешно обновлен', 'success')
            return redirect(url_for('users'))
    
    return render_template('edit_user.html', user=user)

@app.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.group == 'admin':
        flash('Нельзя удалить администратора', 'danger')
    else:
        db.session.delete(user)
        db.session.commit()
        flash('Пользователь успешно удален', 'success')
    
    return redirect(url_for('users'))

# Обработчики ошибок
@app.errorhandler(403)
def forbidden(error):
    return render_template('403.html'), 403

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

# Инициализация базы данных
def init_db():
    with app.app_context():
        db.create_all()
        # Создаем админа, если его еще нет
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                group='admin',
                password_hash=generate_password_hash(os.environ.get('ADMIN_PASSWORD') or 'admin')
            )
            db.session.add(admin)
            db.session.commit()

if __name__ == '__main__':
    init_db()
    app.run(debug=True)