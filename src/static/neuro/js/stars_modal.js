/**
 * Модальное окно для покупки звезд
 */
class PagesModal {
    constructor() {
        this.modal = null;
        this.overlay = null;
        this.container = null;
        this.pricePerPage = 0;
        this.minPages = 1;
        this.maxPages = 100;
        this.selectedPages = 10;
        this.isLoading = false;

        this.init();
    }

    init() {
        console.log('PagesModal init');
        this.createModal();
        this.loadPriceSettings();
        this.attachStarsClickHandler();
    }

    createModal() {
        const oldModal = document.getElementById('pagesModal');
        if (oldModal) oldModal.remove();

        this.modal = document.createElement('div');
        this.modal.className = 'pages-modal';
        this.modal.id = 'pagesModal';

        this.overlay = document.createElement('div');
        this.overlay.className = 'pages-modal-overlay';
        this.overlay.addEventListener('click', () => this.close());

        this.container = document.createElement('div');
        this.container.className = 'pages-modal-container';

        this.container.innerHTML = `
            <div class="pages-modal-header">
                <h2>
                    <i class="fas fa-shopping-cart"></i>
                    Пополнение баланса
                </h2>
                <button class="pages-modal-close" id="pagesModalClose">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="pages-modal-body">
                <div class="current-balance">
                    <div class="balance-label">
                        <i class="fas fa-file-alt"></i>
                        <span>Доступно сейчас</span>
                    </div>
                    <div class="balance-value">
                        <span id="currentPagesBalance">0</span>
                        <span>₽</span>
                    </div>
                </div>

                <div class="pages-selector">
                    <label class="pages-labels">Выберите сумму пополнения</label>
                    <div class="pages-presets">
                        <button class="pages-preset-btn" data-pages="50">
                            <span>50</span>
                            <span>₽</span>
                        </button>
                        <button class="pages-preset-btn" data-pages="100">
                            <span>100</span>
                            <span>₽</span>
                        </button>
                        <button class="pages-preset-btn" data-pages="500">
                            <span>500</span>
                            <span>₽</span>
                        </button>
                        <button class="pages-preset-btn" data-pages="1000">
                            <span>1000</span>
                            <span>₽</span>
                        </button>
                    </div>

                    <div class="custom-input-group">
                        <div class="custom-input-wrapper">
                            <i class="fas fa-pencil-alt"></i>
                            <input type="number" class="pages-custom-input" id="customPagesInput"
                                   placeholder="Своё количество" min="1" max="1000" value="">
                        </div>
                    </div>
                    <div id="pagesInputError" class="error-message" style="display: none;"></div>
                </div>

                <div class="price-info">
                    <div class="price-row">
                        <span class="price-label">
                            <i class="fas fa-tag"></i>
                            Цена за 1 ₽ баланса
                        </span>
                        <span class="price-value" id="pricePerPageDisplay">0 ₽</span>
                    </div>
                    <div class="price-row total-price">
                        <span class="price-label">
                            <i class="fas fa-calculator"></i>
                            Итого к оплате
                        </span>
                        <span class="price-value" id="totalPriceDisplay">0 ₽</span>
                    </div>
                </div>
            </div>
            <div class="pages-modal-footer">
                <button class="pages-modal-btn cancel" id="cancelPurchaseBtn">
                    <i class="fas fa-times"></i>
                    Отмена
                </button>
                <button class="pages-modal-btn buy" id="confirmPurchaseBtn" disabled>
                    <i class="fas fa-shopping-cart"></i>
                    Купить
                </button>
            </div>
        `;

        this.modal.appendChild(this.overlay);
        this.modal.appendChild(this.container);
        document.body.appendChild(this.modal);

        this.addEventListeners();
        console.log('Modal created');
    }

    addEventListeners() {
        const closeBtn = this.modal.querySelector('#pagesModalClose');
        if (closeBtn) closeBtn.addEventListener('click', () => this.close());

        const cancelBtn = this.modal.querySelector('#cancelPurchaseBtn');
        if (cancelBtn) cancelBtn.addEventListener('click', () => this.close());

        const buyBtn = this.modal.querySelector('#confirmPurchaseBtn');
        if (buyBtn) buyBtn.addEventListener('click', () => this.purchase());

        const presetBtns = this.modal.querySelectorAll('.pages-preset-btn');
        presetBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const pages = parseInt(btn.dataset.pages);
                this.selectPages(pages);
                const customInput = this.modal.querySelector('#customPagesInput');
                if (customInput) {
                    customInput.value = '';
                    customInput.classList.remove('error');
                }
            });
        });

        const customInput = this.modal.querySelector('#customPagesInput');
        if (customInput) {
            customInput.addEventListener('input', (e) => {
                const value = e.target.value.trim();
                if (value === '') {
                    this.clearSelection();
                    return;
                }
                const pages = parseInt(value);
                if (!isNaN(pages)) this.selectPages(pages);
            });
            customInput.addEventListener('blur', (e) => {
                const value = e.target.value.trim();
                if (value === '') {
                    this.clearSelection();
                } else {
                    const pages = parseInt(value);
                    if (!isNaN(pages)) this.selectPages(pages);
                }
            });
        }
    }

    attachStarsClickHandler() {
        const starsBlock = document.getElementById('starsBlock') || document.querySelector('.stars');
        if (starsBlock) {
            starsBlock.style.cursor = 'pointer';
            // Удаляем старый обработчик
            const newStars = starsBlock.cloneNode(true);
            starsBlock.parentNode.replaceChild(newStars, starsBlock);
            newStars.addEventListener('click', async (e) => {
                e.preventDefault();
                console.log('Stars clicked');
                // Проверяем наличие активной подписки
                const hasActiveSubscription = await this.checkSubscriptionStatus();
                if (hasActiveSubscription) {
                    // Открываем окно покупки звезд
                    this.open();
                } else {
                    // Открываем окно тарифов
                    if (typeof openTariffsModal === 'function') {
                        openTariffsModal();
                    } else {
                        console.warn('openTariffsModal not defined');
                    }
                }
            });
            console.log('Stars click handler attached');
        } else {
            console.warn('Stars block not found');
        }
    }

    async checkSubscriptionStatus() {
        try {
            const response = await fetch('/users/api/subscription-status/', {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const data = await response.json();
            // data.success и data.has_subscription, data.is_free
            if (data.success) {
                // Если есть подписка и она не бесплатная (или активная)
                // Поскольку бесплатный тариф может быть у всех, считаем что подписка есть, если не is_free
                // Либо проверяем has_subscription и не is_free
                return data.has_subscription === true && data.is_free === false;
            }
            return false;
        } catch (err) {
            console.error('Ошибка проверки подписки:', err);
            return false;
        }
    }

    loadPriceSettings() {
        fetch('/users/api/page-settings/')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    this.pricePerPage = parseFloat(data.price_per_page);
                    this.minPages = data.min_pages || 1;
                    this.maxPages = data.max_pages || 100;
                    this.updatePriceDisplay();
                }
            })
            .catch(error => {
                console.error('Ошибка загрузки настроек цен:', error);
                this.pricePerPage = 2;
                this.updatePriceDisplay();
            });
    }

    updateBalance(availablePages) {
        const balanceEl = this.modal.querySelector('#currentPagesBalance');
        if (balanceEl) balanceEl.textContent = availablePages;
    }

    selectPages(pages) {
        if (pages < this.minPages) {
            this.showError(`Минимальная сумма пополнения: ${this.minPages} ₽`);
            return;
        }
        if (pages > this.maxPages) {
            this.showError(`Максимальная сумма пополнения: ${this.maxPages} ₽`);
            return;
        }
        this.hideError();

        const presetBtns = this.modal.querySelectorAll('.pages-preset-btn');
        presetBtns.forEach(btn => {
            const btnPages = parseInt(btn.dataset.pages);
            btn.classList.toggle('active', btnPages === pages);
        });

        const customInput = this.modal.querySelector('#customPagesInput');
        if (customInput) {
            const hasPreset = Array.from(presetBtns).some(btn => parseInt(btn.dataset.pages) === pages);
            if (!hasPreset) customInput.value = pages;
            customInput.classList.remove('error');
        }

        this.selectedPages = pages;
        const buyBtn = this.modal.querySelector('#confirmPurchaseBtn');
        if (buyBtn) buyBtn.disabled = false;
        this.updatePriceDisplay();
    }

    clearSelection() {
        const presetBtns = this.modal.querySelectorAll('.pages-preset-btn');
        presetBtns.forEach(btn => btn.classList.remove('active'));
        this.selectedPages = 0;
        const buyBtn = this.modal.querySelector('#confirmPurchaseBtn');
        if (buyBtn) buyBtn.disabled = true;
        this.updatePriceDisplay();
        this.hideError();
    }

    updatePriceDisplay() {
        const pricePerPageEl = this.modal.querySelector('#pricePerPageDisplay');
        if (pricePerPageEl) pricePerPageEl.textContent = `${this.pricePerPage.toFixed(2)} ₽`;
        const totalPriceEl = this.modal.querySelector('#totalPriceDisplay');
        if (totalPriceEl) {
            const total = this.selectedPages * this.pricePerPage;
            totalPriceEl.textContent = total > 0 ? `${total.toFixed(2)} ₽` : '0 ₽';
        }
    }

    showError(message) {
        const errorEl = this.modal.querySelector('#pagesInputError');
        if (errorEl) {
            errorEl.textContent = message;
            errorEl.style.display = 'flex';
        }
        const customInput = this.modal.querySelector('#customPagesInput');
        if (customInput) customInput.classList.add('error');
        const buyBtn = this.modal.querySelector('#confirmPurchaseBtn');
        if (buyBtn) buyBtn.disabled = true;
    }

    hideError() {
        const errorEl = this.modal.querySelector('#pagesInputError');
        if (errorEl) errorEl.style.display = 'none';
        const customInput = this.modal.querySelector('#customPagesInput');
        if (customInput) customInput.classList.remove('error');
    }

    open() {
        console.log('Opening modal');
        if (!this.modal) {
            console.error('Modal not created');
            return;
        }
        this.updateCurrentBalance();
        this.clearSelection();
        this.modal.style.display = 'flex';
        this.modal.classList.add('active');
        document.body.style.overflow = 'hidden';
        console.log('Modal opened');
    }

    close() {
        if (!this.modal) return;
        this.modal.style.display = 'none';
        this.modal.classList.remove('active');
        document.body.style.overflow = '';
    }

    updateCurrentBalance() {
        const starBalanceSpan = document.getElementById('starBalance');
        if (starBalanceSpan) {
            const balance = parseInt(starBalanceSpan.textContent) || 0;
            this.updateBalance(balance);
        }
    }

    purchase() {
        if (this.isLoading) return;
        const pagesToBuy = this.selectedPages;
        if (pagesToBuy <= 0) {
            this.showError('Выберите сумму пополнения');
            return;
        }

        this.isLoading = true;
        const buyBtn = this.modal.querySelector('#confirmPurchaseBtn');
        if (buyBtn) {
            buyBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Обработка...';
            buyBtn.disabled = true;
        }

        fetch('/users/api/buy-pages/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin',
            body: JSON.stringify({ pages: pagesToBuy })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.form_html) {
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = data.form_html;
                document.body.appendChild(tempDiv);
                const form = document.getElementById('robokassa_form');
                if (form) form.submit();
                else {
                    if (window.showNotification) window.showNotification('Платеж создан, перенаправление...', 'success');
                    setTimeout(() => window.location.href = '/users/pages/pricing/', 1500);
                }
            } else {
                this.showError(data.message || 'Ошибка при покупке');
                if (window.showNotification) window.showNotification(data.message || 'Ошибка при покупке', 'error');
                this.isLoading = false;
                if (buyBtn) {
                    buyBtn.innerHTML = '<i class="fas fa-shopping-cart"></i> Купить';
                    buyBtn.disabled = false;
                }
            }
        })
        .catch(error => {
            console.error('Purchase error:', error);
            this.showError('Ошибка соединения с сервером');
            if (window.showNotification) window.showNotification('Ошибка соединения с сервером', 'error');
            this.isLoading = false;
            if (buyBtn) {
                buyBtn.innerHTML = '<i class="fas fa-shopping-cart"></i> Купить';
                buyBtn.disabled = false;
            }
        });
    }

    getCsrfToken() {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.startsWith('csrftoken=')) {
                    cookieValue = decodeURIComponent(cookie.substring('csrftoken='.length));
                    break;
                }
            }
        }
        return cookieValue;
    }
}

// Инициализация
document.addEventListener('DOMContentLoaded', function() {
    window.pagesModal = new PagesModal();
});