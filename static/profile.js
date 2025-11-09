// ===================================
// PROFILE REDESIGN - MODERN JAVASCRIPT (UPDATED VERSION)
// ===================================

(function() {
    'use strict';

    // Cache DOM elements for performance
    const elements = {};

    // State management
    const state = {
        currentFriendStatus: null,
        friendToRemove: null,
        isLoadingFriends: false,
        editingSection: null
    };

    // Configuration
    const config = {
        maxPhotoSize: 5 * 1024 * 1024, // 5MB
        maxAboutLength: 70,
        maxNameLength: 20,
        maxSurnameLength: 20,
        maxHobbiesLength: 30,
        maxSubjectsLength: 50,
        maxProfessorLength: 30,
        toastDuration: 3000,
        animationDuration: 300
    };

    // Initialize on DOM load
    document.addEventListener('DOMContentLoaded', init);

    function init() {
        console.log('Initializing profile page...');
        console.log('Profile User ID:', window.profileUserId);
        console.log('Is Own Profile:', window.isOwnProfile);
        console.log('CSRF Token:', window.csrfToken ? 'Present' : 'Missing');

        cacheElements();
        initializeEventListeners();
        loadInitialData();
        setupPhotoUpload();
    }

    // Cache DOM elements for better performance
    function cacheElements() {
        elements.friendBtn = document.getElementById('friendBtn');
        elements.friendsList = document.getElementById('friendsList');
        elements.friendsLoading = document.getElementById('friendsLoading');
        elements.friendsEmpty = document.getElementById('friendsEmpty');
        elements.friendsCount = document.querySelector('.friends-count');
        elements.editModal = document.getElementById('editModal');
        elements.modalTitle = document.getElementById('modalTitle');
        elements.modalFormContent = document.getElementById('modalFormContent');
        elements.editForm = document.getElementById('editForm');
        elements.unfriendModal = document.getElementById('unfriendModal');
        elements.unfriendText = document.getElementById('unfriendText');
        elements.confirmUnfriendBtn = document.getElementById('confirmUnfriendBtn');
        elements.toastContainer = document.getElementById('toastContainer');
        elements.photoUploadInput = document.getElementById('photoUploadInput');
        elements.editButtons = document.querySelectorAll('.edit-section-btn');

        console.log('Elements cached:', {
            friendBtn: !!elements.friendBtn,
            friendsList: !!elements.friendsList,
            editModal: !!elements.editModal
        });
    }

    // Initialize all event listeners
    function initializeEventListeners() {
        // Friend button
        if (elements.friendBtn && !window.isOwnProfile) {
            console.log('Adding friend button listener');
            elements.friendBtn.addEventListener('click', handleFriendAction);
        }

        // Edit buttons - Fixed selector
        document.querySelectorAll('.edit-section-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                const section = btn.dataset.section;
                console.log('Edit button clicked for section:', section);
                openEditModal(section);
            });
        });

        // Edit form submission
        if (elements.editForm) {
            elements.editForm.addEventListener('submit', handleEditSubmit);
        }

        // Modal close handlers
        document.querySelectorAll('.modal-overlay').forEach(overlay => {
            overlay.addEventListener('click', closeAllModals);
        });

        // Unfriend confirmation
        if (elements.confirmUnfriendBtn) {
            elements.confirmUnfriendBtn.addEventListener('click', confirmRemoveFriend);
        }

        // Escape key to close modals
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                closeAllModals();
            }
        });

        // Photo upload
        if (elements.photoUploadInput) {
            elements.photoUploadInput.addEventListener('change', handlePhotoUpload);
        }
    }

    // Load initial data
    async function loadInitialData() {
        console.log('Loading initial data...');

        // Load friend status if not own profile
        if (!window.isOwnProfile && elements.friendBtn) {
            await loadFriendStatus();
        }

        // Load friends list
        await loadFriends();
    }

    // ===================================
    // FRIEND SYSTEM
    // ===================================

    async function loadFriendStatus() {
        try {
            console.log('Loading friend status for user:', window.profileUserId);
            console.log('CSRF Token:', window.csrfToken);

            const response = await fetchWithRetry(`/api/friends/status/${window.profileUserId}`);
            console.log('Response status:', response.status);

            if (!response.ok) {
                const errorText = await response.text();
                console.error('Error response:', errorText);
                throw new Error(`HTTP ${response.status}: ${errorText}`);
            }

            const data = await response.json();
            console.log('Friend status data:', data);

            if (data.success) {
                state.currentFriendStatus = data.status;
                console.log('Setting friend status to:', data.status);
                updateFriendButton(data.status);
            } else {
                console.error('API returned error:', data.error);
                // Still try to update button with null status (will show "Add Friend")
                state.currentFriendStatus = null;
                updateFriendButton(null);
            }
        } catch (error) {
            console.error('Error loading friend status:', error);
            console.error('Error stack:', error.stack);

            // Still show the button in default state instead of hiding it
            state.currentFriendStatus = null;
            updateFriendButton(null);

            // Don't disable button, let user try to add friend anyway
            if (elements.friendBtn) {
                elements.friendBtn.disabled = false;
            }
        }
    }

    function updateFriendButton(status) {
        if (!elements.friendBtn) {
            console.error('Friend button element not found');
            return;
        }

        console.log('Updating button with status:', status);

        elements.friendBtn.classList.remove('pending', 'friends', 'loading');
        elements.friendBtn.disabled = false;

        const btnText = elements.friendBtn.querySelector('.btn-text');
        const btnIcon = elements.friendBtn.querySelector('.btn-icon');

        if (!btnText) {
            console.error('Button text element not found');
            return;
        }

        if (!btnIcon) {
            console.error('Button icon element not found');
            return;
        }

        switch (status) {
            case 'friends':
                btnText.textContent = 'Friends';
                btnIcon.textContent = '✓';
                elements.friendBtn.classList.add('friends');
                elements.friendBtn.disabled = true;
                console.log('Button set to FRIENDS state');
                break;
            case 'pending_sent':
                btnText.textContent = 'Request Sent';
                btnIcon.textContent = '⏳';
                elements.friendBtn.classList.add('pending');
                elements.friendBtn.disabled = true;
                console.log('Button set to PENDING SENT state');
                break;
            case 'pending_received':
                btnText.textContent = 'Accept Request';
                btnIcon.textContent = '✓';
                console.log('Button set to PENDING RECEIVED state');
                break;
            default:
                btnText.textContent = 'Add Friend';
                btnIcon.textContent = '';
                console.log('Button set to DEFAULT (Add Friend) state');
        }

        console.log('Button updated successfully to status:', status);
    }

    async function handleFriendAction() {
        if (elements.friendBtn.disabled) {
            console.log('Button is disabled, ignoring click');
            return;
        }

        console.log('Handling friend action, current status:', state.currentFriendStatus);

        elements.friendBtn.disabled = true;
        elements.friendBtn.classList.add('loading');

        try {
            let response;
            let endpoint;
            let method;
            let body = null;

            if (!state.currentFriendStatus) {
                // Send friend request
                endpoint = '/api/friends/request';
                method = 'POST';
                body = JSON.stringify({ to_user_id: window.profileUserId });
                console.log('Sending friend request to:', endpoint);
            } else if (state.currentFriendStatus === 'pending_received') {
                // Accept friend request
                endpoint = `/api/friends/accept/${window.profileUserId}`;
                method = 'POST';
                console.log('Accepting friend request at:', endpoint);
            }

            response = await fetchWithRetry(endpoint, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.csrfToken
                },
                body: body
            });

            console.log('Friend action response status:', response.status);

            if (!response.ok) {
                const errorText = await response.text();
                console.error('Friend action error response:', errorText);
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            console.log('Friend action result:', data);

            if (data.success) {
                if (!state.currentFriendStatus) {
                    state.currentFriendStatus = 'pending_sent';
                    showToast('Friend request sent!', 'success');
                } else {
                    state.currentFriendStatus = 'friends';
                    showToast('Friend request accepted!', 'success');
                    await loadFriends(); // Reload friends list
                }
                updateFriendButton(state.currentFriendStatus);
            } else {
                showToast(data.error || 'Action failed', 'error');
            }
        } catch (error) {
            console.error('Error handling friend action:', error);
            console.error('Error stack:', error.stack);
            showToast('Something went wrong. Please try again.', 'error');
        } finally {
            elements.friendBtn.disabled = false;
            elements.friendBtn.classList.remove('loading');
        }
    }

    async function loadFriends() {
        if (state.isLoadingFriends) return;

        state.isLoadingFriends = true;
        showFriendsLoading();

        try {
            console.log('Loading friends for user:', window.profileUserId);
            const response = await fetchWithRetry(`/api/friends?page=1&per_page=20&user_id=${window.profileUserId}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }

            const data = await response.json();
            console.log('Friends loaded:', data);

            if (data.success && data.friends.length > 0) {
                renderFriends(data.friends);
                updateFriendsCount(data.pagination.total);
            } else {
                showFriendsEmpty();
            }
        } catch (error) {
            console.error('Error loading friends:', error);
            showFriendsEmpty();
        } finally {
            state.isLoadingFriends = false;
        }
    }

    function renderFriends(friends) {
        elements.friendsList.innerHTML = '';
        elements.friendsLoading.style.display = 'none';
        elements.friendsEmpty.style.display = 'none';

        friends.forEach((friend, index) => {
            const friendElement = createFriendElement(friend);
            friendElement.style.animationDelay = `${index * 50}ms`;
            elements.friendsList.appendChild(friendElement);
        });
    }

    function createFriendElement(friend) {
        const div = document.createElement('div');
        div.className = 'friend-item';
        div.style.animation = 'slideUp 0.5s ease backwards';

        const link = document.createElement('a');
        link.href = `/profile/${friend.user_id}`;
        link.style.textDecoration = 'none';
        link.style.display = 'contents';

        // Avatar
        const avatarDiv = document.createElement('div');
        avatarDiv.className = 'friend-avatar';

        if (friend.photo_path || friend.photo_thumb_path) {
            const img = document.createElement('img');
            img.src = friend.photo_thumb_path || friend.photo_path;
            img.alt = friend.name;
            avatarDiv.appendChild(img);
        } else {
            const placeholder = document.createElement('div');
            placeholder.className = 'friend-avatar-placeholder';
            placeholder.innerHTML = `
                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <circle cx="12" cy="8" r="4"/>
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
                </svg>
            `;
            avatarDiv.appendChild(placeholder);
        }

        // Name
        const nameDiv = document.createElement('div');
        nameDiv.className = 'friend-name';
        nameDiv.textContent = friend.name;

        link.appendChild(avatarDiv);
        link.appendChild(nameDiv);
        div.appendChild(link);

        // Remove button for own profile
        if (window.isOwnProfile) {
            const removeBtn = document.createElement('button');
            removeBtn.className = 'remove-friend-btn';
            removeBtn.innerHTML = '✕';
            removeBtn.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                showUnfriendModal(friend.user_id, friend.name);
            };
            div.appendChild(removeBtn);
        }

        return div;
    }

    function showFriendsLoading() {
        elements.friendsList.innerHTML = '';
        elements.friendsLoading.style.display = 'flex';
        elements.friendsEmpty.style.display = 'none';
    }

    function showFriendsEmpty() {
        elements.friendsList.innerHTML = '';
        elements.friendsLoading.style.display = 'none';
        elements.friendsEmpty.style.display = 'block';
        updateFriendsCount(0);
    }

    function updateFriendsCount(count) {
        if (elements.friendsCount) {
            elements.friendsCount.textContent = `(${count})`;
        }
    }

    // ===================================
    // UNFRIEND MODAL
    // ===================================

    function showUnfriendModal(userId, name) {
        state.friendToRemove = userId;
        elements.unfriendText.textContent = `Are you sure you want to remove ${name} from your friends?`;
        elements.unfriendModal.classList.add('active');
        document.body.style.overflow = 'hidden';
    }

    async function confirmRemoveFriend() {
        if (!state.friendToRemove) return;

        elements.confirmUnfriendBtn.disabled = true;
        elements.confirmUnfriendBtn.textContent = 'Removing...';

        try {
            const response = await fetchWithRetry(`/api/friends/${state.friendToRemove}`, {
                method: 'DELETE',
                headers: {
                    'X-CSRFToken': window.csrfToken
                }
            });

            const data = await response.json();

            if (data.success) {
                showToast('Friend removed', 'success');
                closeUnfriendModal();
                await loadFriends();
            } else {
                showToast(data.error || 'Failed to remove friend', 'error');
            }
        } catch (error) {
            console.error('Error removing friend:', error);
            showToast('Something went wrong', 'error');
        } finally {
            elements.confirmUnfriendBtn.disabled = false;
            elements.confirmUnfriendBtn.textContent = 'Remove';
        }
    }

    // ===================================
    // EDIT MODAL
    // ===================================

    function openEditModal(section) {
        console.log('Opening edit modal for section:', section);
        state.editingSection = section;
        const sectionConfig = getSectionConfig(section);

        if (!sectionConfig) {
            console.error('No config found for section:', section);
            return;
        }

        elements.modalTitle.textContent = `Edit ${sectionConfig.title}`;
        elements.modalFormContent.innerHTML = generateFormFields(sectionConfig);
        elements.editModal.classList.add('active');
        document.body.style.overflow = 'hidden';

        // Setup form validation
        setupFormValidation();
    }

    function getSectionConfig(section) {
        const configs = {
            personal: {
                title: 'Personal Information',
                endpoint: '/api/profile/personal',
                fields: [
                    { name: 'name', label: 'Name', type: 'text', maxLength: config.maxNameLength, placeholder: 'Your first name' },
                    { name: 'surname', label: 'Surname', type: 'text', maxLength: config.maxSurnameLength, placeholder: 'Your last name' },
                    { name: 'relationship', label: 'Relationship Status', type: 'select', options: getRelationshipOptions() },
                    { name: 'hobbies', label: 'Interested in', type: 'textarea', maxLength: config.maxHobbiesLength, placeholder: 'e.g., Reading, Sports, Music' }
                ]
            },
            about: {
                title: 'About Me',
                endpoint: '/api/profile/about',
                fields: [
                    { name: 'about_me', label: 'About Me', type: 'textarea', maxLength: config.maxAboutLength, placeholder: 'Write something about yourself...' }
                ]
            },
            academic: {
                title: 'Academic Information',
                endpoint: '/api/profile/academic',
                fields: [
                    { name: 'faculty', label: 'Faculty', type: 'select', options: getFacultyOptions() },
                    { name: 'level', label: 'Level', type: 'select', options: getLevelOptions() },
                    { name: 'favorite_subjects', label: 'Favorite Subject', type: 'text', maxLength: config.maxSubjectsLength, placeholder: 'e.g., Math, Physics, Programming' },
                    { name: 'professor', label: 'Favorite Professor', type: 'text', maxLength: config.maxProfessorLength, placeholder: 'Professor name' }
                ]
            },
            contact: {
                title: 'Contact Information',
                endpoint: '/api/profile/contact',
                fields: [
                    { name: 'telegram', label: 'Telegram Username', type: 'text', placeholder: '@username', pattern: '@?[a-zA-Z0-9_]+' }
                ]
            }
        };

        return configs[section] || configs.personal;
    }

    function generateFormFields(config) {
        return config.fields.map(field => {
            const value = getCurrentFieldValue(field.name);

            if (field.type === 'select') {
                return `
                    <div class="form-group">
                        <label for="${field.name}">${field.label}</label>
                        <select id="${field.name}" name="${field.name}" required>
                            ${field.options.map(opt => 
                                `<option value="${opt.value}" ${value === opt.value ? 'selected' : ''}>${opt.label}</option>`
                            ).join('')}
                        </select>
                    </div>
                `;
            } else if (field.type === 'textarea') {
                return `
                    <div class="form-group">
                        <label for="${field.name}">${field.label}</label>
                        <textarea id="${field.name}" name="${field.name}" 
                                  maxlength="${field.maxLength}" 
                                  rows="3"
                                  placeholder="${field.placeholder || ''}">${value}</textarea>
                        <small><span class="char-count">0</span>/${field.maxLength} characters</small>
                    </div>
                `;
            } else {
                return `
                    <div class="form-group">
                        <label for="${field.name}">${field.label}</label>
                        <input type="${field.type}" 
                               id="${field.name}" 
                               name="${field.name}" 
                               value="${value}" 
                               ${field.placeholder ? `placeholder="${field.placeholder}"` : ''}
                               ${field.pattern ? `pattern="${field.pattern}"` : ''}
                               ${field.maxLength ? `maxlength="${field.maxLength}"` : ''}>
                        ${field.maxLength ? `<small><span class="char-count-${field.name}">0</span>/${field.maxLength} characters</small>` : ''}
                    </div>
                `;
            }
        }).join('');
    }

    function getRelationshipOptions() {
        const options = window.studentGender === 'female' ? [
            { value: 'Taken (happily in love 💕)', label: 'Taken (happily in love 💕)' },
            { value: 'Secretly crushing', label: 'Secretly crushing' },
            { value: 'Single (Independent queen 👑)', label: 'Single (Independent queen 👑)' },
            { value: "It's complicated", label: "It's complicated" }
        ] : [
            { value: 'In a relationship', label: 'In a relationship' },
            { value: 'Crushing on someone', label: 'Crushing on someone' },
            { value: 'Single (Lone wolf 🐺)', label: 'Single (Lone wolf 🐺)' },
            { value: "It's complicated", label: "It's complicated" }
        ];
        return options;
    }

    function getFacultyOptions() {
        return [
            { value: 'SBL_B', label: 'SBL-B' },
            { value: 'SBL_L', label: 'SBL-L' },
            { value: 'ICE', label: 'SOCIE-ICE' },
            { value: 'CSE', label: 'SOCIE-CSE' }
        ];
    }

    function getLevelOptions() {
        return [
            { value: 'Freshman', label: 'Freshman' },
            { value: 'Sophomore', label: 'Sophomore' },
            { value: 'Junior', label: 'Junior' },
            { value: 'Senior', label: 'Senior' }
        ];
    }

    function getCurrentFieldValue(fieldName) {
        // Extract current values from the page using data-field attributes
        const fieldMappings = {
            'birthday': '[data-field="birthday"]',
            'relationship': '[data-field="relationship"]',
            'hobbies': '[data-field="hobbies"]',
            'about_me': '[data-field="about_me"]',
            'name': '[data-field="name"]',
            'surname': '[data-field="surname"]',
            'faculty': '[data-field="faculty"]',
            'level': '[data-field="level"]',
            'favorite_subjects': '[data-field="favorite_subjects"]',
            'professor': '[data-field="professor"]',
            'telegram': '[data-field="telegram"]'
        };

        const selector = fieldMappings[fieldName];
        if (selector) {
            const element = document.querySelector(selector);
            if (element) {
                const text = element.textContent.trim();
                return text === 'Not specified' ? '' : text;
            }
        }

        return '';
    }

    function setupFormValidation() {
        // Character counter for textareas
        const textareas = elements.modalFormContent.querySelectorAll('textarea');
        textareas.forEach(textarea => {
            const counter = textarea.parentElement.querySelector('.char-count');
            if (counter) {
                const updateCounter = () => {
                    counter.textContent = textarea.value.length;
                };
                textarea.addEventListener('input', updateCounter);
                updateCounter();
            }
        });

        // Character counter for text inputs with maxlength
        const textInputs = elements.modalFormContent.querySelectorAll('input[type="text"][maxlength]');
        textInputs.forEach(input => {
            const fieldName = input.getAttribute('name');
            const counter = input.parentElement.querySelector(`.char-count-${fieldName}`);
            if (counter) {
                const updateCounter = () => {
                    counter.textContent = input.value.length;
                };
                input.addEventListener('input', updateCounter);
                updateCounter();
            }
        });

        // Name and surname validation (no spaces allowed)
        const nameInput = elements.modalFormContent.querySelector('input[name="name"]');
        const surnameInput = elements.modalFormContent.querySelector('input[name="surname"]');

        if (nameInput) {
            nameInput.addEventListener('input', (e) => {
                // Remove spaces and limit to maxLength
                e.target.value = e.target.value.replace(/\s/g, '');
                if (e.target.value.length > config.maxNameLength) {
                    e.target.value = e.target.value.substring(0, config.maxNameLength);
                }
            });
        }

        if (surnameInput) {
            surnameInput.addEventListener('input', (e) => {
                // Remove spaces and limit to maxLength
                e.target.value = e.target.value.replace(/\s/g, '');
                if (e.target.value.length > config.maxSurnameLength) {
                    e.target.value = e.target.value.substring(0, config.maxSurnameLength);
                }
            });
        }

        // Enforce strict maxlength on all textareas
        textareas.forEach(textarea => {
            textarea.addEventListener('input', (e) => {
                const maxLength = parseInt(e.target.getAttribute('maxlength'));
                if (e.target.value.length > maxLength) {
                    e.target.value = e.target.value.substring(0, maxLength);
                }
            });
        });

        // Enforce strict maxlength on all text inputs
        textInputs.forEach(input => {
            input.addEventListener('input', (e) => {
                const maxLength = parseInt(e.target.getAttribute('maxlength'));
                if (maxLength && e.target.value.length > maxLength) {
                    e.target.value = e.target.value.substring(0, maxLength);
                }
            });
        });
    }

    async function handleEditSubmit(e) {
        e.preventDefault();

        const formData = new FormData(e.target);
        const data = Object.fromEntries(formData);
        const config = getSectionConfig(state.editingSection);

        // Validate name and surname (no spaces)
        if (data.name && data.name.includes(' ')) {
            showToast('Name cannot contain spaces', 'error');
            return;
        }
        if (data.surname && data.surname.includes(' ')) {
            showToast('Surname cannot contain spaces', 'error');
            return;
        }

        const submitBtn = e.target.querySelector('.btn-primary');
        submitBtn.disabled = true;
        submitBtn.textContent = 'Saving...';

        try {
            const response = await fetchWithRetry(config.endpoint, {
                method: 'PATCH',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.csrfToken
                },
                body: JSON.stringify(data)
            });

            const result = await response.json();

            if (result.success) {
                showToast('Changes saved successfully!', 'success');
                closeEditModal();
                setTimeout(() => window.location.reload(), 1000);
            } else {
                showToast(result.error || 'Failed to save changes', 'error');
            }
        } catch (error) {
            console.error('Error saving changes:', error);
            showToast('Something went wrong', 'error');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Save Changes';
        }
    }

    // ===================================
    // PHOTO UPLOAD
    // ===================================

    function setupPhotoUpload() {
        if (!elements.photoUploadInput) return;

        // Drag and drop support (optional enhancement)
        const photoWrapper = document.querySelector('.profile-image-wrapper');
        if (photoWrapper && window.isOwnProfile) {
            photoWrapper.addEventListener('dragover', (e) => {
                e.preventDefault();
                photoWrapper.classList.add('drag-over');
            });

            photoWrapper.addEventListener('dragleave', () => {
                photoWrapper.classList.remove('drag-over');
            });

            photoWrapper.addEventListener('drop', (e) => {
                e.preventDefault();
                photoWrapper.classList.remove('drag-over');
                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    handlePhotoFile(files[0]);
                }
            });
        }
    }

    async function handlePhotoUpload(e) {
        const file = e.target.files[0];
        if (file) {
            await handlePhotoFile(file);
        }
    }

    async function handlePhotoFile(file) {
        // Validate file
        if (!file.type.match('image.*')) {
            showToast('Please select an image file', 'error');
            return;
        }

        if (file.size > config.maxPhotoSize) {
            showToast('File too large (max 5MB)', 'error');
            return;
        }

        const formData = new FormData();
        formData.append('photo', file);

        showToast('Uploading photo...', 'info');

        try {
            const response = await fetchWithRetry('/api/profile/photo', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': window.csrfToken
                },
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                showToast('Photo uploaded successfully!', 'success');
                setTimeout(() => window.location.reload(), 1000);
            } else {
                showToast(result.error || 'Upload failed', 'error');
            }
        } catch (error) {
            console.error('Error uploading photo:', error);
            showToast('Upload failed', 'error');
        }
    }

    // ===================================
    // UTILITIES
    // ===================================

    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        // Add icon based on type
        const icons = {
            success: '✅',
            error: '❌',
            info: 'ℹ️'
        };

        toast.innerHTML = `<span>${icons[type]}</span> ${message}`;
        elements.toastContainer.appendChild(toast);

        // Auto remove after duration
        setTimeout(() => {
            toast.style.animation = 'toastSlide 0.3s ease reverse';
            setTimeout(() => toast.remove(), 300);
        }, config.toastDuration);
    }

    async function fetchWithRetry(url, options = {}, retries = 3) {
        console.log('Fetching:', url, 'Options:', options);

        for (let i = 0; i < retries; i++) {
            try {
                const response = await fetch(url, options);
                console.log('Fetch response:', response.status, response.statusText);

                if (!response.ok && i < retries - 1) {
                    console.log(`Attempt ${i + 1} failed, retrying...`);
                    await new Promise(resolve => setTimeout(resolve, 1000 * Math.pow(2, i)));
                    continue;
                }
                return response;
            } catch (error) {
                console.error(`Fetch attempt ${i + 1} error:`, error);
                if (i === retries - 1) throw error;
                await new Promise(resolve => setTimeout(resolve, 1000 * Math.pow(2, i)));
            }
        }
    }

    function closeEditModal() {
        elements.editModal.classList.remove('active');
        document.body.style.overflow = '';
        state.editingSection = null;
    }

    function closeUnfriendModal() {
        elements.unfriendModal.classList.remove('active');
        document.body.style.overflow = '';
        state.friendToRemove = null;
    }

    function closeAllModals() {
        closeEditModal();
        closeUnfriendModal();
    }

    // Expose some functions globally for inline handlers
    window.closeEditModal = closeEditModal;
    window.closeUnfriendModal = closeUnfriendModal;

})();