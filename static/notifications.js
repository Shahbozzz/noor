// Notifications - SIMPLIFIED (No Filters)

(function() {
    'use strict';

    // State
    let notifications = [];
    let currentPage = 1;
    let isLoading = false;
    let hasMore = true;

    // Elements
    const list = document.getElementById('notificationsList');
    const loader = document.getElementById('loader');
    const empty = document.getElementById('emptyState');
    const markAllBtn = document.getElementById('markAllBtn');

    // Init
    document.addEventListener('DOMContentLoaded', function() {
        loadNotifications(true);
        initInfiniteScroll();

        markAllBtn.addEventListener('click', markAllAsRead);
        updateNavbarBadge();
    });

    // Load notifications
    async function loadNotifications(reset = false) {
        if (isLoading) return;

        if (reset) {
            currentPage = 1;
            hasMore = true;
            notifications = [];
            list.innerHTML = '';
        }

        if (!hasMore) return;

        isLoading = true;
        showLoader();

        try {
            const url = `/api/notifications?page=${currentPage}&per_page=20`;

            const res = await fetch(url);
            
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }
            
            const data = await res.json();

            if (!data.success) {
                console.error('Error:', data.error);
                return;
            }

            if (data.notifications.length === 0 && currentPage === 1) {
                showEmpty();
                return;
            }

            hideEmpty();

            data.notifications.forEach(n => {
                notifications.push(n);
                renderNotification(n);
            });

            hasMore = data.pagination.has_next;
            currentPage++;

        } catch (err) {
            console.error('Error loading notifications:', err);
        } finally {
            hideLoader();
            isLoading = false;
        }
    }

    // Render single notification
    function renderNotification(n) {
        const div = document.createElement('div');
        div.className = `notification ${n.is_read ? '' : 'unread'}`;
        div.dataset.id = n.id;

        // ⭐ Get avatar URL - FIXED to use thumb and handle paths correctly
        let avatar = '/static/default-avatar.png';
        if (n.sender) {
            if (n.sender.photo_thumb_path) {
                // Check if it's a full path or just filename
                avatar = n.sender.photo_thumb_path.startsWith('/uploads/')
                    ? n.sender.photo_thumb_path
                    : `/uploads/${n.sender.photo_thumb_path.split('/').pop()}`;
            } else if (n.sender.photo_path) {
                avatar = n.sender.photo_path.startsWith('/uploads/')
                    ? n.sender.photo_path
                    : `/uploads/${n.sender.photo_path.split('/').pop()}`;
            }
        }

        const time = formatTime(new Date(n.created_at));

        // Special rendering for friend_request notifications
        const isRequestPending = n.type === 'friend_request' && !n.is_read;

        // ⭐ NEW: Change cursor for friend requests (they require button click)
        if (isRequestPending) {
            div.style.cursor = 'default';
        }

        // Get the actual friend request ID from notification data (with fallback)
        const requestId = (n.data && n.data.request_id) ? n.data.request_id : n.id;

        const actionsHTML = isRequestPending ? `
            <div class="notification-actions">
                <button class="notif-action-btn accept-btn" data-request-id="${requestId}">
                    ✓ Accept
                </button>
                <button class="notif-action-btn decline-btn" data-request-id="${requestId}">
                    ✕ Decline
                </button>
            </div>
        ` : '';

        // Profile URL
        const profileUrl = n.sender && n.sender.user_id ? `/profile/${n.sender.user_id}` : '#';

        div.innerHTML = `
            <img src="${avatar}" 
                 alt="Avatar" 
                 class="avatar"
                 loading="lazy"
                 onerror="this.src='/static/default-avatar.png'"
                 style="cursor: pointer;">
            <div class="notification-content">
                <p class="message">${escapeHtml(n.message)}</p>
                <span class="time">${time}</span>
                ${actionsHTML}
            </div>
            ${!n.is_read ? '<span class="unread-dot"></span>' : ''}
        `;

        // ⭐ Click on AVATAR - go to profile (WITHOUT deleting)
        const avatarImg = div.querySelector('.avatar');
        avatarImg.addEventListener('click', (e) => {
            e.stopPropagation();
            if (profileUrl !== '#') {
                window.location.href = profileUrl;
            }
        });

        // Add event listeners for Accept/Decline buttons
        if (isRequestPending) {
            const acceptBtn = div.querySelector('.accept-btn');
            const declineBtn = div.querySelector('.decline-btn');

            if (acceptBtn) {
                acceptBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    handleFriendRequest(n, 'accept', div, requestId);
                });
            }
            if (declineBtn) {
                declineBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    handleFriendRequest(n, 'decline', div, requestId);
                });
            }
        }

        // ⭐ Click on BODY behavior (MODIFIED)
        div.addEventListener('click', (e) => {
            // Ignore if clicked on buttons or avatar
            if (e.target.classList.contains('notif-action-btn') ||
                e.target.closest('.notif-action-btn') ||
                e.target.classList.contains('avatar')) {
                return;
            }
            
            // ⭐ NEW: Don't delete friend_request notifications on body click
            // They should only be deleted when Accept/Decline is pressed
            if (n.type === 'friend_request' && isRequestPending) {
                return; // Do nothing - wait for button click
            }
            
            // For all other notifications - delete on click
            deleteNotification(n.id, div);
        });

        list.appendChild(div);
    }

    // Handle Accept/Decline friend request
    async function handleFriendRequest(n, action, el, requestId) {
        const acceptBtn = el.querySelector('.accept-btn');
        const declineBtn = el.querySelector('.decline-btn');

        // Disable buttons
        if (acceptBtn) acceptBtn.disabled = true;
        if (declineBtn) declineBtn.disabled = true;

        try {
            const endpoint = action === 'accept'
                ? `/api/friends/accept/${requestId}`
                : `/api/friends/decline/${requestId}`;

            const res = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                }
            });

            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }

            const data = await res.json();

            if (data.success) {
                // ⭐ Delete notification after successful action
                await deleteNotification(n.id, el);
            } else {
                alert(data.error || 'Failed to process request');
                // Re-enable buttons on error
                if (acceptBtn) acceptBtn.disabled = false;
                if (declineBtn) declineBtn.disabled = false;
            }

        } catch (err) {
            console.error('Error handling friend request:', err);
            alert('Something went wrong. Please try again.');
            // Re-enable buttons on error
            if (acceptBtn) acceptBtn.disabled = false;
            if (declineBtn) declineBtn.disabled = false;
        }
    }

    // ⭐ Delete single notification
    async function deleteNotification(notificationId, element) {
        try {
            // Fade out animation
            element.style.opacity = '0';
            element.style.transform = 'translateX(-20px)';
            element.style.transition = 'all 0.3s ease';

            // Send delete request
            const res = await fetch(`/api/notifications/${notificationId}/read`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                }
            });

            const data = await res.json();

            if (data.success) {
                // Wait for animation to finish
                setTimeout(() => {
                    element.remove();

                    // Remove from array
                    notifications = notifications.filter(n => n.id !== notificationId);

                    // Check if list is empty
                    if (notifications.length === 0) {
                        showEmpty();
                    }

                    // Update badge
                    updateNavbarBadge();
                }, 300);
            } else {
                // Restore if error
                element.style.opacity = '1';
                element.style.transform = 'translateX(0)';
            }

        } catch (err) {
            console.error('Error deleting notification:', err);
            element.style.opacity = '1';
            element.style.transform = 'translateX(0)';
        }
    }

    // ⭐ Mark all as read (delete all) - with custom modal
    async function markAllAsRead() {
        if (notifications.length === 0) return;

        // Show custom modal instead of confirm
        showConfirmModal();
    }

    // Show custom confirmation modal
    function showConfirmModal() {
        const modal = document.getElementById('confirmModal');
        const confirmBtn = document.getElementById('modalConfirm');
        const cancelBtn = document.getElementById('modalCancel');

        modal.style.display = 'flex';

        // Remove old event listeners
        const newConfirmBtn = confirmBtn.cloneNode(true);
        const newCancelBtn = cancelBtn.cloneNode(true);
        confirmBtn.parentNode.replaceChild(newConfirmBtn, confirmBtn);
        cancelBtn.parentNode.replaceChild(newCancelBtn, cancelBtn);

        // Add new event listeners
        newConfirmBtn.addEventListener('click', async () => {
            modal.style.display = 'none';
            await deleteAllNotifications();
        });

        newCancelBtn.addEventListener('click', () => {
            modal.style.display = 'none';
        });

        // Close on overlay click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.style.display = 'none';
            }
        });
    }

    // Actually delete all notifications
    async function deleteAllNotifications() {
        markAllBtn.disabled = true;
        markAllBtn.textContent = 'Deleting...';

        try {
            const res = await fetch('/api/notifications/read-all', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                }
            });

            const data = await res.json();

            if (data.success) {
                // Cascade animation for all notifications
                const allNotifs = document.querySelectorAll('.notification');
                allNotifs.forEach((el, index) => {
                    setTimeout(() => {
                        el.style.opacity = '0';
                        el.style.transform = 'translateX(-20px)';
                        el.style.transition = 'all 0.3s ease';
                    }, index * 50);
                });

                // Remove all after animation
                setTimeout(() => {
                    list.innerHTML = '';
                    notifications = [];
                    showEmpty();
                    updateNavbarBadge();
                    markAllBtn.disabled = false;
                    markAllBtn.textContent = 'Mark all read';
                }, allNotifs.length * 50 + 300);
            } else {
                markAllBtn.disabled = false;
                markAllBtn.textContent = 'Mark all read';
                alert('Failed to delete notifications');
            }
        } catch (err) {
            console.error('Error:', err);
            markAllBtn.disabled = false;
            markAllBtn.textContent = 'Mark all read';
            alert('Failed to delete notifications');
        }
    }

    // Update navbar badge
    let badgeUpdateTimeout = null;
    let lastBadgeUpdate = 0;
    const BADGE_UPDATE_COOLDOWN = 2000; // 2 seconds

    async function updateNavbarBadge() {
        const now = Date.now();
        if (now - lastBadgeUpdate < BADGE_UPDATE_COOLDOWN) {
            return;
        }

        if (badgeUpdateTimeout) {
            clearTimeout(badgeUpdateTimeout);
        }

        return new Promise((resolve) => {
            badgeUpdateTimeout = setTimeout(async () => {
                try {
                    const res = await fetch('/api/notifications/unread-count');

                    if (!res.ok) {
                        if (res.status === 429) {
                            console.warn('Badge update rate limited');
                        }
                        resolve();
                        return;
                    }

                    const contentType = res.headers.get('content-type');
                    if (!contentType || !contentType.includes('application/json')) {
                        resolve();
                        return;
                    }

                    const data = await res.json();

                    if (data.success) {
                        lastBadgeUpdate = Date.now();

                        const badge = document.getElementById('notificationBadge');
                        const badgeMobile = document.getElementById('notificationBadgeMobile');

                        if (badge) {
                            if (data.unread_count > 0) {
                                badge.textContent = data.unread_count > 99 ? '99+' : data.unread_count;
                                badge.style.display = 'flex';
                            } else {
                                badge.style.display = 'none';
                            }
                        }

                        if (badgeMobile) {
                            if (data.unread_count > 0) {
                                badgeMobile.textContent = data.unread_count > 99 ? '99+' : data.unread_count;
                                badgeMobile.style.display = 'flex';
                            } else {
                                badgeMobile.style.display = 'none';
                            }
                        }
                    }
                    resolve();
                } catch (err) {
                    console.error('Error updating badge:', err);
                    resolve();
                }
            }, 500); // Debounce 500ms
        });
    }

    // Infinite scroll
    function initInfiniteScroll() {
        const observer = new IntersectionObserver(entries => {
            if (entries[0].isIntersecting && !isLoading && hasMore) {
                loadNotifications();
            }
        }, { rootMargin: '100px' });

        observer.observe(loader);
    }

    // Utilities
    function showLoader() {
        loader.style.display = 'flex';
    }

    function hideLoader() {
        loader.style.display = 'none';
    }

    function showEmpty() {
        empty.style.display = 'block';
        list.style.display = 'none';
    }

    function hideEmpty() {
        empty.style.display = 'none';
        list.style.display = 'flex';
    }

    function formatTime(date) {
        const seconds = Math.floor((new Date() - date) / 1000);

        if (seconds < 60) return 'just now';
        const minutes = Math.floor(seconds / 60);
        if (minutes < 60) return minutes + 'm ago';
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return hours + 'h ago';
        const days = Math.floor(hours / 24);
        if (days < 7) return days + 'd ago';
        const weeks = Math.floor(days / 7);
        if (weeks < 4) return weeks + 'w ago';
        return date.toLocaleDateString();
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

})();