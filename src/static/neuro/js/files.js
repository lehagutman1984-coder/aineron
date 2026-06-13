(async function() {
    'use strict';

    // Состояние
    let currentCategory = 'all';
    let isLoading = false;
    let hasMore = true;
    let currentPage = 1;
    let filesList = [];
    let abortController = null;

    // DOM элементы
    const tabs = document.querySelectorAll('.files-tab');
    const grid = document.getElementById('filesGrid');
    const modalOverlay = document.getElementById('fileModalOverlay');
    const modalClose = document.getElementById('fileModalClose');
    const modalMedia = document.getElementById('fileModalMedia');
    const modalTitle = document.getElementById('fileModalTitle');
    const modalDate = document.getElementById('fileModalDate');
    const modalSize = document.getElementById('fileModalSize');
    const modalType = document.getElementById('fileModalType');
    const modalUploaded = document.getElementById('fileModalUploaded');
    const modalDownload = document.getElementById('fileModalDownload');
    const modalDelete = document.getElementById('fileModalDelete');

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

    function formatDate(dateStr) {
        const d = new Date(dateStr);
        return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
    }

    function getFileIcon(type) {
        const icons = {
            pdf: 'fa-file-pdf',
            docx: 'fa-file-word',
            pptx: 'fa-file-powerpoint',
            jpg: 'fa-file-image',
            png: 'fa-file-image',
            jpeg: 'fa-file-image',
            webp: 'fa-file-image',
            gif: 'fa-file-image',
            mp4: 'fa-file-video',
            mov: 'fa-file-video',
            avi: 'fa-file-video',
            default: 'fa-file'
        };
        return icons[type] || icons.default;
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

    function renderGrid() {
        if (filesList.length === 0 && !isLoading) {
            grid.innerHTML = '<div class="files-empty">У вас еще нет сгенерированных файлов</div>';
            return;
        }

        if (filesList.length === 0 && isLoading) {
            // Показываем индикатор загрузки, если ещё идёт первый запрос
            grid.innerHTML = '<div class="files-loading"><i class="fas fa-spinner fa-spin"></i> Загрузка...</div>';
            return;
        }

        let html = '';
        filesList.forEach((file, idx) => {
            const isImage = file.category === 'images';
            const isVideo = file.category === 'videos';
            const iconClass = getFileIcon(file.type);
            html += `
                <div class="file-card" data-index="${idx}" data-id="${file.id}">
                    <div class="myfile-preview">
                        ${isImage ? `<img src="${file.url}" alt="${file.name}" loading="lazy">` : ''}
                        ${isVideo ? `<video src="${file.url}" muted preload="metadata"></video>` : ''}
                        ${!isImage && !isVideo ? `<i class="far ${iconClass}"></i>` : ''}
                    </div>
                    <div class="file-info">
                        <div class="file-name">${escapeHtml(file.name)}.${file.ext}</div>
                        <div class="file-meta">
                            <span class="file-type">${file.ext.toUpperCase()}</span>
                            <span class="file-size">${file.size}</span>
                        </div>
                        <div class="file-date">${formatDate(file.date)}</div>
                    </div>
                </div>
            `;
        });
        grid.innerHTML = html;

        document.querySelectorAll('.file-card').forEach(card => {
            card.addEventListener('click', () => {
                const index = parseInt(card.dataset.index, 10);
                openModal(index);
            });
        });
    }

    async function loadPage(page, append = false) {
        if (isLoading) return false;
        if (!append && page === 1) {
            if (abortController) abortController.abort();
            abortController = new AbortController();
        }

        isLoading = true;
        // Показываем загрузку только если это первая страница и нет файлов
        if (!append && filesList.length === 0) {
            renderGrid(); // отобразит индикатор загрузки
        }

        try {
            const url = `/aitext/api/user-files/?page=${page}&per_page=12&category=${currentCategory}`;
            const response = await fetch(url, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
                signal: abortController ? abortController.signal : undefined
            });
            const data = await response.json();
            if (data.success) {
                if (append) {
                    filesList = filesList.concat(data.files);
                } else {
                    filesList = data.files;
                }
                hasMore = data.has_next;
                currentPage = page;
                renderGrid();
                return true;
            } else {
                console.error('Ошибка загрузки:', data.message);
                if (!append && filesList.length === 0) {
                    filesList = [];
                    renderGrid();
                }
                return false;
            }
        } catch (err) {
            if (err.name !== 'AbortError') {
                console.error(err);
                if (!append && filesList.length === 0) {
                    filesList = [];
                    renderGrid();
                }
            }
            return false;
        } finally {
            isLoading = false;
            // После завершения загрузки перерисовываем на случай, если файлы пусты
            if (!append && filesList.length === 0) {
                renderGrid();
            }
        }
    }

    async function switchCategory(category) {
        if (category === currentCategory) return;
        currentCategory = category;
        hasMore = true;
        currentPage = 1;
        filesList = [];
        await loadPage(1, false);
    }

    let scrollTimer = null;
    function handleScroll() {
        if (scrollTimer) clearTimeout(scrollTimer);
        scrollTimer = setTimeout(async () => {
            const container = document.querySelector('.main-content');
            if (!container) return;
            const { scrollTop, scrollHeight, clientHeight } = container;
            if (scrollTop + clientHeight >= scrollHeight - 200 && !isLoading && hasMore) {
                await loadPage(currentPage + 1, true);
            }
        }, 100);
    }

    function openModal(index) {
        const file = filesList[index];
        if (!file) return;

        const isImage = file.category === 'images';
        const isVideo = file.category === 'videos';
        const isPdf = file.type === 'pdf';

        let mediaHtml = '';
        if (isImage) {
            mediaHtml = `<img src="${file.url}" alt="${file.name}">`;
        } else if (isVideo) {
            mediaHtml = `<video src="${file.url}" controls autoplay loop></video>`;
        } else if (isPdf) {
            mediaHtml = `<iframe src="${file.url}" style="width:100%; height:100%; border:none;"></iframe>`;
        } else {
            mediaHtml = `<div style="color:white; text-align:center; padding:20px;">Предпросмотр недоступен для файлов данного типа</div>`;
        }

        modalMedia.innerHTML = mediaHtml;
        modalTitle.textContent = `${file.name}.${file.ext}`;
        modalDate.textContent = formatDate(file.date);
        modalSize.textContent = file.size;
        modalType.textContent = file.ext.toUpperCase();
        modalUploaded.textContent = formatDate(file.date);

        modalDownload.onclick = () => window.open(file.url, '_blank');
        modalDelete.onclick = async () => {
            if (confirm(`Удалить файл ${file.name}.${file.ext}?`)) {
                try {
                    const response = await fetch(`/aitext/api/delete-file/${file.id}/`, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': getCsrfToken(),
                            'X-Requested-With': 'XMLHttpRequest'
                        }
                    });
                    const data = await response.json();
                    if (data.success) {
                        const idx = filesList.findIndex(f => f.id === file.id);
                        if (idx !== -1) filesList.splice(idx, 1);
                        renderGrid();
                        closeModal();
                    } else {
                        alert(data.message || 'Ошибка удаления');
                    }
                } catch (err) {
                    console.error(err);
                    alert('Ошибка сети');
                }
            }
        };

        modalOverlay.classList.add('show');
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        modalOverlay.classList.remove('show');
        document.body.style.overflow = '';
        const video = modalMedia.querySelector('video');
        if (video) video.pause();
    }

    // Обработчики табов
    tabs.forEach(tab => {
        tab.addEventListener('click', async function() {
            const newCategory = this.dataset.tab;
            if (newCategory === currentCategory) return;
            tabs.forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            await switchCategory(newCategory);
        });
    });

    // Инициализация
    const scrollContainer = document.querySelector('.main-content');
    if (scrollContainer) scrollContainer.addEventListener('scroll', handleScroll);

    modalClose.addEventListener('click', closeModal);
    modalOverlay.addEventListener('click', (e) => {
        if (e.target === modalOverlay) closeModal();
    });
    document.addEventListener('keydown', (e) => {
        if (modalOverlay.classList.contains('show') && e.key === 'Escape') closeModal();
    });

    // Загружаем первую страницу
    await loadPage(1, false);
})();