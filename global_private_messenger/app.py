
import os
import eventlet
eventlet.monkey_patch()

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit, join_room
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-123')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///messenger.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    display_name = db.Column(db.String(64), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'display_name': self.display_name,
            'is_online': self.is_online()
        }

    def is_online(self):
        return self.last_seen and (datetime.utcnow() - self.last_seen) < timedelta(minutes=5)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    sender = db.relationship('User', foreign_keys=[sender_id], backref='sent_messages')
    receiver = db.relationship('User', foreign_keys=[receiver_id], backref='received_messages')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('chat'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            user.last_seen = datetime.utcnow()
            db.session.commit()
            flash('با موفقیت وارد شدید!', 'success')
            return redirect(url_for('chat'))
        else:
            flash('نام کاربری یا رمز عبور نامعتبر است', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('با موفقیت خارج شدید!', 'success')
    return redirect(url_for('login'))

@app.route('/chat')
@login_required
def chat():
    users = User.query.filter(User.id != current_user.id).all()
    return render_template('chat.html', users=users)

@app.route('/api/users')
@login_required
def get_users():
    users = User.query.filter(User.id != current_user.id).all()
    return jsonify([user.to_dict() for user in users])

@app.route('/api/messages/<int:user_id>')
@login_required
def get_messages(user_id):
    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == user_id)) |
        ((Message.sender_id == user_id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.created_at.asc()).all()
    
    messages_data = []
    for msg in messages:
        messages_data.append({
            'id': msg.id,
            'content': msg.content,
            'sender_id': msg.sender_id,
            'receiver_id': msg.receiver_id,
            'created_at': msg.created_at.isoformat(),
            'sender_name': msg.sender.display_name
        })
    
    return jsonify(messages_data)

@app.route('/api/send_message', methods=['POST'])
@login_required
def send_message():
    data = request.get_json()
    message = Message(
        content=data['content'],
        sender_id=current_user.id,
        receiver_id=data.get('receiver_id')
    )
    
    db.session.add(message)
    db.session.commit()
    
    socketio.emit('new_message', {
        'id': message.id,
        'content': message.content,
        'sender_id': message.sender_id,
        'receiver_id': message.receiver_id,
        'sender_name': current_user.display_name,
        'created_at': message.created_at.isoformat()
    }, room=f'user_{message.receiver_id}')
    
    return jsonify({'success': True})

@socketio.on('connect')
@login_required
def handle_connect():
    join_room(f'user_{current_user.id}')
    current_user.last_seen = datetime.utcnow()
    db.session.commit()
    emit('user_online', {'user_id': current_user.id}, broadcast=True)

@socketio.on('disconnect')
@login_required
def handle_disconnect():
    current_user.last_seen = datetime.utcnow()
    db.session.commit()
    emit('user_offline', {'user_id': current_user.id}, broadcast=True)

@socketio.on('send_message')
@login_required
def handle_send_message(data):
    message = Message(
        content=data['content'],
        sender_id=current_user.id,
        receiver_id=data.get('receiver_id')
    )
    
    db.session.add(message)
    db.session.commit()
    
    emit('new_message', {
        'id': message.id,
        'content': message.content,
        'sender_id': message.sender_id,
        'receiver_id': message.receiver_id,
        'sender_name': current_user.display_name,
        'created_at': message.created_at.isoformat()
    }, room=f'user_{message.receiver_id}')
    
    emit('new_message', {
        'id': message.id,
        'content': message.content,
        'sender_id': message.sender_id,
        'receiver_id': message.receiver_id,
        'sender_name': current_user.display_name,
        'created_at': message.created_at.isoformat()
    }, room=f'user_{current_user.id}')

@socketio.on('typing_start')
@login_required
def handle_typing_start(data):
    emit('user_typing', {
        'user_id': current_user.id,
        'username': current_user.username,
        'typing': True
    }, room=f'user_{data["receiver_id"]}')

@socketio.on('typing_stop')
@login_required
def handle_typing_stop(data):
    emit('user_typing', {
        'user_id': current_user.id,
        'username': current_user.username,
        'typing': False
    }, room=f'user_{data["receiver_id"]}')

def init_db():
    with app.app_context():
        db.create_all()
        
        if not User.query.filter_by(username='admin').first():
            admin = User(username='admin', display_name='مدیر سیستم', is_admin=True)
            admin.set_password('admin123')
            db.session.add(admin)
            
        if not User.query.filter_by(username='user1').first():
            user1 = User(username='user1', display_name='کاربر تست ۱')
            user1.set_password('user123')
            db.session.add(user1)
            
        if not User.query.filter_by(username='user2').first():
            user2 = User(username='user2', display_name='کاربر تست ۲')
            user2.set_password('user123')
            db.session.add(user2)
            
        db.session.commit()
        print("✅ کاربران پیش‌فرض ایجاد شدند")

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
