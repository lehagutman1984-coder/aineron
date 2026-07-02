(function() {
    'use strict';

    let currentTariffId = null;
    let activeConfirmPopup = null;

    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.content;
        let cookie = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const c = cookies[i].trim();
                if (c.startsWith('csrftoken=')) {
                    cookie = decodeURIComponent(c.substring('csrftoken='.length));
                    break;
                }
            }
        }
        return cookie;
    }

    function showNotification(message, type = 'info') {
        const old = document.querySelector('.tariff-notification');
        if (old) old.remove();
        const note = document.createElement('div');
        note.className = 'tariff-notification';
        let icon = 'fa-info-circle';
        let color = '#f0a38a';
        if (type === 'success') { icon = 'fa-check-circle'; color = '#21be19'; }
        else if (type === 'error') { icon = 'fa-exclamation-circle'; color = '#e53e3e'; }
        note.innerHTML = `<i class="fas ${icon}"></i><span>${message}</span>`;
        note.style.cssText = `
            position: fixed; bottom: 20px; right: 20px; background: white;
            padding: 12px 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            display: flex; align-items: center; gap: 10px; z-index: 10001;
            font-size: 14px; font-weight: 500; color: #0d0d0d;
            border-left: 4px solid ${color}; animation: slideInRight 0.3s ease;
        `;
        document.body.appendChild(note);
        setTimeout(() => note.remove(), 4000);
    }

    function closeConfirmPopup() {
        if (activeConfirmPopup) {
            activeConfirmPopup.remove();
            activeConfirmPopup = null;
        }
    }

    function positionPopup(popup) {
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;
        const popupRect = popup.getBoundingClientRect();

        let top = (viewportHeight - popupRect.height) / 2;
        let left = (viewportWidth - popupRect.width) / 2;

        if (top < 10) top = 10;
        if (left < 10) left = 10;

        popup.style.position = 'fixed';
        popup.style.top = `${top}px`;
        popup.style.left = `${left}px`;
        popup.style.transform = 'none';
        popup.style.zIndex = '10002';
    }

    function showConfirmPopup(tariff, buttonElement) {
        closeConfirmPopup();

        const termsUrl = document.querySelector('meta[name="terms-url"]').content;
        const privacyUrl = document.querySelector('meta[name="privacy-url"]').content;

        const popup = document.createElement('div');
        popup.className = 'tariff-confirm-popup';
        popup.innerHTML = `
            <div class="tariff-confirm-header">
                <h3>Подтверждение покупки</h3>
                <button class="tariff-confirm-close"><i class="fas fa-times"></i></button>
            </div>
            <div class="tariff-confirm-body">
                <div class="confirm-row">
                    <span>Приобретаемый тариф:</span>
                    <strong>${escapeHtml(tariff.display_name)}</strong>
                </div>
                <div class="confirm-row">
                    <span>Сумма:</span>
                    <strong>${tariff.price} ₽</strong>
                </div>
                <div class="confirm-row">
                    <span>Начисление на баланс:</span>
                    <strong>${tariff.pages} ₽</strong>
                </div>
                <div class="confirm-checkbox">
                    <label>
                        <input type="checkbox" id="confirmTermsCheckbox">
                        <span>Нажимая «Оплатить», я даю согласие на регулярные списания, обработку данных и принимаю условия <a href="${termsUrl}" target="_blank">пользовательского соглашения</a> и <a href="${privacyUrl}" target="_blank">политики конфиденциальности</a>.</span>
                    </label>
                </div>
            </div>
            <div class="tariff-confirm-footer">
                <button class="tariff-confirm-btn cancel">Отмена</button>
                <button class="tariff-confirm-btn pay" disabled>Оплатить</button>
            </div>
        `;

        document.body.appendChild(popup);
        activeConfirmPopup = popup;

        requestAnimationFrame(() => {
            positionPopup(popup);
        });

        const closeBtn = popup.querySelector('.tariff-confirm-close');
        const cancelBtn = popup.querySelector('.cancel');
        const payBtn = popup.querySelector('.pay');
        const checkbox = popup.querySelector('#confirmTermsCheckbox');

        const closePopup = () => {
            closeConfirmPopup();
        };

        closeBtn.addEventListener('click', closePopup);
        cancelBtn.addEventListener('click', closePopup);
        checkbox.addEventListener('change', () => {
            payBtn.disabled = !checkbox.checked;
        });

        payBtn.addEventListener('click', async () => {
            if (!checkbox.checked) return;
            payBtn.disabled = true;
            payBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Оплата...';
            try {
                const response = await fetch('/users/api/create-payment/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken(),
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({ tariff_id: tariff.id })
                });
                const data = await response.json();
                if (data.success && data.form_html) {
                    const div = document.createElement('div');
                    div.innerHTML = data.form_html;
                    document.body.appendChild(div);
                    const form = div.querySelector('form');
                    if (form) form.submit();
                } else {
                    showNotification(data.message || 'Ошибка при создании платежа', 'error');
                    closeConfirmPopup();
                }
            } catch (err) {
                console.error(err);
                showNotification('Ошибка сети. Попробуйте позже.', 'error');
                closeConfirmPopup();
            }
        });
    }

    async function loadTariffs() {
        try {
            const response = await fetch('/users/api/tariffs/', {
                method: 'GET',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const data = await response.json();
            if (data.success) {
                currentTariffId = data.current_tariff ? data.current_tariff.id : null;
                renderTariffs(data.tariffs.paid);
            } else {
                showNotification('Ошибка загрузки тарифов', 'error');
                document.getElementById('tariffsGrid').innerHTML = '<div class="error-message">Не удалось загрузить тарифы</div>';
            }
        } catch (err) {
            console.error(err);
            showNotification('Ошибка сети', 'error');
            document.getElementById('tariffsGrid').innerHTML = '<div class="error-message">Ошибка загрузки</div>';
        }
    }

    function renderTariffs(tariffs) {
        const grid = document.getElementById('tariffsGrid');
        if (!grid) return;
        if (!tariffs || tariffs.length === 0) {
            grid.innerHTML = '<div class="no-tariffs">Нет доступных тарифов</div>';
            return;
        }

        grid.innerHTML = '';
        tariffs.forEach(tariff => {
            const isCurrent = currentTariffId === tariff.id;
            const isPopular = tariff.display_name === 'Ultima';
            const card = document.createElement('div');
            card.className = `tariff-card-modal ${isPopular ? 'popular-card' : ''}`;

            const period = tariff.duration_days === 7 ? 'нед' : 'мес';

            let trialNote = '';
            if (tariff.is_trial && tariff.next_tariff) {
                trialNote = `<li class="feature-note"><i class="fas fa-exchange-alt"></i> Пробный период ${tariff.duration_days} дней, затем автоматический переход на ${escapeHtml(tariff.next_tariff.display_name)} с оплатой ${tariff.next_tariff.price} ₽</li>`;
            }

            const buttonHtml = isCurrent
                ? `<button class="tariff-activate-btn" disabled data-tariff-id="${tariff.id}">Текущий тариф</button>`
                : `<button class="tariff-activate-btn" data-tariff-id="${tariff.id}">Активировать</button>`;

            let descriptionHtml = '';
            if (tariff.description && tariff.description.trim() !== '') {
                descriptionHtml = tariff.description;
            }

            // Безлимитные нейросети
            let unlimitedNetworksHtml = '';
            if (tariff.unlimited_networks && tariff.unlimited_networks.trim() !== '') {
                unlimitedNetworksHtml = `<li><i class="fas fa-check-circle"></i> Безлимитный DeepSeek V3.1, GPT-5 Nano, Нейросети для развлечений и другие!</li>`;
            } else {
                unlimitedNetworksHtml = `<li><i class="fas fa-check-circle"></i> Безлимитный DeepSeek V3.1, GPT-5 Nano, Нейросети для развлечений и другие!</li>`;
            }

            let priceBlock = `
                <div class="tariff-price-block">
                    <span class="tariff-price">${tariff.price} ₽</span>
                    <span class="tariff-period">/${period}</span>
                </div>
                ${descriptionHtml}
            `;

            card.innerHTML = `
                <div class="tariff-card-modal-header">
                    <h3 class="tariff-name">${escapeHtml(tariff.display_name)}</h3>
                    ${priceBlock}
                </div>
                ${buttonHtml}
                <ul class="tariff-features">
                    <li><i class="fas fa-star"></i> ${tariff.pages} ₽ на баланс ${!tariff.is_trial ? 'каждый месяц' : ''}</li>
                    <li><i class="fas fa-check-circle"></i> Доступ к ChatGPT, Gemini, Claude и еще 400 других нейросетей!</li>
                    ${unlimitedNetworksHtml}
                    ${trialNote}
                </ul>
            `;
            grid.appendChild(card);
        });

        document.querySelectorAll('.tariff-activate-btn:not([disabled])').forEach(btn => {
            btn.removeEventListener('click', handleActivateClick);
            btn.addEventListener('click', handleActivateClick);
        });
    }

    async function handleActivateClick(e) {
        const btn = e.currentTarget;
        const tariffId = btn.dataset.tariffId;
        if (!tariffId) return;

        const card = btn.closest('.tariff-card-modal');
        if (!card) return;

        const name = card.querySelector('.tariff-name')?.textContent.trim();
        const priceText = card.querySelector('.tariff-price')?.textContent.trim();
        const pagesText = card.querySelector('.tariff-features li:first-child')?.textContent.trim();
        if (!name || !priceText || !pagesText) {
            showNotification('Ошибка: не удалось получить данные тарифа', 'error');
            return;
        }

        const price = parseInt(priceText, 10);
        const pages = parseInt(pagesText.match(/\d+/)[0], 10);

        const tariffData = {
            id: parseInt(tariffId, 10),
            display_name: name,
            price: price,
            pages: pages
        };
        showConfirmPopup(tariffData, btn);
    }

    function escapeHtml(str) {
        if (!str) return '';
        return str.replace(/[&<>]/g, function(m) {
            if (m === '&') return '&amp;';
            if (m === '<') return '&lt;';
            if (m === '>') return '&gt;';
            return m;
        });
    }

    class TariffsModal {
        constructor() {
            this.overlay = document.getElementById('tariffsModalOverlay');
            if (!this.overlay) return;
            this.init();
        }

        init() {
            this.overlay.addEventListener('click', (e) => {
                if (e.target.closest('#tariffsCloseBtn') || e.target === this.overlay) {
                    this.close();
                }
            });
            window.openTariffsModal = () => this.open();
        }

        async open() {
            this.overlay.classList.add('show');
            document.body.style.overflow = 'hidden';
            await loadTariffs();
        }

        close() {
            this.overlay.classList.remove('show');
            document.body.style.overflow = '';
            closeConfirmPopup();
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => new TariffsModal());
    } else {
        new TariffsModal();
    }
})();
