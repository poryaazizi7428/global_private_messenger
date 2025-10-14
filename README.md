# Web Messenger - Complete System

A Telegram-like web messaging application built with Flask, SQLAlchemy, and WebSocket support.

## Features

### Core Messaging
- ? Real-time messaging with WebSocket
- ? Text messages with typing indicators
- ? File uploads and sharing (50MB max)
- ? Message editing and deletion
- ? Emoji reactions on messages
- ? Read receipts and message timestamps

### User Features
- ? User authentication (register/login)
- ? User profiles with avatar upload
- ? Display name and bio
- ? Online/offline status
- ? User search functionality
- ? Contact management

### Conversation Features
- ? One-on-one private messages
- ? Group conversations
- ? Create/update/delete conversations
- ? Add/remove members
- ? Conversation search
- ? Real-time member updates

### UI/UX Features
- ? Modern Telegram-like interface
- ? Dark mode support
- ? Responsive design (mobile, tablet, desktop)
- ? Toast notifications
- ? Context menus for messages
- ? Emoji picker
- ? File preview before sending
- ? Real-time conversation list updates

## Installation

### Prerequisites
- Python 3.8+
- pip (Python package manager)
- Node.js (optional, for frontend build tools)

### Local Setup

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/web-messenger.git
cd web-messenger
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Create .env file**
```bash
cp .env.example .env
# Edit .env and set your configuration
```

5. **Initialize database**
```bash
python
>>> from app import app, db
>>> with app.app_context():
>>>     db.create_all()
>>> exit()
```

6. **Run the application**
```bash
python app.py
```

The application will be available at `http://localhost:5000`

## Deployment on Render

### Steps:

1. **Push to GitHub**
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/yourusername/web-messenger.git
git push -u origin main
```

2. **Create New Web Service on Render**
- Go to https://render.com
- Click "New" ? "Web Service"
- Connect your GitHub repository
- Select the repository

3. **Configure Build Settings**
- **Name**: web-messenger
- **Environment**: Python 3
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn app:app`

4. **Set Environment Variables**
- Add in Render dashboard:
  - `FLASK_ENV`: production
  - `SECRET_KEY`: (generate a random secret key)
  - `DATABASE_URL`: (use PostgreSQL if available, otherwise SQLite)

5. **Deploy**
- Click "Create Web Service"
- Wait for build and deployment

### PostgreSQL Setup (Recommended for Production)

1. Create PostgreSQL database on Render or use external service
2. Update `DATABASE_URL` in environment variables:
```
postgresql://username:password@host:port/database_name
```

## Project Structure

```
web-messenger/
+-- app.py                      # Main Flask application
+-- requirements.txt            # Python dependencies
+-- .env.example                # Environment variables template
+-- .gitignore                  # Git ignore rules
+-- README.md                   # Documentation
¦
+-- templates/
¦   +-- base.html              # Base template
¦   +-- index.html             # Main application template
¦   +-- chat.html              # Chat template
¦
+-- static/
¦   +-- css/
¦   ¦   +-- style.css          # Main styles
¦   ¦   +-- responsive.css     # Responsive design
¦   +-- js/
¦   ¦   +-- app.js             # Main application logic
¦   ¦   +-- api.js             # API client
¦   ¦   +-- socket.js          # WebSocket manager
¦   ¦   +-- ui.js              # UI management
¦   +-- images/                # Static images
¦
+-- uploads/                    # User uploaded files
+-- migrations/                 # Database migrations (optional)
```

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user
- `POST /api/auth/logout` - Logout user
- `GET /api/auth/me` - Get current user

### Users
- `GET /api/users/<username>` - Get user info
- `GET /api/users/search/<query>` - Search users
- `PUT /api/users/<user_id>/profile` - Update profile
- `POST /api/users/<user_id>/avatar` - Upload avatar

### Conversations
- `GET /api/conversations` - Get all conversations
- `POST /api/conversations` - Create conversation
- `GET /api/conversations/<conv_id>` - Get conversation
- `PUT /api/conversations/<conv_id>` - Update conversation
- `POST /api/conversations/<conv_id>/members` - Add member
- `DELETE /api/conversations/<conv_id>/members/<member_id>` - Remove member

### Messages
- `GET /api/conversations/<conv_id>/messages` - Get messages
- `POST /api/conversations/<conv_id>/messages` - Send message
- `PUT /api/messages/<msg_id>` - Edit message
- `DELETE /api/messages/<msg_id>` - Delete message
- `POST /api/messages/<msg_id>/file` - Upload file
- `POST /api/messages/<msg_id>/react` - Add emoji reaction

### Contacts
- `GET /api/contacts` - Get all contacts
- `POST /api/contacts` - Add contact
- `DELETE /api/contacts/<contact_id>` - Delete contact

## WebSocket Events

### Client to Server
- `join_conversation` - Join conversation room
- `leave_conversation` - Leave conversation room
- `typing` - User is typing
- `stop_typing` - User stopped typing

### Server to Client
- `new_message` - New message received
- `message_edited` - Message was edited
- `message_deleted` - Message was deleted
- `message_reacted` - Emoji reaction added
- `user_typing` - User is typing
- `user_stop_typing` - User stopped typing
- `user_joined` - User joined conversation
- `user_left` - User left conversation
- `status_changed` - User status changed

## Configuration

### Environment Variables

```env
# Flask
FLASK_ENV=production
SECRET_KEY=your-secret-key-here

# Database
DATABASE_URL=sqlite:///messenger.db

# File Upload
MAX_CONTENT_LENGTH=52428800  # 50MB

# Security
DEBUG=False
```

## Database Models

### User
- id: Integer (Primary Key)
- username: String (Unique)
- email: String (Unique)
- password_hash: String
- display_name: String
- bio: String
- avatar: String (URL)
- status: String (online/offline/away)
- created_at: DateTime
- last_seen: DateTime

### Conversation
- id: Integer (Primary Key)
- title: String
- description: String
- is_group: Boolean
- creator_id: Integer (Foreign Key)
- icon: String (URL)
- created_at: DateTime
- updated_at: DateTime

### Message
- id: Integer (Primary Key)
- content: Text
- sender_id: Integer (Foreign Key)
- conversation_id: Integer (Foreign Key)
- message_type: String (text/file/image/video/audio)
- file_url: String
- file_name: String
- file_size: Integer
- is_edited: Boolean
- is_deleted: Boolean
- created_at: DateTime
- edited_at: DateTime

### Contact
- id: Integer (Primary Key)
- user_id: Integer (Foreign Key)
- contact_id: Integer (Foreign Key)
- contact_name: String
- created_at: DateTime

### Reaction
- id: Integer (Primary Key)
- message_id: Integer (Foreign Key)
- emoji: String
- count: Integer

## Security Features

- ? Password hashing with Werkzeug
- ? JWT token authentication
- ? CORS protection
- ? SQL injection prevention (SQLAlchemy ORM)
- ? File upload validation
- ? Rate limiting ready
- ? Input sanitization

## Performance Optimizations

- ? Database indexing on frequently queried fields
- ? Pagination for messages and search results
- ? Real-time updates via WebSocket
- ? Efficient file caching
- ? Lazy loading of conversations

## Browser Support

- ? Chrome/Chromium (latest)
- ? Firefox (latest)
- ? Safari (latest)
- ? Edge (latest)
- ? Mobile browsers

## Troubleshooting

### WebSocket Connection Issues
1. Check if Socket.IO is properly installed
2. Ensure firewall allows WebSocket connections
3. Check browser console for errors
4. Verify `socketManager` is initialized

### File Upload Issues
1. Check upload folder permissions
2. Verify MAX_CONTENT_LENGTH setting
3. Check available disk space
4. Ensure file type is allowed

### Database Issues
1. Check DATABASE_URL format
2. Verify database credentials
3. Run migrations if needed
4. Check database permissions

### Authentication Issues
1. Clear browser cache and cookies
2. Verify SECRET_KEY is set
3. Check token expiration
4. Verify CORS settings

## Future Enhancements

- [ ] Video/Audio calling
- [ ] Message search
- [ ] User blocking
- [ ] Channel support
- [ ] Message forwarding
- [ ] Pinned messages
- [ ] Custom emoji support
- [ ] Message voice notes
- [ ] End-to-end encryption
- [ ] Admin controls
- [ ] Moderation tools
- [ ] Analytics dashboard

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, email support@webmessenger.com or open an issue on GitHub.

## Changelog

### Version 1.0.0 (2024)
- Initial release
- Basic messaging features
- User authentication
- Group conversations
- File sharing
- Real-time updates