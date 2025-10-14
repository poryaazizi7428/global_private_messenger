// static/js/socket.js

class SocketManager {
    constructor() {
        this.socket = null;
        this.connected = false;
        this.currentConversation = null;
        this.typingUsers = new Set();
        this.typingTimeout = null;
    }

    init() {
        const token = API.getToken();
        if (!token) return;

        this.socket = io({
            auth: { token },
            reconnection: true,
            reconnectionDelay: 1000,
            reconnectionDelayMax: 5000,
            reconnectionAttempts: 5
        });

        this.socket.on('connect', () => {
            this.connected = true;
            console.log('Socket connected');
            ui.updateConnectionStatus(true);
        });

        this.socket.on('disconnect', () => {
            this.connected = false;
            console.log('Socket disconnected');
            ui.updateConnectionStatus(false);
        });

        this.socket.on('new_message', (message) => {
            if (message.conversation_id === this.currentConversation) {
                ui.addMessage(message);
                this.socket.emit('message_read', { message_id: message.id });
            }
        });

        this.socket.on('message_edited', (message) => {
            ui.updateMessage(message);
        });

        this.socket.on('message_deleted', (data) => {
            ui.removeMessage(data.message_id);
        });

        this.socket.on('message_reacted', (message) => {
            ui.updateMessage(message);
        });

        this.socket.on('user_typing', (data) => {
            this.typingUsers.add(data.user_id);
            ui.showTypingIndicator(data.username);
        });

        this.socket.on('user_stop_typing', (data) => {
            this.typingUsers.delete(data.user_id);
            if (this.typingUsers.size === 0) {
                ui.hideTypingIndicator();
            }
        });

        this.socket.on('user_joined', (data) => {
            ui.showNotification(`${data.user.display_name} joined the conversation`, 'info');
        });

        this.socket.on('user_left', (data) => {
            ui.showNotification(`User left the conversation`, 'info');
        });

        this.socket.on('status_changed', (data) => {
            ui.updateUserStatus(data.user_id, data.status);
        });
    }

    joinConversation(conversationId) {
        if (!this.socket) return;
        this.currentConversation = conversationId;
        this.socket.emit('join_conversation', { conversation_id: conversationId });
    }

    leaveConversation(conversationId) {
        if (!this.socket) return;
        this.socket.emit('leave_conversation', { conversation_id: conversationId });
        this.currentConversation = null;
        this.typingUsers.clear();
    }

    emitTyping(conversationId) {
        if (!this.socket) return;
        this.socket.emit('typing', { conversation_id: conversationId });
    }

    emitStopTyping(conversationId) {
        if (!this.socket) return;
        this.socket.emit('stop_typing', { conversation_id: conversationId });
    }

    disconnect() {
        if (this.socket) {
            this.socket.disconnect();
        }
    }
}

const socketManager = new SocketManager();

