// auth.js
(function() {
    'use strict';

    let currentNext = null;

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

    function showFieldError(elementId, message) {
        const el = document.getElementById(elementId);
        if (el) {
            el.textContent = message;
            el.classList.add('show');
            setTimeout(() => el.classList.remove('show'), 5000);
        }
    }

    function clearAllErrors() {
        document.querySelectorAll('.auth-error-message').forEach(el => {
            el.textContent = '';
            el.classList.remove('show');
        });
        document.querySelectorAll('.auth-field').forEach(f => f.classList.remove('error'));
    }

    function toggleButtonLoader(btn, show) {
        if (!btn) return;
        const loader = btn.querySelector('.btn-loader');
        const span = btn.querySelector('span');
        btn.disabled = show;
        if (loader) loader.style.display = show ? 'flex' : 'none';
        if (span) span.style.opacity = show ? '0.7' : '1';
    }

    function showNotification(message, type = 'info') {
        const oldNote = document.querySelector('.auth-floating-notification');
        if (oldNote) oldNote.remove();

        const note = document.createElement('div');
        note.className = `auth-floating-notification ${type}`;
        note.innerHTML = `
            <div class="notification-content">
                <i class="fas ${type === 'success' ? 'fa-check-circle' : type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle'}"></i>
                <span>${message}</span>
            </div>
        `;
        document.body.appendChild(note);
        setTimeout(() => note.classList.add('show'), 10);
        setTimeout(() => {
            note.classList.remove('show');
            setTimeout(() => note.remove(), 300);
        }, 4000);
    }

    document.addEventListener('DOMContentLoaded', function() {
        const overlay = document.getElementById('authModalOverlay');
        if (!overlay) return;

        const screenInitial = overlay.querySelector('.auth-screen-initial');
        const screenAuth = overlay.querySelector('.auth-screen-auth');
        const screenForgot = overlay.querySelector('.auth-screen-forgot');

        const loginForm = document.getElementById('loginForm');
        const registerForm = document.getElementById('registerForm');
        const forgotForm = document.getElementById('forgotForm');

        const loginEmail = document.getElementById('loginEmail');
        const loginPassword = document.getElementById('loginPassword');
        const registerEmail = document.getElementById('registerEmail');
        const registerPassword = document.getElementById('registerPassword');
        const registerConfirm = document.getElementById('registerConfirmPassword');
        const resetEmail = document.getElementById('resetEmail');

        const confirmField = document.getElementById('confirmPasswordField');
        const passwordMatchError = document.getElementById('passwordMatchError');
        const forgotSuccessMessage = document.getElementById('forgotSuccessMessage');

        const loginSubmitBtn = document.getElementById('loginSubmitBtn');
        const registerSubmitBtn = document.getElementById('registerSubmitBtn');
        const resetSubmitBtn = document.getElementById('resetSubmitBtn');

        const strengthBar = document.getElementById('strengthBar');
        const strengthText = document.getElementById('strengthText');

        function updateStrengthIndicator(password) {
            if (!strengthBar || !strengthText) return;
            if (password.length === 0) {
                strengthBar.style.width = '0%';
                strengthBar.style.backgroundColor = '#e0e0e0';
                strengthText.textContent = '';
                return;
            }
            let score = 0;
            if (password.length >= 8) score++;
            if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
            if (/[0-9]/.test(password)) score++;
            if (/[^a-zA-Z0-9]/.test(password)) score++;

            let width = '0%', text = '', color = '#e53e3e';
            if (score <= 1) {
                width = '33%';
                text = 'Слабый пароль';
                color = '#e53e3e';
            } else if (score === 2) {
                width = '66%';
                text = 'Средний пароль';
                color = '#ff8a00';
            } else {
                width = '100%';
                text = 'Сильный пароль';
                color = '#21be19';
            }
            strengthBar.style.width = width;
            strengthBar.style.backgroundColor = color;
            strengthText.textContent = text;
        }

        function checkPasswordMatch() {
            if (!registerPassword || !registerConfirm) return;
            const pass = registerPassword.value;
            const conf = registerConfirm.value;
            if (pass !== conf && conf.length > 0) {
                if (confirmField) confirmField.classList.add('error');
                if (passwordMatchError) passwordMatchError.classList.add('show');
            } else {
                if (confirmField) confirmField.classList.remove('error');
                if (passwordMatchError) passwordMatchError.classList.remove('show');
            }
        }

        function passwordsMatch() {
            if (!registerPassword || !registerConfirm) return false;
            return registerPassword.value === registerConfirm.value;
        }

        function hideAllScreens() {
            if (screenInitial) screenInitial.classList.remove('active');
            if (screenAuth) screenAuth.classList.remove('active');
            if (screenForgot) screenForgot.classList.remove('active');
        }

        function showInitialScreen() {
            hideAllScreens();
            if (screenInitial) screenInitial.classList.add('active');
            if (confirmField) confirmField.classList.remove('error');
            if (passwordMatchError) passwordMatchError.classList.remove('show');
            if (forgotForm) forgotForm.style.display = 'flex';
            if (forgotSuccessMessage) forgotSuccessMessage.style.display = 'none';
            clearAllErrors();
            if (strengthBar) strengthBar.style.width = '0%';
            if (strengthText) strengthText.textContent = '';
        }

        function showAuthScreen(tab = 'login') {
            hideAllScreens();
            if (screenAuth) screenAuth.classList.add('active');
            const tabs = overlay.querySelectorAll('.auth-tab');
            tabs.forEach(t => t.classList.remove('active'));
            const activeTab = overlay.querySelector(`[data-tab="${tab}"]`);
            if (activeTab) activeTab.classList.add('active');
            if (tab === 'login') {
                if (loginForm) loginForm.classList.add('active');
                if (registerForm) registerForm.classList.remove('active');
            } else {
                if (loginForm) loginForm.classList.remove('active');
                if (registerForm) registerForm.classList.add('active');
            }
            if (confirmField) confirmField.classList.remove('error');
            if (passwordMatchError) passwordMatchError.classList.remove('show');
            if (forgotForm) forgotForm.style.display = 'flex';
            if (forgotSuccessMessage) forgotSuccessMessage.style.display = 'none';
            clearAllErrors();
            if (strengthBar) strengthBar.style.width = '0%';
            if (strengthText) strengthText.textContent = '';
        }

        function showForgotScreen() {
            hideAllScreens();
            if (screenForgot) screenForgot.classList.add('active');
            if (forgotForm) forgotForm.style.display = 'flex';
            if (forgotSuccessMessage) forgotSuccessMessage.style.display = 'none';
            clearAllErrors();
        }

        async function handleRegister(e) {
            e.preventDefault();
            if (!registerEmail || !registerPassword || !registerConfirm) {
                showNotification('Ошибка: не найдены поля формы', 'error');
                return;
            }
            const email = registerEmail.value.trim();
            const password = registerPassword.value;
            const confirm = registerConfirm.value;

            clearAllErrors();
            if (!email || !password || !confirm) {
                showFieldError('registerEmailError', 'Заполните все поля');
                return;
            }
            const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRe.test(email)) {
                showFieldError('registerEmailError', 'Введите корректный email');
                return;
            }
            if (password.length < 8) {
                showFieldError('registerPasswordError', 'Пароль должен быть не менее 8 символов');
                return;
            }
            if (password !== confirm) {
                if (confirmField) confirmField.classList.add('error');
                if (passwordMatchError) passwordMatchError.classList.add('show');
                return;
            }

            toggleButtonLoader(registerSubmitBtn, true);
            try {
                const response = await fetch('/users/api/ajax/register/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken(),
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({ email, password, confirm_password: confirm, next: currentNext })
                });
                const data = await response.json();
                if (data.success) {
                    if (data.shadow_banned) {
                        showNotification('Ваш аккаунт заблокирован', 'error');
                    } else {
                        showNotification('Регистрация успешна! Проверьте почту для подтверждения.', 'success');
                    }
                    window.location.href = data.redirect;
                } else {
                    if (data.errors) {
                        if (data.errors.email) showFieldError('registerEmailError', data.errors.email);
                        if (data.errors.password) showFieldError('registerPasswordError', data.errors.password);
                        if (data.errors.confirm_password) showFieldError('passwordMatchError', data.errors.confirm_password);
                    } else {
                        showFieldError('registerEmailError', data.message || 'Ошибка регистрации');
                    }
                }
            } catch (err) {
                console.error(err);
                showFieldError('registerEmailError', 'Ошибка сети. Попробуйте позже.');
            } finally {
                toggleButtonLoader(registerSubmitBtn, false);
            }
        }

        async function handleLogin(e) {
            e.preventDefault();
            if (!loginEmail || !loginPassword) {
                showNotification('Ошибка: не найдены поля формы', 'error');
                return;
            }
            const email = loginEmail.value.trim();
            const password = loginPassword.value;

            clearAllErrors();
            if (!email || !password) {
                showFieldError('loginEmailError', 'Заполните все поля');
                return;
            }
            const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRe.test(email)) {
                showFieldError('loginEmailError', 'Введите корректный email');
                return;
            }

            toggleButtonLoader(loginSubmitBtn, true);
            try {
                const response = await fetch('/users/api/ajax/login/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken(),
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({ username: email, password: password, next: currentNext })
                });
                const data = await response.json();
                if (data.success) {
                    window.location.href = data.redirect || '/';
                } else {
                    if (data.errors) {
                        if (data.errors.username) showFieldError('loginEmailError', data.errors.username);
                        if (data.errors.password) showFieldError('loginPasswordError', data.errors.password);
                    } else {
                        showFieldError('loginEmailError', data.message || 'Ошибка входа');
                    }
                }
            } catch (err) {
                console.error(err);
                showFieldError('loginEmailError', 'Ошибка сети. Попробуйте позже.');
            } finally {
                toggleButtonLoader(loginSubmitBtn, false);
            }
        }

        async function handleForgot(e) {
            e.preventDefault();
            if (!resetEmail) {
                showNotification('Ошибка: не найдено поле email', 'error');
                return;
            }
            const email = resetEmail.value.trim();

            clearAllErrors();
            if (!email) {
                showFieldError('resetEmailError', 'Введите email');
                return;
            }
            const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRe.test(email)) {
                showFieldError('resetEmailError', 'Введите корректный email');
                return;
            }

            toggleButtonLoader(resetSubmitBtn, true);
            try {
                const response = await fetch('/users/api/ajax/password-reset/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken(),
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({ email: email, next: currentNext })
                });
                const data = await response.json();
                if (data.success) {
                    if (forgotForm) forgotForm.style.display = 'none';
                    if (forgotSuccessMessage) forgotSuccessMessage.style.display = 'block';
                    showNotification('Письмо для восстановления отправлено на ваш email', 'success');
                    setTimeout(() => showAuthScreen('login'), 3000);
                } else {
                    showFieldError('resetEmailError', data.message || 'Пользователь не найден');
                }
            } catch (err) {
                console.error(err);
                showFieldError('resetEmailError', 'Ошибка сети. Попробуйте позже.');
            } finally {
                toggleButtonLoader(resetSubmitBtn, false);
            }
        }

        function onDocumentClick(e) {
            const target = e.target;
            if (target.closest('#authCloseBtn') || target === overlay) {
                overlay.classList.remove('show');
                document.body.style.overflow = '';
                clearAllErrors();
                return;
            }
            const socialBtn = target.closest('.auth-social-btn');
            if (socialBtn) {
                e.preventDefault();
                let provider = '';
                if (socialBtn.classList.contains('yandex')) provider = 'yandex';
                else if (socialBtn.classList.contains('vk')) provider = 'vk';
                else if (socialBtn.classList.contains('mailru')) provider = 'mailru';
                if (provider) {
                    let url = `/accounts/${provider}/login/`;
                    if (currentNext) {
                        url += `?next=${encodeURIComponent(currentNext)}`;
                    }
                    window.location.href = url;
                }
                return;
            }
            if (target.closest('#authEmailBtn')) {
                showAuthScreen('login');
                return;
            }
            const tab = target.closest('.auth-tab');
            if (tab) {
                const tabName = tab.getAttribute('data-tab');
                if (tabName === 'login') showAuthScreen('login');
                else showAuthScreen('register');
                return;
            }
            const toggle = target.closest('.password-toggle');
            if (toggle) {
                const wrapper = toggle.closest('.password-wrapper');
                if (wrapper) {
                    const input = wrapper.querySelector('input');
                    const icon = toggle.querySelector('i');
                    if (input.type === 'password') {
                        input.type = 'text';
                        icon.classList.remove('fa-eye');
                        icon.classList.add('fa-eye-slash');
                    } else {
                        input.type = 'password';
                        icon.classList.remove('fa-eye-slash');
                        icon.classList.add('fa-eye');
                    }
                }
                return;
            }
            if (target.closest('#forgotPasswordLink')) {
                e.preventDefault();
                showForgotScreen();
                return;
            }
            if (target.closest('#backToInitialBtn')) {
                showInitialScreen();
                return;
            }
            if (target.closest('#backToLoginBtn')) {
                showAuthScreen('login');
                return;
            }
            if (target.closest('#loginForm button[type="submit"]')) {
                handleLogin(e);
                return;
            }
            if (target.closest('#registerForm button[type="submit"]')) {
                if (passwordsMatch()) {
                    handleRegister(e);
                } else {
                    if (confirmField) confirmField.classList.add('error');
                    if (passwordMatchError) passwordMatchError.classList.add('show');
                }
                return;
            }
            if (target.closest('#forgotForm button[type="submit"]')) {
                handleForgot(e);
                return;
            }
        }

        document.addEventListener('click', onDocumentClick);

        if (registerPassword) {
            registerPassword.addEventListener('input', function(e) {
                updateStrengthIndicator(e.target.value);
                checkPasswordMatch();
            });
        }
        if (registerConfirm) {
            registerConfirm.addEventListener('input', checkPasswordMatch);
        }

        window.openAuthModal = function() {
            currentNext = window.location.pathname + window.location.search;
            overlay.classList.add('show');
            document.body.style.overflow = 'hidden';
            showInitialScreen();
            if (loginEmail) loginEmail.value = '';
            if (loginPassword) loginPassword.value = '';
            if (registerEmail) registerEmail.value = '';
            if (registerPassword) registerPassword.value = '';
            if (registerConfirm) registerConfirm.value = '';
            if (resetEmail) resetEmail.value = '';
            if (strengthBar) strengthBar.style.width = '0%';
            if (strengthText) strengthText.textContent = '';
        };
    });
})();
