/**
 * Дополнительные анимации и эффекты для современного интерфейса
 */

// Анимация появления элементов при скролле
function initScrollAnimations() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
                observer.unobserve(entry.target);
            }
        });
    }, observerOptions);

    // Применяем к элементам с классом animate-on-scroll
    document.querySelectorAll('.animate-on-scroll').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = 'all 0.6s cubic-bezier(0.4, 0, 0.2, 1)';
        observer.observe(el);
    });
}

// Плавные переходы между страницами
function initPageTransitions() {
    document.querySelectorAll('a[href^="/"]').forEach(link => {
        link.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            if (href && href !== '#' && !href.startsWith('http')) {
                // Добавляем эффект затухания
                document.body.style.transition = 'opacity 0.3s ease';
                document.body.style.opacity = '0.7';
            }
        });
    });
}

// Анимация чисел (для баланса и счетчиков)
function animateNumber(element, start, end, duration = 1000) {
    const startTime = performance.now();
    const difference = end - start;

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // Используем easing функцию для плавности
        const easeOutQuart = 1 - Math.pow(1 - progress, 4);
        const current = Math.floor(start + difference * easeOutQuart);
        
        element.textContent = current.toLocaleString('uk-UA');
        
        if (progress < 1) {
            requestAnimationFrame(update);
        } else {
            element.textContent = end.toLocaleString('uk-UA');
        }
    }

    requestAnimationFrame(update);
}

// Эффект параллакса для фона
function initParallax() {
    let ticking = false;

    function updateParallax() {
        const scrolled = window.pageYOffset;
        const parallaxElements = document.querySelectorAll('.parallax');
        
        parallaxElements.forEach(element => {
            const speed = element.dataset.speed || 0.5;
            const yPos = -(scrolled * speed);
            element.style.transform = `translate3d(0, ${yPos}px, 0)`;
        });

        ticking = false;
    }

    window.addEventListener('scroll', () => {
        if (!ticking) {
            window.requestAnimationFrame(updateParallax);
            ticking = true;
        }
    });
}

// Эффект магнитного притяжения для кнопок
function initMagneticButtons() {
    document.querySelectorAll('.magnetic').forEach(button => {
        button.addEventListener('mousemove', function(e) {
            const rect = this.getBoundingClientRect();
            const x = e.clientX - rect.left - rect.width / 2;
            const y = e.clientY - rect.top - rect.height / 2;
            
            const moveX = x * 0.3;
            const moveY = y * 0.3;
            
            this.style.transform = `translate(${moveX}px, ${moveY}px)`;
        });

        button.addEventListener('mouseleave', function() {
            this.style.transform = 'translate(0, 0)';
        });
    });
}

// Анимация загрузки с эффектом волны
function createLoadingWave() {
    const loader = document.createElement('div');
    loader.className = 'loading-wave';
    loader.innerHTML = `
        <div class="wave-dot"></div>
        <div class="wave-dot"></div>
        <div class="wave-dot"></div>
        <div class="wave-dot"></div>
    `;
    return loader;
}

// Эффект частиц при клике
function createClickParticles(x, y) {
    for (let i = 0; i < 8; i++) {
        const particle = document.createElement('div');
        particle.className = 'click-particle';
        particle.style.left = x + 'px';
        particle.style.top = y + 'px';
        
        const angle = (Math.PI * 2 * i) / 8;
        const velocity = 50 + Math.random() * 50;
        const vx = Math.cos(angle) * velocity;
        const vy = Math.sin(angle) * velocity;
        
        document.body.appendChild(particle);
        
        particle.animate([
            { transform: 'translate(0, 0) scale(1)', opacity: 1 },
            { transform: `translate(${vx}px, ${vy}px) scale(0)`, opacity: 0 }
        ], {
            duration: 600,
            easing: 'ease-out'
        }).onfinish = () => particle.remove();
    }
}

// Инициализация всех эффектов при загрузке
document.addEventListener('DOMContentLoaded', () => {
    initScrollAnimations();
    initPageTransitions();
    initParallax();
    initMagneticButtons();
    
    // Добавляем эффект частиц при клике на карточки
    document.querySelectorAll('.menu-card').forEach(card => {
        card.addEventListener('click', function(e) {
            const rect = this.getBoundingClientRect();
            createClickParticles(
                e.clientX - rect.left + rect.width / 2,
                e.clientY - rect.top + rect.height / 2
            );
        });
    });
    
    // Анимация баланса при загрузке
    const balanceElement = document.getElementById('userBalance');
    if (balanceElement) {
        const balanceText = balanceElement.textContent;
        const balanceValue = parseFloat(balanceText.replace(/[^\d.,]/g, '').replace(',', '.'));
        if (!isNaN(balanceValue)) {
            animateNumber(balanceElement, 0, balanceValue, 1500);
        }
    }
});

// Экспорт функций для использования в других скриптах
window.Animations = {
    animateNumber,
    createClickParticles,
    initScrollAnimations,
    initParallax
};

