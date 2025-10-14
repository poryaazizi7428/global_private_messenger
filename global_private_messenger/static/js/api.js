// static/js/api.js

const API = {
    baseURL: '/api',
    token: null,

    setToken(token) {
        this.token = token;
        localStorage.setItem('auth_token', token);
    },

    getToken() {
        return this.token || localStorage.getItem('auth_token');
    },

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        if (this.getToken()) {
            headers['Authorization'] = `Bearer ${this.getToken()}`;
        }

        try {
            const response = await fetch(url, {
                ...options,
                headers
            });

            if (response.status === 401) {
                this.token = null;
                localStorage.removeItem('auth_token');
                window.location.reload();
            }

            const data = response.ok ? await response.json() : await response.text();

            if (!response.ok) {
                throw {
                    status: response.status,
                    message: typeof data === 'object' ? data.error : data
                };
            }

            return data;
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    },

    // Authentication
    auth: {
        register(username, email, password, displayName) {
            return API.request('/auth/register', {
                method: 'POST',
                body: JSON.stringify({
                    username,
                    email,
                    password,
                    display_name: displayName
                })
            });
        },

        login(username, password) {
            return API.request('/auth/login', {
                method: 'POST',
                body: JSON.stringify({ username, password })
            });
        },

        logout() {
            return API.request('/auth/logout', { method: 'POST' });
        },

        getCurrentUser() {
            return API.request('/auth/me');
        }
    },

    // Users
    users: {
        getUser(username) {
            return API.request(`/users/${username}`);
        },

        search(query) {
            return API.request(`/users/search/${encodeURIComponent(query)}`);
        },

        updateProfile(userId, data) {
            return API.request(`/users/${userId}/profile`, {
                method: 'PUT',
                body: JSON.stringify(data)
            });
        },

        uploadAvatar(userId, file) {
            const formData = new FormData();
            formData.append('file', file);
            return API.request(`/users/${userId}/avatar`, {
                method: 'POST',
                body: formData,
                headers: {}
            });
        }
    },

    // Conversations
    conversations: {
        getAll() {
            return API.request('/conversations');
        },

        get(convId, includeMessages = false) {
            return API.request(`/conversations/${convId}?include_messages=${includeMessages}`);
        },

        create(title, description = '', isGroup = false, members = []) {
            return API.request('/conversations', {
                method: 'POST',
                body: JSON.stringify({
                    title,
                    description,
                    is_group: isGroup,
                    members
                })
            });
        },

        update(convId, data) {
            return API.request(`/conversations/${convId}`, {
                method: 'PUT',
                body: JSON.stringify(data)
            });
        },

        addMember(convId, userId) {
            return API.request(`/conversations/${convId}/members`, {
                method: 'POST',
                body: JSON.stringify({ user_id: userId })
            });
        },

        removeMember(convId, memberId) {
            return API.request(`/conversations/${convId}/members/${memberId}`, {
                method: 'DELETE'
            });
        }
    },

    // Messages
    messages: {
        getMessages(convId, page = 1, perPage = 50) {
            return API.request(
                `/conversations/${convId}/messages?page=${page}&per_page=${perPage}`
            );
        },

        send(convId, content, type = 'text') {
            return API.request(`/conversations/${convId}/messages`, {
                method: 'POST',
                body: JSON.stringify({
                    content,
                    message_type: type
                })
            });
        },

        update(msgId, content) {
            return API.request(`/messages/${msgId}`, {
                method: 'PUT',
                body: JSON.stringify({ content })
            });
        },

        delete(msgId) {
            return API.request(`/messages/${msgId}`, {
                method: 'DELETE'
            });
        },

        uploadFile(msgId, file) {
            const formData = new FormData();
            formData.append('file', file);
            return API.request(`/messages/${msgId}/file`, {
                method: 'POST',
                body: formData,
                headers: {}
            });
        },

        addReaction(msgId, emoji) {
            return API.request(`/messages/${msgId}/react`, {
                method: 'POST',
                body: JSON.stringify({ emoji })
            });
        }
    },

    // Contacts
    contacts: {
        getAll() {
            return API.request('/contacts');
        },

        add(contactId, contactName = '') {
            return API.request('/contacts', {
                method: 'POST',
                body: JSON.stringify({
                    contact_id: contactId,
                    contact_name: contactName
                })
            });
        },

        delete(contactId) {
            return API.request(`/contacts/${contactId}`, {
                method: 'DELETE'
            });
        }
    }
};

