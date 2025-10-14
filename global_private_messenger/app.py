"""
Web Messenger Application - Complete Implementation
A Telegram-like web messenger with Flask, SQLAlchemy, and WebSocket support
"""

import os
import json
import sqlite3
from datetime import datetime
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import jwt
from flask import Flask, render_template, request, jsonify, send_from_directory, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_socketio import SocketIO, emit, join_room, leave_room, rooms
import secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///messenger.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
app.config['UPLOAD_FOLDER'] = 'uploads'

# Create upload folder
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize extensions
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
socketio = SocketIO(app, cors_allowed_origins="*")
CORS(app)

# Allowed file extensions
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'zip', 'rar', 'mp3', 'mp4', 'avi', 'mov'}

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120), default='')
    bio = db.Column(db.String(500), default='')
    avatar = db.Column(db.String(255), default='')
    status = db.Column(db.String(50), default='offline')  # online, offline, away
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    
    messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy='dynamic')
    conversations = db.relationship('Conversation', secondary='conversation_users', backref=db.backref('members', lazy='dynamic'))
    contacts = db.relationship('Contact', foreign_keys='Contact.user_id', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self, include_email=False):
        data = {
            'id': self.id,
            'username': self.username,
            'display_name': self.display_name,
            'bio': self.bio,
            'avatar': self.avatar,
            'status': self.status,
            'last_seen': self.last_seen.isoformat()
        }
        if include_email:
            data['email'] = self.email
        return data

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    description = db.Column(db.String(500))
    is_group = db.Column(db.Boolean, default=False)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    icon = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    messages = db.relationship('Message', backref='conversation', lazy='dynamic', cascade='all, delete-orphan')
    creator = db.relationship('User', foreign_keys=[creator_id], backref='created_conversations')
    
    def to_dict(self, include_messages=False):
        data = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'is_group': self.is_group,
            'creator_id': self.creator_id,
            'icon': self.icon,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'members_count': len(self.members.all()),
            'members': [member.to_dict() for member in self.members.all()]
        }
        if include_messages:
            data['messages'] = [msg.to_dict() for msg in self.messages.order_by(Message.created_at).all()]
        return data

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False, index=True)
    message_type = db.Column(db.String(50), default='text')  # text, image, file, video, audio
    file_url = db.Column(db.String(255))
    file_name = db.Column(db.String(255))
    file_size = db.Column(db.Integer)
    is_edited = db.Column(db.Boolean, default=False)
    is_deleted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    edited_at = db.Column(db.DateTime)
    
    reactions = db.relationship('Reaction', backref='message', lazy='dynamic', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'content': self.content,
            'sender': self.sender.to_dict(),
            'conversation_id': self.conversation_id,
            'message_type': self.message_type,
            'file_url': self.file_url,
            'file_name': self.file_name,
            'file_size': self.file_size,
            'is_edited': self.is_edited,
            'is_deleted': self.is_deleted,
            'created_at': self.created_at.isoformat(),
            'edited_at': self.edited_at.isoformat() if self.edited_at else None,
            'reactions': {r.emoji: r.count for r in self.reactions.all()}
        }

class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    contact_name = db.Column(db.String(120), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    contact = db.relationship('User', foreign_keys=[contact_id], backref='contacts_with_me')

class Reaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('message.id'), nullable=False)
    emoji = db.Column(db.String(10), nullable=False)
    count = db.Column(db.Integer, default=1)

# Association table for conversation members
conversation_users = db.Table('conversation_users',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('conversation_id', db.Integer, db.ForeignKey('conversation.id'), primary_key=True)
)

# Login Manager
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Utility Functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_jwt_token(user_id):
    return jwt.encode({'user_id': user_id, 'exp': datetime.utcnow().timestamp() + 86400}, 
                     app.config['SECRET_KEY'], algorithm='HS256')

# Routes - Authentication
@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    
    if not data or not all(k in data for k in ['username', 'email', 'password']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already exists'}), 409
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already exists'}), 409
    
    user = User(
        username=data['username'],
        email=data['email'],
        display_name=data.get('display_name', data['username'])
    )
    user.set_password(data['password'])
    
    db.session.add(user)
    db.session.commit()
    
    login_user(user)
    return jsonify({
        'message': 'Registration successful',
        'user': user.to_dict(include_email=True),
        'token': get_jwt_token(user.id)
    }), 201

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if not data or not all(k in data for k in ['username', 'password']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    user = User.query.filter_by(username=data['username']).first()
    
    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Invalid credentials'}), 401
    
    login_user(user)
    return jsonify({
        'message': 'Login successful',
        'user': user.to_dict(include_email=True),
        'token': get_jwt_token(user.id)
    }), 200

@app.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return jsonify({'message': 'Logout successful'}), 200

@app.route('/api/auth/me', methods=['GET'])
@login_required
def get_current_user():
    return jsonify(current_user.to_dict(include_email=True)), 200

# Routes - Users
@app.route('/api/users/<username>', methods=['GET'])
def get_user(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    return jsonify(user.to_dict()), 200

@app.route('/api/users/search/<query>', methods=['GET'])
@login_required
def search_users(query):
    users = User.query.filter(
        (User.username.ilike(f'%{query}%')) | 
        (User.display_name.ilike(f'%{query}%'))
    ).limit(20).all()
    return jsonify([user.to_dict() for user in users]), 200

@app.route('/api/users/<user_id>/profile', methods=['PUT'])
@login_required
def update_profile(user_id):
    if current_user.id != int(user_id):
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    
    current_user.display_name = data.get('display_name', current_user.display_name)
    current_user.bio = data.get('bio', current_user.bio)
    current_user.status = data.get('status', current_user.status)
    
    db.session.commit()
    return jsonify(current_user.to_dict(include_email=True)), 200

@app.route('/api/users/<user_id>/avatar', methods=['POST'])
@login_required
def upload_avatar(user_id):
    if current_user.id != int(user_id):
        return jsonify({'error': 'Unauthorized'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        filename = f"avatar_{user_id}_{secrets.token_hex(8)}.{file.filename.rsplit('.', 1)[1].lower()}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        current_user.avatar = f'/uploads/{filename}'
        db.session.commit()
        return jsonify({'avatar_url': current_user.avatar}), 200
    
    return jsonify({'error': 'Invalid file type'}), 400

# Routes - Conversations
@app.route('/api/conversations', methods=['GET'])
@login_required
def get_conversations():
    conversations = current_user.conversations.all()
    return jsonify([conv.to_dict() for conv in conversations]), 200

@app.route('/api/conversations', methods=['POST'])
@login_required
def create_conversation():
    data = request.get_json()
    
    if not data or 'title' not in data:
        return jsonify({'error': 'Title is required'}), 400
    
    conversation = Conversation(
        title=data['title'],
        description=data.get('description', ''),
        is_group=data.get('is_group', False),
        creator_id=current_user.id
    )
    
    db.session.add(conversation)
    db.session.flush()
    
    conversation.members.append(current_user)
    
    if 'members' in data:
        for member_id in data['members']:
            member = User.query.get(member_id)
            if member:
                conversation.members.append(member)
    
    db.session.commit()
    return jsonify(conversation.to_dict()), 201

@app.route('/api/conversations/<conv_id>', methods=['GET'])
@login_required
def get_conversation(conv_id):
    conversation = Conversation.query.get(conv_id)
    if not conversation or current_user not in conversation.members.all():
        return jsonify({'error': 'Conversation not found'}), 404
    
    return jsonify(conversation.to_dict(include_messages=True)), 200

@app.route('/api/conversations/<conv_id>', methods=['PUT'])
@login_required
def update_conversation(conv_id):
    conversation = Conversation.query.get(conv_id)
    if not conversation or conversation.creator_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    conversation.title = data.get('title', conversation.title)
    conversation.description = data.get('description', conversation.description)
    conversation.updated_at = datetime.utcnow()
    
    db.session.commit()
    return jsonify(conversation.to_dict()), 200

@app.route('/api/conversations/<conv_id>/members', methods=['POST'])
@login_required
def add_member(conv_id):
    conversation = Conversation.query.get(conv_id)
    if not conversation or current_user not in conversation.members.all():
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    user = User.query.get(data.get('user_id'))
    
    if user and user not in conversation.members.all():
        conversation.members.append(user)
        db.session.commit()
        return jsonify(conversation.to_dict()), 200
    
    return jsonify({'error': 'User not found or already member'}), 400

@app.route('/api/conversations/<conv_id>/members/<member_id>', methods=['DELETE'])
@login_required
def remove_member(conv_id, member_id):
    conversation = Conversation.query.get(conv_id)
    if not conversation or (conversation.creator_id != current_user.id and int(member_id) != current_user.id):
        return jsonify({'error': 'Unauthorized'}), 403
    
    member = User.query.get(member_id)
    if member in conversation.members.all():
        conversation.members.remove(member)
        db.session.commit()
        return jsonify({'message': 'Member removed'}), 200
    
    return jsonify({'error': 'Member not found'}), 404

# Routes - Messages
@app.route('/api/conversations/<conv_id>/messages', methods=['GET'])
@login_required
def get_messages(conv_id):
    conversation = Conversation.query.get(conv_id)
    if not conversation or current_user not in conversation.members.all():
        return jsonify({'error': 'Unauthorized'}), 403
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    messages = conversation.messages.order_by(Message.created_at.desc()).paginate(page=page, per_page=per_page)
    
    return jsonify({
        'messages': [msg.to_dict() for msg in reversed(messages.items)],
        'total': messages.total,
        'pages': messages.pages,
        'current_page': page
    }), 200

@app.route('/api/conversations/<conv_id>/messages', methods=['POST'])
@login_required
def send_message(conv_id):
    conversation = Conversation.query.get(conv_id)
    if not conversation or current_user not in conversation.members.all():
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    
    if not data or 'content' not in data:
        return jsonify({'error': 'Content is required'}), 400
    
    message = Message(
        content=data['content'],
        sender_id=current_user.id,
        conversation_id=conv_id,
        message_type=data.get('message_type', 'text')
    )
    
    db.session.add(message)
    db.session.commit()
    
    socketio.emit('new_message', message.to_dict(), room=f'conv_{conv_id}')
    
    return jsonify(message.to_dict()), 201

@app.route('/api/messages/<msg_id>/file', methods=['POST'])
@login_required
def upload_file(msg_id):
    message = Message.query.get(msg_id)
    if not message or message.sender_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file and allowed_file(file.filename):
        filename = f"{msg_id}_{secrets.token_hex(8)}_{secure_filename(file.filename)}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        message.file_url = f'/uploads/{filename}'
        message.file_name = file.filename
        message.file_size = os.path.getsize(filepath)
        message.message_type = 'file'
        
        db.session.commit()
        return jsonify(message.to_dict()), 200
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/api/messages/<msg_id>', methods=['PUT'])
@login_required
def edit_message(msg_id):
    message = Message.query.get(msg_id)
    if not message or message.sender_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    data = request.get_json()
    message.content = data.get('content', message.content)
    message.is_edited = True
    message.edited_at = datetime.utcnow()
    
    db.session.commit()
    
    socketio.emit('message_edited', message.to_dict(), room=f'conv_{message.conversation_id}')
    
    return jsonify(message.to_dict()), 200

@app.route('/api/messages/<msg_id>', methods=['DELETE'])
@login_required
def delete_message(msg_id):
    message = Message.query.get(msg_id)
    if not message or message.sender_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    message.is_deleted = True
    message.content = ''
    
    db.session.commit()
    
    socketio.emit('message_deleted', {'message_id': msg_id}, room=f'conv_{message.conversation_id}')
    
    return jsonify({'message': 'Message deleted'}), 200

@app.route('/api/messages/<msg_id>/react', methods=['POST'])
@login_required
def add_reaction(msg_id):
    message = Message.query.get(msg_id)
    if not message:
        return jsonify({'error': 'Message not found'}), 404
    
    data = request.get_json()
    emoji = data.get('emoji')
    
    reaction = Reaction.query.filter_by(message_id=msg_id, emoji=emoji).first()
    if reaction:
        reaction.count += 1
    else:
        reaction = Reaction(message_id=msg_id, emoji=emoji, count=1)
        db.session.add(reaction)
    
    db.session.commit()
    
    socketio.emit('message_reacted', message.to_dict(), room=f'conv_{message.conversation_id}')
    
    return jsonify(message.to_dict()), 200

# Routes - File serving
@app.route('/uploads/<filename>', methods=['GET'])
def download_file(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except:
        return jsonify({'error': 'File not found'}), 404

# Routes - Contacts
@app.route('/api/contacts', methods=['GET'])
@login_required
def get_contacts():
    contacts = Contact.query.filter_by(user_id=current_user.id).all()
    return jsonify([{
        'id': c.contact_id,
        'name': c.contact_name,
        'user': c.contact.to_dict()
    } for c in contacts]), 200

@app.route('/api/contacts', methods=['POST'])
@login_required
def add_contact():
    data = request.get_json()
    contact_id = data.get('contact_id')
    
    if not contact_id or User.query.get(contact_id) is None:
        return jsonify({'error': 'Invalid contact'}), 400
    
    contact = Contact(
        user_id=current_user.id,
        contact_id=contact_id,
        contact_name=data.get('contact_name', '')
    )
    
    db.session.add(contact)
    db.session.commit()
    
    return jsonify({'message': 'Contact added'}), 201

@app.route('/api/contacts/<contact_id>', methods=['DELETE'])
@login_required
def delete_contact(contact_id):
    contact = Contact.query.filter_by(user_id=current_user.id, contact_id=contact_id).first()
    if not contact:
        return jsonify({'error': 'Contact not found'}), 404
    
    db.session.delete(contact)
    db.session.commit()
    
    return jsonify({'message': 'Contact deleted'}), 200

# WebSocket Events
@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        current_user.status = 'online'
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
        emit('status_changed', {'user_id': current_user.id, 'status': 'online'}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    if current_user.is_authenticated:
        current_user.status = 'offline'
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
        emit('status_changed', {'user_id': current_user.id, 'status': 'offline'}, broadcast=True)

@socketio.on('join_conversation')
def on_join(data):
    if current_user.is_authenticated:
        conv_id = data.get('conversation_id')
        room = f'conv_{conv_id}'
        join_room(room)
        emit('user_joined', {'user': current_user.to_dict()}, room=room)

@socketio.on('leave_conversation')
def on_leave(data):
    if current_user.is_authenticated:
        conv_id = data.get('conversation_id')
        room = f'conv_{conv_id}'
        leave_room(room)
        emit('user_left', {'user_id': current_user.id}, room=room)

@socketio.on('typing')
def handle_typing(data):
    if current_user.is_authenticated:
        conv_id = data.get('conversation_id')
        room = f'conv_{conv_id}'
        emit('user_typing', {
            'user_id': current_user.id,
            'username': current_user.username
        }, room=room, skip_sid=True)

@socketio.on('stop_typing')
def handle_stop_typing(data):
    if current_user.is_authenticated:
        conv_id = data.get('conversation_id')
        room = f'conv_{conv_id}'
        emit('user_stop_typing', {
            'user_id': current_user.id
        }, room=room, skip_sid=True)

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500

# Frontend routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat/<conv_id>')
def chat(conv_id):
    return render_template('chat.html', conversation_id=conv_id)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
