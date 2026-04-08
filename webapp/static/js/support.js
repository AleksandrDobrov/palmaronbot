/**
 * Центр підтримки користувача
 */

class SupportCenter {
    constructor() {
        this.state = {
            tickets: [],
            messages: [],
            activeTicketId: null,
            activeTicket: null,
            loadingTickets: false,
            loadingThread: false,
            composerMode: false,
            sending: false,
            closing: false
        };
        this.elements = {};
        this.badgePoller = null;
        this.categoryLabels = {
            general: 'Загальне питання',
            deposits: 'Поповнення',
            withdrawals: 'Виведення',
            garden: 'Сад',
            gift: 'Подарунки',
            technical: 'Технічна проблема',
            verification: 'Верифікація'
        };
        this.categoryIcons = {
            general: '💬',
            deposits: '💰',
            withdrawals: '💸',
            garden: '🌱',
            gift: '🎁',
            technical: '🛠',
            verification: '🔐'
        };
    }

    init() {
        this.cacheElements();
        if (!this.elements.modal || typeof api === 'undefined') {
            return;
        }
        this.bindEvents();
        this.renderEmptyState();
        this.toggleComposer(false);
        this.refreshTickets();
        this.refreshUnreadBadge();
        this.badgePoller = setInterval(() => this.refreshUnreadBadge(), 60000);
    }

    cacheElements() {
        this.elements = {
            modal: document.getElementById('supportModal'),
            ticketList: document.getElementById('supportTicketList'),
            badge: document.getElementById('supportBadge'),
            chat: document.getElementById('supportChat'),
            emptyState: document.getElementById('supportEmptyState'),
            title: document.getElementById('supportActiveTitle'),
            meta: document.getElementById('supportActiveMeta'),
            status: document.getElementById('supportStatusPill'),
            messageInput: document.getElementById('supportMessageInput'),
            subjectRow: document.getElementById('supportSubjectRow'),
            subjectInput: document.getElementById('supportSubjectInput'),
            categoryRow: document.getElementById('supportCategoryRow'),
            categorySelect: document.getElementById('supportCategorySelect'),
            sendBtn: document.getElementById('supportSendBtn'),
            cancelBtn: document.getElementById('supportCancelBtn'),
            closeBtn: document.getElementById('supportCloseBtn'),
            newTicketBtn: document.getElementById('supportNewTicketBtn'),
            refreshBtn: document.getElementById('supportRefreshBtn')
        };
    }

    bindEvents() {
        if (this.elements.sendBtn) {
            this.elements.sendBtn.addEventListener('click', () => this.handleSend());
        }
        if (this.elements.messageInput) {
            this.elements.messageInput.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                    event.preventDefault();
                    this.handleSend();
                }
            });
        }
        if (this.elements.closeBtn) {
            this.elements.closeBtn.addEventListener('click', () => this.handleCloseTicket());
        }
        if (this.elements.newTicketBtn) {
            this.elements.newTicketBtn.addEventListener('click', () => this.startComposer());
        }
        if (this.elements.refreshBtn) {
            this.elements.refreshBtn.addEventListener('click', () => this.refreshTickets());
        }
    }

    open() {
        if (!this.elements.modal) return;
        this.elements.modal.style.display = 'flex';
        this.refreshTickets();
        setTimeout(() => this.elements.messageInput?.focus(), 100);
    }

    close() {
        if (!this.elements.modal) return;
        this.elements.modal.style.display = 'none';
    }

    async refreshTickets() {
        if (this.state.loadingTickets) return;
        if (typeof api === 'undefined') return;
        this.state.loadingTickets = true;
        this.renderTicketList({ loading: true });
        try {
            const data = await api.getSupportTickets({ limit: 50 });
            this.state.tickets = data?.tickets || [];
            this.renderTicketList();
            this.updateBadge();
            if (!this.state.activeTicketId && this.state.tickets.length && !this.state.composerMode) {
                this.selectTicket(this.state.tickets[0].id);
            } else if (!this.state.tickets.length && !this.state.composerMode) {
                this.renderEmptyState();
            }
        } catch (error) {
            console.error('[Support] Failed to load tickets:', error);
            this.renderTicketList({ error: error.message || 'Не вдалося завантажити звернення' });
            this.notify(error.message || 'Не вдалося завантажити звернення', 'error');
        } finally {
            this.state.loadingTickets = false;
        }
    }

    renderTicketList(options = {}) {
        const list = this.elements.ticketList;
        if (!list) return;
        if (options.loading) {
            list.innerHTML = '<div class="support-empty-list">Завантаження...</div>';
            return;
        }
        if (options.error) {
            list.innerHTML = `<div class="support-empty-list">${options.error}</div>`;
            return;
        }
        if (!this.state.tickets.length) {
            list.innerHTML = '<div class="support-empty-list">Немає звернень</div>';
            return;
        }
        list.innerHTML = this.state.tickets.map((ticket) => {
            const statusClass = this.mapStatusToClass(ticket.status);
            const updatedAt = ticket.updated_at ? this.formatRelative(ticket.updated_at) : 'щойно';
            const preview = (ticket.last_message_preview || '').substring(0, 60);
            const isActive = ticket.id === this.state.activeTicketId;
            const unreadCount = Number(ticket.user_unread_count) || 0;
            const unreadBadge = unreadCount > 0
                ? `<span class="support-unread-pill">+${unreadCount}</span>`
                : '';
            const categoryPill = this.renderCategoryPill(ticket.category);
            const classes = ['support-ticket-card'];
            if (isActive) classes.push('active');
            if (unreadCount > 0) classes.push('unread');
            return `
                <div class="${classes.join(' ')}" data-ticket-id="${ticket.id}">
                    <div class="support-ticket-title">#${ticket.id} • ${this.escapeHtml(ticket.subject || 'Без теми')}</div>
                    <div>${categoryPill}</div>
                    <div class="support-ticket-meta">
                        <span>${updatedAt}</span>
                        <div class="support-ticket-meta-right">
                            ${unreadBadge}
                            <span class="support-status-pill ${statusClass}">${this.mapStatusLabel(ticket.status)}</span>
                        </div>
                    </div>
                    <div class="support-ticket-preview">${this.escapeHtml(preview || '—')}</div>
                </div>
            `;
        }).join('');
        list.querySelectorAll('.support-ticket-card').forEach((card) => {
            card.addEventListener('click', () => {
                const id = Number(card.getAttribute('data-ticket-id'));
                this.selectTicket(id);
            });
        });
    }

    async selectTicket(ticketId) {
        if (!ticketId || this.state.loadingThread) return;
        if (typeof api === 'undefined') return;
        this.state.loadingThread = true;
        this.state.composerMode = false;
        this.toggleComposer(false);
        this.showChatPlaceholder('Завантаження діалогу...');
        try {
            const data = await api.getSupportTicket(ticketId, { limit: 400 });
            this.state.activeTicketId = ticketId;
            this.state.activeTicket = data.ticket;
            this.state.messages = data.messages || [];
            this.state.tickets = this.state.tickets.map((ticket) =>
                ticket.id === ticketId ? { ...ticket, user_unread_count: 0 } : ticket
            );
            this.renderTicketList();
            this.renderActiveTicket();
            this.scrollChatToBottom();
            this.updateBadge();
        } catch (error) {
            console.error('[Support] Failed to load ticket', error);
            this.notify(error.message || 'Не вдалося завантажити діалог', 'error');
        } finally {
            this.state.loadingThread = false;
        }
    }

    renderActiveTicket() {
        const { title, meta, status, emptyState, chat } = this.elements;
        const ticket = this.state.activeTicket;
        if (!ticket || !chat) return;
        if (title) title.textContent = `Звернення #${ticket.id}`;
        const categoryLabel = this.mapCategoryLabel(ticket.category);
        if (meta) {
            meta.textContent = `${categoryLabel} • Оновлено ${this.formatRelative(ticket.updated_at)} • Створено ${this.formatDate(ticket.created_at)}`;
        }
        if (status) {
            status.style.display = 'inline-flex';
            status.className = `support-status-pill ${this.mapStatusToClass(ticket.status)}`;
            status.textContent = this.mapStatusLabel(ticket.status);
        }
        this.updateTicketActions(ticket);
        if (emptyState) {
            emptyState.style.display = 'none';
        }
        chat.innerHTML = this.state.messages.map((msg) => this.renderMessage(msg)).join('');
    }

    renderMessage(msg) {
        const isUser = msg.sender_role !== 'admin';
        const author = isUser ? 'Ви' : 'Адмін';
        return `
            <div class="support-bubble ${isUser ? 'user' : 'admin'}">
                <div class="bubble-author">${author}</div>
                <div class="bubble-text">${this.escapeHtml(msg.body)}</div>
                <div class="bubble-meta">${this.formatRelative(msg.created_at)}</div>
            </div>
        `;
    }

    startComposer() {
        this.state.composerMode = true;
        this.state.activeTicketId = null;
        if (this.elements.title) this.elements.title.textContent = 'Нове звернення';
        if (this.elements.meta) this.elements.meta.textContent = 'Опишіть питання та надішліть нам';
        if (this.elements.status) this.elements.status.style.display = 'none';
        if (this.elements.emptyState) this.elements.emptyState.style.display = 'none';
        if (this.elements.chat) this.elements.chat.innerHTML = '';
        if (this.elements.categorySelect) {
            this.elements.categorySelect.value = this.elements.categorySelect.getAttribute('data-default') || 'general';
        }
        this.toggleComposer(true);
        this.toggleCloseButton(false);
        this.elements.messageInput?.focus();
    }

    cancelComposer() {
        this.state.composerMode = false;
        this.elements.subjectInput && (this.elements.subjectInput.value = '');
        this.elements.messageInput && (this.elements.messageInput.value = '');
        if (this.elements.categorySelect) {
            this.elements.categorySelect.value = this.elements.categorySelect.getAttribute('data-default') || 'general';
        }
        if (this.state.tickets.length) {
            this.selectTicket(this.state.tickets[0].id);
        } else {
            this.renderEmptyState();
        }
    }

    toggleComposer(showComposer) {
        if (this.elements.subjectRow) {
            this.elements.subjectRow.style.display = showComposer ? 'block' : 'none';
        }
        if (this.elements.categoryRow) {
            this.elements.categoryRow.style.display = showComposer ? 'block' : 'none';
        }
        if (this.elements.cancelBtn) {
            this.elements.cancelBtn.style.display = showComposer ? 'inline-flex' : 'none';
        }
    }

    renderEmptyState() {
        if (this.elements.emptyState) {
            this.elements.emptyState.style.display = 'block';
        }
        if (this.elements.title) this.elements.title.textContent = 'Обери звернення';
        if (this.elements.meta) this.elements.meta.textContent = 'Поки що немає діалогів';
        if (this.elements.status) this.elements.status.style.display = 'none';
        if (this.elements.chat) this.elements.chat.innerHTML = '';
        this.toggleCloseButton(false);
    }

    showChatPlaceholder(text) {
        if (this.elements.chat) {
            this.elements.chat.innerHTML = `<div class="support-empty-list">${text}</div>`;
        }
    }

    updateTicketActions(ticket) {
        if (!ticket) {
            this.toggleCloseButton(false);
            return;
        }
        const isClosed = (ticket.status || '').toLowerCase() === 'closed';
        this.toggleCloseButton(!isClosed && !this.state.composerMode);
    }

    toggleCloseButton(show) {
        if (!this.elements.closeBtn) return;
        this.elements.closeBtn.style.display = show ? 'inline-flex' : 'none';
        this.elements.closeBtn.classList.remove('is-loading');
    }

    async handleCloseTicket() {
        if (!this.state.activeTicketId || this.state.closing) { return; }
        const ticket = this.state.activeTicket;
        if (!ticket || (ticket.status || '').toLowerCase() === 'closed') { return; }
        if (!confirm('Закрити це звернення? Після закриття ви зможете створити нове.')) { return; }
        this.state.closing = true;
        this.elements.closeBtn?.classList.add('is-loading');
        try {
            await api.closeSupportTicket(this.state.activeTicketId);
            await this.selectTicket(this.state.activeTicketId);
            this.notify('Звернення закрито', 'success');
        } catch (error) {
            console.error('[Support] Close ticket error', error);
            this.notify(error.message || 'Не вдалося закрити звернення', 'error');
        } finally {
            this.state.closing = false;
            this.elements.closeBtn?.classList.remove('is-loading');
        }
    }

    async handleSend() {
        if (this.state.sending) return;
        const message = (this.elements.messageInput?.value || '').trim();
        if (!message) {
            this.notify('Введіть повідомлення', 'warning');
            return;
        }
        const ticket = this.state.activeTicket;
        if (ticket && (ticket.status || '').toLowerCase() === 'closed') {
            this.notify('Неможливо надіслати повідомлення в закрите звернення', 'warning');
            return;
        }
        this.state.sending = true;
        this.elements.sendBtn?.classList.add('is-loading');
        try {
            if (this.state.composerMode) {
                await this.createTicket(message);
            } else if (this.state.activeTicketId) {
                await this.replyToTicket(message);
            } else {
                this.startComposer();
                this.state.sending = false;
                this.elements.sendBtn?.classList.remove('is-loading');
                return;
            }
            this.elements.messageInput.value = '';
        } catch (error) {
            console.error('[Support] Send error', error);
            this.notify(error.message || 'Не вдалося надіслати повідомлення', 'error');
        } finally {
            this.state.sending = false;
            this.elements.sendBtn?.classList.remove('is-loading');
        }
    }

    async createTicket(message) {
        const payload = { message };
        const subject = (this.elements.subjectInput?.value || '').trim();
        if (subject) payload.subject = subject;
        const category = this.elements.categorySelect?.value;
        if (category) payload.category = category;
        const response = await api.createSupportTicket(payload);
        this.notify('Звернення створено', 'success');
        this.elements.subjectInput && (this.elements.subjectInput.value = '');
        this.state.composerMode = false;
        await this.refreshTickets();
        if (response?.ticket?.id) {
            this.selectTicket(response.ticket.id);
        }
    }

    async replyToTicket(message) {
        if (!this.state.activeTicketId) return;
        await api.replySupportTicket(this.state.activeTicketId, { message });
        await this.selectTicket(this.state.activeTicketId);
        this.refreshTickets();
        this.notify('Повідомлення надіслано', 'success');
    }

    updateBadge() {
        const badge = this.elements.badge;
        if (!badge) return;
        const unreadCount = this.state.tickets.reduce((sum, ticket) => {
            const value = Number(ticket.user_unread_count) || 0;
            return sum + value;
        }, 0);
        this.applyBadgeValue(unreadCount);
    }

    applyBadgeValue(value) {
        const badge = this.elements.badge;
        if (!badge) return;
        const count = Math.max(0, Number(value) || 0);
        if (count > 0) {
            badge.textContent = count > 99 ? '99+' : String(count);
            badge.style.display = 'flex';
        } else {
            badge.style.display = 'none';
        }
    }

    async refreshUnreadBadge() {
        if (typeof api === 'undefined') return;
        try {
            const data = await api.getSupportUnreadCount();
            const count = data?.count ?? 0;
            this.applyBadgeValue(count);
        } catch (error) {
            console.warn('[Support] Failed to refresh unread badge', error);
        }
    }

    scrollChatToBottom() {
        if (this.elements.chat) {
            requestAnimationFrame(() => {
                this.elements.chat.scrollTop = this.elements.chat.scrollHeight;
            });
        }
    }

    notify(message, type = 'info') {
        if (typeof showToast === 'function') {
            showToast(message, type);
        } else if (window.telegramWebApp?.showAlert) {
            window.telegramWebApp.showAlert(message);
        } else {
            alert(message);
        }
    }

    mapStatusLabel(status) {
        switch ((status || '').toLowerCase()) {
            case 'answered':
                return 'Очікує вас';
            case 'closed':
                return 'Закрито';
            case 'pending':
            default:
                return 'В обробці';
        }
    }

    mapStatusToClass(status) {
        switch ((status || '').toLowerCase()) {
            case 'answered':
                return 'answered';
            case 'closed':
                return 'closed';
            default:
                return 'pending';
        }
    }

    mapCategoryLabel(category) {
        const key = (category || 'general').toLowerCase();
        return this.categoryLabels[key] || this.categoryLabels.general;
    }

    renderCategoryPill(category) {
        const key = (category || 'general').toLowerCase();
        const label = this.mapCategoryLabel(key);
        const icon = this.categoryIcons[key] || this.categoryIcons.general;
        return `<span class="support-ticket-category ${key}">${icon} ${label}</span>`;
    }

    formatRelative(timestamp) {
        if (!timestamp) return '—';
        const now = Date.now();
        const diff = now - timestamp * 1000;
        const minutes = Math.floor(diff / 60000);
        if (minutes < 1) return 'щойно';
        if (minutes < 60) return `${minutes} хв`;
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return `${hours} год`;
        const days = Math.floor(hours / 24);
        return `${days} дн`;
    }

    formatDate(timestamp) {
        if (!timestamp) return '—';
        return new Date(timestamp * 1000).toLocaleDateString('uk-UA', {
            day: '2-digit',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text ?? '';
        return div.innerHTML;
    }
}

let supportCenter = null;

document.addEventListener('DOMContentLoaded', () => {
    supportCenter = new SupportCenter();
    supportCenter.init();
});

function openSupport() {
    supportCenter?.open();
}

function closeSupportModal() {
    supportCenter?.close();
}
