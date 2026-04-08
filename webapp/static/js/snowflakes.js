/**
 * Новогодняя анимация снежинок
 */

function createSnowflakes() {
    const snowflakesContainer = document.createElement('div');
    snowflakesContainer.className = 'snowflakes-container';
    document.body.appendChild(snowflakesContainer);

    const snowflakeSymbols = ['❄', '❅', '❆', '✻', '✼', '✽', '✾', '✿'];
    const numSnowflakes = 50;

    for (let i = 0; i < numSnowflakes; i++) {
        setTimeout(() => {
            const snowflake = document.createElement('div');
            snowflake.className = 'snowflake';
            snowflake.textContent = snowflakeSymbols[Math.floor(Math.random() * snowflakeSymbols.length)];
            
            // Случайная позиция по горизонтали
            const left = Math.random() * 100;
            snowflake.style.left = left + '%';
            
            // Случайная скорость падения (от 10 до 20 секунд)
            const duration = 10 + Math.random() * 10;
            snowflake.style.setProperty('--drift', (Math.random() * 100 - 50) + 'px');
            snowflake.style.animationDuration = duration + 's';
            
            // Случайный размер
            const size = 0.8 + Math.random() * 1.2;
            snowflake.style.fontSize = size + 'em';
            
            // Случайная задержка начала анимации
            snowflake.style.animationDelay = Math.random() * 5 + 's';
            
            snowflakesContainer.appendChild(snowflake);

            // Удаляем снежинку после завершения анимации
            setTimeout(() => {
                if (snowflake.parentNode) {
                    snowflake.parentNode.removeChild(snowflake);
                }
            }, (duration + 5) * 1000);
        }, i * 200);
    }

    // Постоянно создаем новые снежинки
    setInterval(() => {
        const snowflake = document.createElement('div');
        snowflake.className = 'snowflake';
        snowflake.textContent = snowflakeSymbols[Math.floor(Math.random() * snowflakeSymbols.length)];
        
        const left = Math.random() * 100;
        snowflake.style.left = left + '%';
        
        const duration = 10 + Math.random() * 10;
        snowflake.style.setProperty('--drift', (Math.random() * 100 - 50) + 'px');
        snowflake.style.animationDuration = duration + 's';
        
        const size = 0.8 + Math.random() * 1.2;
        snowflake.style.fontSize = size + 'em';
        
        snowflake.style.animationDelay = '0s';
        
        snowflakesContainer.appendChild(snowflake);

        setTimeout(() => {
            if (snowflake.parentNode) {
                snowflake.parentNode.removeChild(snowflake);
            }
        }, duration * 1000);
    }, 500);
}

// Запускаем анимацию снежинок при загрузке страницы
document.addEventListener('DOMContentLoaded', createSnowflakes);

