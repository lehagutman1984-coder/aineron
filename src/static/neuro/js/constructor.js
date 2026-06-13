(function() {
    'use strict';

    let activePopup = null;
    let activeButton = null;
    let currentConfig = null;
    let currentSettings = {};
    window.constructorSettings = {};

    // ========== CSRF TOKEN ==========
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

    // ========== ЗАГРУЗКА СОХРАНЁННЫХ НАСТРОЕК ДЛЯ ЧАТА ==========
    function loadChatSettings() {
        const chatSettingsMeta = document.querySelector('meta[name="chat-settings"]');
        if (chatSettingsMeta && chatSettingsMeta.content) {
            try {
                const savedSettings = JSON.parse(chatSettingsMeta.getAttribute('content'));
                if (savedSettings && Object.keys(savedSettings).length > 0) {
                    currentSettings = savedSettings;
                    window.constructorSettings = savedSettings;
                    console.log('Загружены настройки чата:', savedSettings);
                }
            } catch (e) {
                console.error('Ошибка парсинга настроек чата', e);
            }
        }
    }

    // ========== СОХРАНЕНИЕ НАСТРОЕК НА СЕРВЕРЕ ==========
    async function saveSettingsToServer(settings) {
        const chatIdMeta = document.querySelector('meta[name="chat-id"]');
        if (!chatIdMeta) return; // нет чата (лендинг)

        const chatId = parseInt(chatIdMeta.content);
        if (!chatId) return;

        try {
            const response = await fetch(`/aitext/api/chat-settings/${chatId}/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ settings: settings })
            });
            const data = await response.json();
            if (!data.success) {
                console.error('Ошибка сохранения настроек:', data.message);
            }
        } catch (err) {
            console.error('Ошибка сети при сохранении настроек:', err);
        }
    }

    function closePopup() {
        if (activePopup) {
            activePopup.remove();
            activePopup = null;
            activeButton = null;
        }
        document.removeEventListener('click', handleDocumentClick);
    }

    function handleDocumentClick(e) {
        if (activePopup && activePopup.contains(e.target)) return;
        if (activeButton && activeButton.contains(e.target)) return;
        closePopup();
    }

    function positionPopup(popup, button) {
        const rect = button.getBoundingClientRect();
        const popupRect = popup.getBoundingClientRect();
        const viewportWidth = window.innerWidth;
        const viewportHeight = window.innerHeight;

        let top = rect.top - popupRect.height - 8;
        let left = rect.left;

        if (top < 10) {
            top = rect.bottom + 8;
        }

        if (left + popupRect.width > viewportWidth - 10) {
            left = viewportWidth - popupRect.width - 10;
        }
        if (left < 10) left = 10;

        if (top + popupRect.height > viewportHeight - 10) {
            top = rect.top - popupRect.height - 8;
            if (top < 10) top = 10;
        }

        popup.style.position = 'fixed';
        popup.style.top = `${top}px`;
        popup.style.left = `${left}px`;
        popup.style.transform = 'none';
        popup.style.zIndex = '10001';
    }

    function createPopup(button, title, bodyContent, onApply) {
        closePopup();

        const popup = document.createElement('div');
        popup.className = 'constructor-popup-desktop';
        popup.innerHTML = `
            <div class="constructor-popup-header">
                <h3>${escapeHtml(title)}</h3>
                <button class="constructor-popup-close"><i class="fas fa-times"></i></button>
            </div>
            <div class="constructor-popup-body" id="popupBody">
                ${bodyContent}
            </div>
            <div class="constructor-popup-footer">
                <button class="constructor-btn-secondary" data-action="cancel">Отмена</button>
                <button class="constructor-btn-primary" data-action="apply">Применить</button>
            </div>
        `;

        document.body.appendChild(popup);
        activePopup = popup;
        activeButton = button;

        if (window.innerWidth > 768) {
            positionPopup(popup, button);
        }

        popup.querySelector('.constructor-popup-close').addEventListener('click', closePopup);
        popup.querySelector('[data-action="cancel"]').addEventListener('click', closePopup);
        popup.querySelector('[data-action="apply"]').addEventListener('click', () => {
            const settings = collectSettings(popup);
            Object.assign(currentSettings, settings);
            window.constructorSettings = currentSettings;
            console.log('Настройки сохранены:', currentSettings);
            // Сохраняем на сервере, если это чат
            saveSettingsToServer(currentSettings);
            closePopup();
            if (onApply) onApply(settings);
        });

        document.addEventListener('click', handleDocumentClick);
    }

    function collectSettings(popup) {
        const settings = {};
        const body = popup.querySelector('#popupBody');
        const inputs = body.querySelectorAll('[data-settings-name]');
        inputs.forEach(input => {
            const name = input.dataset.settingsName;
            let value;
            if (input.type === 'checkbox') {
                value = input.checked;
            } else if (input.type === 'radio') {
                if (input.checked) value = input.value;
            } else if (input.type === 'range') {
                value = parseFloat(input.value);
            } else {
                value = input.value;
            }
            if (value !== undefined && value !== null) {
                settings[name] = value;
            }
        });
        return settings;
    }

    // Получить extra_cost для поля (фиксированная стоимость, не зависящая от выбранного значения)
    function getFieldExtraCost(field) {
        const extra = field.extra_cost;
        if (extra !== undefined && extra !== null && extra !== 0) {
            return parseFloat(extra);
        }
        return 0;
    }

    // Для select – получить extra_cost выбранной опции
    function getSelectedOptionExtraCost(field, selectedValue) {
        if (!field.options) return 0;
        const option = field.options.find(opt => opt.value == selectedValue);
        if (option && option.extra_cost) {
            return parseFloat(option.extra_cost);
        }
        return 0;
    }

    // Создать HTML-бейдж с дополнительной стоимостью
    function renderExtraCostBadge(extraCost) {
        if (!extraCost || extraCost === 0) return '';
        return `<span class="extra-cost-badge">+${extraCost} <i class="fas fa-star"></i></span>`;
    }

    // Обновить бейдж extra_cost для select (при изменении опции)
    function updateSelectExtraCost(selectElement, field) {
        const container = selectElement.closest('.constructor-field');
        if (!container) return;
        const selectedValue = selectElement.value;
        const extra = getSelectedOptionExtraCost(field, selectedValue);
        let badgeSpan = container.querySelector('.extra-cost-badge');
        if (extra > 0) {
            if (badgeSpan) {
                badgeSpan.innerHTML = `+${extra} <i class="fas fa-star"></i>`;
            } else {
                const label = container.querySelector('label');
                if (label) {
                    const badge = document.createElement('span');
                    badge.className = 'extra-cost-badge';
                    badge.innerHTML = `+${extra} <i class="fas fa-star"></i>`;
                    label.appendChild(badge);
                }
            }
        } else {
            if (badgeSpan) badgeSpan.remove();
        }
    }

    // Получить текущее значение для поля из сохранённых настроек
    function getCurrentFieldValue(field) {
        const name = field.name;
        if (currentSettings.hasOwnProperty(name)) {
            return currentSettings[name];
        }
        // иначе дефолтное значение из конфига
        return field.default !== undefined ? field.default : '';
    }

    function createField(field) {
        const fieldHtml = [];
        const fieldName = field.name;
        const currentValue = getCurrentFieldValue(field);
        const fieldExtraCost = getFieldExtraCost(field);

        switch (field.type) {
            case 'select':
                fieldHtml.push(`
                    <div class="constructor-field" data-field-name="${escapeHtml(fieldName)}">
                        <label>${escapeHtml(field.label || '')}</label>
                        <select data-settings-name="${escapeHtml(fieldName)}" class="constructor-select">
                            ${field.options.map(opt => {
                                const optExtra = opt.extra_cost ? parseFloat(opt.extra_cost) : 0;
                                const extraText = optExtra > 0 ? ` (+${optExtra}⭐)` : '';
                                const selected = (opt.value == currentValue) ? 'selected' : '';
                                return `<option value="${escapeHtml(opt.value)}" ${selected}>${escapeHtml(opt.label)}${extraText}</option>`;
                            }).join('')}
                        </select>
                        ${field.description ? `<div class="field-description">${escapeHtml(field.description)}</div>` : ''}
                    </div>
                `);
                // Добавим обработчик для обновления extra_cost бейджа при изменении
                setTimeout(() => {
                    const select = document.querySelector(`select[data-settings-name="${fieldName}"]`);
                    if (select) {
                        const updateBadge = () => updateSelectExtraCost(select, field);
                        select.addEventListener('change', updateBadge);
                        updateBadge(); // инициализация
                    }
                }, 10);
                break;
            case 'slider':
                fieldHtml.push(`
                    <div class="constructor-field">
                        <label>${escapeHtml(field.label || '')} ${renderExtraCostBadge(fieldExtraCost)}</label>
                        <div class="range-wrapper">
                            <input type="range" data-settings-name="${escapeHtml(fieldName)}" class="constructor-range" min="${field.min}" max="${field.max}" step="${field.step || 1}" value="${currentValue}">
                            <span class="constructor-range-value">${currentValue}</span>
                        </div>
                        ${field.description ? `<div class="field-description">${escapeHtml(field.description)}</div>` : ''}
                    </div>
                `);
                setTimeout(() => {
                    const range = document.querySelector(`input[data-settings-name="${fieldName}"]`);
                    if (range) {
                        const valueSpan = range.closest('.range-wrapper').querySelector('.constructor-range-value');
                        const updateValue = () => { valueSpan.textContent = range.value; };
                        range.addEventListener('input', updateValue);
                        updateValue();
                    }
                }, 10);
                break;
            case 'checkbox':
                const checked = currentValue ? 'checked' : '';
                fieldHtml.push(`
                    <div class="constructor-field">
                        <label class="constructor-checkbox-label">
                            <input type="checkbox" data-settings-name="${escapeHtml(fieldName)}" ${checked}>
                            <span>${escapeHtml(field.label || '')} ${renderExtraCostBadge(fieldExtraCost)}</span>
                        </label>
                        ${field.description ? `<div class="field-description">${escapeHtml(field.description)}</div>` : ''}
                    </div>
                `);
                break;
            case 'number':
                fieldHtml.push(`
                    <div class="constructor-field">
                        <label>${escapeHtml(field.label || '')} ${renderExtraCostBadge(fieldExtraCost)}</label>
                        <input type="number" data-settings-name="${escapeHtml(fieldName)}" class="constructor-number-input" min="${field.min || 0}" max="${field.max || ''}" step="${field.step || 1}" value="${currentValue}" placeholder="${escapeHtml(field.placeholder || '')}">
                        ${field.description ? `<div class="field-description">${escapeHtml(field.description)}</div>` : ''}
                    </div>
                `);
                break;
            case 'text':
                fieldHtml.push(`
                    <div class="constructor-field">
                        <label>${escapeHtml(field.label || '')} ${renderExtraCostBadge(fieldExtraCost)}</label>
                        <input type="text" data-settings-name="${escapeHtml(fieldName)}" class="constructor-text-input" value="${escapeHtml(currentValue)}" placeholder="${escapeHtml(field.placeholder || '')}">
                        ${field.description ? `<div class="field-description">${escapeHtml(field.description)}</div>` : ''}
                    </div>
                `);
                break;
            case 'textarea':
                fieldHtml.push(`
                    <div class="constructor-field">
                        <label>${escapeHtml(field.label || '')} ${renderExtraCostBadge(fieldExtraCost)}</label>
                        <textarea data-settings-name="${escapeHtml(fieldName)}" class="constructor-textarea" rows="${field.rows || 3}" placeholder="${escapeHtml(field.placeholder || '')}">${escapeHtml(currentValue)}</textarea>
                        ${field.description ? `<div class="field-description">${escapeHtml(field.description)}</div>` : ''}
                    </div>
                `);
                break;
            default:
                break;
        }
        return fieldHtml.join('');
    }

    function generateSettingsPopup(config) {
        const sections = config.ui_settings?.sections || [];
        let bodyHtml = '';
        for (const section of sections) {
            bodyHtml += `<div class="constructor-section">
                <h4 class="constructor-section-title">${escapeHtml(section.label)}</h4>
                <div class="constructor-section-content">`;
            for (const field of section.fields) {
                bodyHtml += createField(field);
            }
            bodyHtml += `</div></div>`;
        }
        if (!bodyHtml) {
            bodyHtml = '<p>Нет доступных настроек для этой модели</p>';
        }
        return bodyHtml;
    }

    function initSettingsButton() {
        const settingsBtn = document.getElementById('constructorSettingsBtn');
        const configMeta = document.querySelector('meta[name="network-config"]');

        if (!configMeta) {
            if (settingsBtn) settingsBtn.style.display = 'none';
            return;
        }

        try {
            currentConfig = JSON.parse(configMeta.getAttribute('content'));
            if (!currentConfig || (typeof currentConfig === 'object' && Object.keys(currentConfig).length === 0)) {
                if (settingsBtn) settingsBtn.style.display = 'none';
                return;
            }
        } catch (e) {
            console.error('Ошибка парсинга конфигурации', e);
            if (settingsBtn) settingsBtn.style.display = 'none';
            return;
        }

        if (!settingsBtn) return;
        settingsBtn.style.display = 'inline-flex';

        settingsBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const title = currentConfig.name || 'Настройки модели';
            const bodyHtml = generateSettingsPopup(currentConfig);
            createPopup(settingsBtn, title, bodyHtml, (settings) => {});
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

    // Инициализация при загрузке DOM
    document.addEventListener('DOMContentLoaded', () => {
        loadChatSettings();
        initSettingsButton();
    });
})();