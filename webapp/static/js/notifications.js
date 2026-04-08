/**
 * Скрипт для работы с уведомлениями (модальное окно)
 */

let currentNotificationId = null;
let isLoadingNotifications = false;

/**
 * Открывает модальное окно уведомлений
 */
function openNotificationsModal() {
    console.log('[Notifications] openNotificationsModal called');
    try {
        const modal = document.getElementById('notificationsModal');
        if (!modal) {
            console.error('[Notifications] ERROR: notificationsModal element not found!');
            // Показываем alert пользователю
            if (typeof telegramWebApp !== 'undefined' && telegramWebApp.showAlert) {
                telegramWebApp.showAlert('Помилка: модальне вікно уведомлень не знайдено. Перезавантажте сторінку.');
            } else {
                alert('Помилка: модальне вікно уведомлень не знайдено. Перезавантажте сторінку.');
            }
            return;
        }
        
        console.log('[Notifications] Modal found, displaying...');
        modal.style.display = 'flex';
        modal.style.visibility = 'visible';
        modal.style.opacity = '1';
        
        // Загружаем уведомления
        loadNotificationsModal();
    } catch (error) {
        console.error('[Notifications] Error in openNotificationsModal:', error);
        if (typeof telegramWebApp !== 'undefined' && telegramWebApp.showAlert) {
            telegramWebApp.showAlert('Помилка відкриття уведомлень: ' + error.message);
        } else {
            alert('Помилка відкриття уведомлень: ' + error.message);
        }
    }
}

/**
 * Закрывает модальное окно уведомлений
 */
function closeNotificationsModal() {
    console.log('[Notifications] closeNotificationsModal called');
    try {
        const modal = document.getElementById('notificationsModal');
        if (modal) {
            modal.style.display = 'none';
            modal.style.visibility = 'hidden';
            modal.style.opacity = '0';
        }
    } catch (error) {
        console.error('[Notifications] Error in closeNotificationsModal:', error);
    }
}

/**
 * Загружает уведомления в модальное окно
 */
async function loadNotificationsModal() {
    if (isLoadingNotifications) {
        console.log('[Notifications] Already loading, skipping...');
        return;
    }
    
    isLoadingNotifications = true;
    const list = document.getElementById('notificationsListModal');
    const emptyState = document.getElementById('emptyStateModal');
    
    if (!list || !emptyState) {
        isLoadingNotifications = false;
        return;
    }
    
    // Показываем состояние загрузки
    list.style.display = 'block';
    emptyState.style.display = 'none';
    list.innerHTML = `
        <div class="loading-message" style="text-align: center; padding: 40px; color: var(--text-secondary);">
            <div style="font-size: 48px; margin-bottom: 16px;">⏳</div>
            <div>Завантаження...</div>
        </div>
    `;
    
    try {
        // Проверяем доступность API
        if (typeof api === 'undefined' || !api) {
            throw new Error('API не завантажено. Перезавантажте сторінку.');
        }
        
        console.log('[Notifications] Loading notifications...');
        const data = await api.getNotifications(false, 100);
        console.log('[Notifications] Received data:', data);
        
        const notifications = data.notifications || [];
        
        if (notifications.length === 0) {
            list.style.display = 'none';
            emptyState.style.display = 'block';
            isLoadingNotifications = false;
            return;
        }
        
        list.style.display = 'block';
        emptyState.style.display = 'none';
        
        // Группируем по датам
        const grouped = groupNotificationsByDate(notifications);
        
        list.innerHTML = Object.keys(grouped).map(date => {
            const dateNotifications = grouped[date];
            return `
                <div class="date-group">
                    <div class="date-divider">${formatDateHeader(date)}</div>
                    ${dateNotifications.map(notif => renderNotification(notif)).join('')}
                </div>
            `;
        }).join('');
        
        // Обновляем счетчик
        updateNotificationsBadge(data.unread_count || 0);
        console.log('[Notifications] Loaded successfully');
    } catch (error) {
        console.error('[Notifications] Error loading notifications:', error);
        list.innerHTML = `
            <div class="error-message" style="text-align: center; padding: 40px; color: #f5576c;">
                <div style="font-size: 48px; margin-bottom: 16px;">❌</div>
                <div>Помилка завантаження уведомлень</div>
                <div style="font-size: 12px; margin-top: 8px; opacity: 0.7;">${error.message || 'Невідома помилка'}</div>
            </div>
        `;
    } finally {
        isLoadingNotifications = false;
    }
}

/**
 * Группирует уведомления по датам
 */
function groupNotificationsByDate(notifications) {
    const grouped = {};
    notifications.forEach(notif => {
        const date = new Date(notif.created_at * 1000);
        const dateKey = date.toDateString();
        if (!grouped[dateKey]) {
            grouped[dateKey] = [];
        }
        grouped[dateKey].push(notif);
    });
    return grouped;
}

/**
 * Форматирует заголовок даты
 */
function formatDateHeader(dateString) {
    const date = new Date(dateString);
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    
    if (date.toDateString() === today.toDateString()) {
        return 'Сьогодні';
    } else if (date.toDateString() === yesterday.toDateString()) {
        return 'Вчора';
    } else {
        return date.toLocaleDateString('uk-UA', { day: 'numeric', month: 'long', year: 'numeric' });
    }
}

function notificationTypeClass(type) {
    if (!type) return '';
    if (type === 'deposit' || type === 'withdraw') return 'finance';
    if (typeof type === 'string' && type.startsWith('garden')) return 'garden';
    return '';
}

function renderNotificationTags(notif) {
    const data = notif.data || {};
    const tags = [];
    if (typeof data.amount !== 'undefined') {
        tags.push(`<span class="message-tag amount">Сума: ${formatCurrency(data.amount)}₴</span>`);
    }
    if (data.status) {
        const statusMap = {
            pending: 'Очікує',
            approved: 'Підтверджено',
            done: 'Підтверджено',
            rejected: 'Відхилено'
        };
        const cls = data.status === 'pending'
            ? 'pending'
            : (data.status === 'rejected' ? 'rejected' : 'approved');
        tags.push(`<span class="status-chip ${cls}">${statusMap[data.status] || data.status}</span>`);
    }
    if (data.tree_type && notif.type === 'garden_water') {
        tags.push(`<span class="message-tag">Дерево: ${escapeHtml(String(data.tree_type))}</span>`);
    }
    if (!tags.length) return '';
    return `<div class="message-tags">${tags.join('')}</div>`;
}

function formatCurrency(value) {
    const num = parseFloat(value || 0);
    if (isNaN(num)) return '0.00';
    return num.toFixed(2);
}

/**
 * Рендерит одно уведомление
 */
function renderNotification(notif) {
    const date = new Date(notif.created_at * 1000);
    const timeStr = date.toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' });
    
    const icons = {
        'balance_change': '💰',
        'deposit': '💵',
        'withdraw': '💸',
        'news': '📰',
        'promo': '🎁',
        'garden': '🌿',
        'support_reply': '💬',
        'support_status': '🛠',
        'beta': '🧪',
        'gift': '🎁',
        'info': 'ℹ️'
    };
    
    const icon = icons[notif.type] || '🔔';
    const isUnread = !notif.is_read;
    const typeClass = notificationTypeClass(notif.type);
    const tags = renderNotificationTags(notif);
    
    return `
        <div class="chat-message ${typeClass} ${isUnread ? 'unread' : ''}" onclick="openNotificationDetail(${notif.id}, '${escapeHtml(notif.title)}', '${escapeHtml(notif.message)}', '${icon}', ${notif.created_at}, ${notif.is_read})">
            <div class="message-avatar">${icon}</div>
            <div class="message-content">
                <div class="message-header">
                    <span class="message-title">${escapeHtml(notif.title)}</span>
                    <span class="message-time">${timeStr}</span>
                </div>
                <div class="message-text">${escapeHtml(notif.message)}</div>
                ${tags}
                ${isUnread ? '<div class="unread-indicator"></div>' : ''}
            </div>
        </div>
    `;
}

/**
 * Открывает детальное окно уведомления
 */
function openNotificationDetail(id, title, message, icon, createdAt, isRead) {
    currentNotificationId = id;
    const date = new Date(createdAt * 1000);
    const dateStr = date.toLocaleString('uk-UA', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
    
    document.getElementById('notificationDetailTitle').textContent = title;
    document.getElementById('notificationDetailIcon').textContent = icon;
    document.getElementById('notificationDetailMessage').textContent = message;
    document.getElementById('notificationDetailDate').textContent = dateStr;
    
    const modal = document.getElementById('notificationDetailModal');
    modal.style.display = 'flex';
    
    // Отмечаем как прочитанное при открытии
    if (!isRead) {
        markNotificationAsRead(id);
    }
}

/**
 * Закрывает детальное окно уведомления
 */
function closeNotificationDetailModal() {
    document.getElementById('notificationDetailModal').style.display = 'none';
    currentNotificationId = null;
    loadNotificationsModal(); // Обновляем список
}

/**
 * Отмечает текущее уведомление как прочитанное
 */
async function markCurrentNotificationAsRead() {
    if (currentNotificationId) {
        await markNotificationAsRead(currentNotificationId);
        closeNotificationDetailModal();
    }
}

/**
 * Удаляет текущее уведомление
 */
async function deleteCurrentNotification() {
    if (currentNotificationId) {
        await deleteNotificationById(currentNotificationId);
        closeNotificationDetailModal();
    }
}

/**
 * Отмечает уведомление как прочитанное
 */
async function markNotificationAsRead(notificationId) {
    try {
        await api.markNotificationRead(notificationId);
        loadNotificationsModal();
        // Обновляем счетчик в header
        updateNotificationsBadge();
    } catch (error) {
        console.error('Error marking as read:', error);
    }
}

/**
 * Удаляет уведомление
 */
async function deleteNotificationById(notificationId) {
    try {
        await api.deleteNotification(notificationId);
        loadNotificationsModal();
        // Обновляем счетчик в header
        updateNotificationsBadge();
    } catch (error) {
        console.error('Error deleting notification:', error);
    }
}

/**
 * Отмечает все уведомления как прочитанные
 */
async function markAllNotificationsAsRead() {
    try {
        await api.markAllNotificationsRead();
        loadNotificationsModal();
        // Обновляем счетчик в header
        updateNotificationsBadge();
    } catch (error) {
        console.error('Error marking all as read:', error);
    }
}

/**
 * Обновляет счетчик уведомлений в header
 */
async function updateNotificationsBadge(count) {
    if (count === undefined) {
        try {
            const data = await api.getUnreadNotificationsCount();
            count = data.unread_count || 0;
        } catch (error) {
            console.error('Error getting unread count:', error);
            return;
        }
    }
    
    const badge = document.getElementById('notificationsBadge');
    if (badge) {
        if (count > 0) {
            badge.textContent = count > 99 ? '99+' : count;
            badge.style.display = 'block';
        } else {
            badge.style.display = 'none';
        }
    }
}

/**
 * Экранирует HTML
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', () => {
    // Обработчик кнопки "Прочитати всі"
    const markAllBtn = document.getElementById('markAllReadBtnModal');
    if (markAllBtn) {
        markAllBtn.addEventListener('click', markAllNotificationsAsRead);
    }
    
    // Обновляем счетчик при загрузке
    updateNotificationsBadge();
    
    // Обновляем счетчик каждые 30 секунд
    setInterval(updateNotificationsBadge, 30000);
});

