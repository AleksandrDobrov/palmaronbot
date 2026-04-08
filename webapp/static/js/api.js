/**
 * API клиент для взаимодействия с бэкендом
 */

function resolveTelegramApp() {
    if (window.telegramWebApp) { return window.telegramWebApp; }
    if (window.Telegram) {
        if (window.Telegram.WebApp) { return window.Telegram.WebApp; }
        if (window.Telegram.webApp) { return window.Telegram.webApp; }
    }
    return null;
}

class API {
    constructor() {
        this.baseURL = window.location.origin;
        const tgApp = resolveTelegramApp();
        if (tgApp && typeof tgApp.getInitData === 'function') {
            try {
                this.initData = tgApp.getInitData();
            } catch (err) {
                console.warn('[API] getInitData failed:', err);
                this.initData = '';
            }
        } else {
            this.initData = '';
        }
    }
    
    /**
     * Выполняет запрос к API
     */
    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };
        
        // Добавляем initData для авторизации
        if (this.initData) {
            headers['X-Telegram-Init-Data'] = this.initData;
        }
        
        const config = {
            ...options,
            headers
        };
        
        try {
            const response = await fetch(url, config);
            let data = null;
            try {
                data = await response.json();
            } catch (jsonError) {
                console.warn('[API] Failed to parse JSON response', jsonError);
            }
            
            if (!response.ok) {
                const message = (data && (data.error || data.message)) || `HTTP ${response.status}`;
                const error = new Error(message);
                error.status = response.status;
                
                if (data && data.maintenance) {
                    error.isMaintenance = true;
                    error.maintenanceMessage = data.message || message;
                    if (typeof window.handleMaintenanceFromApi === 'function') {
                        window.handleMaintenanceFromApi(error.maintenanceMessage);
                    }
                }
                
                throw error;
            }
            
            return data || {};
        } catch (error) {
            console.error(`[API] Error in ${endpoint}:`, error);
            throw error;
        }
    }
    
    /**
     * GET запрос
     */
    async get(endpoint) {
        return this.request(endpoint, { method: 'GET' });
    }
    
    /**
     * POST запрос
     */
    async post(endpoint, data) {
        return this.request(endpoint, {
            method: 'POST',
            body: JSON.stringify(data)
        });
    }
    
    /**
     * DELETE запрос
     */
    async delete(endpoint) {
        return this.request(endpoint, { method: 'DELETE' });
    }
    
    /**
     * Получает информацию о пользователе
     */
    async getUserInfo() {
        return this.get('/api/user/info');
    }
    
    /**
     * Получает данные кабинета
     */
    async getCabinetData() {
        return this.get('/api/user/cabinet');
    }
    
    /**
     * Получает данные админ-панели
     */
    async getAdminPanelData() {
        return this.get('/api/admin/panel');
    }
    
    /**
     * Выполняет действие пользователя
     */
    async userAction(action, data = {}) {
        return this.post('/api/user/action', {
            action,
            ...data
        });
    }
    
    /**
     * Выполняет админское действие
     */
    async adminAction(action, data = {}) {
        return this.post('/api/admin/action', {
            action,
            params: data
        });
    }
    
    /**
     * Получает рефералов пользователя
     */
    async getReferrals() {
        return this.get('/api/user/referrals');
    }
    
    /**
     * Создает депозит
     */
    async createDeposit(amount, comment = '') {
        return this.post('/api/user/deposit', {
            amount,
            comment
        });
    }
    
    /**
     * Создает вывод
     */
    async createWithdraw(amount, requisites) {
        return this.post('/api/user/withdraw', {
            amount,
            requisites
        });
    }
    
    /**
     * Получает список пользователей (админ)
     */
    async getAdminUsers() {
        return this.get('/api/admin/users');
    }
    
    /**
     * Изменяет баланс пользователя (админ)
     */
    async changeUserBalance(userId, amount, action = 'add') {
        return this.post('/api/admin/balance/change', {
            user_id: userId,
            amount,
            action
        });
    }
    
    /**
     * Получает список депозитов (админ)
     */
    async getAdminDeposits(status = null) {
        const url = status ? `/api/admin/deposits?status=${status}` : '/api/admin/deposits';
        return this.get(url);
    }
    
    /**
     * Получает список выводов (админ)
     */
    async getAdminWithdrawals(status = null) {
        const url = status ? `/api/admin/withdrawals?status=${status}` : '/api/admin/withdrawals';
        return this.get(url);
    }
    
    /**
     * Получает задания пользователя
     */
    async getUserTasks() {
        return this.get('/api/user/tasks');
    }
    
    /**
     * Проверяет выполнение задания
     */
    async checkTask(taskId) {
        return this.post(`/api/user/tasks/${taskId}/check`, {});
    }
    
    /**
     * Получает все задания (админ)
     */
    async getAdminTasks(status = null) {
        const url = status ? `/api/admin/tasks?status=${status}` : '/api/admin/tasks';
        return this.get(url);
    }
    
    /**
     * Получает детали задания (админ)
     */
    async getAdminTaskDetail(taskId) {
        return this.get(`/api/admin/tasks/${taskId}`);
    }
    
    /**
     * Создает задание (админ)
     */
    async createTask(taskData) {
        return this.post('/api/admin/action', {
            action: 'create_task',
            params: taskData
        });
    }
    
    /**
     * Обновляет статус задания (админ)
     */
    async updateTaskStatus(taskId, status) {
        return this.post('/api/admin/action', {
            action: 'update_task_status',
            params: {
                task_id: taskId,
                status: status
            }
        });
    }

    /**
     * Получает налаштування дерев (адмін)
     */
    async getAdminTreeSettings() {
        return this.get('/api/admin/garden/prices/tree');
    }

    /**
     * Оновлює ціну/дохід дерева (адмін)
     */
    async updateAdminTreeSetting(treeType, { price = null, income = null } = {}) {
        return this.post('/api/admin/garden/prices/tree', {
            tree_type: treeType,
            price,
            income
        });
    }

    /**
     * Отримує ціни фруктів (адмін)
     */
    async getAdminFruitSettings() {
        return this.get('/api/admin/garden/prices/fruit');
    }

    /**
     * Оновлює ціну фрукту (адмін)
     */
    async updateAdminFruitPrice(fruitType, price) {
        return this.post('/api/admin/garden/prices/fruit', {
            fruit_type: fruitType,
            price
        });
    }

    /**
     * Інформація про сад користувача (адмін)
     */
    async getAdminGardenUser(userId) {
        return this.get(`/api/admin/garden/user/${userId}`);
    }

    /**
     * Встановлює рівень саду (адмін)
     */
    async adminSetGardenLevel(userId, level, reason = '') {
        return this.post(`/api/admin/garden/user/${userId}/set_level`, {
            level,
            reason
        });
    }

    /**
     * Додає дерево користувачу (адмін)
     */
    async adminAddGardenTree(userId, treeType, count) {
        return this.post(`/api/admin/garden/user/${userId}/add_tree`, {
            tree_type: treeType,
            count
        });
    }

    /**
     * Видаляє дерево користувача (адмін)
     */
    async adminRemoveGardenTree(userId, treeType, count) {
        return this.post(`/api/admin/garden/user/${userId}/remove_tree`, {
            tree_type: treeType,
            count
        });
    }

    /**
     * Додає фрукти користувачу (адмін)
     */
    async adminAddGardenFruit(userId, fruitType, amount) {
        return this.post(`/api/admin/garden/user/${userId}/add_fruit`, {
            fruit_type: fruitType,
            amount
        });
    }

    /**
     * Видаляє фрукти користувача (адмін)
     */
    async adminRemoveGardenFruit(userId, fruitType, amount) {
        return this.post(`/api/admin/garden/user/${userId}/remove_fruit`, {
            fruit_type: fruitType,
            amount
        });
    }
    
    /**
     * Получает данные сада
     */
    async getGarden() {
        return this.get('/api/user/garden');
    }
    
    /**
     * Покупает дерево
     */
    async buyTree(treeType) {
        return this.post('/api/user/garden/buy_tree', {
            tree_type: treeType
        });
    }
    
    /**
     * Собирает урожай
     */
    async harvestFruits() {
        return this.post('/api/user/garden/harvest', {});
    }
    
    /**
     * Продает фрукты
     */
    async sellFruits(fruitType, amount) {
        return this.post('/api/user/garden/sell_fruits', {
            fruit_type: fruitType,
            amount: amount
        });
    }
    
    /**
     * Повышает уровень сада
     */
    async upgradeGardenLevel() {
        return this.post('/api/user/garden/upgrade_level', {});
    }
    
    /**
     * Поливает дерево
     */
    async waterTree(treeType) {
        return this.post('/api/user/garden/water_tree', {
            tree_type: treeType
        });
    }
    
    /**
     * Получает цены на деревья
     */
    async getTreePrices() {
        return this.get('/api/user/garden/tree_prices');
    }

    /**
     * Завантажує новини користувача
     */
    async getNews(limit = 3) {
        return this.get(`/api/user/news?limit=${limit}`);
    }

    /**
     * Позначає новину як переглянуту / вподобану
     */
    async markNewsViewed(newsId, payload = {}) {
        return this.post(`/api/user/news/${newsId}/view`, payload);
    }
    
    /**
     * Получает уведомления пользователя
     */
    async getNotifications(unreadOnly = false, limit = 50) {
        const url = `/api/user/notifications?unread_only=${unreadOnly}&limit=${limit}`;
        return this.get(url);
    }
    
    /**
     * Получает количество непрочитанных уведомлений
     */
    async getUnreadNotificationsCount() {
        return this.get('/api/user/notifications/unread/count');
    }
    
    /**
     * Отмечает уведомление как прочитанное
     */
    async markNotificationRead(notificationId) {
        return this.post(`/api/user/notifications/${notificationId}/read`, {});
    }
    
    /**
     * Отмечает все уведомления как прочитанные
     */
    async markAllNotificationsRead() {
        return this.post('/api/user/notifications/read-all', {});
    }
    
    /**
     * Удаляет уведомление
     */
    async deleteNotification(notificationId) {
        return this.delete(`/api/user/notifications/${notificationId}`);
    }

    /**
     * Історія операцій користувача
     */
    async getUserHistory(limit = 30) {
        const safeLimit = Math.min(Math.max(parseInt(limit, 10) || 30, 1), 200);
        return this.get(`/api/user/history?limit=${safeLimit}`);
    }

    /**
     * Список тікетів підтримки користувача
     */
    async getSupportTickets({ status = null, limit = 20, offset = 0, category = null } = {}) {
        const params = new URLSearchParams({
            limit: String(limit),
            offset: String(offset)
        });
        if (status) {
            params.set('status', status);
        }
        if (category) {
            params.set('category', category);
        }
        const query = params.toString();
        const endpoint = query ? `/api/user/support/tickets?${query}` : '/api/user/support/tickets';
        return this.get(endpoint);
    }

    /**
     * Створює тікет підтримки
     */
    async createSupportTicket(payload) {
        return this.post('/api/user/support/tickets', payload);
    }

    /**
     * Деталі тікета підтримки
     */
    async getSupportTicket(ticketId, { limit = 100, offset = 0 } = {}) {
        const params = new URLSearchParams({
            limit: String(limit),
            offset: String(offset)
        });
        return this.get(`/api/user/support/tickets/${ticketId}?${params.toString()}`);
    }

    /**
     * Відповідь користувача у тікеті
     */
    async replySupportTicket(ticketId, payload) {
        return this.post(`/api/user/support/tickets/${ticketId}/reply`, payload);
    }

    /**
     * Закриває тікет користувача
     */
    async closeSupportTicket(ticketId, payload = {}) {
        return this.post(`/api/user/support/tickets/${ticketId}/close`, payload);
    }

    /**
     * Непрочитані тікети користувача
     */
    async getSupportUnreadCount() {
        return this.get('/api/user/support/unread-count');
    }

    /**
     * Адмін: список тікетів
     */
    async getAdminSupportTickets({ status = null, assigned = null, search = null, userId = null, category = null, limit = 50, offset = 0 } = {}) {
        const params = new URLSearchParams({
            limit: String(limit),
            offset: String(offset)
        });
        if (status) params.set('status', Array.isArray(status) ? status.join(',') : status);
        if (assigned) params.set('assigned', assigned);
        if (search) params.set('search', search);
        if (userId) params.set('user_id', String(userId));
        if (category) params.set('category', category);
        const query = params.toString();
        const endpoint = query ? `/api/admin/support/tickets?${query}` : '/api/admin/support/tickets';
        return this.get(endpoint);
    }

    /**
     * Адмін: деталі тікета
     */
    async getAdminSupportTicket(ticketId, { limit = 200, offset = 0, includeInternal = true } = {}) {
        const params = new URLSearchParams({
            limit: String(limit),
            offset: String(offset),
            include_internal: includeInternal ? 'true' : 'false'
        });
        return this.get(`/api/admin/support/tickets/${ticketId}?${params.toString()}`);
    }

    /**
     * Адмін: відповідь у тікеті
     */
    async replyAdminSupportTicket(ticketId, payload) {
        return this.post(`/api/admin/support/tickets/${ticketId}/reply`, payload);
    }

    /**
     * Адмін: зміна статусу тікета
     */
    async updateAdminSupportTicketStatus(ticketId, payload) {
        return this.post(`/api/admin/support/tickets/${ticketId}/status`, payload);
    }

    /**
     * Адмін: скільки тікетів потребують відповіді
     */
    async getAdminSupportUnreadCount() {
        return this.get('/api/admin/support/unread-count');
    }

    /**
     * Адмін: список новин
     */
    async getAdminNews(limit = 50, includeDrafts = true, status = null) {
        const params = new URLSearchParams({
            limit: limit.toString(),
            include_drafts: includeDrafts ? '1' : '0'
        });
        if (status) {
            params.set('status', status);
        }
        return this.get(`/api/admin/news?${params.toString()}`);
    }

    /**
     * Адмін: створення новини
     */
    async createAdminNews(newsData) {
        return this.post('/api/admin/news', newsData);
    }

    /**
     * Адмін: оновлення новини
     */
    async updateAdminNews(newsId, newsData) {
        return this.request(`/api/admin/news/${newsId}`, {
            method: 'PUT',
            body: JSON.stringify(newsData)
        });
    }

    /**
     * Адмін: видалення новини
     */
    async deleteAdminNews(newsId) {
        return this.delete(`/api/admin/news/${newsId}`);
    }

    /**
     * Адмін: статистика окремої новини
     */
    async getAdminNewsStats(newsId) {
        return this.get(`/api/admin/news/${newsId}/stats`);
    }

    /**
     * Адмін: налаштування брендингу
     */
    async getBrandingSettings() {
        return this.get('/api/admin/branding');
    }

    /**
     * Адмін: збереження брендингу
     */
    async updateBrandingSettings(payload) {
        return this.post('/api/admin/branding', payload);
    }

    /**
     * Адмін: отримує налаштування подарунків
     */
    async getAdminGiftSettings() {
        return this.get('/api/admin/gift/settings');
    }

    /**
     * Адмін: оновлює налаштування подарунків
     */
    async updateAdminGiftSettings(payload) {
        return this.post('/api/admin/gift/settings', payload);
    }
    
    /**
     * Создает уведомление (админ)
     */
    async createNotification(userId, type, title, message, data = null) {
        return this.post('/api/admin/notifications/create', {
            user_id: userId,
            type,
            title,
            message,
            data
        });
    }
    
    /**
     * Создает промокод (админ)
     */
    async createPromoCode(code, rewardType, rewardValue, maxUses, expiry, itemType, itemValue) {
        return this.post('/api/admin/promo/create', {
            code,
            reward_type: rewardType,
            reward_value: rewardValue,
            max_uses: maxUses,
            expiry,
            item_type: itemType,
            item_value: itemValue
        });
    }
    
    /**
     * Получает список промокодов (админ)
     */
    async getPromoCodes() {
        return this.get('/api/admin/promo/list');
    }
    
    /**
     * Получает информацию о промокоде (админ)
     */
    async getPromoCodeInfo(code) {
        return this.get(`/api/admin/promo/${code}`);
    }
}

// Создаем глобальный экземпляр
const api = new API();

