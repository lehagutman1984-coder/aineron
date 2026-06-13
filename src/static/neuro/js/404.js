(function() {
    // Небольшая анимация для плавающих фигур при движении мыши
    const container = document.querySelector('.error-container');
    const shapes = document.querySelectorAll('.shape');

    if (!container || shapes.length === 0) return;

    container.addEventListener('mousemove', (e) => {
        const x = e.clientX / window.innerWidth - 0.5;
        const y = e.clientY / window.innerHeight - 0.5;

        shapes.forEach((shape, index) => {
            const speed = (index + 1) * 15;
            const moveX = x * speed;
            const moveY = y * speed;
            shape.style.transform = `translate(${moveX}px, ${moveY}px)`;
        });
    });

    container.addEventListener('mouseleave', () => {
        shapes.forEach(shape => {
            shape.style.transform = '';
        });
    });
})();