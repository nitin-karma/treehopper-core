/**
 * Toast Notification System
 * Professional replacement for alert()
 */

// Toast container management
let toastContainer = null;

/**
 * Initialize toast container (called once)
 */
function initToastContainer() {
    if (toastContainer) return;

    toastContainer = document.createElement('div');
    toastContainer.className = 'toast-container';
    document.body.appendChild(toastContainer);
}

/**
 * Show toast notification
 * @param {string} message - Message to display
 * @param {string} type - Type: 'success', 'error', 'warning', 'info'
 * @param {number} duration - Duration in ms (default: 5000)
 * @param {string} title - Optional title
 */
function showToast(message, type = 'info', duration = 5000, title = null) {
    // Initialize container if needed
    initToastContainer();

    // Create toast element
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    // Get icon based on type
    const icons = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };

    // Get default title based on type
    const defaultTitles = {
        success: 'Success',
        error: 'Error',
        warning: 'Warning',
        info: 'Info'
    };

    const toastTitle = title || defaultTitles[type];
    const toastIcon = icons[type] || 'ℹ️';

    // Build toast HTML
    toast.innerHTML = `
        <div class="toast-icon">${toastIcon}</div>
        <div class="toast-content">
            <div class="toast-title">${toastTitle}</div>
            <div class="toast-message">${message}</div>
        </div>
        <button class="toast-close" onclick="closeToast(this.parentElement)">×</button>
        ${duration > 0 ? '<div class="toast-progress"></div>' : ''}
    `;

    // Add to container
    toastContainer.appendChild(toast);

    // Trigger animation
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);

    // Auto-remove after duration (if duration > 0)
    if (duration > 0) {
        setTimeout(() => {
            closeToast(toast);
        }, duration);
    }

    return toast;
}

/**
 * Close toast notification
 */
function closeToast(toast) {
    if (!toast) return;

    toast.classList.remove('show');
    toast.classList.add('hide');

    setTimeout(() => {
        if (toast.parentElement) {
            toast.parentElement.removeChild(toast);
        }
    }, 300);
}

/**
 * Convenience methods for different toast types
 */
const Toast = {
    success: (message, title = null, duration = 5000) => {
        return showToast(message, 'success', duration, title);
    },

    error: (message, title = null, duration = 7000) => {
        return showToast(message, 'error', duration, title);
    },

    warning: (message, title = null, duration = 6000) => {
        return showToast(message, 'warning', duration, title);
    },

    info: (message, title = null, duration = 5000) => {
        return showToast(message, 'info', duration, title);
    },

    // Special case: persistent toast (doesn't auto-close)
    persistent: (message, type = 'info', title = null) => {
        return showToast(message, type, 0, title);
    }
};

// Export for use in other scripts
window.showToast = showToast;
window.closeToast = closeToast;
window.Toast = Toast;

// Debug: Log that Toast is loaded
console.log('[Toast] System loaded successfully');
