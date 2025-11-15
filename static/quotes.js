// Student Voice - Faculty-Based with Auto-Select
(function() {
    'use strict';

    // ==================== CONFIGURATION ====================

    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }
    const csrfToken = getCsrfToken();

    // ==================== STATE MANAGEMENT ====================

    let currentFaculty = null;  // Will be set to user's faculty
    let currentSort = 'most_liked';
    let currentPage = 1;
    let isLoading = false;
    let hasMorePages = true;
    let posts = new Map();
    let userFaculty = null;  // User's actual faculty (SOCIE or SBL)
    let userId = null;
    let isInitialized = false;

    // ==================== DOM CACHE ====================

    const elements = {};

    function cacheDOMElements() {
        elements.postsFeed = document.getElementById('postsFeed');
        elements.loadingIndicator = document.getElementById('loadingIndicator');
        elements.postInput = document.getElementById('postInput');
        elements.charCounter = document.getElementById('charCounter');
        elements.sendBtn = document.getElementById('sendBtn');
        elements.editModal = document.getElementById('editModal');
        elements.modalOverlay = document.getElementById('modalOverlay');
        elements.editInput = document.getElementById('editInput');
        elements.editCharCounter = document.getElementById('editCharCounter');
        elements.cancelEditBtn = document.getElementById('cancelEditBtn');
        elements.saveEditBtn = document.getElementById('saveEditBtn');
        elements.composer = document.getElementById('composer');
        elements.rateLimitWarning = document.getElementById('rateLimitWarning');
        elements.rateLimitMessage = document.getElementById('rateLimitMessage');
    }

    // ==================== USER INFO ====================

    async function loadUserInfo() {
        console.log('🔄 Loading user info...');

        try {
            const response = await fetch('/api/voice/user-info');
            const data = await response.json();

            console.log('📥 User info response:', data);

            if (!data.success) {
                console.error('❌ Failed to load user info:', data.error);
                showError(`Error: ${data.error}\n\nPlease check your faculty is one of: ICE, CSE, SBL_B, or SBL_L`);
                return false;
            }

            userFaculty = data.faculty_group;
            userId = data.user_id;

            console.log(`✅ User faculty: ${userFaculty}`);

            // Set initial faculty view to user's faculty
            currentFaculty = userFaculty;
            updateActiveFacultyTab();

            // Show/hide composer based on faculty match
            updateComposerVisibility();

            return true;

        } catch (error) {
            console.error('❌ Error loading user info:', error);
            showError('Failed to load user information. Please refresh the page.');
            return false;
        }
    }

    // ==================== FACULTY MANAGEMENT ====================

    function updateActiveFacultyTab() {
        const tabs = document.querySelectorAll('.faculty-tab');
        tabs.forEach(tab => {
            if (tab.getAttribute('data-faculty') === currentFaculty) {
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
            }
        });
    }

    function updateComposerVisibility() {
        if (!elements.composer) return;

        if (currentSort === 'my_quote' || currentFaculty === userFaculty) {
            elements.composer.style.display = 'block';
            elements.postInput.placeholder = currentSort === 'my_quote'
                ? 'Update your thought...'
                : 'Share your thoughts...';
        } else {
            elements.composer.style.display = 'none';
        }
    }

    // ==================== POSTS LOADING ====================

    async function loadPosts(reset = false) {
        if (isLoading || (!hasMorePages && !reset)) return;

        // Wait for initialization
        if (!isInitialized) {
            console.log('⏳ Waiting for initialization...');
            return;
        }

        // Special handling for "my_quote" mode
        if (currentSort === 'my_quote') {
            await loadMyQuote();
            return;
        }

        isLoading = true;
        showLoader();

        if (reset) {
            currentPage = 1;
            hasMorePages = true;
            elements.postsFeed.innerHTML = '';
            posts.clear();
        }

        try {
            const url = `/api/voice?faculty=${currentFaculty}&sort=${currentSort}&page=${currentPage}&per_page=30`;
            console.log(`📖 Loading posts: ${url}`);

            const response = await fetch(url);
            const data = await response.json();

            if (!data.success) {
                console.error('❌ API error:', data.error);
                showError(data.error);
                hideLoader();
                isLoading = false;
                return;
            }

            console.log(`✅ Loaded ${data.posts.length} posts`);

            const fragment = document.createDocumentFragment();

            data.posts.forEach(post => {
                posts.set(post.id, post);
                const postElement = createPostCard(post);
                fragment.appendChild(postElement);
            });

            elements.postsFeed.appendChild(fragment);

            hasMorePages = data.pagination.has_next;
            currentPage++;

            if (data.posts.length === 0 && currentPage === 2) {
                elements.postsFeed.innerHTML = `
                    <div class="no-posts">
                        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                            <circle cx="12" cy="12" r="10"/>
                            <path d="M8 12h8M12 8v8"/>
                        </svg>
                        <h3>No posts yet in ${currentFaculty}</h3>
                        <p>Be the first to share your thoughts!</p>
                    </div>
                `;
            }

            hideLoader();

        } catch (error) {
            console.error('❌ Error loading posts:', error);
            showError('Failed to load posts. Please refresh.');
            hideLoader();
        } finally {
            isLoading = false;
        }
    }

    // ==================== MY QUOTE ====================

    async function loadMyQuote() {
        isLoading = true;
        showLoader();
        elements.postsFeed.innerHTML = '';

        try {
            const response = await fetch('/api/voice/me');
            const data = await response.json();

            if (!data.success) {
                hideLoader();
                isLoading = false;
                return;
            }

            if (!data.post) {
                elements.postsFeed.innerHTML = `
                    <div class="my-quote-empty">
                        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                            <path d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
                        </svg>
                        <h3>You haven't shared your voice yet</h3>
                        <p>Use the composer below to share your thoughts in ${userFaculty}</p>
                    </div>
                `;
            } else {
                // Show user's post
                const postElement = createPostCard({
                    id: data.post.id,
                    text: data.post.text,
                    likes_count: data.post.likes_count,
                    created_at: data.post.created_at,
                    user_liked: false,
                    faculty_group: data.post.faculty_group,
                    author: {
                        user_id: userId,
                        name: 'You',
                        surname: '',
                        photo_thumb_path: null,
                        photo_path: null,
                        faculty: userFaculty
                    }
                }, true);

                elements.postsFeed.appendChild(postElement);
            }

            hideLoader();

        } catch (error) {
            console.error('❌ Error loading my quote:', error);
            showError('Failed to load your quote.');
            hideLoader();
        } finally {
            isLoading = false;
        }
    }

    // ==================== POST CARD CREATION ====================

    function createPostCard(post, isMyPost = false) {
        const card = document.createElement('div');
        card.className = 'post-card';
        card.setAttribute('data-post-id', post.id);

        // Check if this is user's own post
        if (!isMyPost && userId && post.author.user_id === userId) {
            isMyPost = true;
        }

        // Avatar
        let photoHTML = '';
        if (post.author.photo_thumb_path) {
            photoHTML = `<img src="/uploads/${post.author.photo_thumb_path.split('/').pop()}" alt="${post.author.name}">`;
        } else if (post.author.photo_path) {
            photoHTML = `<img src="/uploads/${post.author.photo_path.split('/').pop()}" alt="${post.author.name}">`;
        } else {
            photoHTML = `
                <div class="avatar-placeholder">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                        <circle cx="12" cy="7" r="4"/>
                    </svg>
                </div>
            `;
        }

        const timeAgo = formatTimeAgo(new Date(post.created_at));

        // Faculty badge
        const facultyBadge = `<span class="faculty-badge ${post.faculty_group.toLowerCase()}">${post.faculty_group}</span>`;

        // Add Edit/Delete buttons for my post
        const actionsHTML = isMyPost ? `
            <div class="post-actions">
                <button class="action-btn edit-btn" data-post-id="${post.id}">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                    </svg>
                    Edit
                </button>
                <button class="action-btn delete-btn" data-post-id="${post.id}">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"/>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                    Delete
                </button>
            </div>
        ` : '';

        card.innerHTML = `
            <div class="post-avatar" data-user-id="${post.author.user_id}">
                ${photoHTML}
            </div>
            <div class="post-content">
                <div class="post-header">
                    <div class="post-author" data-user-id="${post.author.user_id}">
                        ${post.author.name} ${post.author.surname}
                    </div>
                    ${facultyBadge}
                </div>
                <div class="post-text">${escapeHtml(post.text)}</div>
                <div class="post-footer">
                    <button class="like-btn ${post.user_liked ? 'liked' : ''}" data-post-id="${post.id}">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="${post.user_liked ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="2">
                            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
                        </svg>
                        <span class="like-count">${post.likes_count}</span>
                    </button>
                    <span class="post-time">${timeAgo}</span>
                </div>
                ${actionsHTML}
            </div>
        `;

        // Add event listeners
        if (!isMyPost) {
            const avatar = card.querySelector('.post-avatar');
            const author = card.querySelector('.post-author');
            avatar.addEventListener('click', () => openProfile(post.author.user_id));
            author.addEventListener('click', () => openProfile(post.author.user_id));
        }

        const likeBtn = card.querySelector('.like-btn');
        likeBtn.addEventListener('click', () => toggleLike(post.id, likeBtn));

        // Add Edit/Delete listeners if present
        if (isMyPost) {
            const editBtn = card.querySelector('.edit-btn');
            const deleteBtn = card.querySelector('.delete-btn');

            editBtn.addEventListener('click', () => openEditModal(post));
            deleteBtn.addEventListener('click', () => deletePost(post.id));
        }

        return card;
    }

    // ==================== POST ACTIONS ====================

    async function submitPost() {
        const text = elements.postInput.value.trim();

        if (!text || text.length > 100) return;

        elements.sendBtn.disabled = true;
        elements.postInput.disabled = true;

        try {
            const response = await fetch('/api/voice', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    text: text,
                    faculty: userFaculty
                })
            });

            const data = await response.json();

            if (!data.success) {
                if (response.status === 429) {
                    showRateLimitWarning(data.error || 'Rate limit exceeded. You can only edit 5 times per hour.');
                } else {
                    showError(data.error || 'Failed to post');
                }
                elements.sendBtn.disabled = false;
                elements.postInput.disabled = false;
                return;
            }

            elements.postInput.value = '';
            updateCharCounter();

            // Refresh appropriate view
            if (currentSort === 'my_quote') {
                await loadMyQuote();
            } else {
                await loadPosts(true);
            }

        } catch (error) {
            console.error('❌ Error submitting post:', error);
            showError('Failed to post. Please try again.');
        } finally {
            elements.sendBtn.disabled = false;
            elements.postInput.disabled = false;
        }
    }

    async function saveEdit() {
        const text = elements.editInput.value.trim();

        if (!text || text.length > 100) return;

        elements.saveEditBtn.disabled = true;

        try {
            const response = await fetch('/api/voice', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    text: text,
                    faculty: userFaculty
                })
            });

            const data = await response.json();

            if (!data.success) {
                if (response.status === 429) {
                    showRateLimitWarning(data.error);
                } else {
                    showError(data.error || 'Failed to update');
                }
                elements.saveEditBtn.disabled = false;
                return;
            }

            closeEditModal();

            // Refresh view
            if (currentSort === 'my_quote') {
                await loadMyQuote();
            } else {
                await loadPosts(true);
            }

        } catch (error) {
            console.error('❌ Error updating post:', error);
            showError('Failed to update. Please try again.');
            elements.saveEditBtn.disabled = false;
        }
    }

    async function deletePost(postId) {
        if (!confirm('Are you sure you want to delete your quote? This cannot be undone.')) {
            return;
        }

        try {
            const response = await fetch('/api/voice/me', {
                method: 'DELETE',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ faculty: userFaculty })
            });

            const data = await response.json();

            if (!data.success) {
                showError(data.error || 'Failed to delete');
                return;
            }

            elements.postInput.placeholder = 'Share your thoughts...';

            if (currentSort === 'my_quote') {
                await loadMyQuote();
            } else {
                await loadPosts(true);
            }

        } catch (error) {
            console.error('❌ Error deleting post:', error);
            showError('Failed to delete. Please try again.');
        }
    }

    // ==================== LIKE FUNCTIONALITY ====================

    async function toggleLike(postId, btnElement) {
        const post = posts.get(postId);
        if (!post) return;

        const wasLiked = post.user_liked;
        post.user_liked = !wasLiked;
        post.likes_count += wasLiked ? -1 : 1;

        updateLikeButton(btnElement, post.user_liked, post.likes_count);

        try {
            const response = await fetch('/api/voice/like', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ post_id: postId })
            });

            const data = await response.json();

            if (!data.success) {
                // Revert on error
                post.user_liked = wasLiked;
                post.likes_count = wasLiked ? post.likes_count + 1 : post.likes_count - 1;
                updateLikeButton(btnElement, post.user_liked, post.likes_count);
                return;
            }

            // Update with server response
            post.likes_count = data.likes_count;
            post.user_liked = data.liked;
            updateLikeButton(btnElement, post.user_liked, post.likes_count);

        } catch (error) {
            console.error('❌ Error toggling like:', error);
            // Revert on error
            post.user_liked = wasLiked;
            post.likes_count = wasLiked ? post.likes_count + 1 : post.likes_count - 1;
            updateLikeButton(btnElement, post.user_liked, post.likes_count);
        }
    }

    function updateLikeButton(btnElement, liked, count) {
        const svg = btnElement.querySelector('svg');
        const countSpan = btnElement.querySelector('.like-count');

        if (liked) {
            btnElement.classList.add('liked');
            svg.setAttribute('fill', 'currentColor');
        } else {
            btnElement.classList.remove('liked');
            svg.setAttribute('fill', 'none');
        }

        countSpan.textContent = count;
    }

    // ==================== MODAL ====================

    function openEditModal(post) {
        elements.editModal.classList.add('active');
        elements.editInput.value = post.text;
        elements.editInput.dataset.postId = post.id;
        updateEditCharCounter();
        elements.editInput.focus();
        document.body.style.overflow = 'hidden';
    }

    function closeEditModal() {
        elements.editModal.classList.remove('active');
        elements.editInput.value = '';
        delete elements.editInput.dataset.postId;
        document.body.style.overflow = '';
    }

    // ==================== UI HELPERS ====================

    function updateCharCounter() {
        const length = elements.postInput.value.length;
        elements.charCounter.textContent = `${length}/100`;

        if (length > 100) {
            elements.charCounter.classList.add('warning');
            elements.sendBtn.disabled = true;
        } else {
            elements.charCounter.classList.remove('warning');
            elements.sendBtn.disabled = length === 0;
        }
    }

    function updateEditCharCounter() {
        const length = elements.editInput.value.length;
        elements.editCharCounter.textContent = `${length}/100`;

        if (length > 100) {
            elements.editCharCounter.classList.add('warning');
            elements.saveEditBtn.disabled = true;
        } else {
            elements.editCharCounter.classList.remove('warning');
            elements.saveEditBtn.disabled = length === 0;
        }
    }

    function autoResizeTextarea() {
        elements.postInput.style.height = 'auto';
        elements.postInput.style.height = elements.postInput.scrollHeight + 'px';
    }

    function showLoader() {
        elements.loadingIndicator.style.display = 'flex';
    }

    function hideLoader() {
        elements.loadingIndicator.style.display = 'none';
    }

    function showError(message) {
        alert(message);
    }

    function showRateLimitWarning(message) {
        if (elements.rateLimitWarning) {
            elements.rateLimitMessage.textContent = message;
            elements.rateLimitWarning.style.display = 'flex';

            setTimeout(() => {
                elements.rateLimitWarning.style.display = 'none';
            }, 5000);
        }
    }

    // ==================== UTILITIES ====================

    function openProfile(userId) {
        window.location.href = `/profile/${userId}`;
    }

    function formatTimeAgo(dateString) {
	    // Parse the ISO string correctly as UTC
	const postDate = new Date(dateString);
	const now = new Date();
	    
	    // Calculate difference in seconds
	const seconds = Math.floor((now - postDate) / 1000);

	    // Debugging (remove after testing)
	console.log('Post date:', postDate.toISOString());
	console.log('Current time:', now.toISOString());
	console.log('Seconds ago:', seconds);

	if (seconds < 0) return 'just now'; // Handle future dates
	if (seconds < 60) return 'just now';
	    
	const minutes = Math.floor(seconds / 60);
	if (minutes < 60) return `${minutes}m ago`;
	    
	const hours = Math.floor(minutes / 60);
	if (hours < 24) return `${hours}h ago`;
	    
	const days = Math.floor(hours / 24);
	if (days < 7) return `${days}d ago`;
	    
	    // For older posts, show the actual date
	return postDate.toLocaleDateString(); 
    }
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ==================== INFINITE SCROLL ====================

    function initInfiniteScroll() {
        const observer = new IntersectionObserver((entries) => {
            if (entries[0].isIntersecting && !isLoading && hasMorePages && currentSort !== 'my_quote') {
                loadPosts();
            }
        }, {
            rootMargin: '200px'
        });

        observer.observe(elements.loadingIndicator);
    }

    // ==================== EVENT LISTENERS ====================

    function initFacultyTabs() {
        const tabs = document.querySelectorAll('.faculty-tab');

        tabs.forEach(tab => {
            tab.addEventListener('click', function() {
                const newFaculty = this.getAttribute('data-faculty');
                if (newFaculty === currentFaculty) return;

                tabs.forEach(t => t.classList.remove('active'));
                this.classList.add('active');

                currentFaculty = newFaculty;
                updateComposerVisibility();

                if (currentSort !== 'my_quote') {
                    loadPosts(true);
                }
            });
        });
    }

    function initSortButtons() {
        const sortBtns = document.querySelectorAll('.sort-btn');

        sortBtns.forEach(btn => {
            btn.addEventListener('click', function() {
                const newSort = this.getAttribute('data-sort');
                if (newSort === currentSort) return;

                sortBtns.forEach(b => b.classList.remove('active'));
                this.classList.add('active');

                currentSort = newSort;
                updateComposerVisibility();
                loadPosts(true);
            });
        });
    }

    function initComposer() {
        elements.postInput.addEventListener('input', () => {
            updateCharCounter();
            autoResizeTextarea();
        });

        elements.sendBtn.addEventListener('click', submitPost);

        elements.postInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (elements.postInput.value.trim() && elements.postInput.value.length <= 100) {
                    submitPost();
                }
            }
        });

        elements.postInput.addEventListener('paste', () => {
            setTimeout(() => {
                updateCharCounter();
                autoResizeTextarea();
            }, 0);
        });
    }

    function initEditModal() {
        elements.modalOverlay.addEventListener('click', closeEditModal);
        elements.cancelEditBtn.addEventListener('click', closeEditModal);
        elements.saveEditBtn.addEventListener('click', saveEdit);
        elements.editInput.addEventListener('input', updateEditCharCounter);

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && elements.editModal.classList.contains('active')) {
                closeEditModal();
            }
        });

        elements.editInput.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                if (elements.editInput.value.trim() && elements.editInput.value.length <= 100) {
                    saveEdit();
                }
            }
        });
    }

    // ==================== INITIALIZATION ====================

    async function init() {
        console.log('🚀 Student Voice initializing...');

        cacheDOMElements();

        if (!elements.postsFeed || !elements.postInput) {
            console.error('❌ Required elements not found');
            return;
        }

        // Load user info FIRST (critical!)
        const success = await loadUserInfo();

        if (!success) {
            console.error('❌ Failed to load user info - stopping initialization');
            return;
        }

        // Mark as initialized
        isInitialized = true;
        console.log('✅ Initialization complete');

        // Initialize UI components
        initFacultyTabs();
        initSortButtons();
        initComposer();
        initEditModal();
        initInfiniteScroll();

        // Load initial posts (user's faculty automatically selected)
        console.log(`📖 Loading ${currentFaculty} posts...`);
        loadPosts();
    }

    // ==================== RUN ====================

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})();
