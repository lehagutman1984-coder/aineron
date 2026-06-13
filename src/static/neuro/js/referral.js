// referral.js
(function() {
    'use strict';

    const modal = document.getElementById('withdrawModal');
    const withdrawBtn = document.getElementById('withdrawBtn');
    const closeBtn = document.getElementById('closeModalBtn');
    const overlay = document.querySelector('.withdraw-modal-overlay');
    const withdrawForm = document.getElementById('withdrawForm');

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
        const old = document.querySelector('.referral-notification');
        if (old) old.remove();
        const note = document.createElement('div');
        note.className = 'referral-notification';
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

    // Копирование ссылки
    window.copyLink = function() {
        const input = document.getElementById('referralLink');
        if (!input) return;
        const link = input.value;
        navigator.clipboard.writeText(link).then(() => {
            showNotification('Ссылка скопирована', 'success');
        }).catch(err => {
            console.error(err);
            input.select();
            document.execCommand('copy');
            showNotification('Ссылка скопирована', 'success');
        });
    };

    // Модалка вывода
    if (withdrawBtn) {
        withdrawBtn.addEventListener('click', () => {
            modal.classList.add('show');
            document.body.style.overflow = 'hidden';
        });
    }

    function closeModal() {
        modal.classList.remove('show');
        document.body.style.overflow = '';
    }

    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    if (overlay) overlay.addEventListener('click', closeModal);

    if (withdrawForm) {
        withdrawForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const cardNumber = document.getElementById('cardNumber').value.trim();
            const amount = document.getElementById('withdrawAmount').value;
            const agree = document.getElementById('agreeTerms').checked;

            if (!cardNumber) {
                showNotification('Введите номер карты', 'error');
                return;
            }
            if (!amount || amount <= 0) {
                showNotification('Введите корректную сумму', 'error');
                return;
            }
            if (!agree) {
                showNotification('Подтвердите условия', 'error');
                return;
            }

            const submitBtn = withdrawForm.querySelector('.submit-withdraw-btn');
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Отправка...';

            try {
                const response = await fetch('/users/api/request-withdrawal/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken(),
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify({ card_number: cardNumber, amount: parseFloat(amount) })
                });
                const data = await response.json();
                if (data.success) {
                    showNotification('Запрос на вывод отправлен', 'success');
                    setTimeout(() => location.reload(), 2000);
                } else {
                    showNotification(data.message || 'Ошибка отправки', 'error');
                }
            } catch (err) {
                console.error(err);
                showNotification('Ошибка сети', 'error');
            } finally {
                submitBtn.disabled = false;
                submitBtn.innerHTML = 'Отправить запрос';
            }
        });
    }

    // График
    if (typeof Chart !== 'undefined' && document.getElementById('earningsChart')) {
        const months = window.referralMonths || [];
        const earningsData = window.referralEarnings || [];

        if (months.length > 0 && earningsData.length > 0) {
            const ctx = document.getElementById('earningsChart').getContext('2d');
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: months,
                    datasets: [{
                        label: 'Доход',
                        data: earningsData,
                        backgroundColor: '#0a7cff',
                        borderRadius: 8
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    plugins: { legend: { display: false } },
                    scales: {
                        y: { beginAtZero: true, grid: { color: '#eef2f6' } }
                    }
                }
            });
        } else {
            const chartCanvas = document.getElementById('earningsChart');
            if (chartCanvas) chartCanvas.style.display = 'none';
            const chartCard = document.querySelector('.chart-card');
            if (chartCard && !chartCard.querySelector('.no-data')) {
                const noDataMsg = document.createElement('p');
                noDataMsg.className = 'no-data';
                noDataMsg.textContent = 'Нет данных за последние 12 месяцев';
                chartCard.appendChild(noDataMsg);
            }
        }
    }
})();