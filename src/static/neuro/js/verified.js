(function() {
    'use strict';

    // Элементы
    const inputs = document.querySelectorAll('.code-digit');
    const form = document.getElementById('verifiedForm');
    const submitBtn = document.getElementById('submitBtn');
    const resendBtn = document.getElementById('resendBtn');
    const timerDisplay = document.getElementById('timerDisplay');
    const userEmailSpan = document.getElementById('userEmail');

    let timerInterval = null;
    let timeLeft = 300; // 5 минут в секундах
    let canResend = false;

    // Получение CSRF-токена
    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.content;
        const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (input) return input.value;
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

    // Уведомление (временное, не alert)
    function showNotification(message, type = 'info') {
        const oldNote = document.querySelector('.verified-notification');
        if (oldNote) oldNote.remove();

        const note = document.createElement('div');
        note.className = 'verified-notification';
        let icon = 'fa-info-circle';
        let color = '#0a7cff';
        if (type === 'success') {
            icon = 'fa-check-circle';
            color = '#21be19';
        } else if (type === 'error') {
            icon = 'fa-exclamation-circle';
            color = '#e53e3e';
        }
        note.innerHTML = `<i class="fas ${icon}"></i><span>${message}</span>`;
        note.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: white;
            padding: 12px 20px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            display: flex;
            align-items: center;
            gap: 10px;
            z-index: 10001;
            font-size: 14px;
            font-weight: 500;
            color: #0d0d0d;
            border-left: 4px solid ${color};
            animation: slideInRight 0.3s ease;
        `;
        document.body.appendChild(note);
        setTimeout(() => note.remove(), 4000);
    }

    // Обновление таймера на экране
    function updateTimerDisplay() {
        const minutes = Math.floor(timeLeft / 60);
        const seconds = timeLeft % 60;
        timerDisplay.textContent = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }

    // Запуск таймера (отсчёт от текущего timeLeft)
    function startTimer() {
        if (timerInterval) clearInterval(timerInterval);
        canResend = false;
        resendBtn.disabled = true;

        timerInterval = setInterval(() => {
            if (timeLeft <= 0) {
                clearInterval(timerInterval);
                timerInterval = null;
                canResend = true;
                resendBtn.disabled = false;
                timerDisplay.textContent = '00:00';
            } else {
                timeLeft--;
                updateTimerDisplay();
            }
        }, 1000);
    }

    // Сброс таймера (при повторной отправке)
    function resetTimer() {
        timeLeft = 300;
        updateTimerDisplay();
        startTimer();
    }

    // Получение кода из полей
    function getCode() {
        let code = '';
        inputs.forEach(input => {
            code += input.value;
        });
        return code;
    }

    // Очистка полей ввода
    function clearCodeInputs() {
        inputs.forEach(input => {
            input.value = '';
        });
        if (inputs[0]) inputs[0].focus();
    }

    // Проверка, заполнен ли весь код
    function isCodeComplete() {
        let complete = true;
        inputs.forEach(input => {
            if (!input.value.match(/^\d$/)) complete = false;
        });
        return complete;
    }

    // Обновление состояния кнопки "Подтвердить"
    function updateSubmitButton() {
        submitBtn.disabled = !isCodeComplete();
    }

    // Отправка кода на сервер
    async function handleVerify() {
        if (!isCodeComplete()) {
            showNotification('Введите полный 6-значный код', 'error');
            return;
        }
        const code = getCode();
        submitBtn.disabled = true;
        const originalText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Проверка...';

        try {
            const response = await fetch('/users/api/ajax/verify-email/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ token: code })
            });
            const data = await response.json();
            if (data.success) {
                showNotification('Email успешно подтверждён! Перенаправление...', 'success');
                setTimeout(() => {
                    window.location.href = '/';
                }, 1500);
            } else {
                showNotification(data.message || 'Неверный код. Попробуйте ещё раз.', 'error');
                clearCodeInputs();
                submitBtn.disabled = false;
            }
        } catch (err) {
            console.error(err);
            showNotification('Ошибка сети. Попробуйте позже.', 'error');
            submitBtn.disabled = false;
        } finally {
            submitBtn.innerHTML = originalText;
        }
    }

    // Повторная отправка кода
    async function handleResend() {
        if (!canResend) return;
        resendBtn.disabled = true;
        const originalText = resendBtn.innerHTML;
        resendBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Отправка...';

        try {
            const response = await fetch('/users/api/ajax/resend-verification/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            const data = await response.json();
            if (data.success) {
                showNotification('Новый код отправлен на вашу почту', 'success');
                clearCodeInputs();
                resetTimer();
            } else {
                showNotification(data.message || 'Не удалось отправить код', 'error');
                // Возвращаем кнопку в исходное состояние, если не сбросили таймер
                if (timeLeft > 0) {
                    resendBtn.disabled = false;
                    canResend = true;
                }
            }
        } catch (err) {
            console.error(err);
            showNotification('Ошибка сети. Попробуйте позже.', 'error');
            if (timeLeft > 0) {
                resendBtn.disabled = false;
                canResend = true;
            }
        } finally {
            resendBtn.innerHTML = originalText;
        }
    }

    // Обработка ввода в поля
    function setupCodeInputs() {
        inputs.forEach((input, index) => {
            // Ввод только цифр
            input.addEventListener('input', (e) => {
                const val = e.target.value;
                if (!/^\d*$/.test(val)) {
                    e.target.value = '';
                    return;
                }
                if (val.length === 1) {
                    if (index < inputs.length - 1) {
                        inputs[index + 1].focus();
                    }
                }
                updateSubmitButton();
            });

            // Backspace
            input.addEventListener('keydown', (e) => {
                if (e.key === 'Backspace' && !e.target.value && index > 0) {
                    inputs[index - 1].focus();
                }
            });

            // Вставка из буфера (6 цифр)
            input.addEventListener('paste', (e) => {
                e.preventDefault();
                const paste = e.clipboardData.getData('text');
                const digits = paste.replace(/\D/g, '').split('');
                for (let i = 0; i < inputs.length && i < digits.length; i++) {
                    inputs[i].value = digits[i];
                }
                // Фокус на последнем заполненном поле
                const lastFilled = Math.min(digits.length, inputs.length) - 1;
                if (lastFilled >= 0 && lastFilled < inputs.length) {
                    inputs[lastFilled].focus();
                }
                updateSubmitButton();
            });
        });
    }

    // Проверка, не подтверждён ли уже email (редирект)
    async function checkAlreadyVerified() {
        try {
            const response = await fetch('/users/api/auth-status/', {
                method: 'GET',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const data = await response.json();
            if (data.email_verified) {
                showNotification('Email уже подтверждён. Перенаправление...', 'success');
                setTimeout(() => window.location.href = '/', 1500);
            }
        } catch (err) {
            console.error('Ошибка проверки статуса:', err);
        }
    }

    // Инициализация
    function init() {
        setupCodeInputs();
        startTimer();
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            handleVerify();
        });
        resendBtn.addEventListener('click', handleResend);
        updateSubmitButton();
        checkAlreadyVerified();
    }

    init();
})();