/**
 * Скрипт для работы с админ-панелью
 */

/**
 * Показывает модальное окно промокодов
 */
function showPromoCodesModal() {
    const modal = document.getElementById('promoCodesModal');
    if (modal) {
        modal.style.display = 'flex';
        loadPromoCodesList();
    }
}

/**
 * Закрывает модальное окно промокодов
 */
function closePromoCodesModal() {
    const modal = document.getElementById('promoCodesModal');
    if (modal) {
        modal.style.display = 'none';
    }
    hideCreatePromoForm();
}

/**
 * Показывает форму создания промокода
 */
function showCreatePromoForm() {
    const form = document.getElementById('createPromoForm');
    if (form) {
        form.style.display = 'block';
        // Очищаем форму
        document.getElementById('promoCode').value = '';
        document.getElementById('promoRewardType').value = 'balance';
        document.getElementById('promoRewardValue').value = '';
        document.getElementById('promoItemType').value = '';
        document.getElementById('promoMaxUses').value = '0';
        document.getElementById('promoExpiry').value = '';
        document.getElementById('promoCreateStatus').innerHTML = '';
        updatePromoFormFields();
    }
}

/**
 * Скрывает форму создания промокода
 */
function hideCreatePromoForm() {
    const form = document.getElementById('createPromoForm');
    if (form) {
        form.style.display = 'none';
    }
}

/**
 * Обновляет поля формы в зависимости от типа награды
 */
function updatePromoFormFields() {
    const rewardType = document.getElementById('promoRewardType').value;
    const itemTypeContainer = document.getElementById('promoItemTypeContainer');
    
    if (rewardType === 'balance') {
        itemTypeContainer.style.display = 'none';
        document.getElementById('promoRewardValue').placeholder = '100';
        document.getElementById('promoRewardValue').step = '0.01';
    } else {
        itemTypeContainer.style.display = 'block';
        document.getElementById('promoRewardValue').placeholder = '1';
        document.getElementById('promoRewardValue').step = '1';
        
        // Подсказки для типов предметов
        let placeholder = '';
        if (rewardType === 'fruit') {
            placeholder = 'apple, banana, orange';
        } else if (rewardType === 'booster') {
            placeholder = 'speed_boost, harvest_boost';
        } else if (rewardType === 'tree') {
            placeholder = 'oak, apple_tree, cherry_tree';
        }
        document.getElementById('promoItemType').placeholder = placeholder;
    }
}

/**
 * Создает промокод
 */
async function createPromoCode() {
    const code = document.getElementById('promoCode').value.trim().toUpperCase();
    const rewardType = document.getElementById('promoRewardType').value;
    const rewardValue = parseFloat(document.getElementById('promoRewardValue').value);
    const maxUses = parseInt(document.getElementById('promoMaxUses').value) || null;
    const expiry = document.getElementById('promoExpiry').value.trim() || null;
    const itemType = document.getElementById('promoItemType').value.trim() || null;
    const statusDiv = document.getElementById('promoCreateStatus');
    
    // Валидация
    if (!code) {
        statusDiv.innerHTML = '<div class="error-message">Код промокоду не може бути порожнім</div>';
        return;
    }
    
    if (!rewardValue || rewardValue <= 0) {
        statusDiv.innerHTML = '<div class="error-message">Значення винагороди повинно бути більше 0</div>';
        return;
    }
    
    if (rewardType !== 'balance' && !itemType) {
        statusDiv.innerHTML = '<div class="error-message">Тип предмета обов\'язковий для цього типу винагороди</div>';
        return;
    }
    
    statusDiv.innerHTML = '<div style="color: #4facfe;">⏳ Створення промокоду...</div>';
    
    try {
        const response = await fetch('/api/admin/promo/create', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                code: code,
                reward_type: rewardType,
                reward_value: rewardType === 'balance' ? rewardValue : Math.floor(rewardValue),
                max_uses: maxUses === 0 ? null : maxUses,
                expiry: expiry,
                item_type: itemType,
                item_value: null
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.status === 'ok') {
            statusDiv.innerHTML = '<div class="success-message">✅ Промокод успішно створено!</div>';
            // Очищаем форму
            document.getElementById('promoCode').value = '';
            document.getElementById('promoRewardValue').value = '';
            document.getElementById('promoItemType').value = '';
            document.getElementById('promoMaxUses').value = '0';
            document.getElementById('promoExpiry').value = '';
            // Обновляем список
            setTimeout(() => {
                loadPromoCodesList();
                hideCreatePromoForm();
            }, 1000);
        } else {
            statusDiv.innerHTML = `<div class="error-message">❌ Помилка: ${data.error || data.message || 'Невідома помилка'}</div>`;
        }
    } catch (error) {
        console.error('Error creating promo code:', error);
        statusDiv.innerHTML = `<div class="error-message">❌ Помилка підключення: ${error.message}</div>`;
    }
}

/**
 * Загружает список промокодов
 */
async function loadPromoCodesList() {
    const listDiv = document.getElementById('promoCodesList');
    if (!listDiv) return;
    
    listDiv.innerHTML = '<div class="loading-message" style="text-align: center; padding: 40px;"><div style="font-size: 48px; margin-bottom: 16px;">⏳</div><div>Завантаження...</div></div>';
    
    try {
        const response = await fetch('/api/admin/promo/list');
        const data = await response.json();
        
        if (response.ok && data.status === 'ok') {
            const promoCodes = data.promo_codes || [];
            
            if (promoCodes.length === 0) {
                listDiv.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--text-secondary);">Немає промокодів</div>';
                return;
            }
            
            listDiv.innerHTML = promoCodes.map(promo => {
                const usesText = promo.max_uses ? `${promo.uses}/${promo.max_uses}` : `${promo.uses}/∞`;
                const expiryText = promo.expiry ? new Date(promo.expiry * 1000).toLocaleString('uk-UA') : 'Без обмежень';
                const statusBadge = promo.is_active && promo.is_available 
                    ? '<span style="background: #4CAF50; color: white; padding: 4px 8px; border-radius: 8px; font-size: 12px;">Активний</span>'
                    : '<span style="background: #f44336; color: white; padding: 4px 8px; border-radius: 8px; font-size: 12px;">Неактивний</span>';
                
                let rewardText = '';
                if (promo.reward_type === 'balance') {
                    rewardText = `${promo.reward_value.toFixed(2)} UAH`;
                } else {
                    rewardText = `${promo.reward_value} ${promo.item_type || ''}`;
                }
                
                return `
                    <div style="background: rgba(79, 172, 254, 0.1); padding: 16px; border-radius: 12px; margin-bottom: 12px; border: 1px solid rgba(79, 172, 254, 0.3);">
                        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                            <div>
                                <div style="font-weight: 700; font-size: 18px; color: #4facfe; margin-bottom: 4px;">${promo.code}</div>
                                <div style="font-size: 14px; color: var(--text-secondary);">Винагорода: ${rewardText}</div>
                            </div>
                            ${statusBadge}
                        </div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12px; color: var(--text-secondary); margin-top: 8px;">
                            <div>Використано: ${usesText}</div>
                            <div>Закінчується: ${expiryText}</div>
                        </div>
                    </div>
                `;
            }).join('');
        } else {
            listDiv.innerHTML = `<div class="error-message">Помилка завантаження: ${data.error || 'Невідома помилка'}</div>`;
        }
    } catch (error) {
        console.error('Error loading promo codes:', error);
        listDiv.innerHTML = `<div class="error-message">Помилка підключення: ${error.message}</div>`;
    }
}

/**
 * Показывает модальное окно редактирования профиля пользователя
 */
function showEditUserProfileModal() {
    const modal = document.getElementById('editUserProfileModal');
    if (modal) {
        modal.style.display = 'flex';
        // Очищаем форму
        document.getElementById('editUserId').value = '';
        document.getElementById('editUserName').value = '';
        document.getElementById('editUserUsername').value = '';
        document.getElementById('editUserProfileStatus').innerHTML = '';
    }
}

/**
 * Закрывает модальное окно редактирования профиля
 */
function closeEditUserProfileModal() {
    const modal = document.getElementById('editUserProfileModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

/**
 * Сохраняет изменения профиля пользователя
 */
async function saveUserProfile() {
    const userId = parseInt(document.getElementById('editUserId').value);
    const userName = document.getElementById('editUserName').value.trim();
    const username = document.getElementById('editUserUsername').value.trim();
    const statusDiv = document.getElementById('editUserProfileStatus');
    
    if (!userId || userId <= 0) {
        statusDiv.innerHTML = '<div class="error-message">Введіть коректний ID користувача</div>';
        return;
    }
    
    if (!userName && !username) {
        statusDiv.innerHTML = '<div class="error-message">Введіть хоча б одне поле для оновлення</div>';
        return;
    }
    
    statusDiv.innerHTML = '<div style="color: #4facfe;">⏳ Збереження...</div>';
    
    try {
        const response = await fetch(`/api/admin/user/${userId}/profile`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_name: userName || undefined,
                username: username || undefined
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.status === 'ok') {
            statusDiv.innerHTML = '<div class="success-message">✅ Профіль успішно оновлено!</div>';
            setTimeout(() => {
                closeEditUserProfileModal();
            }, 1500);
        } else {
            statusDiv.innerHTML = `<div class="error-message">❌ Помилка: ${data.error || 'Невідома помилка'}</div>`;
        }
    } catch (error) {
        console.error('Error saving user profile:', error);
        statusDiv.innerHTML = `<div class="error-message">❌ Помилка підключення: ${error.message}</div>`;
    }
}

/**
 * Показывает модальное окно управления реквизитами
 */
async function showRequisitesModal() {
    const modal = document.getElementById('requisitesModal');
    if (modal) {
        modal.style.display = 'flex';
        
        // Загружаем текущие реквизиты
        try {
            const response = await fetch('/api/admin/requisites');
            const data = await response.json();
            
            if (response.ok && data.status === 'ok') {
                document.getElementById('requisitesText').value = data.requisites.requisites || '';
            }
        } catch (error) {
            console.error('Error loading requisites:', error);
        }
    }
}

/**
 * Закрывает модальное окно реквизитов
 */
function closeRequisitesModal() {
    const modal = document.getElementById('requisitesModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

/**
 * Сохраняет реквизиты
 */
async function saveRequisites() {
    const requisitesText = document.getElementById('requisitesText').value.trim();
    const statusDiv = document.getElementById('requisitesStatus');
    
    statusDiv.innerHTML = '<div style="color: #4facfe;">⏳ Збереження...</div>';
    
    try {
        const response = await fetch('/api/admin/requisites', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                requisites: requisitesText
            })
        });
        
        const data = await response.json();
        
        if (response.ok && data.status === 'ok') {
            statusDiv.innerHTML = '<div class="success-message">✅ Реквізити успішно збережено!</div>';
            setTimeout(() => {
                closeRequisitesModal();
            }, 1500);
        } else {
            statusDiv.innerHTML = `<div class="error-message">❌ Помилка: ${data.error || 'Невідома помилка'}</div>`;
        }
    } catch (error) {
        console.error('Error saving requisites:', error);
        statusDiv.innerHTML = `<div class="error-message">❌ Помилка підключення: ${error.message}</div>`;
    }
}

