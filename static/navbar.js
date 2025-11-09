// NOOR Navbar JavaScript
// Minimal code - Flask handles active states via Jinja2

(function() {
    'use strict';

    // Initialize when DOM is ready
    function init() {
        console.log('NOOR Navbar initialized');

        // Optional: Add any future interactive features here
    }

    // Run on load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    async function updateNotificationBadge() {
        try {
            const res = await fetch('/api/notifications/unread-count');
            const data = await res.json();

            if (data.success) {
                const badge = document.getElementById('notificationBadge');
                const badgeMobile = document.getElementById('notificationBadgeMobile');
                const count = data.unread_count;
                const display = count > 0 ? 'flex' : 'none';
                const text = count > 99 ? '99+' : count;

                if (badge) {
                    badge.textContent = text;
                    badge.style.display = display;
                }

                if (badgeMobile) {
                    badgeMobile.textContent = text;
                    badgeMobile.style.display = display;
                }
            }
        } catch (err) {
            console.error('Badge update error:', err);
        }
    }

    // Update on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', updateNotificationBadge);
    } else {
        updateNotificationBadge();
    }

    // Update every 30 seconds
    setInterval(updateNotificationBadge, 30000);
})();