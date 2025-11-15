// Home Page with Server-Side Pagination and Filtering
(function() {
    'use strict';

    let currentFaculty = 'all';
    let currentLevel = 'all';
    let currentPage = 1;
    let isLoading = false;
    let hasMorePages = true;
    let searchQuery = '';
    let searchTimeout = null;
    let isSearchMode = false;

    // Search students
    async function searchStudents(query) {
        if (isLoading) return;

        isLoading = true;
        isSearchMode = true;
        showLoader();

        try {
            const url = `/api/search?q=${encodeURIComponent(query)}`;
            console.log('Searching:', url);

            const response = await fetch(url);
            const data = await response.json();

            console.log('Search results:', data);

            if (!data.success) {
                console.error('Search error:', data.error);
                hideLoader();
                isLoading = false;
                return;
            }

            // Clear current students
            const studentsList = document.getElementById('studentsGrid');
            studentsList.innerHTML = '';

            if (data.students.length === 0) {
                studentsList.innerHTML = '<div class="search-info">No students found for "' + escapeHtml(query) + '"</div>';
            } else {
                // Track added IDs to prevent duplicates
                const addedIds = new Set();
                
                data.students.forEach(student => {
                    if (!addedIds.has(student.user_id)) {
                        const card = createStudentCard(student);
                        studentsList.appendChild(card);
                        addedIds.add(student.user_id);
                    }
                });

                // Show result count
                const info = document.createElement('div');
                info.className = 'search-info';
                info.textContent = `Found ${data.total} student${data.total !== 1 ? 's' : ''}`;
                studentsList.insertBefore(info, studentsList.firstChild);
            }

            // Disable pagination during search
            hasMorePages = false;

            hideLoader();

        } catch (error) {
            console.error('Search error:', error);
            hideLoader();
        } finally {
            isLoading = false;
        }
    }

    // Escape HTML helper
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Handle search input with debouncing
    function handleSearchInput(value) {
        searchQuery = value.trim();

        // Show/hide clear button
        const clearBtn = document.getElementById('clearSearch');
        if (searchQuery) {
            clearBtn.style.display = 'flex';
        } else {
            clearBtn.style.display = 'none';
        }

        // Clear previous timeout
        if (searchTimeout) {
            clearTimeout(searchTimeout);
        }

        // If empty, reset to normal view
        if (!searchQuery) {
            resetToNormalView();
            return;
        }

        // If less than 2 characters, don't search
        if (searchQuery.length < 2) {
            return;
        }

        // Debounce: wait 300ms after last keystroke
        searchTimeout = setTimeout(() => {
            searchStudents(searchQuery);
        }, 300);
    }

    // Reset to normal view (with filters)
    function resetToNormalView() {
        searchQuery = '';
        isSearchMode = false;

        // Clear search input
        const searchInput = document.getElementById('searchInput');
        if (searchInput) {
            searchInput.value = '';
        }

        // Hide clear button
        const clearBtn = document.getElementById('clearSearch');
        if (clearBtn) {
            clearBtn.style.display = 'none';
        }

        // Clear students list
        const studentsList = document.getElementById('studentsGrid');
        studentsList.innerHTML = '';

        // Reset pagination
        currentPage = 1;
        hasMorePages = true;

        // Load first page with current filters
        loadMoreStudents();
    }

    // Load students from server
    async function loadMoreStudents() {
        // Don't load if searching or already loading
        if (isLoading || !hasMorePages || isSearchMode) return;

        isLoading = true;
        showLoader();

        try {
            const url = `/api/students?page=${currentPage}&faculty=${currentFaculty}&level=${currentLevel}`;
            console.log('Loading:', url);

            const response = await fetch(url);
            const data = await response.json();

            console.log('Response:', data);

            if (!data.success) {
                console.error('API error:', data.error);
                hideLoader();
                isLoading = false;
                return;
            }

            const studentsList = document.getElementById('studentsGrid');

            // Collect existing user_ids to prevent duplicates
            const existingUserIds = new Set();
            studentsList.querySelectorAll('.student-card-link').forEach(link => {
                const href = link.getAttribute('href');
                const match = href.match(/\/profile\/(\d+)/);
                if (match) {
                    existingUserIds.add(parseInt(match[1]));
                }
            });

            // Add only new cards
            let addedCount = 0;
            data.students.forEach(student => {
                if (!existingUserIds.has(student.user_id)) {
                    const card = createStudentCard(student);
                    studentsList.appendChild(card);
                    existingUserIds.add(student.user_id);
                    addedCount++;
                } else {
                    console.log('Skipping duplicate:', student.user_id, student.name);
                }
            });

            console.log(`Added ${addedCount} new students out of ${data.students.length}`);

            hasMorePages = data.pagination.has_next;
            currentPage++;

            console.log('Loaded page', currentPage - 1, 'Has more:', hasMorePages);

            hideLoader();

        } catch (error) {
            console.error('Error loading students:', error);
            hideLoader();
        } finally {
            isLoading = false;
        }
    }

    // Helper function to create detail value spans
    function createDetailValues(text) {
        if (!text) return '';
        return text.split(',').map(item =>
            `<span class="detail-value">${escapeHtml(item.trim())}</span>`
        ).join('');
    }

    // Create student card HTML
    function createStudentCard(student) {
        const link = document.createElement('a');
        link.href = `/profile/${student.user_id}`;
        link.className = 'student-card-link';

        const card = document.createElement('div');
        card.className = 'student-card';
        card.setAttribute('data-faculty', student.faculty);
        card.setAttribute('data-level', student.level);
        card.setAttribute('data-student-gender', (student.sex || 'male').toLowerCase());
        card.setAttribute('data-user-id', student.user_id); // Add data attribute

        let photoHTML = '';
        if (student.photo_thumb_path) {
            const photoFile = student.photo_thumb_path.split('/').pop();
            photoHTML = `<img src="/uploads/${photoFile}" alt="${escapeHtml(student.name)}" loading="lazy">`;
        } else if (student.photo_path) {
            const photoFile = student.photo_path.split('/').pop();
            photoHTML = `<img src="/uploads/${photoFile}" alt="${escapeHtml(student.name)}" loading="lazy">`;
        } else {
            photoHTML = `
                <div class="photo-placeholder">
                    <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
                        <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                        <circle cx="12" cy="7" r="4"/>
                    </svg>
                </div>
            `;
        }

        const hobbiesHTML = student.hobbies ? 
            `<p class="student-detail hobbies-detail"><strong>Hobbies:</strong> ${createDetailValues(student.hobbies)}</p>` : '';
        
        const subjectsHTML = student.favorite_subjects ? 
            `<p class="student-detail subjects-detail"><strong>Favourite Subjects:</strong> ${createDetailValues(student.favorite_subjects)}</p>` : '';


	card.innerHTML = `
	    <div class="student-photo">
	        ${photoHTML}
	    </div>
	    <div class="student-info">
	        <div class="student-header">
	            <div class="student-main-info">
	                <h3 class="student-name">${student.name} ${student.surname}</h3>
	                <p class="student-faculty">${student.faculty}, ${student.level}</p>
	            </div>
	            <button class="add-friend-btn" data-user-id="${student.user_id}" onclick="event.preventDefault(); event.stopPropagation();">Add Friend</button>
	        </div>
	        ${student.hobbies ? `<p class="student-detail hobbies-detail"><strong>Hobbies:</strong> ${student.hobbies.split(',').map(h => `<span class="detail-value">${h.trim()}</span>`).join('')}</p>` : ''}
	        ${student.favorite_subjects ? `<p class="student-detail subjects-detail"><strong>Favourite Subjects:</strong> ${student.favorite_subjects.split(',').map(s => `<span class="detail-value">${s.trim()}</span>`).join('')}</p>` : ''}
	        <p class="student-detail relationship-detail"><strong>Relationship Status:</strong> <span class="detail-value">${student.relationship}</span></p>
	    </div>
	`;
        link.appendChild(card);
        return link;
    }

    function showLoader() {
        let loader = document.getElementById('loadingIndicator');
        if (!loader) {
            loader = document.createElement('div');
            loader.id = 'loadingIndicator';
            loader.className = 'loading-indicator';
            loader.innerHTML = '<div class="spinner"></div><p>Loading...</p>';
            const container = document.querySelector('.students-list');
            if (container) {
                container.after(loader);
            }
        }
        loader.style.display = 'flex';
    }

    function hideLoader() {
        const loader = document.getElementById('loadingIndicator');
        if (loader) {
            loader.style.display = 'none';
        }
    }

    // Faculty filter
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            // Update active state
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');

            // Get faculty value
            currentFaculty = this.dataset.faculty;

            // Reset search mode
            isSearchMode = false;
            searchQuery = '';
            
            // Clear search input
            const searchInput = document.getElementById('searchInput');
            if (searchInput) {
                searchInput.value = '';
            }
            const clearBtn = document.getElementById('clearSearch');
            if (clearBtn) {
                clearBtn.style.display = 'none';
            }

            // Reset and reload
            const studentsList = document.getElementById('studentsGrid');
            studentsList.innerHTML = '';
            currentPage = 1;
            hasMorePages = true;
            loadMoreStudents();
        });
    });

    // Level filter
    const levelFilter = document.getElementById('levelFilter');
    if (levelFilter) {
        levelFilter.addEventListener('change', function() {
            currentLevel = this.value;

            // Reset search mode
            isSearchMode = false;
            searchQuery = '';
            
            // Clear search input
            const searchInput = document.getElementById('searchInput');
            if (searchInput) {
                searchInput.value = '';
            }
            const clearBtn = document.getElementById('clearSearch');
            if (clearBtn) {
                clearBtn.style.display = 'none';
            }

            // Reset and reload
            const studentsList = document.getElementById('studentsGrid');
            studentsList.innerHTML = '';
            currentPage = 1;
            hasMorePages = true;
            loadMoreStudents();
        });
    }

    // Search input
    const searchInput = document.getElementById('searchInput');
    const clearBtn = document.getElementById('clearSearch');

    if (searchInput) {
        searchInput.addEventListener('input', function() {
            handleSearchInput(this.value);
        });
    }

    if (clearBtn) {
        clearBtn.addEventListener('click', function() {
            if (searchInput) {
                searchInput.value = '';
            }
            this.style.display = 'none';
            resetToNormalView();
        });
    }

    // Mobile search expansion
    const searchBox = document.querySelector('.search-box');
    const searchIcon = document.querySelector('.search-icon');

    if (searchBox && searchIcon && window.innerWidth <= 768) {
        searchIcon.addEventListener('click', function(e) {
            if (!searchBox.classList.contains('expanded')) {
                e.stopPropagation();
                searchBox.classList.add('expanded');
                if (searchInput) {
                    searchInput.focus();
                }
            }
        });

        document.addEventListener('click', function(e) {
            if (!searchBox.contains(e.target) && searchBox.classList.contains('expanded')) {
                if (!searchInput || !searchInput.value) {
                    searchBox.classList.remove('expanded');
                }
            }
        });
    }

    // Infinite scroll
    window.addEventListener('scroll', () => {
        if (isSearchMode) return;

        const scrollPosition = window.innerHeight + window.scrollY;
        const threshold = document.documentElement.scrollHeight - 300;

        if (scrollPosition >= threshold && !isLoading && hasMorePages) {
            loadMoreStudents();
        }
    });

    // Initial load - only if grid is empty and not in search mode
    const studentsGrid = document.getElementById('studentsGrid');
    if (studentsGrid && studentsGrid.children.length === 0 && !isSearchMode) {
        loadMoreStudents();
    }

})();

// ============================================
// FRIEND SYSTEM - Batch Status Updates
// ============================================

(function() {
    'use strict';

    // Cache friend statuses
    const friendStatusCache = new Map();
    let isUpdatingStatuses = false;

    // Get CSRF token
    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }

    // Debounce helper
    function debounce(func, wait) {
        let timeout;
        return function(...args) {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), wait);
        };
    }

    // Update friend statuses for visible students (BATCH)
    async function updateFriendStatuses() {
        if (isUpdatingStatuses) return;

        const buttons = document.querySelectorAll('.add-friend-btn');
        if (buttons.length === 0) return;

        // Collect user IDs that aren't cached
        const userIds = [];
        buttons.forEach(btn => {
            const userId = parseInt(btn.dataset.userId);
            if (userId && !friendStatusCache.has(userId)) {
                userIds.push(userId);
            }
        });

        if (userIds.length === 0) {
            // All cached, just update buttons
            updateAllButtons();
            return;
        }

        isUpdatingStatuses = true;

        try {
            const response = await fetch('/api/friends/status/batch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({ user_ids: userIds })
            });

            const data = await response.json();

            if (data.success) {
                // Cache the statuses
                Object.entries(data.statuses).forEach(([userId, status]) => {
                    friendStatusCache.set(parseInt(userId), status);
                });

                // Update all buttons
                updateAllButtons();
            }

        } catch (error) {
            console.error('Error updating friend statuses:', error);
        } finally {
            isUpdatingStatuses = false;
        }
    }

    // Update all buttons based on cache
    function updateAllButtons() {
        const buttons = document.querySelectorAll('.add-friend-btn');

        buttons.forEach(btn => {
            const userId = parseInt(btn.dataset.userId);
            const status = friendStatusCache.get(userId);

            updateButtonState(btn, status);
        });
    }

    // Update single button state
    function updateButtonState(btn, status) {
        // Remove all state classes
        btn.classList.remove('pending', 'received', 'friends');
        btn.disabled = false;

        if (!status) {
            // No relationship - can send request
            btn.textContent = 'Add Friend';
            btn.classList.remove('pending', 'received', 'friends');
        } else if (status === 'friends') {
            // Already friends
            btn.textContent = 'Friends';
            btn.classList.add('friends');
            btn.disabled = true;
        } else if (status.status === 'pending_sent' || status === 'pending_sent') {
            // Request sent, waiting
            btn.textContent = 'Request Sent';
            btn.classList.add('pending');
            btn.disabled = true;
        } else if (status.status === 'pending_received' || status === 'pending_received') {
            // Received request from this user
            btn.textContent = 'Accept Request';
            btn.classList.add('received');
            btn.dataset.requestId = status.request_id || status;
        }
    }

    // Handle button click
    async function handleFriendButtonClick(event) {
        event.preventDefault();
        event.stopPropagation();

        const btn = event.currentTarget;
        const userId = parseInt(btn.dataset.userId);
        const status = friendStatusCache.get(userId);

        if (btn.disabled) return;

        // Disable button during request
        btn.disabled = true;
        const originalText = btn.textContent;

        try {
            if (!status || status === null) {
                // Send friend request
                const response = await fetch('/api/friends/request', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    },
                    body: JSON.stringify({ to_user_id: userId })
                });

                const data = await response.json();

                if (data.success) {
                    // Update cache and button
                    friendStatusCache.set(userId, 'pending_sent');
                    updateButtonState(btn, 'pending_sent');
                } else if (data.has_incoming) {
                    // They already sent you a request!
                    friendStatusCache.set(userId, {status: 'pending_received'});
                    updateButtonState(btn, {status: 'pending_received'});
                } else {
                    alert(data.error || 'Failed to send request');
                    btn.disabled = false;
                    btn.textContent = originalText;
                }

            } else if (status.status === 'pending_received' || status === 'pending_received') {
                // Accept friend request
                const requestId = btn.dataset.requestId || (status.request_id || status);

                const response = await fetch(`/api/friends/accept/${requestId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken()
                    }
                });

                const data = await response.json();

                if (data.success) {
                    // Update cache and button
                    friendStatusCache.set(userId, 'friends');
                    updateButtonState(btn, 'friends');
                } else {
                    alert(data.error || 'Failed to accept request');
                    btn.disabled = false;
                    btn.textContent = originalText;
                }
            }

        } catch (error) {
            console.error('Error handling friend action:', error);
            alert('Something went wrong. Please try again.');
            btn.disabled = false;
            btn.textContent = originalText;
        }
    }

    // Initialize friend system
    function initFriendSystem() {
        // Add click handlers to all friend buttons
        const buttons = document.querySelectorAll('.add-friend-btn');
        buttons.forEach(btn => {
            if (!btn.dataset.initialized) {
                btn.dataset.initialized = 'true';
                btn.addEventListener('click', handleFriendButtonClick);
            }
        });

        // Initial status update
        updateFriendStatuses();

        // Update statuses when new students are loaded (for infinite scroll)
        const observer = new MutationObserver(debounce(() => {
            const newButtons = document.querySelectorAll('.add-friend-btn:not([data-initialized])');
            newButtons.forEach(btn => {
                btn.dataset.initialized = 'true';
                btn.addEventListener('click', handleFriendButtonClick);
            });
            updateFriendStatuses();
        }, 300));

        const studentsGrid = document.getElementById('studentsGrid');
        if (studentsGrid) {
            observer.observe(studentsGrid, { childList: true, subtree: true });
        }
    }

    // Run on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initFriendSystem);
    } else {
        initFriendSystem();
    }

})();
