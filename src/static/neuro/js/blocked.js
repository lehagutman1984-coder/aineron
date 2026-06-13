// Минимальный JS для дополнительных эффектов (например, параллакс или анимация при движении мыши)
(function() {
    const card = document.querySelector('.blocked-card');
    const icon = document.querySelector('.blocked-icon');

    if (!card) return;

    // Небольшой эффект свечения при движении мыши (для красоты)
    card.addEventListener('mousemove', (e) => {
        const rect = card.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        const angleX = (x - centerX) / 20;
        const angleY = (y - centerY) / 20;
        card.style.transform = `perspective(1000px) rotateX(${-angleY}deg) rotateY(${angleX}deg)`;
    });

    card.addEventListener('mouseleave', () => {
        card.style.transform = '';
    });

    // Лёгкая пульсация для иконки (уже есть в CSS, но можно управлять через JS)
})();