/**
 * Основная логика приложения
 */

// Глобальный объект Telegram WebApp.
// Если файл telegram-webapp.js уже создал window.telegramWebApp – используем его.
// Если нет (например, открыто по прямому URL в браузере) – создаём простую заглушку.
if (typeof telegramWebApp === 'undefined') {
    window.telegramWebApp = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : {
        ready: () => {},
        expand: () => {},
        getTheme: () => 'light',
        showAlert: (message) => alert(message)
    };
}

function safeShowAlert(message) {
    try {
        if (telegramWebApp && typeof telegramWebApp.showAlert === 'function') {
            telegramWebApp.showAlert(message);
        } else {
            alert(message);
        }
    } catch (error) {
        alert(message);
    }
}

// Глобальные переменные
let currentUser = null;
let userData = null;
let maintenanceModeActive = false;

/**
 * Инициализация приложения
 */
async function initApp() {
    try {
        console.log('[App] Initializing...');
        
        // Устанавливаем тему Telegram
        const theme = telegramWebApp && typeof telegramWebApp.getTheme === 'function'
            ? telegramWebApp.getTheme()
            : 'light';
        if (theme === 'dark') {
            document.body.classList.add('dark-theme');
        }
        
        if (typeof telegramWebApp.ready === 'function') {
            telegramWebApp.ready();
        }
        if (typeof telegramWebApp.expand === 'function') {
            telegramWebApp.expand();
        }
        
        // Загружаем данные пользователя
        try {
            await loadUserData();
        } catch (error) {
            if (error.isMaintenance) {
                // Не показываем overlay - страница maintenance уже отображается сервером
                console.warn('[App] Maintenance mode is active, stopping init');
                return;
            }
            throw error;
        }
        
        // Настраиваем навигацию
        setupNavigation();
        setupNotificationsBell();
        
        console.log('[App] Initialized successfully');
    } catch (error) {
        console.error('[App] Initialization error:', error);
        safeShowAlert('Помилка ініціалізації: ' + error.message);
    }
}

/**
 * Глобальный обработчик клика по колокольчику уведомлений
 */
function handleNotificationClick(event) {
    if (event && typeof event.preventDefault === 'function') {
        event.preventDefault();
    }

    try {
        console.log('[UI] notifications bell clicked');
        if (typeof openNotificationsModal === 'function') {
            openNotificationsModal();
        } else {
            console.error('openNotificationsModal is not defined');
            safeShowAlert('Помилка: модальне вікно уведомлень не завантажилося. Оновіть сторінку.');
        }
    } catch (error) {
        console.error('Error on notifications bell click:', error);
        safeShowAlert('Помилка відкриття уведомлень: ' + (error.message || error));
    }
}
window.handleNotificationClick = handleNotificationClick;


/**
 * Загружает данные пользователя
 */
async function loadUserData() {
    try {
        console.log('[App] Loading user data...');
        // Добавляем таймаут для запроса
        const timeoutPromise = new Promise((_, reject) => {
            setTimeout(() => reject(new Error('Request timeout')), 10000); // 10 секунд
        });
        
        const dataPromise = api.getUserInfo();
        const data = await Promise.race([dataPromise, timeoutPromise]);
        
        console.log('[App] User data received:', data);
        currentUser = data;
        userData = data;
        
        // Отладочная информация
        console.log('[App] User data loaded:', {
            user_id: data.user_id,
            user_name: data.user_name,
            balance: data.balance,
            is_admin: data.is_admin,
            is_telegram_user: data.is_telegram_user
        });
        
        // Обновляем UI
        updateUserUI(data);

        if (window.brandingNewsManager) {
            if (data.branding) {
                window.brandingNewsManager.setBrandingData(data.branding);
            }
            if (data.news && typeof data.news.unread_count !== 'undefined') {
                window.brandingNewsManager.setUnreadCount(data.news.unread_count);
            }
        }
        window.dispatchEvent(new CustomEvent('userDataLoaded', { detail: data }));
        
        // Проверяем, что данные загрузились правильно
        if (!data.user_id) {
            console.error('[App] ERROR: user_id is missing!');
        }
        if (data.balance === undefined || data.balance === null) {
            console.error('[App] ERROR: balance is missing!');
        }
        
        // Показываем админку ТОЛЬКО если пользователь действительно админ
        const adminCard = document.getElementById('adminCard');
        if (adminCard) {
            console.log('[App] Admin card found, checking admin status...');
            console.log('[App] is_admin value:', data.is_admin, 'type:', typeof data.is_admin);
            
            // Принимаем true, 1 или строку '1' / 'true' (на всякий случай)
            const isAdmin = data.is_admin === true ||
                data.is_admin === 1 ||
                data.is_admin === '1' ||
                data.is_admin === 'true';
            
            if (isAdmin) {
                console.log('[App] ✅ User IS admin, showing admin card');
                adminCard.classList.add('admin-visible');
                adminCard.setAttribute('aria-hidden', 'false');
                const loginForm = document.getElementById('adminLoginForm');
                if (loginForm) {
                    loginForm.style.display = 'none';
                }
            } else {
                console.log('[App] ❌ User is NOT admin, hiding admin card');
                adminCard.classList.remove('admin-visible');
                adminCard.setAttribute('aria-hidden', 'true');
            }
        } else {
            // Admin card может отсутствовать на некоторых страницах (например, garden) - это нормально
            console.log('[App] ℹ️ Admin card element not found (may not exist on this page)');
        }
        
        // Обновляем счетчик уведомлений
        updateNotificationsBadge();
        
        return data;
    } catch (error) {
        console.error('[App] Error loading user data:', error);
        
        // Показываем ошибку пользователю
        const userNameElements = document.querySelectorAll('#userName, .user-name');
        userNameElements.forEach(el => {
            if (el) {
                el.textContent = 'Помилка завантаження';
            }
        });
        
        // Показываем сообщение об ошибке
        if (error.message && !error.isMaintenance) {
            console.error('[App] Full error:', error);
            // Не показываем alert для maintenance - это обрабатывается отдельно
            if (typeof safeShowAlert === 'function') {
                safeShowAlert('Помилка завантаження даних. Спробуйте оновити сторінку.');
            }
        }
        
        throw error;
    }
}

/**
 * Обновляет UI с данными пользователя
 */
function updateUserUI(data) {
    console.log('[App] updateUserUI called with data:', data);
    
    // Имя пользователя - приоритет: user_name из API → telegram.first_name → fallback
    const userNameElements = document.querySelectorAll('#userName, .user-name');
    userNameElements.forEach(el => {
        if (el) {
            // Приоритет: user_name из API (самый надежный источник)
            let userName = data.user_name;
            
            // Приоритет для отображения: username из Telegram → first_name → user_name → fallback
            if (!userName || userName.trim() === '' || userName === 'Користувач' || userName === 'Гість' || userName === 'Гость') {
                // Сначала пробуем username из Telegram (это ник)
                userName = (data.telegram && data.telegram.username) || data.username || null;
            }
            
            // Если username нет, используем first_name
            if (!userName || userName.trim() === '' || userName === 'Гість' || userName === 'Гость') {
                userName = (data.telegram && data.telegram.first_name) || data.user_name || null;
            }
            
            // Если все еще пустое, используем fallback
            if (!userName || userName.trim() === '') {
                userName = 'Користувач';
            }
            
            el.textContent = userName;
            console.log('[App] Updated user name:', userName, '(from user_name:', data.user_name, ', telegram:', (data.telegram && data.telegram.first_name) || 'N/A', ')');
        }
    });
    
    // ID пользователя - ВСЕГДА показываем для всех пользователей
    const userIdElements = document.querySelectorAll('#userId, .user-id');
    userIdElements.forEach(el => {
        if (el) {
            // Приоритет: user_id из API → telegram.id → fallback
            const userId = data.user_id || (data.telegram && data.telegram.id) || '—';
            el.textContent = 'ID: ' + userId;
            // Убеждаемся, что элемент видим
            el.style.display = '';
            el.style.visibility = 'visible';
            el.style.opacity = '1';
            console.log('[App] Updated user ID:', userId, '(from user_id:', data.user_id, ', telegram:', (data.telegram && data.telegram.id) || 'N/A', ')');
        }
    });
    
    // Аватарка пользователя из Telegram
    const avatarElements = document.querySelectorAll('#userAvatar, .user-avatar, .profile-avatar');
    avatarElements.forEach(userAvatar => {
        if (!userAvatar) return;
        
        const avatarImg = userAvatar.querySelector('img');
        const avatarPlaceholder = userAvatar.querySelector('.avatar-placeholder');
        
        // Пробуем получить photo_url из разных источников
        let photoUrl = null;
        
        // 1. Из Telegram WebApp напрямую (приоритет - самый надежный источник)
        if (!photoUrl) {
            try {
                const tgApp = window.telegramWebApp || (window.Telegram && window.Telegram.WebApp);
                if (tgApp && tgApp.initDataUnsafe && tgApp.initDataUnsafe.user) {
                    photoUrl = tgApp.initDataUnsafe.user.photo_url;
                    console.log('[App] Got photo_url from Telegram WebApp:', photoUrl);
                }
            } catch (e) {
                console.warn('[App] Could not get photo_url from Telegram WebApp:', e);
            }
        }
        
        // 2. Из API ответа
        if (!photoUrl && data.telegram && data.telegram.photo_url) {
            photoUrl = data.telegram.photo_url;
            console.log('[App] Got photo_url from API:', photoUrl);
        }
        
        // Если есть фото - показываем его
        if (photoUrl) {
            if (!avatarImg) {
                const img = document.createElement('img');
                img.src = photoUrl;
                img.alt = data.user_name || 'User';
                img.style.width = '100%';
                img.style.height = '100%';
                img.style.borderRadius = '50%';
                img.style.objectFit = 'cover';
                img.onerror = () => {
                    // Если фото не загрузилось, показываем placeholder
                    if (avatarPlaceholder) {
                        avatarPlaceholder.style.display = 'flex';
                    }
                    if (img.parentNode) {
                        img.parentNode.removeChild(img);
                    }
                };
                userAvatar.appendChild(img);
            } else {
                avatarImg.src = photoUrl;
            }
            if (avatarPlaceholder) {
                avatarPlaceholder.style.display = 'none';
            }
        } else if (avatarPlaceholder) {
            // Если фото нет - показываем placeholder
            avatarPlaceholder.style.display = 'flex';
            if (avatarImg) {
                avatarImg.remove();
            }
        }
    }
    
    // Рефералы
    const refCountEl = document.getElementById('refCount');
    const userRefsEl = document.getElementById('userRefs');
    if (refCountEl && userRefsEl) {
        const refCount = data.ref_count || 0;
        refCountEl.textContent = refCount;
        if (refCount > 0) {
            userRefsEl.style.display = 'inline-flex';
        } else {
            userRefsEl.style.display = 'none';
        }
    }
    
    // Баланс - показываем только если больше 0
    const balanceItem = document.getElementById('balanceItem');
    const balanceElements = document.querySelectorAll('#userBalance, .user-balance');
    const balance = data.balance || 0;
    balanceElements.forEach(el => {
        if (el) {
            el.textContent = formatCurrency(balance) + ' UAH';
        }
    });
    if (balanceItem) {
        if (balance > 0) {
            balanceItem.style.display = 'flex';
        } else {
            balanceItem.style.display = 'none';
        }
    }
    
    // Депозиты - показываем только если больше 0
    const depositsItem = document.getElementById('depositsItem');
    const depositsEl = document.getElementById('userDeposits');
    const deposits = data.deposits_sum || data.deposits || 0;
    if (depositsEl) {
        depositsEl.textContent = formatCurrency(deposits) + ' UAH';
    }
    if (depositsItem) {
        if (deposits > 0) {
            depositsItem.style.display = 'flex';
        } else {
            depositsItem.style.display = 'none';
        }
    }
    
    // Аватарка
    // Дополнительная обработка аватарок (если нужно)
    // Основная логика уже обработана выше в avatarElements.forEach
}

/**
 * Форматирует валюту
 */
function formatCurrency(amount) {
    return parseFloat(amount || 0).toFixed(2);
}

/**
 * Настраивает навигацию
 */
function setupNavigation() {
    // Обработка кликов по карточкам меню
    const menuCards = document.querySelectorAll('.menu-card');
    menuCards.forEach(card => {
        card.addEventListener('click', (e) => {
            // Анимация клика
            card.style.transform = 'scale(0.95)';
            setTimeout(() => {
                card.style.transform = '';
            }, 150);
        });
    });
}

/**
 * Навешивает обработчик на иконку уведомлений
 */
function setupNotificationsBell() {
    const bell = document.getElementById('notificationsIcon');
    if (!bell) {
        // Notifications icon может отсутствовать на некоторых страницах - это нормально
        console.log('[UI] ℹ️ notificationsIcon element not found (may not exist on this page)');
        return;
    }

    // На всякий случай удаляем прошлые обработчики
    bell.removeEventListener('click', handleNotificationClick);

    bell.addEventListener(
        'click',
        (event) => {
            console.log('[UI] notifications icon event fired', {
                target: (event.target && event.target.id) || null,
                currentTarget: (event.currentTarget && event.currentTarget.id) || null
            });
            handleNotificationClick(event);
        },
        { passive: false }
    );
}

function showMaintenanceOverlay(message) {
    const overlay = document.getElementById('maintenanceOverlay');
    if (!overlay) return;
    const textEl = overlay.querySelector('.maintenance-message');
    if (textEl && message) {
        textEl.textContent = message;
    }
    overlay.classList.add('active');
    overlay.setAttribute('aria-hidden', 'false');
    maintenanceModeActive = true;
}

function hideMaintenanceOverlay() {
    const overlay = document.getElementById('maintenanceOverlay');
    if (!overlay) return;
    overlay.classList.remove('active');
    overlay.setAttribute('aria-hidden', 'true');
    maintenanceModeActive = false;
}

function handleMaintenanceFromApi(message) {
    if (maintenanceModeActive) return;
    showMaintenanceOverlay(message || 'Ми оновлюємо систему. Спробуйте трохи пізніше.');
}

window.handleMaintenanceFromApi = handleMaintenanceFromApi;

/**
 * Обработчики действий главного меню
 * Теперь все функции доступны через прямые ссылки на страницы
 */

/**
 * Показывает уведомление
 */
function showNotification(message, type = 'info') {
    // Можно добавить красивую систему уведомлений
    safeShowAlert(message);
}

/**
 * Обработка ошибок
 */
window.addEventListener('error', (event) => {
    console.error('[App] Global error:', event.error);
});

window.addEventListener('unhandledrejection', (event) => {
    console.error('[App] Unhandled promise rejection:', event.reason);
});

/**
 * Обновляет счетчик уведомлений в header
 */
async function updateNotificationsBadge() {
    try {
        const data = await api.getUnreadNotificationsCount();
        const badge = document.getElementById('notificationsBadge');
        if (badge) {
            const count = data.unread_count || 0;
            if (count > 0) {
                badge.textContent = count > 99 ? '99+' : count;
                badge.style.display = 'block';
            } else {
                badge.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Error updating notifications badge:', error);
    }
}

// Инициализация при загрузке DOM
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}

// Обновляем счетчик уведомлений каждые 30 секунд
if (typeof setInterval !== 'undefined') {
    setInterval(updateNotificationsBadge, 30000);
}

