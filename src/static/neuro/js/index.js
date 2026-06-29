(function() {
    'use strict';

    // DOM элементы
    const desktopChip = document.getElementById('desktopModelChip');
    const desktopPopup = document.getElementById('modelPopupDesktop');
    const desktopModelList = document.getElementById('modelListDesktop');
    const desktopSearchInput = document.getElementById('modelSearchInputDesktop');
    const desktopCategoriesContainer = document.getElementById('modelCategoriesDesktop');
    const selectedModelSpanDesktop = document.getElementById('selectedModelName');
    const desktopAvatar = document.getElementById('desktopModelAvatar');

    const mobileChip = document.getElementById('mobileModelChip');
    const mobilePopup = document.getElementById('modelPopupMobile');
    const mobileModelList = document.getElementById('modelListMobile');
    const mobileSearchInput = document.getElementById('modelSearchInputMobile');
    const mobileCategoriesContainer = document.getElementById('modelCategoriesMobile');
    const selectedModelSpanMobile = document.getElementById('selectedModelNameMobile');
    const mobileAvatar = document.getElementById('mobileModelAvatar');

    // Данные
    let categories = [];
    let allNetworks = [];
    let defaultModel = null;
    let userTariffId = null;

    // Текущая выбранная нейросеть
    let selectedNetworkSlug = null;
    let selectedNetworkName = null;
    let selectedNetworkAvatar = null;

    // Читаем ID тарифа пользователя из мета-тега
    const tariffMeta = document.querySelector('meta[name="user-tariff-id"]');
    if (tariffMeta && tariffMeta.content) {
        userTariffId = parseInt(tariffMeta.content);
    }

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

    // ========== ОТОБРАЖЕНИЕ СООБЩЕНИЙ ИЗ DJANGO MESSAGES ==========
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

    // ========== ИНИЦИАЛИЗАЦИЯ ИЗ МЕТА-ТЕГОВ (для страниц чата) ==========
    function initCurrentModelFromMeta() {
        const currentNetworkNameMeta = document.querySelector('meta[name="current-network-name"]');
        const currentNetworkSlugMeta = document.querySelector('meta[name="current-network-slug"]');
        const currentNetworkAvatarMeta = document.querySelector('meta[name="current-network-avatar"]');
        if (currentNetworkNameMeta && currentNetworkNameMeta.content) {
            const name = currentNetworkNameMeta.content;
            const slug = currentNetworkSlugMeta ? currentNetworkSlugMeta.content : '';
            const avatar = currentNetworkAvatarMeta ? currentNetworkAvatarMeta.content : '';
            selectedNetworkName = name;
            selectedNetworkSlug = slug;
            selectedNetworkAvatar = avatar;
            updateChipDisplay(name, avatar);
            localStorage.setItem('selected_model_slug', slug);
            localStorage.setItem('selected_model_name', name);
            localStorage.setItem('selected_model_avatar', avatar);
            return true;
        }
        return false;
    }

    // ========== РАБОТА С LOCALSTORAGE ==========
    function saveSelectedModel(slug, name, avatar) {
        if (slug && name) {
            localStorage.setItem('selected_model_slug', slug);
            localStorage.setItem('selected_model_name', name);
            localStorage.setItem('selected_model_avatar', avatar || '');
            selectedNetworkSlug = slug;
            selectedNetworkName = name;
            selectedNetworkAvatar = avatar;
            updateChipDisplay(name, avatar);
        }
    }

    function loadSelectedModel() {
        const storedSlug = localStorage.getItem('selected_model_slug');
        const storedName = localStorage.getItem('selected_model_name');
        const storedAvatar = localStorage.getItem('selected_model_avatar');
        if (storedSlug && storedName && allNetworks.some(n => n.slug === storedSlug)) {
            selectedNetworkSlug = storedSlug;
            selectedNetworkName = storedName;
            selectedNetworkAvatar = storedAvatar;
        } else if (defaultModel) {
            selectedNetworkSlug = defaultModel.slug;
            selectedNetworkName = defaultModel.name;
            selectedNetworkAvatar = defaultModel.avatar;
        } else if (allNetworks.length > 0) {
            selectedNetworkSlug = allNetworks[0].slug;
            selectedNetworkName = allNetworks[0].name;
            selectedNetworkAvatar = allNetworks[0].avatar;
        }
        if (selectedNetworkName) {
            updateChipDisplay(selectedNetworkName, selectedNetworkAvatar);
        }
    }

    function updateChipDisplay(name, avatar) {
        if (selectedModelSpanDesktop) selectedModelSpanDesktop.textContent = name;
        if (selectedModelSpanMobile) selectedModelSpanMobile.textContent = name;
        if (desktopAvatar && avatar) desktopAvatar.src = avatar;
        if (mobileAvatar && avatar) mobileAvatar.src = avatar;
    }

    // ========== ЗАГРУЗКА ДАННЫХ С СЕРВЕРА ==========
    async function loadNetworks() {
        try {
            const response = await fetch('/aitext/api/networks/', {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const data = await response.json();
            if (data.success) {
                categories = data.categories;
                defaultModel = data.default_model ? {
                    slug: data.default_model.slug,
                    name: data.default_model.name,
                    avatar: data.default_model.avatar
                } : null;
                // Собираем все нейросети в плоский массив для поиска
                allNetworks = [];
                categories.forEach(cat => {
                    cat.networks.forEach(net => {
                        allNetworks.push({
                            ...net,
                            category: cat.name,
                            category_slug: cat.slug,
                            category_id: cat.id
                        });
                    });
                });
                renderCategories();

                // Если мета-теги не установили модель (например, на главной странице), загружаем из localStorage
                if (!initCurrentModelFromMeta()) {
                    loadSelectedModel();
                }

                // Рендерим список моделей в попапе
                renderNetworks('all', '', selectedNetworkSlug);
                // Рендерим популярные модели на главной
                renderPopularNetworks();
            } else {
                console.error('Ошибка загрузки нейросетей');
            }
        } catch (err) {
            console.error('Ошибка сети:', err);
        }
    }

    // ========== ОТОБРАЖЕНИЕ ПОПУЛЯРНЫХ МОДЕЛЕЙ ==========
    function renderPopularNetworks() {
        const container = document.querySelector('.models-grid');
        if (!container) return;

        const popular = allNetworks.filter(net => net.is_popular === true).slice(0, 7);
        if (popular.length === 0) return;

        let html = '';
        popular.forEach(net => {
            html += `
                <div class="model-card" data-slug="${net.slug}">
                    <img src="${net.avatar}" alt="${net.name}" onerror="this.src='https://placehold.co/80x80/f0a38a/white?text=${net.name.charAt(0)}'">
                    <span>${net.name}</span>
                </div>
            `;
        });
        html += `<a href="/aitext/catalog/" class="more-models-btn">Более 400 нейросетей</a>`;
        container.innerHTML = html;

        container.querySelectorAll('.model-card').forEach(card => {
            card.addEventListener('click', (e) => {
                const slug = card.dataset.slug;
                if (slug) window.location.href = `/aitext/chatland/${slug}/`;
            });
        });
    }

    // ========== РЕНДЕР КАТЕГОРИЙ (ЧИПСЫ) ==========
    function renderCategories() {
        if (!categories.length) return;

        // Десктоп
        if (desktopCategoriesContainer) {
            desktopCategoriesContainer.innerHTML = `
                <span class="category-chip active" data-category="all">Все</span>
                ${categories.map(cat => `<span class="category-chip" data-category="${cat.slug}">${cat.name}</span>`).join('')}
            `;
            desktopCategoriesContainer.querySelectorAll('.category-chip').forEach(chip => {
                chip.addEventListener('click', (e) => {
                    e.stopPropagation();
                    desktopCategoriesContainer.querySelectorAll('.category-chip').forEach(c => c.classList.remove('active'));
                    chip.classList.add('active');
                    const catSlug = chip.dataset.category;
                    renderNetworks(catSlug, desktopSearchInput.value, selectedNetworkSlug);
                });
            });
        }

        // Мобилка
        if (mobileCategoriesContainer) {
            mobileCategoriesContainer.innerHTML = `
                <span class="category-chip active" data-category="all">Все</span>
                ${categories.map(cat => `<span class="category-chip" data-category="${cat.slug}">${cat.name}</span>`).join('')}
            `;
            mobileCategoriesContainer.querySelectorAll('.category-chip').forEach(chip => {
                chip.addEventListener('click', (e) => {
                    e.stopPropagation();
                    mobileCategoriesContainer.querySelectorAll('.category-chip').forEach(c => c.classList.remove('active'));
                    chip.classList.add('active');
                    const catSlug = chip.dataset.category;
                    renderNetworks(catSlug, mobileSearchInput.value, selectedNetworkSlug);
                });
            });
        }
    }

    // ========== ФИЛЬТРАЦИЯ ==========
    function filterNetworks(categorySlug, searchText) {
        let filtered = allNetworks;
        if (categorySlug !== 'all') {
            filtered = filtered.filter(net => net.category_slug === categorySlug);
        }
        if (searchText) {
            const lowerSearch = searchText.toLowerCase();
            filtered = filtered.filter(net =>
                net.name.toLowerCase().includes(lowerSearch) ||
                net.description.toLowerCase().includes(lowerSearch)
            );
        }
        return filtered;
    }

    // ========== ОТОБРАЖЕНИЕ ЦЕНЫ ИЛИ "БЕЗЛИМИТ" ==========
    function getDisplayPrice(net) {
        if (net.unlimited && net.tariff_ids && net.tariff_ids.length > 0 && userTariffId && net.tariff_ids.includes(userTariffId) && net.messages_limit > 0) {
            return 'Безлимит';
        }
        return `${net.cost}`;
    }

    // ========== РЕНДЕР СПИСКА МОДЕЛЕЙ ==========
    function renderNetworks(categorySlug, searchText, selectedSlug) {
        const filtered = filterNetworks(categorySlug, searchText);

        // Десктоп
        if (desktopModelList) {
            desktopModelList.innerHTML = filtered.map(net => `
                <div class="model-item ${net.slug === selectedSlug ? 'selected' : ''}" data-slug="${net.slug}" data-name="${net.name}" data-avatar="${net.avatar}">
                    <img src="${net.avatar}" alt="${net.name}" onerror="this.src='https://placehold.co/40x40/f0a38a/white?text=${net.name.charAt(0)}'">
                    <div class="model-info">
                        <h4>
                            ${net.name}
                            <span class="model-price"><i class="fas fa-star"></i> ${getDisplayPrice(net)}</span>
                        </h4>
                        <p>${net.description}</p>
                    </div>
                    <div class="model-radio"></div>
                </div>
            `).join('');

            desktopModelList.querySelectorAll('.model-item').forEach(item => {
                item.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const slug = item.dataset.slug;
                    const name = item.dataset.name;
                    const avatar = item.dataset.avatar;
                    saveSelectedModel(slug, name, avatar);
                    window.location.href = `/aitext/chatland/${slug}/`;
                });
            });
        }

        // Мобилка
        if (mobileModelList) {
            mobileModelList.innerHTML = filtered.map(net => `
                <div class="model-item ${net.slug === selectedSlug ? 'selected' : ''}" data-slug="${net.slug}" data-name="${net.name}" data-avatar="${net.avatar}">
                    <img src="${net.avatar}" alt="${net.name}" onerror="this.src='https://placehold.co/40x40/f0a38a/white?text=${net.name.charAt(0)}'">
                    <div class="model-info">
                        <h4>
                            ${net.name}
                            <span class="model-price"><i class="fas fa-star"></i> ${getDisplayPrice(net)}</span>
                        </h4>
                        <p>${net.description}</p>
                    </div>
                    <div class="model-radio"></div>
                </div>
            `).join('');

            mobileModelList.querySelectorAll('.model-item').forEach(item => {
                item.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const slug = item.dataset.slug;
                    const name = item.dataset.name;
                    const avatar = item.dataset.avatar;
                    saveSelectedModel(slug, name, avatar);
                    window.location.href = `/aitext/chatland/${slug}/`;
                });
            });
        }
    }

    // ========== ОБРАБОТЧИКИ ПОИСКА ==========
    if (desktopSearchInput) {
        desktopSearchInput.addEventListener('input', (e) => {
            const activeCat = desktopCategoriesContainer?.querySelector('.category-chip.active')?.dataset.category || 'all';
            renderNetworks(activeCat, e.target.value, selectedNetworkSlug);
        });
    }
    if (mobileSearchInput) {
        mobileSearchInput.addEventListener('input', (e) => {
            const activeCat = mobileCategoriesContainer?.querySelector('.category-chip.active')?.dataset.category || 'all';
            renderNetworks(activeCat, e.target.value, selectedNetworkSlug);
        });
    }

    // ========== ОТКРЫТИЕ/ЗАКРЫТИЕ ПОПАПОВ ==========
    if (desktopChip && desktopPopup) {
        desktopChip.addEventListener('click', (e) => {
            e.stopPropagation();
            desktopPopup.classList.toggle('show');
            if (mobilePopup) mobilePopup.classList.remove('show');
        });
    }
    if (mobileChip && mobilePopup) {
        mobileChip.addEventListener('click', (e) => {
            e.stopPropagation();
            mobilePopup.classList.toggle('show');
            if (desktopPopup) desktopPopup.classList.remove('show');
        });
    }
    document.addEventListener('click', (e) => {
        if (desktopPopup && !desktopPopup.contains(e.target) && !desktopChip?.contains(e.target)) {
            desktopPopup.classList.remove('show');
        }
        if (mobilePopup && !mobilePopup.contains(e.target) && !mobileChip?.contains(e.target)) {
            mobilePopup.classList.remove('show');
        }
    });

    // ========== ПОПАП НОВОСТЕЙ ==========
    const newsBtn = document.getElementById('newsBtn');
    const newsPopup = document.getElementById('newsPopup');
    const closeNewsPopup = document.getElementById('closeNewsPopup');

    if (newsBtn && newsPopup) {
        newsBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            newsPopup.classList.toggle('show');
        });
        if (closeNewsPopup) {
            closeNewsPopup.addEventListener('click', () => {
                newsPopup.classList.remove('show');
            });
        }
        document.addEventListener('click', (e) => {
            if (!newsPopup.contains(e.target) && !newsBtn.contains(e.target)) {
                newsPopup.classList.remove('show');
            }
        });
    }

    // ========== ОБРАБОТЧИК ТАРИФА (только для index.html) ==========
    let activeConfirmPopup = null;

    function closeConfirmPopup() {
        if (activeConfirmPopup) {
            activeConfirmPopup.remove();
            activeConfirmPopup = null;
        }
    }

    function showConfirmPopup(tariff) {
        closeConfirmPopup();

        const termsUrl = document.querySelector('meta[name="terms-url"]')?.content || '#';
        const privacyUrl = document.querySelector('meta[name="privacy-url"]')?.content || '#';

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

        // Центрирование попапа
        const centerPopup = () => {
            const popupRect = popup.getBoundingClientRect();
            const viewportWidth = window.innerWidth;
            const viewportHeight = window.innerHeight;
            let top = (viewportHeight - popupRect.height) / 2;
            let left = (viewportWidth - popupRect.width) / 2;
            if (top < 10) top = 10;
            if (left < 10) left = 10;
            popup.style.position = 'fixed';
            popup.style.top = `${top}px`;
            popup.style.left = `${left}px`;
            popup.style.transform = 'none';
        };
        centerPopup();
        window.addEventListener('resize', centerPopup);

        const closeBtn = popup.querySelector('.tariff-confirm-close');
        const cancelBtn = popup.querySelector('.cancel');
        const payBtn = popup.querySelector('.pay');
        const checkbox = popup.querySelector('#confirmTermsCheckbox');

        const closePopup = () => {
            window.removeEventListener('resize', centerPopup);
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
                    closePopup();
                }
            } catch (err) {
                console.error(err);
                showNotification('Ошибка сети. Попробуйте позже.', 'error');
                closePopup();
            }
        });
    }

    function initIndexTariffButton() {
        const tariffBtn = document.getElementById('activateTariffBtn');
        if (!tariffBtn) return;
        const newBtn = tariffBtn.cloneNode(true);
        tariffBtn.parentNode.replaceChild(newBtn, tariffBtn);
        const tariffData = {
            id: parseInt(newBtn.dataset.tariffId, 10),
            display_name: newBtn.dataset.tariffName,
            price: parseInt(newBtn.dataset.tariffPrice, 10),
            pages: parseInt(newBtn.dataset.tariffPages, 10)
        };
        newBtn.addEventListener('click', (e) => {
            e.preventDefault();
            showConfirmPopup(tariffData);
        });
    }

    // ========== ИНИЦИАЛИЗАЦИЯ ==========
    // Сначала пытаемся установить модель из мета-тегов (для страниц чата)
    initCurrentModelFromMeta();
    // Загружаем данные с сервера (для главной и для попапа)
    loadNetworks();

    // FAQ аккордеон
    document.querySelectorAll('.faq-question').forEach(question => {
        question.addEventListener('click', () => {
            const item = question.closest('.faq-item');
            item.classList.toggle('open');
        });
    });

    // Инициализация тарифа (только на главной странице) и отображение Django messages
    document.addEventListener('DOMContentLoaded', function() {
        initIndexTariffButton();
        displayDjangoMessages();
    });
})();
