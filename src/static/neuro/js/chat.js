(function() {
    'use strict';

    // DOM элементы
    const chatMessages = document.getElementById('chatMessages');
    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    const attachBtn = document.getElementById('attachBtn');
    const fileInput = document.getElementById('fileInput');
    const previewContainer = document.getElementById('previewContainer');
    const footerText = document.querySelector('.chat-footer-text');

    // Данные из мета-тегов
    const networkCost = parseInt(document.querySelector('meta[name="network-cost"]')?.content || '30');
    const chatId = parseInt(document.querySelector('meta[name="chat-id"]')?.content || '0');
    let currentBalance = parseInt(document.querySelector('meta[name="user-balance"]')?.content || '0');

    let isSending = false;
    let isWaitingForResponse = false;
    let activePollIntervals = new Map();
    let currentCapabilities = null;

    // Таймер для бесплатных пользователей
    let timerContainer = null;
    let timerInterval = null;
    let pendingMessage = null;
    const timerSeconds = 17;
    let timerRemaining = timerSeconds;

    // ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
    function updateBalanceDisplay() {
        const starBalance = document.getElementById('starBalance');
        if (starBalance) starBalance.textContent = currentBalance;
    }

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

    function scrollToBottom() {
        const mainContent = document.querySelector('.main-content');
        if (mainContent) mainContent.scrollTop = mainContent.scrollHeight;
    }

    function decodeUnicodeEscapes(str) {
        if (!str) return '';
        return str.replace(/\\u([0-9a-fA-F]{4})/g, (match, hex) => {
            return String.fromCharCode(parseInt(hex, 16));
        });
    }

    function copyToClipboard(text, notificationText = 'Текст скопирован') {
        const decodedText = decodeUnicodeEscapes(text);
        navigator.clipboard.writeText(decodedText).then(() => {
            showNotification(notificationText, 'success');
        }).catch(err => {
            console.error('Ошибка копирования:', err);
            showNotification('Не удалось скопировать', 'error');
        });
    }

    function addCopyButton(container, text, notificationText = 'Текст скопирован') {
        const oldBtn = container.querySelector('.copy-btn');
        if (oldBtn) oldBtn.remove();
        const copyBtn = document.createElement('button');
        copyBtn.classList.add('copy-btn');
        copyBtn.innerHTML = '<i class="far fa-copy"></i>';
        copyBtn.setAttribute('aria-label', 'Копировать ответ');
        copyBtn.onclick = (e) => {
            e.stopPropagation();
            copyToClipboard(text, notificationText);
        };
        container.appendChild(copyBtn);
    }

    // ========== ОБРАБОТЧИКИ ДЛЯ БЛОКОВ КОДА ==========
    function attachCodeBlockHandlers(container) {
        const codeBlocks = container.querySelectorAll('.code-block');
        codeBlocks.forEach(block => {
            const copyBtn = block.querySelector('.copy-code');
            if (copyBtn && !copyBtn.hasAttribute('data-handled')) {
                copyBtn.setAttribute('data-handled', 'true');
                copyBtn.addEventListener('click', async (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    const codeElement = block.querySelector('code');
                    if (codeElement) {
                        let codeText = codeElement.textContent;
                        codeText = codeText.trim();
                        await copyToClipboard(codeText, 'Код скопирован');
                    } else {
                        showNotification('Не удалось найти код', 'error');
                    }
                });
            }
            const downloadBtn = block.querySelector('.download-code');
            if (downloadBtn && !downloadBtn.hasAttribute('data-handled')) {
                downloadBtn.setAttribute('data-handled', 'true');
                downloadBtn.addEventListener('click', (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    const codeElement = block.querySelector('code');
                    if (codeElement) {
                        let codeText = codeElement.textContent;
                        codeText = codeText.trim();
                        const languageSpan = block.querySelector('.code-language');
                        let language = languageSpan ? languageSpan.textContent.trim().toLowerCase() : 'text';
                        const extMap = {
                            'python': 'py', 'javascript': 'js', 'typescript': 'ts', 'html': 'html',
                            'css': 'css', 'sql': 'sql', 'bash': 'sh', 'json': 'json', 'xml': 'xml',
                            'yaml': 'yml', 'markdown': 'md', 'c#': 'cs', 'c++': 'cpp', 'java': 'java',
                            'php': 'php', 'ruby': 'rb', 'go': 'go', 'rust': 'rs', 'swift': 'swift'
                        };
                        const ext = extMap[language] || 'txt';
                        const blob = new Blob([codeText], { type: 'text/plain;charset=utf-8' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `code.${ext}`;
                        document.body.appendChild(a);
                        a.click();
                        document.body.removeChild(a);
                        URL.revokeObjectURL(url);
                        showNotification('Файл скачан', 'success');
                    } else {
                        showNotification('Не удалось найти код', 'error');
                    }
                });
            }
        });
    }

    // ========== ПОБЛОЧНАЯ ПЕЧАТЬ HTML ==========
    async function typewriter(element, text, delay = 15) {
        element.textContent = '';
        for (let i = 0; i < text.length; i++) {
            element.textContent += text[i];
            scrollToBottom();
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }

    async function typewriterBlocks(container, html, charDelay = 15, blockDelay = 80) {
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = html;
        container.innerHTML = '';

        async function printElement(element, delay) {
            const textNodes = [];
            const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT, null, false);
            while (walker.nextNode()) textNodes.push(walker.currentNode);
            if (textNodes.length === 0) return;

            const originalTexts = textNodes.map(node => node.textContent);
            textNodes.forEach(node => node.textContent = '');

            for (let i = 0; i < textNodes.length; i++) {
                const node = textNodes[i];
                const fullText = originalTexts[i];
                for (let j = 0; j <= fullText.length; j++) {
                    node.textContent = fullText.substring(0, j);
                    scrollToBottom();
                    await new Promise(resolve => setTimeout(resolve, charDelay));
                }
            }
        }

        const children = Array.from(tempDiv.childNodes);
        for (const node of children) {
            if (node.nodeType === Node.TEXT_NODE) {
                const text = node.textContent;
                if (text.trim()) {
                    const span = document.createElement('span');
                    span.style.display = 'inline';
                    container.appendChild(span);
                    await typewriter(span, text, charDelay);
                }
            } else if (node.nodeType === Node.ELEMENT_NODE) {
                const tag = node.tagName.toLowerCase();
                if (tag === 'table') {
                    const rows = Array.from(node.querySelectorAll('tr'));
                    for (const row of rows) {
                        const rowClone = row.cloneNode(true);
                        container.appendChild(rowClone);
                        await printElement(rowClone, charDelay);
                        await new Promise(resolve => setTimeout(resolve, blockDelay));
                    }
                } else if (tag === 'ul' || tag === 'ol') {
                    const listClone = node.cloneNode(true);
                    container.appendChild(listClone);
                    const lis = Array.from(listClone.querySelectorAll(':scope > li'));
                    for (const li of lis) {
                        await printElement(li, charDelay);
                        await new Promise(resolve => setTimeout(resolve, blockDelay));
                    }
                } else {
                    const elementClone = node.cloneNode(true);
                    container.appendChild(elementClone);
                    await printElement(elementClone, charDelay);
                    await new Promise(resolve => setTimeout(resolve, blockDelay));
                }
            }
            scrollToBottom();
        }
        attachCodeBlockHandlers(container);
    }

    // ========== СОЗДАНИЕ СООБЩЕНИЙ ==========
    function addUserMessage(text, files = []) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', 'user');
        const bubble = document.createElement('div');
        bubble.classList.add('message-bubble');
        const contentDiv = document.createElement('div');
        contentDiv.classList.add('message-user-content');

        if (text) {
            const textDiv = document.createElement('div');
            textDiv.classList.add('message-text-only');
            textDiv.textContent = text;
            contentDiv.appendChild(textDiv);
        }

        if (files.length > 0) {
            const filesDiv = document.createElement('div');
            filesDiv.classList.add('message-file-preview');
            files.forEach(file => {
                const fileItem = document.createElement('div');
                fileItem.classList.add('message-file-item');
                if (file.type && file.type.startsWith('image/')) {
                    const img = document.createElement('img');
                    img.src = file.dataUrl;
                    img.alt = file.name;
                    fileItem.appendChild(img);
                } else {
                    const icon = document.createElement('i');
                    icon.className = `fas ${getFileIcon(file.type)} file-icon`;
                    fileItem.appendChild(icon);
                    const nameSpan = document.createElement('span');
                    nameSpan.className = 'file-name';
                    nameSpan.textContent = file.name.length > 15 ? file.name.substr(0, 12) + '...' : file.name;
                    fileItem.appendChild(nameSpan);
                }
                filesDiv.appendChild(fileItem);
            });
            contentDiv.appendChild(filesDiv);
        }

        bubble.appendChild(contentDiv);
        messageDiv.appendChild(bubble);
        const time = document.createElement('div');
        time.classList.add('message-time');
        time.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        messageDiv.appendChild(time);
        chatMessages.appendChild(messageDiv);
        scrollToBottom();

        addCopyButton(bubble, text, 'Текст скопирован');
        return messageDiv;
    }

    function addBotMessage(messageId, content = '', status = 'pending', plainText = '') {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message', 'bot');
        messageDiv.setAttribute('data-message-id', messageId);
        messageDiv.setAttribute('data-status', status);
        if (plainText) {
            messageDiv.setAttribute('data-plain-text', plainText);
        }

        if (status === 'pending') {
            const indicator = document.createElement('div');
            indicator.classList.add('typing-indicator');
            for (let i = 0; i < 3; i++) {
                const dot = document.createElement('span');
                indicator.appendChild(dot);
            }
            messageDiv.appendChild(indicator);
        } else {
            const bubble = document.createElement('div');
            bubble.classList.add('message-bubble');
            const textSpan = document.createElement('span');
            textSpan.classList.add('message-text');
            bubble.appendChild(textSpan);
            messageDiv.appendChild(bubble);

            typewriterBlocks(textSpan, content, 15, 80).then(() => {
                addCopyButton(bubble, plainText || content, 'Текст скопирован');
                const time = document.createElement('div');
                time.classList.add('message-time');
                time.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                messageDiv.appendChild(time);
            });
        }

        chatMessages.appendChild(messageDiv);
        scrollToBottom();
        return messageDiv;
    }

    function getFileIcon(type) {
        if (type.includes('pdf')) return 'fa-file-pdf';
        if (type.includes('word')) return 'fa-file-word';
        if (type.includes('powerpoint')) return 'fa-file-powerpoint';
        if (type.includes('video')) return 'fa-file-video';
        if (type.includes('audio')) return 'fa-file-audio';
        if (type.includes('image')) return 'fa-file-image';
        return 'fa-file';
    }

    // ========== ОПРОС СТАТУСА ==========
    function startPollingForMessage(messageId, messageElement) {
        if (activePollIntervals.has(messageId)) {
            clearInterval(activePollIntervals.get(messageId));
            activePollIntervals.delete(messageId);
        }
        const interval = setInterval(async () => {
            try {
                const response = await fetch(`/aitext/api/message_status/${messageId}/`, {
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                });
                const data = await response.json();
                if (data.success) {
                    if (data.status === 'completed') {
                        clearInterval(interval);
                        activePollIntervals.delete(messageId);

                        messageElement.innerHTML = '';
                        const bubble = document.createElement('div');
                        bubble.classList.add('message-bubble');
                        const textSpan = document.createElement('span');
                        textSpan.classList.add('message-text');
                        bubble.appendChild(textSpan);
                        messageElement.appendChild(bubble);

                        messageElement.setAttribute('data-status', 'completed');
                        messageElement.setAttribute('data-plain-text', data.plain_text || '');

                        await typewriterBlocks(textSpan, data.content, 15, 80);

                        addCopyButton(bubble, data.plain_text || data.content, 'Текст скопирован');
                        const time = document.createElement('div');
                        time.classList.add('message-time');
                        time.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                        messageElement.appendChild(time);

                        isWaitingForResponse = false;
                    } else if (data.status === 'failed') {
                        clearInterval(interval);
                        activePollIntervals.delete(messageId);
                        messageElement.innerHTML = '';
                        const errorSpan = document.createElement('span');
                        errorSpan.classList.add('message-text', 'error');
                        errorSpan.textContent = data.error || 'Ошибка генерации ответа';
                        messageElement.appendChild(errorSpan);
                        const time = document.createElement('div');
                        time.classList.add('message-time');
                        time.textContent = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                        messageElement.appendChild(time);
                        messageElement.setAttribute('data-status', 'failed');
                        isWaitingForResponse = false;
                    }
                }
            } catch (err) {
                console.error('Polling error:', err);
            }
        }, 1000);
        activePollIntervals.set(messageId, interval);
    }

    function checkPendingMessages() {
        const pendingMessages = document.querySelectorAll('.message.bot[data-status="pending"]');
        if (pendingMessages.length > 0) {
            isWaitingForResponse = true;
        }
        pendingMessages.forEach(msgElement => {
            const messageId = msgElement.dataset.messageId;
            if (messageId) {
                startPollingForMessage(messageId, msgElement);
            }
        });
    }

    function addCopyButtonsToExistingMessages() {
        const botBubbles = document.querySelectorAll('.message.bot[data-status="completed"] .message-bubble');
        botBubbles.forEach(bubble => {
            const textSpan = bubble.querySelector('.message-text');
            if (textSpan) {
                const messageDiv = bubble.closest('.message');
                let plainText = messageDiv ? messageDiv.getAttribute('data-plain-text') : '';
                if (!plainText) {
                    plainText = textSpan.innerText;
                }
                addCopyButton(bubble, plainText, 'Текст скопирован');
            }
        });
        const userBubbles = document.querySelectorAll('.message.user .message-bubble');
        userBubbles.forEach(bubble => {
            const textSpan = bubble.querySelector('.message-text-only');
            if (textSpan) {
                addCopyButton(bubble, textSpan.textContent, 'Текст скопирован');
            }
        });
        document.querySelectorAll('.message.bot .message-text, .message.user .message-text-only').forEach(container => {
            attachCodeBlockHandlers(container);
        });
    }

    // ========== ТАЙМЕР В ФОРМЕ ==========
    function showTimerInForm(onComplete) {
        // Удаляем предыдущий таймер, если есть
        if (timerContainer) {
            timerContainer.remove();
            timerContainer = null;
        }
        if (timerInterval) clearInterval(timerInterval);

        timerRemaining = timerSeconds;
        timerContainer = document.createElement('div');
        timerContainer.className = 'chat-timer-bar';
        timerContainer.innerHTML = `
            <div class="timer-content">
                <div class="timer-icon"></div>
                <div class="timer-text">
                    <span>Бесплатный тариф</span>
                    <strong>Подождите ${timerSeconds} секунд</strong>
                    перед отправкой
                </div>
                <button class="timer-subscribe-link">Купить подписку</button>
            </div>
            <div class="timer-progress">
                <div class="timer-progress-fill" style="width: 100%"></div>
            </div>
        `;

        const inputWrapper = document.querySelector('.chat-input-wrapper');
        if (inputWrapper) {
            inputWrapper.insertBefore(timerContainer, inputWrapper.firstChild);
        }

        const updateTimer = () => {
            const secondsText = timerContainer.querySelector('.timer-text strong');
            const progressFill = timerContainer.querySelector('.timer-progress-fill');
            if (secondsText) secondsText.textContent = `Подождите ${timerRemaining} секунд`;
            if (progressFill) {
                const percent = (timerRemaining / timerSeconds) * 100;
                progressFill.style.width = `${percent}%`;
            }
            if (timerRemaining <= 0) {
                clearInterval(timerInterval);
                timerInterval = null;
                if (timerContainer) timerContainer.remove();
                timerContainer = null;
                if (onComplete) onComplete();
            }
            timerRemaining--;
        };
        updateTimer();
        timerInterval = setInterval(updateTimer, 1000);

        const subscribeBtn = timerContainer.querySelector('.timer-subscribe-link');
        subscribeBtn.addEventListener('click', (e) => {
            e.preventDefault();
            if (typeof window.openTariffsModal === 'function') {
                window.openTariffsModal();
            }
        });
    }

    // ========== ОТПРАВКА СООБЩЕНИЯ ==========
    async function executeSend(text, files, settings) {
        if (isSending) return;
        isSending = true;
        sendBtn.disabled = true;
        if (attachBtn) attachBtn.disabled = true;
        if (messageInput) messageInput.disabled = true;

        addUserMessage(text, files);
        messageInput.value = '';
        messageInput.style.height = 'auto';
        clearPreview();

        try {
            const response = await fetch(`/aitext/api/send/${chatId}/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ message: text, files: files, settings: settings })
            });
            const data = await response.json();
            if (data.success) {
                currentBalance = data.new_balance;
                updateBalanceDisplay();
                const botMessageElement = addBotMessage(data.assistant_message_id, '', 'pending', '');
                startPollingForMessage(data.assistant_message_id, botMessageElement);
                isWaitingForResponse = true;
            } else {
                showNotification(data.message || 'Ошибка отправки', 'error');
            }
        } catch (err) {
            console.error(err);
            showNotification('Ошибка сети', 'error');
        } finally {
            isSending = false;
            sendBtn.disabled = false;
            if (attachBtn) attachBtn.disabled = false;
            if (messageInput) messageInput.disabled = false;
            messageInput.focus();
        }
    }

    async function handleSend() {
        if (isSending) return;
        if (isWaitingForResponse) {
            showNotification('Дождитесь окончания генерации чтобы сделать новый запрос', 'error');
            return;
        }
        const text = messageInput.value.trim();
        const files = collectFilesFromPreview();
        if (!text && files.length === 0) return;

        const hasPaidSubscription = document.querySelector('meta[name="has-paid-subscription"]')?.content === 'true';
        if (!hasPaidSubscription && !timerContainer) {
            pendingMessage = { text, files, settings: window.constructorSettings || {} };
            showTimerInForm(() => {
                if (pendingMessage) {
                    const { text: msgText, files: msgFiles, settings: msgSettings } = pendingMessage;
                    pendingMessage = null;
                    executeSend(msgText, msgFiles, msgSettings);
                }
            });
            return;
        }

        if (timerContainer) {
            showNotification('Подождите, идёт обратный отсчёт', 'info');
            return;
        }

        executeSend(text, files, window.constructorSettings || {});
    }

    // ========== ФАЙЛЫ ==========
    function collectFilesFromPreview() {
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

    function createFilePreview(file) {
        const preview = document.createElement('div');
        preview.className = 'file-preview';
        preview.setAttribute('data-fullname', file.name);
        preview.setAttribute('data-type', file.type);
        preview.setAttribute('data-size', file.size);

        const reader = new FileReader();
        reader.onload = (e) => {
            preview.setAttribute('data-dataurl', e.target.result);
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

    // ========== НАСТРОЙКА КНОПКИ ПРИКРЕПЛЕНИЯ ==========
    function initFileAttach() {
        const capabilitiesMeta = document.querySelector('meta[name="file-capabilities"]');
        if (capabilitiesMeta) {
            try {
                currentCapabilities = JSON.parse(capabilitiesMeta.getAttribute('content'));
                console.log('File capabilities:', currentCapabilities);
                const hasAny = currentCapabilities.archive || currentCapabilities.text_files || currentCapabilities.photo || currentCapabilities.video;
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
                        console.log('Accept set to:', accept.join(','));
                    }
                }
            } catch (e) {
                console.error('Ошибка парсинга file-capabilities', e);
            }
        }
    }

    // ========== ИНИЦИАЛИЗАЦИЯ ==========
    if (attachBtn && fileInput && previewContainer) {
        attachBtn.onclick = (e) => {
            e.preventDefault();
            e.stopPropagation();
            fileInput.click();
        };

        fileInput.onchange = function(e) {
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
        };
    }

    sendBtn.addEventListener('click', handleSend);
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey && !isSending && !isWaitingForResponse) {
            e.preventDefault();
            handleSend();
        }
    });
    messageInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(120, this.scrollHeight) + 'px';
    });

    if (footerText) {
        footerText.innerHTML = `Стоимость ${networkCost} <i class="fas fa-star"></i> за одно сообщение.`;
    }
    updateBalanceDisplay();

    document.addEventListener('DOMContentLoaded', function() {
        initFileAttach();
        checkPendingMessages();
        addCopyButtonsToExistingMessages();
        scrollToBottom();
    });
})();
