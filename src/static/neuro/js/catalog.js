(function() {
    'use strict';

    let allNetworks = [];
    let categories = [];

    const grid = document.getElementById('catalogGrid');
    const searchInput = document.getElementById('searchInput');
    const categoriesContainer = document.getElementById('catalogCategories');
    let activeCategory = 'all';
    let searchText = '';

    // ID тарифа пользователя
    let userTariffId = null;
    const tariffMeta = document.querySelector('meta[name="user-tariff-id"]');
    if (tariffMeta && tariffMeta.content) {
        userTariffId = parseInt(tariffMeta.content);
    }

    // Форматирование числа (например, 1234 -> 1.2K)
    function formatNumber(num) {
        if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
        if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
        return num.toString();
    }

    // Загрузка данных с сервера
    async function loadNetworks() {
        try {
            const response = await fetch('/aitext/api/networks/', {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const data = await response.json();
            if (data.success) {
                categories = data.categories;
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
                renderGrid();
            } else {
                console.error('Ошибка загрузки нейросетей');
            }
        } catch (err) {
            console.error('Ошибка сети:', err);
        }
    }

    // Рендер категорий
    function renderCategories() {
        if (!categoriesContainer) return;
        categoriesContainer.innerHTML = `
            <span class="category-chip active" data-category="all">Все</span>
            ${categories.map(cat => `<span class="category-chip" data-category="${cat.slug}">${cat.name}</span>`).join('')}
        `;
        categoriesContainer.querySelectorAll('.category-chip').forEach(chip => {
            chip.addEventListener('click', () => {
                categoriesContainer.querySelectorAll('.category-chip').forEach(c => c.classList.remove('active'));
                chip.classList.add('active');
                activeCategory = chip.dataset.category;
                renderGrid();
            });
        });
    }

    // Фильтрация
    function filterNetworks() {
        let filtered = allNetworks;
        if (activeCategory !== 'all') {
            filtered = filtered.filter(net => net.category_slug === activeCategory);
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

    // Рендер сетки
    function renderGrid() {
        const filtered = filterNetworks();
        if (filtered.length === 0) {
            grid.innerHTML = '<div class="catalog-empty">Ничего не найдено</div>';
            return;
        }
        grid.innerHTML = filtered.map(net => {
            // Определяем, показывать стоимость или "Безлимит"
            const showUnlimited = net.unlimited && net.tariff_ids && net.tariff_ids.length > 0 && userTariffId && net.tariff_ids.includes(userTariffId) && net.messages_limit > 0;
            const priceHtml = showUnlimited
                ? '<span class="catalog-price"><i class="fas fa-infinity"></i> Безлимит</span>'
                : `<span class="catalog-price"><i class="fas fa-star"></i> ${net.cost}</span>`;

            // Количество диалогов
            const chatsCount = net.chats_count || 0;
            const chatsHtml = `<span class="catalog-users"><i class="far fa-user"></i> ${formatNumber(chatsCount)}</span>`;

            return `
                <div class="catalog-card" data-slug="${net.slug}">
                    <div class="catalog-card-header">
                        <img src="${net.avatar}" alt="${net.name}" onerror="this.src='https://placehold.co/48x48/0a7cff/white?text=${net.name.charAt(0)}'">
                        <h3>${escapeHtml(net.name)}</h3>
                    </div>
                    <p class="catalog-card-description">${escapeHtml(net.description)}</p>
                    <div class="catalog-card-footer">
                        ${priceHtml}
                        ${chatsHtml}
                    </div>
                </div>
            `;
        }).join('');

        // Обработчики клика по карточке
        document.querySelectorAll('.catalog-card').forEach(card => {
            card.addEventListener('click', (e) => {
                const slug = card.dataset.slug;
                if (slug) {
                    window.location.href = `/aitext/chatland/${slug}/`;
                }
            });
        });
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

    // Поиск
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            searchText = this.value;
            renderGrid();
        });
    }

    // Загрузка
    loadNetworks();
})();