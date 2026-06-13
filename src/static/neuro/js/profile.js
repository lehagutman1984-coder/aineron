(function() {
    'use strict';

    // Данные пользователя
    let userData = null;
    let trialTariff = null;
    let purchases = [];
    let spendings = [];

    // Состояние
    let currentTab = 'purchases';
    let currentPage = 1;
    const itemsPerPage = 5;

    // Для попапа
    let activeConfirmPopup = null;

    // Для управления подпиской
    let pendingAction = null;
    let timerInterval = null;
    let secondsLeft = 0;

    // Элементы DOM
    const userNameEl = document.querySelector('.user-fullname');
    const userEmailEl = document.querySelector('.user-email');
    const userDaysEl = document.querySelector('.user-days');
    const tariffBadgeEl = document.querySelector('.user-tariff-badge');
    const starBalanceEl = document.getElementById('profileStarBalance');
    const logoutBtn = document.getElementById('logoutBtn');
    const promoInput = document.getElementById('promoInput');
    const applyPromoBtn = document.getElementById('applyPromoBtn');
    const promoMessage = document.getElementById('promoMessage');
    const historyList = document.getElementById('historyList');
    const historyPagination = document.getElementById('historyPagination');
    const historyTabs = document.querySelectorAll('.history-tab');
    const tariffCardContainer = document.querySelector('.tariff-card');
    const tariffActivateBtn = document.querySelector('.tariff-activate-btn');

    // Элементы управления подпиской
    const manageSubscriptionBtn = document.getElementById('manageSubscriptionBtn');
    const subscriptionModal = document.getElementById('subscriptionModal');
    const subscriptionModalOverlay = document.getElementById('subscriptionModalOverlay');
    const subscriptionModalClose = document.getElementById('subscriptionModalClose');
    const subscriptionModalCloseBtn = document.getElementById('subscriptionModalCloseBtn');
    const autoRenewalToggle = document.getElementById('autoRenewalToggle');
    const confirmationBlock = document.getElementById('confirmationBlock');
    const verifyCodeBtn = document.getElementById('verifyCodeBtn');
    const resendCodeBtn = document.getElementById('resendCodeBtn');
    const confirmationCode = document.getElementById('confirmationCode');
    const resendTimer = document.getElementById('resendTimer');
    const currentTariffName = document.getElementById('currentTariffName');
    const currentTariffStars = document.getElementById('currentTariffStars');
    const currentTariffExpiry = document.getElementById('currentTariffExpiry');

    // ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
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

    function showNotification(message, type = 'success') {
        const old = document.querySelector('.chat-notification');
        if (old) old.remove();
        const note = document.createElement('div');
        note.className = 'chat-notification';
        let icon = type === 'error' ? 'fa-exclamation-circle' : 'fa-check-circle';
        let color = type === 'error' ? '#e53e3e' : '#21be19';
        note.innerHTML = `<i class="fas ${icon}"></i><span>${message}</span>`;
        note.style.cssText = `
            position: fixed; top: 20px; right: 20px; background: white;
            padding: 12px 20px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            display: flex; align-items: center; gap: 10px; z-index: 10001;
            font-size: 14px; font-weight: 500; color: #0d0d0d;
            border-left: 4px solid ${color}; animation: slideInRight 0.3s ease;
        `;
        document.body.appendChild(note);
        setTimeout(() => note.remove(), 4000);
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

    // ========== ОТОБРАЖЕНИЕ СООБЩЕНИЙ ИЗ DJANGO ==========
    function displayDjangoMessages() {
        const messagesContainer = document.getElementById('django-messages');
        if (!messagesContainer) return;
        const messages = messagesContainer.querySelectorAll('[data-message]');
        messages.forEach(msg => {
            const text = msg.getAttribute('data-message');
            const tags = msg.getAttribute('data-tags');
            let type = 'info';
            if (tags.includes('success')) type = 'success';
            else if (tags.includes('error')) type = 'error';
            else if (tags.includes('warning')) type = 'warning';
            showNotification(text, type);
        });
    }

    // ========== ПОПАП ПОДТВЕРЖДЕНИЯ (для покупки тарифа) ==========
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

    function showConfirmPopup(tariff) {
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
                    <span>Звезд по тарифу:</span>
                    <strong>${tariff.pages} <i class="fas fa-star"></i></strong>
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

    // ========== УПРАВЛЕНИЕ ПОДПИСКОЙ ==========
    function loadSubscriptionStatus() {
        return fetch('/users/api/subscription-status/', {
            method: 'GET',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                if (currentTariffName) currentTariffName.textContent = data.tariff_name || '—';
                if (currentTariffStars) currentTariffStars.textContent = data.pages_count || 0;
                if (currentTariffExpiry) {
                    if (data.expires_at) {
                        const date = new Date(data.expires_at);
                        currentTariffExpiry.textContent = date.toLocaleDateString('ru-RU');
                    } else {
                        currentTariffExpiry.textContent = '—';
                    }
                }
                if (autoRenewalToggle) autoRenewalToggle.checked = data.auto_renew === true;
                return data;
            }
            return null;
        })
        .catch(error => {
            console.error('Error loading subscription status:', error);
            return null;
        });
    }

    function enableAutoRenewal() {
        fetch('/users/api/update-auto-renewal/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin',
            body: JSON.stringify({ auto_renew: true })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('Автопродление включено', 'success');
            } else {
                showNotification(data.message || 'Ошибка при включении автопродления', 'error');
                loadSubscriptionStatus();
            }
        })
        .catch(error => {
            console.error('Error enabling auto-renewal:', error);
            showNotification('Ошибка соединения с сервером', 'error');
            loadSubscriptionStatus();
        });
    }

    function disableAutoRenewal() {
        fetch('/users/api/update-auto-renewal/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin',
            body: JSON.stringify({ auto_renew: false })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showNotification('Автопродление отключено', 'success');
            } else {
                showNotification(data.message || 'Ошибка при отключении автопродления', 'error');
                loadSubscriptionStatus();
            }
        })
        .catch(error => {
            console.error('Error disabling auto-renewal:', error);
            showNotification('Ошибка соединения с сервером', 'error');
            loadSubscriptionStatus();
        });
    }

    function sendConfirmationCode(action) {
        fetch('/users/api/send-renewal-code/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin',
            body: JSON.stringify({ action: action })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('Код отправлен на почту');
                startResendTimer(60);
            } else {
                showNotification(data.message || 'Ошибка при отправке кода', 'error');
                resetConfirmationBlock();
                loadSubscriptionStatus();
            }
        })
        .catch(error => {
            console.error('Error sending code:', error);
            showNotification('Ошибка соединения с сервером', 'error');
            resetConfirmationBlock();
            loadSubscriptionStatus();
        });
    }

    function verifyCode() {
        const code = confirmationCode.value.trim();
        if (code.length !== 6) {
            showNotification('Введите 6-значный код', 'error');
            return;
        }

        verifyCodeBtn.disabled = true;
        verifyCodeBtn.textContent = 'Проверка...';

        fetch('/users/api/verify-renewal-code/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin',
            body: JSON.stringify({ code: code })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                disableAutoRenewal();
                showNotification('Автопродление отключено', 'success');
                setTimeout(() => {
                    closeSubscriptionModal();
                }, 1500);
            } else {
                showNotification(data.message || 'Неверный код подтверждения', 'error');
                verifyCodeBtn.disabled = false;
                verifyCodeBtn.textContent = 'Подтвердить';
                confirmationCode.value = '';
                loadSubscriptionStatus();
            }
        })
        .catch(error => {
            console.error('Verify error:', error);
            showNotification('Ошибка соединения с сервером', 'error');
            verifyCodeBtn.disabled = false;
            verifyCodeBtn.textContent = 'Подтвердить';
            loadSubscriptionStatus();
        });
    }

    function startResendTimer(seconds) {
        secondsLeft = seconds;
        resendCodeBtn.disabled = true;
        if (timerInterval) clearInterval(timerInterval);
        timerInterval = setInterval(() => {
            secondsLeft--;
            const minutes = Math.floor(secondsLeft / 60);
            const secs = secondsLeft % 60;
            resendTimer.textContent = `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
            if (secondsLeft <= 0) {
                clearInterval(timerInterval);
                timerInterval = null;
                resendCodeBtn.disabled = false;
                resendTimer.textContent = '';
            }
        }, 1000);
    }

    function resendCode() {
        resendCodeBtn.disabled = true;
        resendCodeBtn.textContent = 'Отправка...';
        fetch('/users/api/resend-renewal-code/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest'
            },
            credentials: 'same-origin',
            body: JSON.stringify({})
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                startResendTimer(60);
                resendCodeBtn.disabled = false;
                resendCodeBtn.textContent = 'Отправить повторно';
            } else {
                showNotification(data.message || 'Ошибка при отправке кода', 'error');
                resendCodeBtn.disabled = false;
                resendCodeBtn.textContent = 'Отправить повторно';
            }
        })
        .catch(error => {
            console.error('Resend error:', error);
            showNotification('Ошибка соединения с сервером', 'error');
            resendCodeBtn.disabled = false;
            resendCodeBtn.textContent = 'Отправить повторно';
        });
    }

    function showConfirmationBlock() {
        confirmationBlock.style.display = 'block';
        sendConfirmationCode('disable');
    }

    function resetConfirmationBlock() {
        confirmationBlock.style.display = 'none';
        confirmationCode.value = '';
        if (timerInterval) {
            clearInterval(timerInterval);
            timerInterval = null;
        }
        resendCodeBtn.disabled = false;
        resendTimer.textContent = '';
    }

    function openSubscriptionModal() {
        loadSubscriptionStatus().then(() => {
            subscriptionModal.classList.add('show');
            document.body.style.overflow = 'hidden';
            resetConfirmationBlock();
        });
    }

    function closeSubscriptionModal() {
        subscriptionModal.classList.remove('show');
        document.body.style.overflow = '';
        resetConfirmationBlock();
        pendingAction = null;
    }

    function initSubscriptionManagement() {
        if (manageSubscriptionBtn) {
            manageSubscriptionBtn.addEventListener('click', openSubscriptionModal);
        }

        if (subscriptionModalClose) subscriptionModalClose.addEventListener('click', closeSubscriptionModal);
        if (subscriptionModalCloseBtn) subscriptionModalCloseBtn.addEventListener('click', closeSubscriptionModal);
        if (subscriptionModalOverlay) subscriptionModalOverlay.addEventListener('click', closeSubscriptionModal);

        if (autoRenewalToggle) {
            autoRenewalToggle.addEventListener('change', function(e) {
                if (e.target.checked) {
                    enableAutoRenewal();
                } else {
                    pendingAction = 'disable';
                    showConfirmationBlock();
                }
            });
        }

        if (verifyCodeBtn) verifyCodeBtn.addEventListener('click', verifyCode);
        if (resendCodeBtn) resendCodeBtn.addEventListener('click', resendCode);
        if (confirmationCode) {
            confirmationCode.addEventListener('input', function(e) {
                this.value = this.value.replace(/[^0-9]/g, '').slice(0, 6);
                if (this.value.length === 6) verifyCode();
            });
        }
    }

    // ========== ЗАГРУЗКА ДАННЫХ ПРОФИЛЯ ==========
    async function loadProfileData() {
        try {
            const response = await fetch('/users/api/profile-data/', {
                method: 'GET',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const data = await response.json();
            if (data.success) {
                userData = data.user;
                trialTariff = data.trial_tariff;
                purchases = data.history || [];
                spendings = data.spendings || [];
                renderUserInfo();
                renderTariffCard();
                renderHistory();
            } else {
                showNotification('Ошибка загрузки профиля', 'error');
            }
        } catch (err) {
            console.error(err);
            showNotification('Ошибка сети', 'error');
        }
    }

    // ========== ОТОБРАЖЕНИЕ ИНФОРМАЦИИ О ПОЛЬЗОВАТЕЛЕ ==========
    function renderUserInfo() {
        if (!userData) return;
        if (userNameEl) userNameEl.textContent = userData.name;
        if (userEmailEl) userEmailEl.textContent = userData.email;
        if (userDaysEl) userDaysEl.textContent = `${userData.days} дней с нами`;
        if (tariffBadgeEl) tariffBadgeEl.textContent = userData.tariff;
        if (starBalanceEl) starBalanceEl.textContent = userData.stars;
        const headerStarBalance = document.getElementById('starBalance');
        if (headerStarBalance) headerStarBalance.textContent = userData.stars;
        const avatarImg = document.querySelector('.user-avatar img');
        if (avatarImg && userData.avatar_url) avatarImg.src = userData.avatar_url;
    }

    // ========== ОТОБРАЖЕНИЕ КАРТОЧКИ ПРОБНОГО ТАРИФА ==========
    function renderTariffCard() {
        if (!tariffCardContainer) return;
        const isFree = userData.tariff === 'Бесплатный';
        if (isFree && trialTariff) {
            tariffCardContainer.style.display = 'block';
            const tariffNameEl = tariffCardContainer.querySelector('.tariff-title h3');
            const tariffBadgeSpan = tariffCardContainer.querySelector('.tariff-title .tariff-badge');
            const priceValue = tariffCardContainer.querySelector('.price-value');
            const pricePeriod = tariffCardContainer.querySelector('.price-period');
            if (tariffNameEl) tariffNameEl.textContent = trialTariff.display_name;
            if (tariffBadgeSpan) tariffBadgeSpan.innerHTML = `${trialTariff.pages} <i class="fas fa-star"></i>`;
            if (priceValue) priceValue.textContent = `${trialTariff.price} ₽`;
            if (pricePeriod) pricePeriod.textContent = trialTariff.duration_days === 7 ? '/нед' : '/мес';
        } else {
            tariffCardContainer.style.display = 'none';
        }
    }

    // ========== АКТИВАЦИЯ ПРОБНОГО ТАРИФА ==========
    async function handleActivateTariff() {
        if (!trialTariff) return;
        const tariffData = {
            id: trialTariff.id,
            display_name: trialTariff.display_name,
            price: trialTariff.price,
            pages: trialTariff.pages
        };
        showConfirmPopup(tariffData);
    }

    // ========== ПОЛУЧЕНИЕ ТЕКУЩЕЙ ИСТОРИИ ==========
    function getCurrentHistory() {
        return currentTab === 'purchases' ? purchases : spendings;
    }

    // ========== ОТОБРАЖЕНИЕ ИСТОРИИ ==========
    function renderHistory() {
        const filtered = getCurrentHistory();
        const totalPages = Math.ceil(filtered.length / itemsPerPage);
        const start = (currentPage - 1) * itemsPerPage;
        const end = start + itemsPerPage;
        const pageItems = filtered.slice(start, end);

        if (pageItems.length === 0) {
            historyList.innerHTML = '<div class="history-empty">Нет операций</div>';
        } else {
            historyList.innerHTML = pageItems.map(item => {
                const sign = currentTab === 'purchases' ? '+' : '-';
                return `
                    <div class="history-item">
                        <div class="history-info">
                            <div class="history-date">${escapeHtml(item.date)}</div>
                            <div class="history-description">${escapeHtml(item.description)}</div>
                        </div>
                        <div class="history-amount">
                            <span class="amount-value">${sign}${item.amount}</span>
                            <i class="fas fa-star"></i>
                        </div>
                    </div>
                `;
            }).join('');
        }

        let paginationHtml = '';
        if (totalPages > 1) {
            paginationHtml += `<button class="pagination-btn" data-page="prev" ${currentPage === 1 ? 'disabled' : ''}>‹</button>`;
            for (let i = 1; i <= totalPages; i++) {
                paginationHtml += `<button class="pagination-btn ${i === currentPage ? 'active' : ''}" data-page="${i}">${i}</button>`;
            }
            paginationHtml += `<button class="pagination-btn" data-page="next" ${currentPage === totalPages ? 'disabled' : ''}>›</button>`;
        }
        historyPagination.innerHTML = paginationHtml;

        document.querySelectorAll('.pagination-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const page = e.target.dataset.page;
                if (page === 'prev') {
                    if (currentPage > 1) currentPage--;
                } else if (page === 'next') {
                    if (currentPage < totalPages) currentPage++;
                } else {
                    currentPage = parseInt(page, 10);
                }
                renderHistory();
            });
        });
    }

    // ========== АКТИВАЦИЯ ПРОМОКОДА ==========
    async function applyPromoCode() {
        const code = promoInput.value.trim();
        if (!code) {
            promoMessage.textContent = 'Введите промокод';
            promoMessage.className = 'promo-message error';
            return;
        }
        promoMessage.textContent = '';
        try {
            const response = await fetch('/users/api/apply-promo/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ code: code })
            });
            const data = await response.json();
            if (data.success) {
                promoMessage.textContent = data.message;
                promoMessage.className = 'promo-message success';
                promoInput.value = '';
                if (starBalanceEl) starBalanceEl.textContent = data.new_balance;
                const headerStarBalance = document.getElementById('starBalance');
                if (headerStarBalance) headerStarBalance.textContent = data.new_balance;
                if (userData) userData.stars = data.new_balance;
                await loadProfileData();
            } else {
                promoMessage.textContent = data.message;
                promoMessage.className = 'promo-message error';
            }
        } catch (err) {
            console.error(err);
            promoMessage.textContent = 'Ошибка сети';
            promoMessage.className = 'promo-message error';
        }
    }

    // ========== ВЫХОД ==========
    async function logout() {
        if (confirm('Вы уверены, что хотите выйти?')) {
            try {
                const response = await fetch('/users/api/ajax/logout/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });
                const data = await response.json();
                if (data.success) {
                    window.location.href = '/';
                } else {
                    showNotification('Ошибка выхода', 'error');
                }
            } catch (err) {
                console.error(err);
                showNotification('Ошибка сети', 'error');
            }
        }
    }

    // ========== ПЕРЕКЛЮЧЕНИЕ ТАБОВ ==========
    function initTabs() {
        historyTabs.forEach(tab => {
            tab.addEventListener('click', () => {
                historyTabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                currentTab = tab.dataset.tab;
                currentPage = 1;
                renderHistory();
            });
        });
    }

    // ========== ИНИЦИАЛИЗАЦИЯ ==========
    function init() {
        if (logoutBtn) logoutBtn.addEventListener('click', logout);
        if (applyPromoBtn) applyPromoBtn.addEventListener('click', applyPromoCode);
        if (tariffActivateBtn) tariffActivateBtn.addEventListener('click', handleActivateTariff);
        initTabs();
        initSubscriptionManagement();
        loadProfileData();
        displayDjangoMessages();
    }

    init();
})();