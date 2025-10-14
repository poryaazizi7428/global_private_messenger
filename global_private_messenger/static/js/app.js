// static/js/app.js

const app = {
    currentUser: null,
    selectedConversation: null,
    editingMessageId: null,
    filesToSend: [],

    async init() {
        ui.init();

        const token = API.getToken();
        if (token) {
            try {
                await this.loadCurrentUser();
                socketManager.init();
                await this.loadConversations();
                ui.hideAuthModal();
            } catch (error) {
                API.token = null;
                localStorage.removeItem('auth_token');
                ui.showAuthModal();
            }
        } else {
            ui.showAuthModal();
        }
    },

    async handleLogin(e) {
        e.preventDefault();

        const username = document.getElementById('loginUsername').value;
        const password = document.getElementById('loginPassword').value;
        const errorEl = document.getElementById('loginError');

        try {
            errorEl.classList.remove('show');
            const response = await API.auth.login(username, password);
            API.setToken(response.token);
            this.currentUser = response.user;
            ui.displayUser(response.user);
            socketManager.init();
            await this.loadConversations();
            ui.hideAuthModal();
        } catch (error) {
            errorEl.textContent = error.message || 'Login failed';
            errorEl.classList.add('show');
        }
    },

    async handleRegister(e) {
        e.preventDefault();

        const username = document.getElementById('regUsername').value;
        const email = document.getElementById('regEmail').value;
        const password = document.getElementById('regPassword').value;
        const displayName = document.getElementById('regDisplayName').value;
        const errorEl = document.getElementById('registerError');

        try {
            errorEl.classList.remove('show');
            const response = await API.auth.register(username, email, password, displayName);
            API.setToken(response.token);
            this.currentUser = response.user;
            ui.displayUser(response.user);
            socketManager.init();
            await this.loadConversations();
            ui.hideAuthModal();
        } catch (error) {
            errorEl.textContent = error.message || 'Registration failed';
            errorEl.classList.add('show');
        }
    },

    async loadCurrentUser() {
        try {
            const user = await API.auth.getCurrentUser();
            this.currentUser = user;
            ui.displayUser(user);
        } catch (error) {
            throw error;
        }
    },

    async loadConversations() {
        try {
            const conversations = await API.conversations.getAll();
            ui.displayConversations(conversations);
        } catch (error) {
            ui.showNotification('Failed to load conversations', 'error');
        }
    },

    async selectConversation(convId) {
        try {
            this.selectedConversation = convId;
            ui.selectedConversation = convId;

            document.getElementById('chatEmpty').classList.add('hidden');
            document.getElementById('activeChat').classList.remove('hidden');

            const conversation = await API.conversations.get(convId, true);
            document.getElementById('chatTitle').textContent = conversation.title;
            ui.displayMessages(conversation.messages);

            socketManager.joinConversation(convId);

            this.loadConversationInfo(conversation);
        } catch (error) {
            ui.showNotification('Failed to load conversation', 'error');
        }
    },

    loadConversationInfo(conversation) {
        const membersList = document.getElementById('membersList');
        membersList.innerHTML = '';

        conversation.members.forEach(member => {
            const item = document.createElement('div');
            item.className = 'member-item';
            item.innerHTML = `
                <img src="${member.avatar || 'https://via.placeholder.com/36'}" alt="${member.username}" class="member-avatar">
                <div class="member-info">
                    <div class="member-name">${member.display_name || member.username}</div>
                    <div class="member-status">${member.status}</div>
                </div>
            `;
            membersList.appendChild(item);
        });
    },

    async sendMessage() {
        const input = document.getElementById('messageInput');
        const content = input.value.trim();
        const files = document.getElementById('fileInput').files;

        if (!content && files.length === 0) return;

        try {
            if (content) {
                const message = await API.messages.send(this.selectedConversation, content, 'text');
                input.value = '';
                this.editingMessageId = null;

                if (files.length > 0) {
                    for (let file of files) {
                        await API.messages.uploadFile(message.id, file);
                    }
                    document.getElementById('fileInput').value = '';
                    document.getElementById('filePreview').innerHTML = '';
                }
            } else if (files.length > 0) {
                for (let file of files) {
                    const msg = await API.messages.send(this.selectedConversation, file.name, 'file');
                    await API.messages.uploadFile(msg.id, file);
                }
                document.getElementById('fileInput').value = '';
                document.getElementById('filePreview').innerHTML = '';
            }

            socketManager.emitStopTyping(this.selectedConversation);
        } catch (error) {
            ui.showNotification('Failed to send message', 'error');
        }
    },

    async createConversation() {
        const title = document.getElementById('newChatTitle').value.trim();
        if (!title) {
            ui.showNotification('Please enter a title', 'error');
            return;
        }

        try {
            const members = Array.from(document.querySelectorAll('.user-item.selected'))
                .map(item => parseInt(item.dataset.userId));

            const conversation = await API.conversations.create(title, '', members.length > 0, members);
            await this.loadConversations();
            document.getElementById('newChatModal').classList.add('hidden');
            ui.showNotification('Conversation created', 'success');
            this.selectConversation(conversation.id);
        } catch (error) {
            ui.showNotification('Failed to create conversation', 'error');
        }
    },

    async searchUsers(query) {
        if (!query.trim()) {
            document.getElementById('usersList').innerHTML = '';
            return;
        }

        try {
            const users = await API.users.search(query);
            const container = document.getElementById('usersList');
            container.innerHTML = '';

            users.forEach(user => {
                const item = document.createElement('div');
                item.className = 'user-item';
                item.dataset.userId = user.id;
                item.innerHTML = `
                    <img src="${user.avatar || 'https://via.placeholder.com/36'}" alt="${user.username}" class="user-avatar">
                    <div class="user-info">
                        <div class="user-name">${user.display_name || user.username}</div>
                        <div class="user-username">@${user.username}</div>
                    </div>
                    <div class="user-checkbox"></div>
                `;

                item.addEventListener('click', () => {
                    item.classList.toggle('selected');
                });

                container.appendChild(item);
            });
        } catch (error) {
            console.error('Search error:', error);
        }
    },

    async deleteMessage(msgId) {
        try {
            await API.messages.delete(msgId);
            ui.showNotification('Message deleted', 'success');
        } catch (error) {
            ui.showNotification('Failed to delete message', 'error');
        }
    },

    async saveSettings() {
        try {
            const data = {
                display_name: document.getElementById('displayNameInput').value,
                bio: document.getElementById('bioInput').value,
                status: 'online'
            };

            await API.users.updateProfile(this.currentUser.id, data);
            ui.showNotification('Settings saved', 'success');
            document.getElementById('settingsModal').classList.add('hidden');
        } catch (error) {
            ui.showNotification('Failed to save settings', 'error');
        }
    },

    async uploadAvatar(e) {
        const file = e.target.files[0];
        if (!file) return;

        try {
            const result = await API.users.uploadAvatar(this.currentUser.id, file);
            this.currentUser.avatar = result.avatar_url;
            document.getElementById('userAvatarMini').src = result.avatar_url;
            document.getElementById('settingsAvatar').src = result.avatar_url;
            ui.showNotification('Avatar uploaded', 'success');
        } catch (error) {
            ui.showNotification('Failed to upload avatar', 'error');
        }
    },

    async logout() {
        try {
            await API.auth.logout();
            socketManager.disconnect();
            API.token = null;
            localStorage.removeItem('auth_token');
            this.currentUser = null;
            ui.showAuthModal();
            document.getElementById('loginForm').reset();
            document.getElementById('registerForm').reset();
        } catch (error) {
            ui.showNotification('Logout failed', 'error');
        }
    }
};

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    app.init();
});
