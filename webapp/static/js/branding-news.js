/**
 * Branding & News manager shared between home and cabinet pages.
 * Requires global `api` and `telegramWebApp` objects.
 */

class BrandingNewsManager {
    constructor(options = {}) {
        this.options = {
            limit: options.limit || 3,
            heroTitle: options.heroTitle || 'heroTitle',
            heroSubtitle: options.heroSubtitle || 'heroSubtitle',
            heroBadge: options.heroBadge || 'heroBadge',
            heroPrimaryCta: options.heroPrimaryCta || 'heroPrimaryCta',
            heroSecondaryCta: options.heroSecondaryCta || 'heroSecondaryCta',
            channelTitle: options.channelTitle || 'channelTitle',
            channelDescription: options.channelDescription || 'channelDescription',
            channelButton: options.channelButton || 'channelButton',
            newsTitle: options.newsTitle || 'newsWidgetTitle',
            newsHint: options.newsHint || 'newsWidgetHint',
            newsCounter: options.newsCounter || 'newsCounter',
            newsList: options.newsList || 'newsWidgetList',
            modalId: options.modalId || 'newsModal',
            modalBody: options.modalBody || 'newsModalBody'
        };

        this.branding = {};
        this.newsFeed = [];
        this.unreadCount = 0;
        this.elements = {};
        this.modalOpen = false;
        this.loadingNews = false;

        this.handleNewsCardClick = this.handleNewsCardClick.bind(this);
    }

    init() {
        this.cacheElements();
        this.bindModalClose();
        this.loadNews();
        this.initialized = true;
    }

    cacheElements() {
        Object.keys(this.options).forEach((key) => {
            const id = this.options[key];
            if (typeof id === 'string') {
                this.elements[key] = document.getElementById(id);
            }
        });
    }

    bindModalClose() {
        const modal = this.elements.modalId;
        if (!modal) return;
        const overlay = modal.querySelector('.modal-overlay');
        if (overlay) {
            overlay.addEventListener('click', () => this.closeModal());
        }
    }

    setBrandingData(data) {
        this.branding = data || {};
        this.applyBranding();
    }

    setUnreadCount(count) {
        if (typeof count === 'number') {
            this.unreadCount = count;
            this.updateNewsCounter();
        }
    }

    applyBranding() {
        const map = [
            ['heroTitle', 'hero_title'],
            ['heroSubtitle', 'hero_subtitle'],
            ['heroBadge', 'hero_badge'],
            ['channelTitle', 'channel_title'],
            ['channelDescription', 'channel_description'],
            ['newsTitle', 'news_widget_title'],
            ['newsHint', 'news_widget_hint'],
        ];

        map.forEach(([elementKey, brandKey]) => {
            const el = this.elements[elementKey];
            if (el && this.branding[brandKey]) {
                el.textContent = this.branding[brandKey];
            }
        });

        const channelBtn = this.elements.channelButton;
        if (channelBtn) {
            if (this.branding.channel_cta) {
                channelBtn.textContent = this.branding.channel_cta;
            }
            channelBtn.dataset.channelUrl = this.branding.channel_url || '';
            channelBtn.addEventListener('click', () => this.openChannelLink());
        }

        if (this.elements.heroPrimaryCta && this.branding.hero_cta_primary) {
            this.elements.heroPrimaryCta.textContent = this.branding.hero_cta_primary;
        }
        if (this.elements.heroSecondaryCta && this.branding.hero_cta_secondary) {
            this.elements.heroSecondaryCta.textContent = this.branding.hero_cta_secondary;
        }
    }

    openChannelLink() {
        const link = this.elements.channelButton?.dataset.channelUrl || this.branding.channel_url;
        if (!link) {
            telegramWebApp?.showAlert?.('Посилання на канал ще не налаштоване');
            return;
        }
        if (telegramWebApp?.openTelegramLink) {
            telegramWebApp.openTelegramLink(link);
        } else {
            window.open(link, '_blank', 'noopener');
        }
    }

    loadNews(limit) {
        if (this.loadingNews || !api?.getNews) return;
        this.loadingNews = true;
        const newsLimit = limit || this.options.limit || 3;
        const listEl = this.elements.newsList;
        if (listEl) {
            listEl.innerHTML = '<p class="empty-message">Завантажуємо новини...</p>';
        }
        api.getNews(newsLimit)
            .then((data) => {
                this.newsFeed = Array.isArray(data.news) ? data.news : [];
                this.renderNewsWidget();
            })
            .catch((error) => {
                console.error('[BrandingNews] Error loading news:', error);
                if (listEl) {
                    listEl.innerHTML = '<p class="empty-message error">Не вдалося завантажити новини</p>';
                }
            })
            .finally(() => {
                this.loadingNews = false;
            });
    }

    renderNewsWidget() {
        const list = this.elements.newsList;
        if (!list) return;
        if (!this.newsFeed.length) {
            list.innerHTML = '<p class="empty-message">Ще немає новин</p>';
            this.updateNewsCounter(0);
            return;
        }
        list.innerHTML = this.newsFeed.map((item) => `
            <div class="news-pill ${item.is_viewed ? 'viewed' : ''}" data-news-id="${item.id}">
                <div class="news-pill-text">
                    <div class="news-pill-title">${this.escapeHtml(item.title)}</div>
                    <div class="news-pill-meta">${this.formatDateLabel(item.created_at)} • ${item.views || 0} переглядів</div>
                </div>
                <span class="news-pill-status">${item.is_viewed ? 'Переглянуто' : 'Нове'}</span>
            </div>
        `).join('');
        list.querySelectorAll('.news-pill').forEach((pill) => {
            pill.addEventListener('click', this.handleNewsCardClick);
        });
        this.updateNewsCounter();
    }

    handleNewsCardClick(event) {
        const id = Number(event.currentTarget.dataset.newsId);
        this.openNewsModal(id);
    }

    updateNewsCounter(countOverride) {
        const badge = this.elements.newsCounter;
        if (!badge) return;
        const unread = typeof countOverride === 'number'
            ? countOverride
            : this.newsFeed.filter((item) => !item.is_viewed).length || this.unreadCount;
        if (unread > 0) {
            badge.textContent = `+${unread}`;
            badge.style.display = 'inline-flex';
        } else {
            badge.style.display = 'none';
        }
    }

    openNewsModal(focusId = null) {
        if (!this.newsFeed.length || !this.elements.modalId) {
            this.loadNews(this.options.limit || 5);
        }
        this.renderNewsModal(focusId);
        this.elements.modalId.style.display = 'flex';
        this.modalOpen = true;
        if (focusId) {
            this.markNewsAsRead(focusId);
        }
    }

    closeModal() {
        if (this.elements.modalId) {
            this.elements.modalId.style.display = 'none';
        }
        this.modalOpen = false;
    }

    renderNewsModal(focusId = null) {
        const container = this.elements.modalBody;
        if (!container) return;
        if (!this.newsFeed.length) {
            container.innerHTML = '<p class="empty-message">Новини завантажуються...</p>';
            return;
        }
        container.innerHTML = this.newsFeed.map((item) => `
            <article class="news-modal-item ${Number(focusId) === Number(item.id) ? 'active' : ''}" data-news-id="${item.id}">
                <header class="news-modal-item-header">
                    <div>
                        <h3>${this.escapeHtml(item.title)}</h3>
                        <span>${this.formatDateLabel(item.created_at)}</span>
                    </div>
                    <span class="news-modal-views">${item.views || 0} переглядів</span>
                </header>
                <div class="news-modal-text">${this.formatNewsBody(item.content)}</div>
                <div class="news-modal-actions">
                    ${item.cta_url ? `<button class="primary-btn ghost news-link-btn" data-link="${encodeURIComponent(item.cta_url)}">${this.escapeHtml(item.cta_label || 'Детальніше')}</button>` : ''}
                    <button class="ghost-btn like-btn ${item.liked ? 'liked' : ''}" data-like-id="${item.id}">
                        ${item.liked ? '💙 Вподобано' : '🤍 Вподобати'}
                    </button>
                </div>
            </article>
        `).join('');
        container.querySelectorAll('.news-link-btn').forEach((btn) => {
            btn.addEventListener('click', () => this.openNewsLink(decodeURIComponent(btn.dataset.link)));
        });
        container.querySelectorAll('.like-btn').forEach((btn) => {
            btn.addEventListener('click', () => {
                const newsId = Number(btn.dataset.likeId);
                const willLike = !btn.classList.contains('liked');
                this.toggleNewsLike(newsId, willLike);
            });
        });
    }

    async markNewsAsRead(newsId) {
        try {
            await api.markNewsViewed(newsId, { liked: false });
            this.newsFeed = this.newsFeed.map((item) =>
                item.id === Number(newsId) ? { ...item, is_viewed: true } : item
            );
            this.renderNewsWidget();
            if (this.modalOpen) {
                this.renderNewsModal(newsId);
            }
        } catch (error) {
            console.error('[BrandingNews] Error marking news read:', error);
        }
    }

    async toggleNewsLike(newsId, like) {
        try {
            await api.markNewsViewed(newsId, { like });
            this.newsFeed = this.newsFeed.map((item) =>
                item.id === Number(newsId) ? { ...item, liked: like, is_viewed: true } : item
            );
            this.renderNewsWidget();
            this.renderNewsModal(newsId);
        } catch (error) {
            console.error('[BrandingNews] Error toggling like:', error);
        }
    }

    openNewsLink(url) {
        if (!url) return;
        if (telegramWebApp?.openTelegramLink) {
            telegramWebApp.openTelegramLink(url);
        } else {
            window.open(url, '_blank', 'noopener');
        }
    }

    formatDateLabel(value) {
        if (!value) return '—';
        const numeric = parseInt(value, 10);
        if (!Number.isNaN(numeric) && numeric > 1000000000) {
            return new Date(numeric * 1000).toLocaleDateString('uk-UA');
        }
        const parsed = Date.parse(value);
        if (!Number.isNaN(parsed)) {
            return new Date(parsed).toLocaleDateString('uk-UA');
        }
        return value;
    }

    escapeHtml(value) {
        if (value === null || value === undefined) return '';
        return String(value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    formatNewsBody(text) {
        return this.escapeHtml(text || '').replace(/\n/g, '<br>');
    }
}

window.initBrandingNews = function initBrandingNews(options) {
    const manager = new BrandingNewsManager(options);
    manager.init();
    return manager;
};

