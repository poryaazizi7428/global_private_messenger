// static/js/ui.js

const ui = {
    currentUser: null,
    conversations: [],
    messages: {},
    selectedConversation: null,
    typingTimer: null,

    init() {
        this.setupEventListeners();
        this.loadTheme();
    },

    setupEventListeners() {
        // Auth
        document.getElementById('loginForm').addEventListener('submit', (e) => app.handleLogin(e));
        document.getElementById('registerForm').addEventListener('submit', (e) => app.handleRegister(e));

        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.switchAuthTab(e.target.dataset.tab));
        });

        // Chat
        document.getElementById('sendBtn').addEventListener('click', () => app.sendMessage());
        document.getElementById('messageInput').addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                app.sendMessage();
            }
        });

        document.getElementById('messageInput').addEventListener('input', () => {
            this.handleTyping();
        });

        document.getElementById('attachBtn').addEventListener('click', () => {
            document.getElementById('fileInput').click();
        });

        document.getElementById('fileInput').addEventListener('change', (e) => this.handleFileSelect(e));

        document.getElementById('emojiBtn').addEventListener('click', () => this.toggleEmojiPicker());

        document.querySelectorAll('.emoji').forEach(emoji => {
            emoji.addEventListener('click', (e) => {
                const text = document.getElementById('messageInput');
                text.value += e.target.dataset.emoji;
                text.focus();
                this.toggleEmojiPicker();
            });
        });

        // Modals
        document.getElementById('newChatBtn').addEventListener('click', () => this.openNewChatModal());
        document.getElementById('createChatBtn').addEventListener('click', () => app.createConversation());
        document.getElementById('settingsBtn').addEventListener('click', () => this.openSettingsModal());
        document.getElementById('infoBtn').addEventListener('click', () => this.toggleRightPanel());
        document.getElementById('logoutBtn').addEventListener('click', () => app.logout());

        document.querySelectorAll('.close-modal').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.target.closest('.modal-overlay').classList.add('hidden');
            });
        });

        // Settings
        document.getElementById('saveSettingsBtn').addEventListener('click', () => app.saveSettings());
        document.getElementById('avatarInput').addEventListener('change', (e) => app.uploadAvatar(e));
        document.getElementById('darkModeToggle').addEventListener('change', (e) => {
            this.toggleDarkMode(e.target.checked);
        });

        // Conversation search
        document.getElementById('conversationSearch').addEventListener('input', (e) => {
            this.filterConversations(e.target.value);
        });

        // Member search
        document.getElementById('memberSearchInput').addEventListener('input', (e) => {
            app.searchUsers(e.target.value);
        });

        // Close panels
        document.getElementById('closePanelBtn').addEventListener('click', () => {
            this.toggleRightPanel();
        });

        // Context menu
        document.addEventListener('contextmenu', (e) => {
            if (e.target.closest('.message-bubble')) {
                e.preventDefault();
                this.showMessageContextMenu(e, e.target.closest('.message-group'));
            }
        });

        document.addEventListener('click', () => {
            document.getElementById('messageContextMenu').classList.add('hidden');
        });
    },

    switchAuthTab(tab) {
        document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.getElementById(tab + 'Form').classList.add('active');
        document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
    },

    showAuthModal() {
        document.getElementById('authModal').classList.remove('hidden');
        document.getElementById('mainApp').classList.add('hidden');
    },

    hideAuthModal() {
        document.getElementById('authModal').classList.add('hidden');
        document.getElementById('mainApp').classList.remove('hidden');
    },

    displayUser(user) {
        this.currentUser = user;
        document.getElementById('usernameMini').textContent = user.display_name || user.username;
        if (user.avatar) {
            document.getElementById('userAvatarMini').src = user.avatar;
        }
        document.getElementById('settingsAvatar').src = user.avatar || 'https://via.placeholder.com/80';
        document.getElementById('displayNameInput').value = user.display_name || '';
        document.getElementById('bioInput').value = user.bio || '';
    },

    displayConversations(conversations) {
        this.conversations = conversations;
        const container = document.getElementById('conversationsList');
        container.innerHTML = '';

        conversations.forEach(conv => {
            const item = document.createElement('div');
            item.className = 'conversation-item';
            item.dataset.convId = conv.id;

            const lastMessage = conv.last_message || { content: 'No messages yet' };
            const members = conv.members.slice(0, 3).map(m => m.display_name || m.username).join(', ');

            item.innerHTML = `
                <img src="${conv.icon || 'https://via.placeholder.com/48'}" alt="${conv.title}" class="conversation-avatar">
                <div class="conversation-content">
                    <div class="conv-name">${conv.title}</div>
                    <div class="conv-preview">${lastMessage.content}</div>
                </div>
                ${conv.unread_count ? `<div class="conv-unread">${conv.unread_count}</div>` : ''}
            `;

            item.addEventListener('click', () => app.selectConversation(conv.id));
            container.appendChild(item);
        });
    },

    selectConversation(convId) {
        document.querySelectorAll('.conversation-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`[data-conv-id="${convId}"]`).classList.add('active');
        app.selectConversation(convId);
    },

    displayMessages(messages) {
        const container = document.getElementById('messagesContainer');
        container.innerHTML = '';

        messages.forEach(msg => {
            this.addMessage(msg);
        });

        container.scrollTop = container.scrollHeight;
    },

    addMessage(msg) {
        const container = document.getElementById('messagesContainer');
        const isOwn = msg.sender.id === this.currentUser.id;
        const group = document.createElement('div');
        group.className = `message-group ${isOwn ? 'own' : ''}`;
        group.dataset.msgId = msg.id;

        let content = '';
        if (msg.message_type === 'file') {
            content = `
                <div class="file-attachment">
                    <div class="file-icon">
                        <i class="fas fa-file"></i>
                    </div>
                    <a href="${msg.file_url}" download="${msg.file_name}" class="file-info">
                        <div class="file-name">${msg.file_name}</div>
                        <div class="file-size">${this.formatFileSize(msg.file_size)}</div>
                    </a>
                </div>
            `;
        } else {
            content = msg.is_deleted ? '<em>Message deleted</em>' : msg.content;
        }

        let reactionsHTML = '';
        if (Object.keys(msg.reactions).length > 0) {
            reactionsHTML = '<div class="message-reactions">' +
                Object.entries(msg.reactions).map(([emoji, count]) =>
                    `<span class="reaction">${emoji} ${count}</span>`
                ).join('') +
                '</div>';
        }

        group.innerHTML = `
            ${!isOwn ? `<img src="${msg.sender.avatar || 'https://via.placeholder.com/32'}" alt="${msg.sender.username}" class="message-avatar">` : ''}
            <div class="message-bubble ${msg.message_type}">
                ${content}
                <div class="message-time">${this.formatTime(msg.created_at)}${msg.is_edited ? ' (edited)' : ''}</div>
                ${reactionsHTML}
            </div>
        `;

        container.appendChild(group);
        container.scrollTop = container.scrollHeight;
    },

    updateMessage(msg) {
        const group = document.querySelector(`[data-msg-id="${msg.id}"]`);
        if (group) {
            const bubble = group.querySelector('.message-bubble');
            bubble.innerHTML = msg.content + 
                `<div class="message-time">${this.formatTime(msg.created_at)}${msg.is_edited ? ' (edited)' : ''}</div>`;
        }
    },

    removeMessage(msgId) {
        const group = document.querySelector(`[data-msg-id="${msgId}"]`);
        if (group) {
            group.remove();
        }
    },

    handleFileSelect(e) {
        const files = e.target.files;
        const preview = document.getElementById('filePreview');
        preview.innerHTML = '';

        Array.from(files).forEach(file => {
            const item = document.createElement('div');
            item.className = 'preview-item';
            item.innerHTML = `
                <i class="fas fa-file"></i>
                <span>${file.name}</span>
                <button type="button" class="remove-file" data-file-name="${file.name}">
                    <i class="fas fa-times"></i>
                </button>
            `;
            item.querySelector('.remove-file').addEventListener('click', () => {
                item.remove();
            });
            preview.appendChild(item);
        });
    },

    handleTyping() {
        if (!this.selectedConversation) return;

        socketManager.emitTyping(this.selectedConversation);

        clearTimeout(this.typingTimer);
        this.typingTimer = setTimeout(() => {
            socketManager.emitStopTyping(this.selectedConversation);
        }, 1000);
    },

    showTypingIndicator(username) {
        const indicator = document.getElementById('typingIndicator');
        indicator.classList.remove('hidden');
        document.getElementById('typingUsers').textContent = `${username} is typing`;
    },

    hideTypingIndicator() {
        document.getElementById('typingIndicator').classList.add('hidden');
    },

    toggleEmojiPicker() {
        document.getElementById('emojiPicker').classList.toggle('hidden');
    },

    openNewChatModal() {
        document.getElementById('newChatModal').classList.remove('hidden');
        document.getElementById('memberSearchInput').value = '';
        document.getElementById('usersList').innerHTML = '';
    },

    openSettingsModal() {
        document.getElementById('settingsModal').classList.remove('hidden');
    },

    toggleRightPanel() {
        document.getElementById('rightPanel').classList.toggle('hidden');
    },

    showMessageContextMenu(e, messageGroup) {
        const menu = document.getElementById('messageContextMenu');
        menu.style.top = e.clientY + 'px';
        menu.style.left = e.clientX + 'px';
        menu.classList.remove('hidden');

        document.querySelectorAll('.context-item').forEach(item => {
            item.onclick = () => {
                const action = item.dataset.action;
                this.handleMessageAction(action, messageGroup);
                menu.classList.add('hidden');
            };
        });
    },

    handleMessageAction(action, messageGroup) {
        const msgId = messageGroup.dataset.msgId;
        const content = messageGroup.querySelector('.message-bubble').textContent;

        switch(action) {
            case 'edit':
                document.getElementById('messageInput').value = content;
                app.editingMessageId = msgId;
                break;
            case 'copy':
                navigator.clipboard.writeText(content);
                this.showNotification('Message copied to clipboard', 'info');
                break;
            case 'delete':
                if (confirm('Delete this message?')) {
                    app.deleteMessage(msgId);
                }
                break;
            case 'react':
                this.toggleEmojiPicker();
                break;
        }
    },

    toggleDarkMode(enabled) {
        const app = document.getElementById('app');
        if (enabled) {
            app.classList.add('dark-mode');
            localStorage.setItem('darkMode', 'true');
        } else {
            app.classList.remove('dark-mode');
            localStorage.setItem('darkMode', 'false');
        }
    },

    loadTheme() {
        if (localStorage.getItem('darkMode') === 'true') {
            document.getElementById('app').classList.add('dark-mode');
            document.getElementById('darkModeToggle').checked = true;
        }
    },

    showNotification(message, type = 'info') {
        const container = document.getElementById('toastContainer');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            info: 'fa-info-circle'
        };

        toast.innerHTML = `
            <i class="fas ${icons[type]} toast-icon"></i>
            <span>${message}</span>
            <button class="toast-close"><i class="fas fa-times"></i></button>
        `;

        toast.querySelector('.toast-close').addEventListener('click', () => {
            toast.remove();
        });

        container.appendChild(toast);

        setTimeout(() => {
            toast.remove();
        }, 3000);
    },

    formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        const msgDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());

        if (msgDate.getTime() === today.getTime()) {
            return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
        }

        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    },

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    },

    filterConversations(query) {
        const items = document.querySelectorAll('.conversation-item');
        items.forEach(item => {
            const title = item.querySelector('.conv-name').textContent.toLowerCase();
            item.style.display = title.includes(query.toLowerCase()) ? '' : 'none';
        });
    },

    updateConnectionStatus(connected) {
        // Visual indicator could be added here
        console.log('Connection status:', connected);
    },

    updateUserStatus(userId, status) {
        // Update user status indicator if needed
    }
};
