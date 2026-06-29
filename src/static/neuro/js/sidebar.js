(function() {
    // Элементы сайдбара
    const sidebar = document.getElementById('sidebar');
    const collapseBtn = document.getElementById('collapseSidebar');
    const mobileMenuBtn = document.getElementById('mobileMenuBtn');
    const overlay = document.getElementById('sidebarOverlay');
    const userTrigger = document.getElementById('userMenuTrigger');
    const userMenu = document.getElementById('userMenu');
    const logoutMenuItem = document.getElementById('logoutMenuItem');

    // Элементы модалки удаления
    const deleteModalOverlay = document.getElementById('deleteModalOverlay');
    const deleteModalCancel = document.getElementById('deleteModalCancel');
    const deleteModalConfirm = document.getElementById('deleteModalConfirm');
    let chatToDelete = null;

    // Сворачивание/разворачивание (десктоп)
    if (collapseBtn) {
        collapseBtn.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
            const icon = collapseBtn.querySelector('i');
            if (sidebar.classList.contains('collapsed')) {
                icon.classList.remove('fa-chevron-left');
                icon.classList.add('fa-chevron-right');
            } else {
                icon.classList.remove('fa-chevron-right');
                icon.classList.add('fa-chevron-left');
            }
        });
    }

    // Мобильное меню (открытие/закрытие)
    if (mobileMenuBtn && overlay) {
        function openSidebar() {
            sidebar.classList.add('show');
            overlay.classList.add('show');
            document.body.style.overflow = 'hidden';
        }

        function closeSidebar() {
            sidebar.classList.remove('show');
            overlay.classList.remove('show');
            document.body.style.overflow = '';
        }

        mobileMenuBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            openSidebar();
        });

        overlay.addEventListener('click', closeSidebar);

        // Закрытие сайдбара при клике на пункты меню (кроме user-row) на мобильных
        document.querySelectorAll('.menu-row, .chat-row').forEach(item => {
            item.addEventListener('click', () => {
                if (window.innerWidth <= 768) {
                    closeSidebar();
                }
            });
        });
    }

    // Меню пользователя
    if (userTrigger && userMenu) {
        userTrigger.addEventListener('click', (e) => {
            e.stopPropagation();
            userMenu.classList.toggle('show');
        });

        document.addEventListener('click', (e) => {
            if (!userMenu.contains(e.target) && !userTrigger.contains(e.target)) {
                userMenu.classList.remove('show');
            }
        });
    }

    // Выход из системы (реальный AJAX logout)
    if (logoutMenuItem) {
        logoutMenuItem.addEventListener('click', async (e) => {
            e.preventDefault();
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
        });
    }

    // Функция получения CSRF-токена
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

    // Функция показа уведомления
    function showNotification(message, type = 'info') {
        const old = document.querySelector('.sidebar-notification');
        if (old) old.remove();
        const note = document.createElement('div');
        note.className = 'sidebar-notification';
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

    // ========== РАБОТА С ЧАТАМИ ==========
    function initChats() {
        const chatRows = document.querySelectorAll('.chat-row');
        chatRows.forEach(row => {
            const chatId = row.dataset.chatId;
            if (!chatId) return;

            row.addEventListener('click', (e) => {
                if (e.target.closest('.delete-chat')) return;
                window.location.href = `/aitext/chat/${chatId}/`;
            });

            const deleteBtn = row.querySelector('.delete-chat');
            if (deleteBtn) {
                deleteBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    chatToDelete = row;
                    if (deleteModalOverlay) {
                        deleteModalOverlay.classList.add('show');
                    }
                });
            }
        });
    }

    // Удаление чата через API (вызывается из модалки)
    async function deleteChat() {
        if (!chatToDelete) return;
        const chatId = chatToDelete.dataset.chatId;
        try {
            const response = await fetch(`/aitext/api/delete-chat/${chatId}/`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            const data = await response.json();
            if (data.success) {
                chatToDelete.remove();
                showNotification('Чат удалён', 'success');
                if (window.location.pathname.includes(`/aitext/chat/${chatId}/`)) {
                    window.location.href = '/';
                }
            } else {
                showNotification('Ошибка удаления', 'error');
            }
        } catch (err) {
            console.error(err);
            showNotification('Ошибка сети', 'error');
        } finally {
            closeDeleteModal();
        }
    }

    function closeDeleteModal() {
        if (deleteModalOverlay) deleteModalOverlay.classList.remove('show');
        chatToDelete = null;
    }

    if (deleteModalCancel) {
        deleteModalCancel.addEventListener('click', closeDeleteModal);
    }
    if (deleteModalConfirm) {
        deleteModalConfirm.addEventListener('click', deleteChat);
    }
    if (deleteModalOverlay) {
        deleteModalOverlay.addEventListener('click', (e) => {
            if (e.target === deleteModalOverlay) {
                closeDeleteModal();
            }
        });
    }

    // ========== ПЕРЕХОД ПО ПУНКТАМ МЕНЮ ==========
    function initMenuLinks() {
        const menuRows = document.querySelectorAll('.menu-row');
        menuRows.forEach(row => {
            const href = row.getAttribute('data-href');
            if (href) {
                row.addEventListener('click', (e) => {
                    if (window.innerWidth <= 768) {
                        const close = document.querySelector('.sidebar .close-sidebar');
                        if (close) close.click();
                        else setTimeout(() => { window.location.href = href; }, 100);
                    } else {
                        window.location.href = href;
                    }
                });
            }
        });
    }

    // ========== ПОДСВЕТКА АКТИВНОГО ПУНКТА МЕНЮ ==========
    function highlightCurrentMenuItem() {
        const currentPath = window.location.pathname;
        const menuRows = document.querySelectorAll('.menu-row');
        let activeFound = false;

        menuRows.forEach(row => {
            const href = row.getAttribute('data-href');
            if (href && currentPath === href) {
                menuRows.forEach(r => r.classList.remove('active'));
                row.classList.add('active');
                activeFound = true;
            }
        });
    }

    // ========== БЕСКОНЕЧНАЯ ПОДГРУЗКА ЧАТОВ ==========
    let currentPage = 1;
    let isLoading = false;
    let hasMore = true;
    const perPage = 15;

    async function loadMoreChats() {
        if (isLoading || !hasMore) return;
        isLoading = true;
        const loadingIndicator = document.getElementById('loadingMoreChats');
        if (loadingIndicator) loadingIndicator.style.display = 'block';

        try {
            const response = await fetch(`/aitext/api/user-chats/?page=${currentPage + 1}&per_page=${perPage}`, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const data = await response.json();
            if (data.success && data.chats.length > 0) {
                const chatsList = document.getElementById('chatsList');
                if (!chatsList) return;

                const emptyRow = chatsList.querySelector('.chat-row.empty');
                if (emptyRow) emptyRow.remove();

                data.chats.forEach(chat => {
                    const chatRow = document.createElement('div');
                    chatRow.className = 'chat-row';
                    if (window.location.pathname.includes(`/aitext/chat/${chat.id}/`)) {
                        chatRow.classList.add('active');
                    }
                    chatRow.setAttribute('data-chat-id', chat.id);
                    chatRow.innerHTML = `
                        <img src="${escapeHtml(chat.network_avatar)}" alt="${escapeHtml(chat.network_name)}" class="chat-avatar" width="24" height="24">
                        <div class="chat-info">
                            <div class="chat-name">${escapeHtml(chat.title)}</div>
                            <div class="chat-preview">${escapeHtml(chat.preview)}</div>
                        </div>
                        <button class="delete-chat" title="Удалить чат"><i class="fas fa-times"></i></button>
                        <span class="tooltip">${escapeHtml(chat.title)}</span>
                    `;
                    chatsList.appendChild(chatRow);
                });

                currentPage = data.current_page;
                hasMore = data.has_next;
                initChats();
            } else {
                hasMore = false;
            }
        } catch (err) {
            console.error('Ошибка загрузки чатов:', err);
            showNotification('Ошибка загрузки чатов', 'error');
        } finally {
            isLoading = false;
            if (loadingIndicator) loadingIndicator.style.display = 'none';
        }
    }

    function initInfiniteScroll() {
        const chatsSection = document.getElementById('chatsSection');
        if (!chatsSection) return;

        let loadingIndicator = document.getElementById('loadingMoreChats');
        if (!loadingIndicator) {
            loadingIndicator = document.createElement('div');
            loadingIndicator.id = 'loadingMoreChats';
            loadingIndicator.style.cssText = 'text-align: center; padding: 12px; display: none; color: rgba(13,13,13,0.5);';
            loadingIndicator.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Загрузка...';
            chatsSection.appendChild(loadingIndicator);
        }

        chatsSection.addEventListener('scroll', function() {
            if (this.scrollTop + this.clientHeight >= this.scrollHeight - 50) {
                loadMoreChats();
            }
        });

        const chatsList = document.getElementById('chatsList');
        if (chatsList && chatsList.children.length === 0) {
            loadMoreChats();
        }
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

    // Кнопка "Новый чат"
    const newChatBtn = document.querySelector('.menu-row:first-child');
    if (newChatBtn && !newChatBtn.hasAttribute('data-handled')) {
        newChatBtn.setAttribute('data-handled', 'true');
        newChatBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            let slug = localStorage.getItem('selected_model_slug');
            if (!slug) {
                fetch('/aitext/api/networks/')
                    .then(r => r.json())
                    .then(data => {
                        const defaultSlug = data.default_model?.slug;
                        if (defaultSlug) window.location.href = `/aitext/chatland/${defaultSlug}/`;
                        else if (data.categories?.[0]?.networks?.[0]?.slug) {
                            window.location.href = `/aitext/chatland/${data.categories[0].networks[0].slug}/`;
                        }
                    })
                    .catch(err => console.error('Ошибка получения моделей', err));
            } else {
                window.location.href = `/aitext/chatland/${slug}/`;
            }
        });
    }

    // Кнопка входа в сайдбаре (для неавторизованных)
    const sidebarLoginBtn = document.getElementById('sidebarLoginBtn');
    if (sidebarLoginBtn) {
        sidebarLoginBtn.addEventListener('click', function() {
            if (typeof openAuthModal === 'function') {
                openAuthModal();
            } else {
                console.warn('openAuthModal not defined');
            }
        });
    }

    // ========== НОВЫЙ ПУНКТ "Купить звезды" ==========
    const buyStarsMenuItem = document.getElementById('buyStarsMenuItem');
    if (buyStarsMenuItem) {
        buyStarsMenuItem.addEventListener('click', function() {
            if (typeof window.pagesModal !== 'undefined' && window.pagesModal) {
                window.pagesModal.open();
            } else if (typeof window.openPagesModal === 'function') {
                window.openPagesModal();
            } else {
                console.warn('Модальное окно покупки звезд не найдено');
            }
        });
    }

    // Инициализация после загрузки DOM
    document.addEventListener('DOMContentLoaded', () => {
        initChats();
        initMenuLinks();
        highlightCurrentMenuItem();
        initInfiniteScroll();
    });
})();
