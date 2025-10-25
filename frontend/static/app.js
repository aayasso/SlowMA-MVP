// SlowMA JavaScript

// Menu toggle
function toggleMenu() {
    const menu = document.getElementById('menu');
    menu.classList.toggle('hidden');
}

// Close menu when clicking outside
document.addEventListener('click', function(event) {
    const menu = document.getElementById('menu');
    const menuBtn = document.querySelector('.menu-btn');
    
    if (menu && !menu.contains(event.target) && event.target !== menuBtn) {
        menu.classList.add('hidden');
    }
});

// Check for inactivity on page load
window.addEventListener('load', async function() {
    try {
        await fetch('/api/check_inactivity');
    } catch (error) {
        console.error('Error checking inactivity:', error);
    }
});