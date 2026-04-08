/**
 * Интеграция с Telegram WebApp API
 */

class TelegramWebApp {
    constructor() {
        this.tg = null;
        this.initData = null;
        this.user = null;
        
        // Проверяем, запущено ли в Telegram
        if (typeof window !== 'undefined' && window.Telegram && window.Telegram.WebApp) {
            this.tg = window.Telegram.WebApp;
            this.tg.ready();
            this.tg.expand();
            
            // Получаем initData
            this.initData = this.tg.initData;
            
            // Получаем данные пользователя
            if (this.tg.initDataUnsafe && this.tg.initDataUnsafe.user) {
                this.user = this.tg.initDataUnsafe.user;
            }
            
            console.log('[TelegramWebApp] Initialized in Telegram');
        } else {
            console.warn('[TelegramWebApp] Not running in Telegram, using mock data');
            // Для разработки вне Telegram
            this.user = {
                id: 6029312631,
                first_name: 'Test',
                username: 'test_user'
            };
        }
    }
    
    /**
     * Получает данные пользователя
     */
    getUser() {
        return this.user;
    }
    
    /**
     * Получает initData для отправки на сервер
     */
    getInitData() {
        return this.initData || '';
    }
    
    /**
     * Показывает главную кнопку
     */
    showMainButton(text, callback) {
        if (this.tg) {
            this.tg.MainButton.setText(text);
            this.tg.MainButton.onClick(callback);
            this.tg.MainButton.show();
        }
    }
    
    /**
     * Скрывает главную кнопку
     */
    hideMainButton() {
        if (this.tg) {
            this.tg.MainButton.hide();
        }
    }
    
    /**
     * Показывает алерт
     */
    showAlert(message) {
        if (this.tg) {
            this.tg.showAlert(message);
        } else {
            alert(message);
        }
    }
    
    /**
     * Показывает подтверждение
     */
    showConfirm(message, callback) {
        if (this.tg) {
            this.tg.showConfirm(message, callback);
        } else {
            if (confirm(message)) {
                callback(true);
            } else {
                callback(false);
            }
        }
    }
    
    /**
     * Открывает ссылку
     */
    openLink(url) {
        if (this.tg) {
            this.tg.openLink(url);
        } else {
            window.open(url, '_blank');
        }
    }
    
    /**
     * Закрывает WebApp
     */
    close() {
        if (this.tg) {
            this.tg.close();
        }
    }
    
    /**
     * Устанавливает цвет темы
     */
    setThemeColor(color) {
        if (this.tg) {
            this.tg.setHeaderColor(color);
            this.tg.setBackgroundColor(color);
        }
    }
    
    /**
     * Получает тему (light/dark)
     */
    getTheme() {
        if (this.tg) {
            return this.tg.colorScheme || 'light';
        }
        return 'light';
    }
}

// Создаем глобальный экземпляр
const telegramWebApp = new TelegramWebApp();

