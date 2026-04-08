const GiftHUD = (() => {
    const CASE_COUNT = 10;
    const CASE_ITEM_WIDTH = 160;
    const ROLLER_FILLER_COUNT = 24;
    const DEFAULT_PREVIEW = [
        { attempt: 1, balance: 12, fruit_amount: 0, fruit_type: 'apple' },
        { attempt: 2, balance: 4, fruit_amount: 1, fruit_type: 'pear' },
        { attempt: 3, balance: 0, fruit_amount: 3, fruit_type: 'peach' },
        { attempt: 4, balance: 22, fruit_amount: 0, fruit_type: 'golden_apple' },
        { attempt: 5, balance: 0, fruit_amount: 2, fruit_type: 'cherry' }
    ];
    const state = {
        giftStatus: null,
        rewardPreview: [],
        pickedBoxes: new Array(CASE_COUNT).fill(false),
        isSpinning: false,
        toastReady: false,
        lastOutcome: null,
        spinPhase: 'idle',
        autoSessionLock: false,
        broadcastData: [],
        broadcastTimer: null,
        viewerName: 'Player'
    };

    const elements = {};

    document.addEventListener('DOMContentLoaded', init);
    window.addEventListener('beforeunload', () => {
        if (state.broadcastTimer) {
            clearInterval(state.broadcastTimer);
        }
    });

    function init() {
        cacheElements();
        setupTelegram();
        bindEvents();
        ensureToastStack();
        renderRewardPool();
        renderIdleRoller();
        setRewardSummary(null);
        initBroadcast();
        loadGiftStatus();
    }

    function cacheElements() {
        elements.spinButton = document.getElementById('spinCaseButton');
        elements.collectButton = document.getElementById('collectButton');
        elements.rollerTrack = document.getElementById('rollerTrack');
        elements.rewardPool = document.getElementById('rewardPool');
        elements.rewardSummary = document.getElementById('rewardSummary');
        elements.sessionChip = document.getElementById('sessionChip');
        elements.giftMessage = document.getElementById('giftMessage');
        elements.waitMessage = document.getElementById('waitMessage');
        elements.sessionState = document.getElementById('sessionState');
        elements.caseInstruction = document.getElementById('caseInstruction');
        elements.caseStage = document.getElementById('caseStage');
        elements.caseShell = document.getElementById('caseShell');
        elements.caseHint = document.getElementById('caseHint');
        elements.caseStageStatus = document.getElementById('caseStageStatus');
        elements.attemptsRow = document.getElementById('attemptsRow');
        elements.rewardSubtitle = document.getElementById('rewardSubtitle');
        elements.toastContainer = document.getElementById('toastContainer');
        elements.broadcastTrack = document.getElementById('broadcastTrack');
        elements.overlay = document.getElementById('caseOverlay');
        elements.overlayResult = document.getElementById('overlayResult');
        elements.overlayClose = document.getElementById('overlayCloseButton');
        elements.overlayParticles = document.getElementById('overlayParticles');
    }

    function setupTelegram() {
        const app = resolveTelegramApp();
        const alias = resolveViewerAlias(app);
        if (alias) {
            state.viewerName = alias;
        }
        if (app && typeof app.ready === 'function') {
            try { app.ready(); } catch (err) { console.warn('tg.ready error', err); }
        }
        if (app && typeof app.expand === 'function') {
            try { app.expand(); } catch (err) { console.warn('tg.expand error', err); }
        }
    }

    function bindEvents() {
        if (elements.spinButton) {
            elements.spinButton.addEventListener('click', autoPickCase);
        }
        if (elements.collectButton) {
            elements.collectButton.addEventListener('click', collectReward);
        }
        if (elements.overlayClose) {
            elements.overlayClose.addEventListener('click', closeOverlay);
        }
        if (elements.overlay) {
            elements.overlay.addEventListener('click', (event) => {
                if (event.target === elements.overlay || event.target.classList.contains('overlay-backdrop')) {
                    closeOverlay();
                }
            });
        }
    }

    function resolveTelegramApp() {
        if (window.telegramWebApp) { return window.telegramWebApp; }
        if (window.Telegram) {
            if (window.Telegram.WebApp) { return window.Telegram.WebApp; }
            if (window.Telegram.webApp) { return window.Telegram.webApp; }
        }
        return null;
    }

    function ensureToastStack() {
        if (state.toastReady || !elements.toastContainer) { return; }
        state.toastReady = true;
        elements.toastContainer.className = 'toast-stack';
    }

    function showToast(message, type) {
        ensureToastStack();
        if (!elements.toastContainer) { return; }
        const toast = document.createElement('div');
        toast.className = `toast ${type || 'info'}`;
        toast.textContent = message;
        elements.toastContainer.appendChild(toast);
        requestAnimationFrame(() => toast.classList.add('visible'));
        setTimeout(() => {
            toast.classList.remove('visible');
            toast.addEventListener('transitionend', () => toast.remove(), { once: true });
        }, 4200);
    }

    async function loadGiftStatus() {
        try {
            const response = await fetch('/api/user/gift/status');
            const data = await response.json();
            if (!response.ok) { throw new Error(data.message || data.error || 'Помилка статусу'); }
            if (!data.has_active_session) {
                data.attempts_allowed = data.attempts || data.attempts_allowed || 0;
                data.attempts_used = data.attempts_used || 0;
            }
            data.picked_safe = data.picked_safe || new Array(CASE_COUNT).fill(false);
            state.giftStatus = data;
            state.pickedBoxes = data.picked_safe;
            state.rewardPreview = Array.isArray(data.reward_preview) ? data.reward_preview : [];
            renderRewardPool();
            renderIdleRoller();
            updateGiftUI();
            await ensureGiftSessionIfNeeded();
        } catch (error) {
            console.error('Error loading gift status:', error);
            showToast(error.message || 'Помилка завантаження подарунку', 'danger');
        }
    }

    async function ensureGiftSessionIfNeeded() {
        if (!state.giftStatus || state.giftStatus.has_active_session || !state.giftStatus.can_play) { return; }
        if (state.autoSessionLock) { return; }
        state.autoSessionLock = true;
        try {
            await startGiftSession(true);
        } finally {
            state.autoSessionLock = false;
        }
    }

    async function startGiftSession(isAuto) {
        try {
            const response = await fetch('/api/user/gift/start', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
            const data = await response.json();
            if (!response.ok || data.status !== 'ok') { throw new Error(data.message || 'Помилка запуску'); }
            state.lastOutcome = null;
            setRewardSummary(null);
            if (!isAuto) {
                showToast('🎁 Сесію перезапущено', 'success');
            }
            await loadGiftStatus();
        } catch (error) {
            if (!isAuto) {
                console.error('Error starting session:', error);
                showToast(error.message || 'Не вдалося підготувати кейс', 'danger');
            }
        }
    }

    function updateGiftUI() {
        if (!state.giftStatus) { return; }
        updateStats();
        const message = elements.giftMessage;
        const waitMessage = elements.waitMessage;
        const chip = elements.sessionChip;

        if (state.giftStatus.has_active_session) {
            if (message) {
                message.style.display = 'block';
                if (state.giftStatus.finished) {
                    message.textContent = '💥 Сесію завершено — заберіть виграш та поверніться завтра.';
                } else if (safeNumber(state.giftStatus.accumulated_balance, 0) > 0 || safeNumber(state.giftStatus.accumulated_fruits, 0) > 0) {
                    message.textContent = '💡 Виграш накопичується. Забирайте зараз або ризикуйте далі.';
                } else {
                    message.textContent = '🔥 Уникайте бомб і відкрийте кейс. Три спроби на добу.';
                }
            }
            if (waitMessage) { waitMessage.style.display = 'none'; }
            if (chip) {
                chip.textContent = 'Сесія активна';
                chip.className = 'case-session-chip chip-live';
                chip.onclick = null;
            }
            updateStageStatus('live');
        } else {
            if (message) { message.style.display = 'none'; }
            if (waitMessage) {
                waitMessage.style.display = 'block';
                waitMessage.textContent = state.giftStatus.can_play
                    ? 'Кейс синхронізується. Як тільки готово — кнопка прокруту засвітиться.'
                    : (state.giftStatus.wait_time_formatted
                        ? `⏳ Наступна спроба через ${state.giftStatus.wait_time_formatted}`
                        : '⏳ Очікуємо відкриття доступу.');
            }
            if (chip) {
                if (state.giftStatus.can_play) {
                    chip.textContent = 'Кейс готується';
                    chip.className = 'case-session-chip chip-wait pulse';
                    chip.onclick = () => startGiftSession(false);
                    updateStageStatus('wait');
                } else {
                    chip.textContent = state.giftStatus.wait_time_formatted ? `Очікуємо ${state.giftStatus.wait_time_formatted}` : 'Кулдаун активний';
                    chip.className = 'case-session-chip chip-wait';
                    chip.onclick = null;
                    updateStageStatus('cooldown');
                }
            }
        }

        updateAttemptsRow();
        updateSessionState();
        updateSpinButtonState();
        updateCollectButton();
        updateCaseShellState();
    }

    function updateStageStatus(mode) {
        if (!elements.caseStageStatus || !state.giftStatus) { return; }
        elements.caseStageStatus.className = 'case-stage-status';
        if (state.giftStatus.has_active_session) {
            if (state.giftStatus.finished) {
                elements.caseStageStatus.textContent = 'Сесію завершено';
                elements.caseStageStatus.classList.add('done');
            } else {
                elements.caseStageStatus.textContent = 'Лайв синхронізація';
                elements.caseStageStatus.classList.add('live');
            }
            return;
        }
        if (mode === 'cooldown') {
            elements.caseStageStatus.textContent = state.giftStatus.wait_time_formatted
                ? `Кулдаун ${state.giftStatus.wait_time_formatted}`
                : 'Кулдаун активний';
            elements.caseStageStatus.classList.add('cooldown');
            return;
        }
        elements.caseStageStatus.textContent = 'Готуємо кейс';
        elements.caseStageStatus.classList.add('wait');
    }

    function updateStats() {
        const attemptsLeft = state.giftStatus.has_active_session
            ? computeAttemptsLeft(state.giftStatus)
            : (state.giftStatus.attempts || state.giftStatus.attempts_allowed || 0);
        const balance = document.getElementById('accumulatedBalance');
        const fruits = document.getElementById('accumulatedFruits');
        const attemptsEl = document.getElementById('attemptsLeft');
        // Убрали levelEl - не показываем уровень сада в подарунку
        if (attemptsEl) { attemptsEl.textContent = attemptsLeft > 0 ? attemptsLeft : '—'; }
        if (balance) { balance.textContent = `${formatCurrency(state.giftStatus.accumulated_balance || 0)}₴`; }
        if (fruits) { fruits.textContent = safeNumber(state.giftStatus.accumulated_fruits || 0, 0); }
        if (elements.rewardSubtitle) {
            elements.rewardSubtitle.textContent = 'Як у Telegram-боті';
        }
    }

    function updateAttemptsRow() {
        if (!elements.attemptsRow || !state.giftStatus) { return; }
        const total = getTotalAttempts(state.giftStatus);
        const left = computeAttemptsLeft(state.giftStatus);
        const used = Math.max(total - left, 0);
        const markup = [];
        for (let i = 0; i < total; i++) {
            const classes = ['attempt-chip'];
            if (i < used) { classes.push('used'); }
            else if (i === used) { classes.push('ready'); }
            markup.push(`
                <div class="${classes.join(' ')}">
                    <span class="chip-index">#${i + 1}</span>
                    <span class="chip-label">${i < used ? 'Використано' : (i === used ? 'Готово' : 'Очікує')}</span>
                </div>
            `);
        }
        elements.attemptsRow.innerHTML = markup.join('');
    }

    function updateSessionState() {
        if (!elements.sessionState) { return; }
        if (!state.giftStatus) {
            elements.sessionState.textContent = 'Завантаження...';
            return;
        }
        if (!state.giftStatus.has_active_session) {
            elements.sessionState.className = 'session-state muted';
            elements.sessionState.textContent = state.giftStatus.can_play
                ? 'Синхронізуємо кейс...'
                : 'Очікуємо доступ після кулдауну.';
            return;
        }
        elements.sessionState.className = 'session-state';
        const attemptsLeft = computeAttemptsLeft(state.giftStatus);
        elements.sessionState.textContent = attemptsLeft > 0
            ? `Спроб залишилось: ${attemptsLeft}`
            : 'Спроби вичерпано — заберіть виграш.';
    }

    function updateSpinButtonState() {
        if (!elements.spinButton) { return; }
        if (!state.giftStatus) {
            elements.spinButton.disabled = true;
            elements.spinButton.textContent = 'Завантаження...';
            if (elements.caseInstruction) {
                elements.caseInstruction.textContent = 'Чекаємо підключення до Telegram WebApp...';
            }
            return;
        }
        if (!state.giftStatus.has_active_session) {
            elements.spinButton.disabled = true;
            elements.spinButton.textContent = state.giftStatus.can_play ? 'Готуємо кейс...' : 'Очікуємо кулдаун';
            if (elements.caseInstruction) {
                elements.caseInstruction.textContent = state.giftStatus.can_play
                    ? 'Кейс синхронізується. Як тільки буде готовий — кнопка засвітиться.'
                    : 'Прокрут стане доступний після завершення кулдауну.';
            }
            return;
        }
        if (state.giftStatus.finished) {
            elements.spinButton.disabled = true;
            elements.spinButton.textContent = 'Сесію завершено';
            if (elements.caseInstruction) {
                elements.caseInstruction.textContent = 'Спроби використані. Заберіть виграш та запустіть нову сесію завтра.';
            }
            return;
        }
        const canSpin = canPickCase();
        elements.spinButton.disabled = !canSpin || state.isSpinning;
        elements.spinButton.textContent = canSpin ? '🚀 Запустити прокрут' : 'Спроб більше немає';
        if (elements.caseInstruction) {
            if (state.isSpinning) {
                elements.caseInstruction.textContent = 'Рулетка крутиться, зачекайте на результат...';
            } else if (canSpin) {
                elements.caseInstruction.textContent = 'Натисніть, щоб витратити спробу і запустити рулетку.';
            } else {
                elements.caseInstruction.textContent = 'Спроби закінчилися. Заберіть виграш та почекайте нову сесію.';
            }
        }
    }

    function updateCollectButton() {
        if (!elements.collectButton) { return; }
        const hasReward = state.giftStatus
            && (safeNumber(state.giftStatus.accumulated_balance, 0) > 0
                || safeNumber(state.giftStatus.accumulated_fruits, 0) > 0);
        elements.collectButton.style.display = hasReward ? 'inline-flex' : 'none';
        elements.collectButton.disabled = !hasReward;
    }

    function updateCaseShellState() {
        if (!elements.caseShell) { return; }
        const hasReward = state.giftStatus
            && (safeNumber(state.giftStatus.accumulated_balance, 0) > 0
                || safeNumber(state.giftStatus.accumulated_fruits, 0) > 0);
        elements.caseShell.classList.toggle('case-shell-ready', !!hasReward);
        elements.caseShell.classList.toggle('case-shell-disabled', !state.giftStatus || !state.giftStatus.has_active_session);
    }

    function getTotalAttempts(payload) {
        if (!payload) { return 0; }
        if (payload.has_active_session) {
            return safeNumber(payload.attempts_allowed, 0);
        }
        return safeNumber(payload.attempts || payload.attempts_allowed, 0);
    }

    function computeAttemptsLeft(payload) {
        if (!payload) { return 0; }
        if (payload.has_active_session) {
            return Math.max(safeNumber(payload.attempts_allowed, 0) - safeNumber(payload.attempts_used, 0), 0);
        }
        return safeNumber(payload.attempts || payload.attempts_allowed, 0);
    }

    function canPickCase() {
        if (!state.giftStatus || !state.giftStatus.has_active_session || state.giftStatus.finished) { return false; }
        return computeAttemptsLeft(state.giftStatus) > 0;
    }

    function autoPickCase() {
        if (!canPickCase() || state.isSpinning) { return; }
        const available = [];
        for (let i = 0; i < state.pickedBoxes.length; i++) {
            if (!state.pickedBoxes[i]) { available.push(i); }
        }
        if (!available.length) { return; }
        const randomIndex = available[Math.floor(Math.random() * available.length)];
        spinCase(randomIndex);
    }

    async function spinCase(index) {
        if (!canPickCase() || state.pickedBoxes[index] || state.isSpinning) { return; }
        state.isSpinning = true;
        setSpinPhase('arming');
        updateSpinButtonState();
        try {
            const response = await fetch('/api/user/gift/pick', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ box_index: index })
            });
            const data = await response.json();
            if (!response.ok) { throw new Error(data.message || 'Помилка відкриття кейсу'); }
            animateRoulette(data);
        } catch (error) {
            console.error('Error picking box:', error);
            showToast(error.message || 'Не вдалося відкрити кейс', 'danger');
            state.isSpinning = false;
            setSpinPhase('idle');
            updateSpinButtonState();
        }
    }

    function animateRoulette(result) {
        if (!elements.rollerTrack) {
            state.isSpinning = false;
            updateSpinButtonState();
            return;
        }
        const items = buildCaseItems(result);
        elements.rollerTrack.innerHTML = items.map(renderCaseItem).join('');
        elements.rollerTrack.style.transition = 'none';
        elements.rollerTrack.style.transform = 'translateX(0)';
        void elements.rollerTrack.offsetWidth;
        const targetIndex = items.length - 3;
        const offset = Math.max((targetIndex * CASE_ITEM_WIDTH) - (CASE_ITEM_WIDTH * 1.6), 0);
        elements.rollerTrack.style.transition = 'transform 2.9s cubic-bezier(0.08, 0.62, 0.12, 0.99)';
        elements.rollerTrack.style.transform = `translateX(-${offset}px)`;
        setSpinPhase('rolling');
        setTimeout(() => handleRouletteResult(result), 3000);
    }

    async function handleRouletteResult(result) {
        if (result.session) {
            const session = result.session;
            session.attempts_left = computeAttemptsLeft(session);
            session.picked_safe = session.picked_safe || state.pickedBoxes;
            state.giftStatus = Object.assign({}, state.giftStatus || {}, session, {
                has_active_session: !session.finished
            });
            state.pickedBoxes = session.picked_safe;
            updateGiftUI();
        }
        const rewardInfo = buildRewardParts(result.reward, result.session?.fruit_type);
        const normalizedStatus = (rewardInfo.balance > 0 || rewardInfo.fruits > 0) && result.status === 'bomb'
            ? 'ok'
            : result.status;
        const normalizedResult = Object.assign({}, result, { status: normalizedStatus });

        state.lastOutcome = normalizedResult;
        setRewardSummary(normalizedResult);
        if (normalizedStatus === 'bomb') {
            setCaseHint('💣 Бомба! Все накопичене згоріло.', 'danger');
            showToast(result.message || '💣 Натрапили на бомбу! Виграш згорів.', 'danger');
        } else if (normalizedStatus === 'finished') {
            setCaseHint('🎉 Сесію завершено. Виграш зараховано.', 'success');
            showToast(result.message || '🎉 Сесію завершено! Виграш зараховано.', 'success');
            if (window.loadUserData) {
                try { await window.loadUserData(); } catch (err) { console.warn(err); }
            }
        } else {
            const rewardText = rewardInfo.parts.join(' + ') || 'без змін';
            setCaseHint(`🎯 Випала нагорода: ${rewardText}`, 'success');
            showToast(rewardInfo.parts.length ? `🎯 Виграш: ${rewardText}` : '🎯 Без змін. Спробуйте ще раз.', 'success');
        }
        addResultToBroadcast(normalizedResult);
        openResultOverlay(normalizedResult);
        state.isSpinning = false;
        setSpinPhase('result');
        updateSpinButtonState();
        await loadGiftStatus();
        setTimeout(() => setSpinPhase('idle'), 800);
    }

    async function collectReward() {
        if (!elements.collectButton) { return; }
        elements.collectButton.disabled = true;
        try {
            const response = await fetch('/api/user/gift/collect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            if (!response.ok || data.status !== 'ok') { throw new Error(data.message || 'Помилка виплати'); }
            const rewardInfo = buildRewardParts(data.reward);
            const rewardText = rewardInfo.parts.join(' + ');
            showToast(rewardText ? `💰 Виплата: ${rewardText}` : 'Виплата зафіксована.', 'success');
            state.lastOutcome = data;
            setRewardSummary(data);
            if (window.loadUserData) {
                try { await window.loadUserData(); } catch (err) { console.warn(err); }
            }
            await loadGiftStatus();
        } catch (error) {
            console.error('Error collecting reward:', error);
            showToast(error.message || 'Не вдалося зафіксувати виграш', 'danger');
        } finally {
            elements.collectButton.disabled = false;
        }
    }

    function buildCaseItems(result) {
        // Сначала создаем точный элемент результата
        const resultItem = convertResultToItem(result);
        
        let pool = getDisplayPool();
        if (!pool.length) {
            pool = DEFAULT_PREVIEW.map(mapPreviewEntry);
        }
        const items = [];
        // Добавляем случайные элементы из пула
        for (let i = 0; i < ROLLER_FILLER_COUNT; i++) {
            items.push(pool[Math.floor(Math.random() * pool.length)]);
        }
        // ВАЖНО: Последний элемент должен быть ТОЧНО результатом с сервера
        items.push(resultItem);
        return items;
    }

    function renderCaseItem(item) {
        return `
            <div class="roller-item ${item.type || ''}">
                <span class="roller-emoji">${item.icon}</span>
                <strong>${item.label}</strong>
                <small>${item.description || ''}</small>
            </div>
        `;
    }

    function convertResultToItem(result) {
        if (!result) {
            return { icon: '❓', label: 'Невідомо', type: 'unknown', description: 'Помилка' };
        }
        
        // Если это бомба
        if (result.status === 'bomb' || result.is_bomb) {
            return { icon: '💣', label: 'Бомба', type: 'bomb', description: 'Спроба завершена' };
        }
        
        // Получаем reward из результата
        const reward = result.reward || {};
        const rewardInfo = buildRewardParts(reward, result.session?.fruit_type);
        
        // Формируем точную метку на основе реальных данных
        let label = '';
        if (rewardInfo.balance > 0 && rewardInfo.fruits > 0) {
            label = `${rewardInfo.balance.toFixed(2)}₴ + ${rewardInfo.fruits} ${getFruitEmoji(rewardInfo.fruitType)}`;
        } else if (rewardInfo.balance > 0) {
            label = `${rewardInfo.balance.toFixed(2)}₴`;
        } else if (rewardInfo.fruits > 0) {
            label = `${rewardInfo.fruits} ${getFruitEmoji(rewardInfo.fruitType)}`;
        } else {
            label = 'Бонус';
        }
        
        return {
            icon: rewardInfo.balance > 0 ? '💰' : (rewardInfo.fruits > 0 ? getFruitEmoji(rewardInfo.fruitType) : '🎁'),
            label: label,
            type: rewardInfo.balance > 0 ? 'balance' : (rewardInfo.fruits > 0 ? 'fruit' : 'bonus'),
            description: 'Результат спроби',
            reward: reward // Сохраняем оригинальный reward для проверки
        };
    }

    function renderRewardPool() {
        if (!elements.rewardPool) { return; }
        const source = state.rewardPreview.length ? state.rewardPreview : DEFAULT_PREVIEW;
        if (!source.length) {
            elements.rewardPool.innerHTML = '<div class="requests-empty" style="margin:0;">Дані відсутні</div>';
            return;
        }
        elements.rewardPool.innerHTML = source.map((item) => {
            const entry = mapPreviewEntry(item);
            return `
                <div class="reward-line ${entry.type}">
                    <div class="reward-icon">${entry.icon}</div>
                    <div>
                        <strong>${entry.label}</strong>
                        <small>${entry.description}</small>
                    </div>
                </div>
            `;
        }).join('');
    }

    function renderIdleRoller() {
        if (!elements.rollerTrack) { return; }
        let pool = getDisplayPool();
        if (!pool.length) {
            pool = DEFAULT_PREVIEW.map(mapPreviewEntry);
        }
        const placeholders = [];
        for (let i = 0; i < 12; i++) {
            placeholders.push(renderCaseItem(pool[i % pool.length]));
        }
        elements.rollerTrack.innerHTML = placeholders.join('');
    }

    function getDisplayPool() {
        return state.rewardPreview.map(mapPreviewEntry);
    }

    function mapPreviewEntry(entry) {
        const balance = safeNumber(entry.balance, 0);
        const fruits = safeNumber(entry.fruit_amount, 0);
        const fruitType = entry.fruit_type || 'apple';
        const parts = [];
        if (balance > 0) { parts.push(`+${balance.toFixed(2)}₴`); }
        if (fruits > 0) { parts.push(`+${fruits} ${getFruitEmoji(fruitType)}`); }
        const label = parts.join(' • ') || '+0';
        const type = balance > 0 ? 'balance' : (fruits > 0 ? 'fruit' : 'bonus');
        return {
            attempt: entry.attempt,
            icon: balance > 0 ? '💰' : getFruitEmoji(fruitType),
            label,
            description: entry.attempt ? `Спроба #${entry.attempt}` : 'Фіксована винагорода',
            type
        };
    }

    function setRewardSummary(payload) {
        if (!elements.rewardSummary) { return; }
        if (!payload) {
            elements.rewardSummary.className = 'reward-summary';
            elements.rewardSummary.innerHTML = '<p>Поки що без виграшу. Запустіть кейс.</p>';
            return;
        }
        if (payload.status === 'bomb') {
            elements.rewardSummary.className = 'reward-summary reward-summary-danger';
            elements.rewardSummary.innerHTML = '<div class="reward-status danger">💣 Бомба! Все згоріло.</div>';
            return;
        }
        if (payload.status === 'finished') {
            elements.rewardSummary.className = 'reward-summary reward-summary-success';
            elements.rewardSummary.innerHTML = '<div class="reward-status success">🎉 Сесію завершено. Виграш зараховано.</div>';
            return;
        }
        const rewardInfo = buildRewardParts(payload.reward);
        if (!rewardInfo.parts.length) {
            elements.rewardSummary.className = 'reward-summary';
            elements.rewardSummary.innerHTML = '<p>Спроба без призу. Спробуйте ще!</p>';
            return;
        }
        elements.rewardSummary.className = 'reward-summary reward-summary-success';
        elements.rewardSummary.innerHTML = `<div class="reward-status success">🎯 Виграш: ${rewardInfo.parts.join(' + ')}</div>`;
    }

    function setCaseHint(text, tone) {
        if (!elements.caseHint) { return; }
        elements.caseHint.textContent = text;
        elements.caseHint.className = `case-rare-hint${tone ? ` tone-${tone}` : ''}`;
    }

    function setSpinPhase(phase) {
        state.spinPhase = phase;
        const phases = ['idle', 'arming', 'rolling', 'result'];
        phases.forEach((ph) => {
            if (elements.caseStage) { elements.caseStage.classList.remove(`phase-${ph}`); }
            if (elements.caseShell) { elements.caseShell.classList.remove(`phase-${ph}`); }
        });
        if (elements.caseStage) { elements.caseStage.classList.add(`phase-${phase}`); }
        if (elements.caseShell) { elements.caseShell.classList.add(`phase-${phase}`); }
    }

    function safeNumber(value, fallback) {
        const num = Number(value);
        return Number.isNaN(num) ? fallback : num;
    }

    function formatCurrency(value) {
        return parseFloat(value || 0).toFixed(2);
    }

    function getFruitEmoji(fruitType) {
        const fruitEmojis = {
            apple: '🍏',
            pear: '🍐',
            cherry: '🍒',
            peach: '🍑',
            golden_apple: '🥇'
        };
        return fruitEmojis[fruitType] || '🍎';
    }

    function initBroadcast() {
        if (!elements.broadcastTrack) { return; }
        state.broadcastData = [];
        renderBroadcastLoop();
        if (state.broadcastTimer) {
            clearInterval(state.broadcastTimer);
        }
        state.broadcastTimer = setInterval(() => {
            renderBroadcastLoop();
        }, 15000);
    }

    function renderBroadcastLoop(resetAnimation) {
        if (!elements.broadcastTrack) { return; }
        if (!state.broadcastData.length) {
            elements.broadcastTrack.innerHTML = '<div class="broadcast-empty">Ще немає лайв-виграшів</div>';
            return;
        }
        const base = state.broadcastData.slice(0);
        const duplicated = base.length >= 3 ? base.concat(base.slice(0, 3)) : base;
        const loop = duplicated.map((entry) => `
            <div class="broadcast-item ${entry.tone || ''}">
                <span>${formatRelativeTime(entry.ts)}</span>
                <strong>${entry.user}</strong>
                <span>${entry.drop}</span>
            </div>
        `).join('');
        elements.broadcastTrack.innerHTML = `<div class="broadcast-loop">${loop}</div>`;
        if (resetAnimation) {
            elements.broadcastTrack.classList.add('refresh');
            void elements.broadcastTrack.offsetWidth;
            elements.broadcastTrack.classList.remove('refresh');
        }
    }

    function addResultToBroadcast(result) {
        if (!elements.broadcastTrack) { return; }
        const entry = {
            user: getViewerAlias(),
            ts: Date.now(),
            tone: result.status
        };
        if (result.status === 'bomb') {
            entry.drop = '💣 Бомба — все згоріло';
        } else {
            const rewardInfo = buildRewardParts(result.reward);
            const rewardText = rewardInfo.parts.join(' + ') || 'Без змін';
            if (result.status === 'finished') {
                entry.drop = rewardText ? `🎉 ${rewardText}` : '🎉 Без змін';
                entry.tone = 'finished';
            } else {
                entry.drop = rewardText;
                entry.tone = 'success';
            }
        }
        state.broadcastData.unshift(entry);
        state.broadcastData = state.broadcastData.slice(0, 10);
        renderBroadcastLoop(true);
    }

    function formatRelativeTime(timestamp) {
        const diffSeconds = Math.max(0, Math.floor((Date.now() - timestamp) / 1000));
        if (diffSeconds < 5) { return 'щойно'; }
        if (diffSeconds < 60) { return `${diffSeconds} с тому`; }
        const diffMinutes = Math.floor(diffSeconds / 60);
        if (diffMinutes === 1) { return '1 хв тому'; }
        if (diffMinutes < 60) { return `${diffMinutes} хв тому`; }
        const diffHours = Math.floor(diffMinutes / 60);
        return `${diffHours} г тому`;
    }

    function getViewerAlias() {
        return state.viewerName || 'Player';
    }

    function resolveViewerAlias(app) {
        const unsafe = app?.initDataUnsafe
            || window.Telegram?.WebApp?.initDataUnsafe
            || window.Telegram?.webApp?.initDataUnsafe;
        const user = unsafe?.user;
        if (!user) { return null; }
        if (user.username) { return `@${user.username}`; }
        if (user.first_name && user.last_name) { return `${user.first_name} ${user.last_name.slice(0, 1)}.`; }
        if (user.first_name) { return user.first_name; }
        return null;
    }

    function buildRewardParts(reward, fallbackFruit) {
        const data = reward || {};
        const balance = safeNumber(data.balance, 0);
        const fruits = safeNumber(data.fruits, 0);
        const fruitType = data.fruit_type || fallbackFruit || (state.giftStatus && state.giftStatus.fruit_type) || 'apple';
        const parts = [];
        if (balance > 0) { parts.push(`+${balance.toFixed(2)}₴`); }
        if (fruits > 0) { parts.push(`+${fruits} ${getFruitEmoji(fruitType)}`); }
        return { parts, balance, fruits, fruitType };
    }

    function openResultOverlay(payload) {
        if (!elements.overlay || !elements.overlayResult) { return; }
        const message = describeOutcome(payload);
        elements.overlayResult.textContent = message;
        spawnOverlayParticles();
        elements.overlay.classList.add('active');
        elements.overlay.setAttribute('aria-hidden', 'false');
    }

    function describeOutcome(payload) {
        if (!payload) { return 'Продовжуйте гру'; }
        if (payload.status === 'bomb') { return '💣 Бомба! Все згоріло.'; }
        if (payload.status === 'finished') { return '🎉 Сесію завершено. Виграш зараховано.'; }
        const rewardInfo = buildRewardParts(payload.reward);
        return rewardInfo.parts.length ? `🎯 ${rewardInfo.parts.join(' + ')}` : '🎯 Спробуйте ще раз';
    }

    function spawnOverlayParticles() {
        if (!elements.overlayParticles) { return; }
        elements.overlayParticles.innerHTML = '';
        const count = 14;
        for (let i = 0; i < count; i++) {
            const dot = document.createElement('span');
            dot.className = 'overlay-particle';
            dot.style.left = `${Math.random() * 100}%`;
            dot.style.bottom = `${Math.random() * 20}px`;
            dot.style.animationDelay = `${Math.random() * 1.5}s`;
            dot.style.animationDuration = `${3 + Math.random() * 2}s`;
            elements.overlayParticles.appendChild(dot);
        }
    }

    function closeOverlay() {
        if (!elements.overlay) { return; }
        if (elements.overlayClose) {
            elements.overlayClose.blur();
        }
        elements.overlay.classList.remove('active');
        elements.overlay.setAttribute('aria-hidden', 'true');
        if (elements.overlayParticles) {
            elements.overlayParticles.innerHTML = '';
        }
    }

    return {
        reload: loadGiftStatus
    };
})();

