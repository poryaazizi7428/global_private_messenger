# فایل create_render_messenger.py را ذخیره کنید
import os

def create_render_ready_project():
    project_files = {
        'app.py': '''
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
''',

        'requirements.txt': '''
flask==2.3.3
flask-socketio==5.3.6
flask-sqlalchemy==3.0.5
flask-login==0.6.3
werkzeug==2.3.7
python-dotenv==1.0.0
eventlet==0.33.3
gunicorn==21.2.0
psycopg2-binary==2.9.7
''',

        'render.yaml': '''
services:
  - type: web
    name: private-messenger
    env: python
    plan: free
    region: ohio
    buildCommand: pip install -r requirements.txt
    startCommand: python app.py
    envVars:
      - key: SECRET_KEY
        generateValue: true
      - key: DATABASE_URL
        fromDatabase:
          name: messenger-db
          type: postgresql
''',

        'templates/login.html': '''
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ورود - پیام‌رسان</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }
        .login-container {
            background: white;
            padding: 40px;
            border-radius: 15px;
            box-shadow: 0 15px 35px rgba(0,0,0,0.1);
            width: 100%;
            max-width: 400px;
        }
        .login-header {
            text-align: center;
            margin-bottom: 30px;
        }
        .login-header h1 {
            color: #333;
            margin-bottom: 10px;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-group label {
            display: block;
            margin-bottom: 5px;
            color: #333;
            font-weight: 500;
        }
        .form-group input {
            width: 100%;
            padding: 12px;
            border: 1px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
        }
        .btn {
            width: 100%;
            padding: 12px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            cursor: pointer;
        }
        .btn:hover { background: #5a6fd8; }
        .demo-accounts {
            margin-top: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            font-size: 12px;
        }
        .flash-message {
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 15px;
            text-align: center;
        }
        .success { background: #d4edda; color: #155724; }
        .error { background: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-header">
            <h1>💬 پیام‌رسان خصوصی</h1>
            <p>لطفا وارد حساب کاربری خود شوید</p>
        </div>
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="flash-message {{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <form method="POST">
            <div class="form-group">
                <label for="username">نام کاربری:</label>
                <input type="text" id="username" name="username" required>
            </div>
            <div class="form-group">
                <label for="password">رمز عبور:</label>
                <input type="password" id="password" name="password" required>
            </div>
            <button type="submit" class="btn">ورود به چت</button>
        </form>
        
        <div class="demo-accounts">
            <h3>حساب‌های آزمایشی:</h3>
            <div>👤 مدیر سیستم: admin / admin123</div>
            <div>👤 کاربر تست ۱: user1 / user123</div>
            <div>👤 کاربر تست ۲: user2 / user123</div>
        </div>
    </div>
</body>
</html>
''',

        'templates/chat.html': '''
<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>چت - پیام‌رسان</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f0f2f5;
            height: 100vh;
            overflow: hidden;
        }
        .chat-container {
            display: flex;
            height: 100vh;
        }
        .sidebar {
            width: 350px;
            background: white;
            border-left: 1px solid #e0e0e0;
            display: flex;
            flex-direction: column;
        }
        .sidebar-header {
            padding: 20px;
            background: #667eea;
            color: white;
        }
        .contacts-list {
            flex: 1;
            overflow-y: auto;
        }
        .contact-item {
            padding: 15px 20px;
            border-bottom: 1px solid #f0f0f0;
            cursor: pointer;
            transition: background 0.2s;
        }
        .contact-item:hover { background: #f8f9fa; }
        .contact-item.active { background: #e3f2fd; }
        .chat-area {
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        .chat-header {
            padding: 20px;
            background: white;
            border-bottom: 1px solid #e0e0e0;
        }
        .chat-messages {
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            background: #fafafa;
        }
        .message {
            margin-bottom: 15px;
            max-width: 70%;
        }
        .message.own { margin-right: auto; }
        .message.other { margin-left: auto; }
        .message-bubble {
            padding: 12px 16px;
            border-radius: 18px;
            background: white;
            box-shadow: 0 1px 2px rgba(0,0,0,0.1);
        }
        .message.own .message-bubble {
            background: #667eea;
            color: white;
        }
        .chat-input {
            padding: 20px;
            background: white;
            border-top: 1px solid #e0e0e0;
        }
        .message-form {
            display: flex;
            gap: 10px;
        }
        .message-input {
            flex: 1;
            padding: 12px;
            border: 1px solid #e0e0e0;
            border-radius: 24px;
            font-size: 14px;
        }
        .send-btn {
            padding: 12px 24px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 24px;
            cursor: pointer;
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <div class="sidebar">
            <div class="sidebar-header">
                <h3>💬 پیام‌رسان</h3>
                <p>کاربر: {{ current_user.display_name }}</p>
                <a href="/logout" style="color: white; font-size: 12px;">خروج</a>
            </div>
            <div class="contacts-list" id="contacts-list">
                {% for user in users %}
                <div class="contact-item" onclick="selectUser({{ user.id }}, '{{ user.display_name }}')">
                    <strong>{{ user.display_name }}</strong>
                    <div style="font-size: 12px; color: #666;">
                        {% if user.is_online() %}🟢 آنلاین{% else %}🔴 آفلاین{% endif %}
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        
        <div class="chat-area">
            <div class="chat-header">
                <h3 id="current-chat-name">انتخاب مخاطب</h3>
                <div id="current-chat-status">یک مخاطب را انتخاب کنید</div>
            </div>
            
            <div class="chat-messages" id="messages-container">
                <div style="text-align: center; color: #666; margin-top: 50px;">
                    <div style="font-size: 48px; margin-bottom: 20px;">💬</div>
                    <div>برای شروع چت، یک مخاطب از لیست سمت چپ انتخاب کنید</div>
                </div>
            </div>
            
            <div class="chat-input">
                <form class="message-form" id="message-form">
                    <input type="text" class="message-input" id="message-input" placeholder="پیام خود را بنویسید..." disabled>
                    <button type="submit" class="send-btn" disabled>ارسال</button>
                </form>
            </div>
        </div>
    </div>

    <script>
        const socket = io();
        let currentUserId = null;
        
        socket.on('new_message', function(data) {
            if (data.receiver_id === currentUserId || data.sender_id === currentUserId) {
                displayMessage(data);
            }
        });
        
        socket.on('user_typing', function(data) {
            // نمایش وضعیت تایپ
            console.log('User typing:', data);
        });
        
        document.getElementById('message-form').addEventListener('submit', function(e) {
            e.preventDefault();
            sendMessage();
        });
        
        function selectUser(userId, userName) {
            currentUserId = userId;
            document.getElementById('current-chat-name').textContent = userName;
            document.getElementById('current-chat-status').textContent = 'آنلاین';
            document.getElementById('message-input').disabled = false;
            document.querySelector('.send-btn').disabled = false;
            loadMessages(userId);
        }
        
        function loadMessages(userId) {
            fetch(`/api/messages/${userId}`)
                .then(response => response.json())
                .then(messages => {
                    const container = document.getElementById('messages-container');
                    container.innerHTML = '';
                    messages.forEach(msg => displayMessage(msg));
                    container.scrollTop = container.scrollHeight;
                });
        }
        
        function displayMessage(msg) {
            const container = document.getElementById('messages-container');
            const messageDiv = document.createElement('div');
            messageDiv.className = `message ${msg.sender_id === {{ current_user.id }} ? 'own' : 'other'}`;
            
            messageDiv.innerHTML = `
                <div class="message-bubble">
                    <div>${msg.content}</div>
                    <div style="font-size: 11px; color: #999; margin-top: 5px;">
                        ${new Date(msg.created_at).toLocaleTimeString('fa-IR')}
                    </div>
                </div>
            `;
            
            container.appendChild(messageDiv);
            container.scrollTop = container.scrollHeight;
        }
        
        function sendMessage() {
            const input = document.getElementById('message-input');
            const content = input.value.trim();
            
            if (content && currentUserId) {
                socket.emit('send_message', {
                    content: content,
                    receiver_id: currentUserId
                });
                
                input.value = '';
            }
        }
        
        // فعال کردن ارسال با Enter
        document.getElementById('message-input').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                sendMessage();
            }
        });
    </script>
</body>
</html>
'''
    }

    # ایجاد پوشه‌ها
    os.makedirs('templates', exist_ok=True)
    
    # ایجاد فایل‌ها
    for filename, content in project_files.items():
        if filename.startswith('templates/'):
            template_name = filename.split('/')[1]
            with open(f'templates/{template_name}', 'w', encoding='utf-8') as f:
                f.write(content)
        else:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(content)
    
    print("✅ پروژه آماده استقرار روی Render ایجاد شد!")

if __name__ == '__main__':
    create_render_ready_project()
