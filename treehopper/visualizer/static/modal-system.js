/**
 * Modal System - Replaces alert(), prompt(), and confirm()
 * Provides theme-aware modals for errors, success, inputs, and confirmations
 */

/* ========================================
   MODAL HTML TEMPLATES
   ======================================== */

// Initialize modals on page load
function initModalSystem() {
    const modalHTML = `
        <!-- Error Modal -->
        <div id="errorModal" class="system-modal">
            <div class="system-modal-content error-modal-content">
                <div class="modal-icon error-icon">⚠️</div>
                <h2 class="modal-title">Error</h2>
                <p class="modal-message" id="errorModalMessage"></p>
                <div class="modal-actions">
                    <button class="modal-btn error-btn" onclick="closeErrorModal()">OK</button>
                </div>
            </div>
        </div>

        <!-- Success Modal -->
        <div id="successModal" class="system-modal">
            <div class="system-modal-content success-modal-content">
                <div class="modal-icon success-icon">✓</div>
                <h2 class="modal-title">Success</h2>
                <p class="modal-message" id="successModalMessage"></p>
                <div class="modal-actions">
                    <button class="modal-btn success-btn" onclick="closeSuccessModal()">OK</button>
                </div>
            </div>
        </div>

        <!-- Confirm Modal -->
        <div id="confirmModal" class="system-modal">
            <div class="system-modal-content confirm-modal-content">
                <div class="modal-icon confirm-icon">❓</div>
                <h2 class="modal-title">Confirm</h2>
                <p class="modal-message" id="confirmModalMessage"></p>
                <div class="modal-actions">
                    <button class="modal-btn cancel-btn" onclick="resolveConfirm(false)">Cancel</button>
                    <button class="modal-btn confirm-btn" onclick="resolveConfirm(true)">Confirm</button>
                </div>
            </div>
        </div>

        <!-- Input Modal -->
        <div id="inputModal" class="system-modal">
            <div class="system-modal-content input-modal-content">
                <h2 class="modal-title" id="inputModalTitle">Input Required</h2>
                <p class="modal-subtitle" id="inputModalSubtitle"></p>
                <form id="inputModalForm">
                    <div id="inputModalFields"></div>
                    <div class="modal-actions">
                        <button type="button" class="modal-btn cancel-btn" onclick="resolveInput(null)">Cancel</button>
                        <button type="submit" class="modal-btn confirm-btn">Submit</button>
                    </div>
                </form>
            </div>
        </div>
    `;

    // Append to body if not already present
    if (!document.getElementById('errorModal')) {
        document.body.insertAdjacentHTML('beforeend', modalHTML);
    }
}

/* ========================================
   ERROR MODAL
   ======================================== */

function showError(message, title = 'Error') {
    const modal = document.getElementById('errorModal');
    const messageEl = document.getElementById('errorModalMessage');
    const titleEl = modal.querySelector('.modal-title');

    titleEl.textContent = title;
    messageEl.textContent = message;
    modal.style.display = 'flex';
}

function closeErrorModal() {
    document.getElementById('errorModal').style.display = 'none';
}

window.showError = showError;
window.closeErrorModal = closeErrorModal;

/* ========================================
   SUCCESS MODAL
   ======================================== */

function showSuccess(message, title = 'Success') {
    const modal = document.getElementById('successModal');
    const messageEl = document.getElementById('successModalMessage');
    const titleEl = modal.querySelector('.modal-title');

    titleEl.textContent = title;
    messageEl.textContent = message;
    modal.style.display = 'flex';

    // Auto-close after 3 seconds for success messages
    setTimeout(() => {
        closeSuccessModal();
    }, 3000);
}

function closeSuccessModal() {
    document.getElementById('successModal').style.display = 'none';
}

window.showSuccess = showSuccess;
window.closeSuccessModal = closeSuccessModal;

/* ========================================
   CONFIRM MODAL
   ======================================== */

let confirmResolve = null;

function showConfirm(message, title = 'Confirm') {
    return new Promise((resolve) => {
        const modal = document.getElementById('confirmModal');
        const messageEl = document.getElementById('confirmModalMessage');
        const titleEl = modal.querySelector('.modal-title');

        titleEl.textContent = title;
        messageEl.textContent = message;
        modal.style.display = 'flex';

        confirmResolve = resolve;
    });
}

function resolveConfirm(value) {
    document.getElementById('confirmModal').style.display = 'none';
    if (confirmResolve) {
        confirmResolve(value);
        confirmResolve = null;
    }
}

window.showConfirm = showConfirm;
window.resolveConfirm = resolveConfirm;

/* ========================================
   INPUT MODAL
   ======================================== */

let inputResolve = null;

/**
 * Show input modal with one or more input fields
 * @param {Object} config - Configuration object
 * @param {string} config.title - Modal title
 * @param {string} config.subtitle - Modal subtitle (optional)
 * @param {Array} config.fields - Array of field objects
 * @param {string} config.fields[].name - Field name/id
 * @param {string} config.fields[].label - Field label
 * @param {string} config.fields[].type - Input type (text, password, select)
 * @param {string} config.fields[].placeholder - Placeholder text
 * @param {string} config.fields[].defaultValue - Default value
 * @param {Array} config.fields[].options - Options for select fields
 * @param {boolean} config.fields[].required - Whether field is required
 */
function showInput(config) {
    return new Promise((resolve) => {
        const modal = document.getElementById('inputModal');
        const titleEl = document.getElementById('inputModalTitle');
        const subtitleEl = document.getElementById('inputModalSubtitle');
        const fieldsContainer = document.getElementById('inputModalFields');
        const form = document.getElementById('inputModalForm');

        titleEl.textContent = config.title || 'Input Required';
        subtitleEl.textContent = config.subtitle || '';
        subtitleEl.style.display = config.subtitle ? 'block' : 'none';

        // Build form fields
        fieldsContainer.innerHTML = config.fields.map(field => {
            if (field.type === 'select') {
                return `
                    <div class="form-group">
                        <label class="form-label">${field.label}</label>
                        <select id="${field.name}" class="form-input" ${field.required ? 'required' : ''}>
                            ${field.options.map(opt => `
                                <option value="${opt.value}" ${opt.value === field.defaultValue ? 'selected' : ''}>
                                    ${opt.label}
                                </option>
                            `).join('')}
                        </select>
                    </div>
                `;
            } else {
                return `
                    <div class="form-group">
                        <label class="form-label">${field.label}</label>
                        <input
                            type="${field.type || 'text'}"
                            id="${field.name}"
                            class="form-input"
                            placeholder="${field.placeholder || ''}"
                            value="${field.defaultValue || ''}"
                            ${field.required ? 'required' : ''}
                        >
                    </div>
                `;
            }
        }).join('');

        modal.style.display = 'flex';

        // Focus first input
        setTimeout(() => {
            const firstInput = fieldsContainer.querySelector('input, select');
            if (firstInput) firstInput.focus();
        }, 100);

        inputResolve = resolve;

        // Handle form submission
        form.onsubmit = (e) => {
            e.preventDefault();
            const result = {};
            config.fields.forEach(field => {
                const element = document.getElementById(field.name);
                result[field.name] = element.value;
            });
            resolveInput(result);
        };
    });
}

function resolveInput(value) {
    document.getElementById('inputModal').style.display = 'none';
    if (inputResolve) {
        inputResolve(value);
        inputResolve = null;
    }
}

window.showInput = showInput;
window.resolveInput = resolveInput;

/* ========================================
   INITIALIZE ON LOAD
   ======================================== */

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initModalSystem);
} else {
    initModalSystem();
}
