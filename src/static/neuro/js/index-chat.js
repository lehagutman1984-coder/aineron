// index-chat.js — обновлённый (полный файл)
(function() {
    'use strict';

    const textarea = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    const attachBtn = document.getElementById('attachBtn');
    const fileInput = document.getElementById('fileInput');
    const previewContainer = document.getElementById('previewContainer');
    const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

    let currentCapabilities = null;
    let pendingFileReads = 0;
    let isProcessingFile = false;
    let currentNetworkSlug = null;
    let currentConfig = null;

    async function loadNetworkConfig() {
        const slug = localStorage.getItem('selected_model_slug');
        if (!slug) {
            console.warn('Модель не выбрана');
            return false;
        }
        currentNetworkSlug = slug;
        try {
            const response = await fetch(`/aitext/api/network-config/${slug}/`, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const data = await response.json();
            if (data.success) {
                currentCapabilities = data.file_capabilities;
                currentConfig = data.config_json;
                initFileAttach();
                initConstructorButton();
                return true;
            } else {
                console.error('Ошибка загрузки конфига:', data.message);
                return false;
            }
        } catch (err) {
            console.error(err);
            return false;
        }
    }

    function initFileAttach() {
        if (!attachBtn || !fileInput || !previewContainer) return;

        const hasAny = currentCapabilities && (currentCapabilities.archive || currentCapabilities.text_files || currentCapabilities.photo || currentCapabilities.video);
        if (!hasAny) {
            if (attachBtn) attachBtn.style.display = 'none';
            if (sendBtn) sendBtn.style.marginLeft = 'auto';
        } else {
            if (attachBtn) attachBtn.style.display = 'flex';
            if (sendBtn) sendBtn.style.marginLeft = '';
            const accept = [];
            if (currentCapabilities.text_files) accept.push('.txt,.pdf,.doc,.docx,.odt,.rtf,.csv,.xlsx,.pptx');
            if (currentCapabilities.photo) accept.push('image/*');
            if (currentCapabilities.video) accept.push('video/*');
            if (currentCapabilities.archive) accept.push('.zip,.rar,.7z,.tar,.gz');
            if (accept.length && fileInput) {
                fileInput.setAttribute('accept', accept.join(','));
            }
        }
    }

    function initConstructorButton() {
        const settingsBtn = document.getElementById('constructorSettingsBtn');
        if (!settingsBtn) return;
        if (!currentConfig || Object.keys(currentConfig).length === 0) {
            settingsBtn.style.display = 'none';
            return;
        }
        settingsBtn.style.display = 'inline-flex';
        if (typeof window.initConstructor === 'function') {
            window.initConstructor(currentConfig);
        } else {
            document.addEventListener('DOMContentLoaded', () => {
                if (typeof window.initConstructor === 'function') {
                    window.initConstructor(currentConfig);
                }
            });
        }
    }

    function isFileAllowed(file) {
        if (!currentCapabilities) return true;

        const ext = file.name.split('.').pop().toLowerCase();
        const mime = file.type;

        if (currentCapabilities.text_files) {
            const textExts = ['txt', 'pdf', 'doc', 'docx', 'odt', 'rtf', 'csv', 'xlsx', 'pptx', 'xls', 'ppt'];
            const textMimes = ['text/plain', 'application/pdf', 'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.ms-excel', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'application/vnd.ms-powerpoint', 'application/vnd.openxmlformats-officedocument.presentationml.presentation'];
            if (textExts.includes(ext) || textMimes.includes(mime)) return true;
        }

        if (currentCapabilities.photo) {
            const imageExts = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg', 'ico', 'tiff'];
            if (imageExts.includes(ext) || mime.startsWith('image/')) return true;
        }

        if (currentCapabilities.video) {
            const videoExts = ['mp4', 'avi', 'mov', 'mkv', 'webm', 'flv', 'wmv', 'm4v', 'mpg', 'mpeg', '3gp', 'ts'];
            if (videoExts.includes(ext) || mime.startsWith('video/')) return true;
        }

        if (currentCapabilities.archive) {
            const archiveExts = ['zip', 'rar', '7z', 'tar', 'gz', 'bz2', 'tgz'];
            const archiveMimes = ['application/zip', 'application/x-rar-compressed', 'application/x-7z-compressed',
                'application/x-tar', 'application/gzip', 'application/x-bzip2'];
            if (archiveExts.includes(ext) || archiveMimes.includes(mime)) return true;
        }

        return false;
    }

    function createFilePreview(file) {
        const preview = document.createElement('div');
        preview.className = 'file-preview';
        preview.setAttribute('data-fullname', file.name);
        preview.setAttribute('data-type', file.type);
        preview.setAttribute('data-size', file.size);

        pendingFileReads++;

        const reader = new FileReader();
        reader.onload = (e) => {
            preview.setAttribute('data-dataurl', e.target.result);
            pendingFileReads--;
            if (pendingFileReads === 0 && sendBtn.disabled && sendBtn.getAttribute('data-waiting') === 'true') {
                sendBtn.disabled = false;
                sendBtn.removeAttribute('data-waiting');
                sendBtn.innerHTML = '<i class="fa-regular fa-paper-plane"></i>';
            }
        };
        reader.readAsDataURL(file);

        if (file.type.startsWith('image/')) {
            const img = document.createElement('img');
            const imgReader = new FileReader();
            imgReader.onload = (e) => { img.src = e.target.result; };
            imgReader.readAsDataURL(file);
            preview.appendChild(img);
        } else {
            const icon = document.createElement('i');
            icon.className = 'fa-regular fa-file-lines file-icon';
            preview.appendChild(icon);
            const nameSpan = document.createElement('span');
            nameSpan.className = 'file-name';
            let shortName = file.name.length > 15 ? file.name.substr(0, 12) + '...' : file.name;
            nameSpan.textContent = shortName;
            preview.appendChild(nameSpan);
        }

        const removeBtn = document.createElement('button');
        removeBtn.className = 'remove-file';
        removeBtn.innerHTML = '<i class="fas fa-times"></i>';
        removeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            preview.remove();
        });
        preview.appendChild(removeBtn);
        return preview;
    }

    function collectFiles() {
        const fileItems = previewContainer.querySelectorAll('.file-preview');
        const files = [];
        fileItems.forEach(item => {
            const name = item.getAttribute('data-fullname') || 'file';
            const type = item.getAttribute('data-type') || 'unknown';
            const size = parseInt(item.getAttribute('data-size') || '0');
            const dataUrl = item.getAttribute('data-dataurl') || null;
            files.push({ name, type, size, dataUrl });
        });
        return files;
    }

    function clearPreview() {
        previewContainer.innerHTML = '';
    }

    async function handleSend() {
        const isAuthenticated = document.querySelector('meta[name="user-authenticated"]')?.content === 'true';
        if (!isAuthenticated) {
            if (typeof openAuthModal === 'function') {
                openAuthModal();
            } else {
                alert('Пожалуйста, войдите в аккаунт');
            }
            return;
        }

        if (!currentNetworkSlug) {
            alert('Сначала выберите нейросеть');
            return;
        }
        const text = textarea.value.trim();
        const files = collectFiles();
        if (!text && files.length === 0) return;

        if (pendingFileReads > 0) {
            sendBtn.disabled = true;
            sendBtn.setAttribute('data-waiting', 'true');
            sendBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Подготовка файлов...';
            return;
        }

        sendBtn.disabled = true;
        sendBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Отправка...';

        const settings = window.constructorSettings || {};

        try {
            const response = await fetch('/aitext/api/create-chat/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({
                    network_slug: currentNetworkSlug,
                    message: text,
                    files: files,
                    settings: settings
                })
            });
            const data = await response.json();
            if (data.success) {
                window.location.href = `/aitext/chat/${data.chat_id}/`;
            } else {
                alert(data.message || 'Ошибка создания чата');
                sendBtn.disabled = false;
                sendBtn.innerHTML = '<i class="fa-regular fa-paper-plane"></i>';
            }
        } catch (err) {
            console.error(err);
            alert('Ошибка сети');
            sendBtn.disabled = false;
            sendBtn.innerHTML = '<i class="fa-regular fa-paper-plane"></i>';
        }
    }

    if (attachBtn && fileInput && previewContainer) {
        attachBtn.onclick = (e) => {
            e.preventDefault();
            e.stopPropagation();
            fileInput.click();
        };

        fileInput.onchange = function(e) {
            if (isProcessingFile) return;
            isProcessingFile = true;

            const files = Array.from(e.target.files);
            const allowedFiles = files.filter(file => isFileAllowed(file));
            const rejected = files.length - allowedFiles.length;
            if (rejected > 0) {
                showNotification(`Некоторые файлы не поддерживаются этой нейросетью`, 'error');
            }
            allowedFiles.forEach(file => {
                previewContainer.appendChild(createFilePreview(file));
            });
            fileInput.value = '';

            isProcessingFile = false;
        };
    }

    if (textarea) {
        textarea.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.min(120, this.scrollHeight) + 'px';
        });
    }

    if (sendBtn) {
        sendBtn.addEventListener('click', handleSend);
    }
    if (textarea) {
        textarea.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
            }
        });
    }

    loadNetworkConfig();

    function showNotification(message, type = 'error') {
        const old = document.querySelector('.chat-notification');
        if (old) old.remove();
        const note = document.createElement('div');
        note.className = 'chat-notification';
        let icon = type === 'error' ? 'fa-exclamation-circle' : 'fa-check-circle';
        let color = type === 'error' ? '#e53e3e' : '#21be19';
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
})();