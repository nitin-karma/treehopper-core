// auth-login.js - Login page authentication logic

const DASHBOARD_HEADER = "TreehopperDash";
let currentUsername = '';
let userNeedsPasswordChange = false;

/* ========================================
   THEME MANAGEMENT
   ======================================== */

function toggleTheme() {
    const isLight = document.body.classList.toggle('light-mode');
    document.getElementById('themeIcon').textContent = isLight ? '🌙' : '☀️';
    localStorage.setItem('loginTheme', isLight ? 'light' : 'dark');
}

function loadTheme() {
    if (localStorage.getItem('loginTheme') === 'light') {
        document.body.classList.add('light-mode');
        document.getElementById('themeIcon').textContent = '🌙';
    }
}

// Load theme on page load
loadTheme();

/* ========================================
   PASSWORD VISIBILITY TOGGLE
   ======================================== */

function togglePasswordVisibility(inputId, iconId) {
    const input = document.getElementById(inputId);
    const icon = document.getElementById(iconId);

    if (input.type === 'password') {
        input.type = 'text';
        icon.textContent = '🙈';
    } else {
        input.type = 'password';
        icon.textContent = '👁️';
    }
}

// Make globally available
window.togglePasswordVisibility = togglePasswordVisibility;

/* ========================================
   PASSWORD VALIDATION
   ======================================== */

function validatePassword(password) {
    const requirements = {
        minLength: password.length >= 8,
        hasUppercase: /[A-Z]/.test(password),
        hasLowercase: /[a-z]/.test(password),
        hasNumber: /[0-9]/.test(password),
        hasSpecial: /[@$!%*?&]/.test(password)
    };

    const errors = [];
    if (!requirements.minLength) errors.push('Password must be at least 8 characters long');
    if (!requirements.hasUppercase) errors.push('Password must contain at least one uppercase letter');
    if (!requirements.hasLowercase) errors.push('Password must contain at least one lowercase letter');
    if (!requirements.hasNumber) errors.push('Password must contain at least one number');
    if (!requirements.hasSpecial) errors.push('Password must contain at least one special character (@$!%*?&)');

    return {
        valid: Object.values(requirements).every(Boolean),
        errors
    };
}

/* ========================================
   LOGIN FORM
   ======================================== */

const loginForm = document.getElementById('loginForm');
const errorMessage = document.getElementById('errorMessage');
const successMessage = document.getElementById('successMessage');
const loginButton = document.getElementById('loginButton');
const buttonContent = document.getElementById('buttonContent');

loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;

    // UI State: Loading
    errorMessage.classList.remove('show');
    successMessage.classList.remove('show');
    loginButton.disabled = true;
    buttonContent.innerHTML = '<span class="spinner"></span>Authenticating...';

    try {
        const response = await fetch('/api/v1/users/login', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'x-requested-with': DASHBOARD_HEADER
            },
            body: JSON.stringify({ username, password })
        });

        if (response.ok) {
            const data = await response.json();

            // Check if user needs to change password
            if (data.needs_password_change) {
                currentUsername = username;
                userNeedsPasswordChange = true;
                buttonContent.innerHTML = 'Sign In';
                loginButton.disabled = false;
                showPasswordChangeModal();
                return;
            }

            // Store JWT and user info
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('user_role', data.role);
            localStorage.setItem('username', username);

            buttonContent.innerHTML = '✓ Success!';

            // Redirect to dashboard
            setTimeout(() => {
                window.location.href = '/home';
            }, 600);

        } else {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Login failed');
        }
    } catch (err) {
        errorMessage.textContent = err.message;
        errorMessage.classList.add('show');
        loginButton.disabled = false;
        buttonContent.innerHTML = 'Sign In';
    }
});

// Clear error when typing
['username', 'password'].forEach(id => {
    document.getElementById(id).addEventListener('input', () => {
        errorMessage.classList.remove('show');
        successMessage.classList.remove('show');
    });
});

/* ========================================
   FIRST-TIME PASSWORD CHANGE MODAL
   ======================================== */

function showPasswordChangeModal() {
    document.getElementById('changePasswordModal').style.display = 'block';
}

function closePasswordModal() {
    if (!userNeedsPasswordChange) {
        document.getElementById('changePasswordModal').style.display = 'none';
    } else {
        alert('You must change your password before continuing.');
    }
}

const changePasswordForm = document.getElementById('changePasswordForm');
const passwordError = document.getElementById('passwordError');
const changePasswordButton = document.getElementById('changePasswordButton');
const changePasswordContent = document.getElementById('changePasswordContent');

changePasswordForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;

    // Clear previous errors
    passwordError.classList.remove('show');

    // Validate passwords match
    if (newPassword !== confirmPassword) {
        passwordError.textContent = 'Passwords do not match';
        passwordError.classList.add('show');
        return;
    }

    // Validate password requirements
    const validation = validatePassword(newPassword);
    if (!validation.valid) {
        passwordError.textContent = validation.errors.join('. ');
        passwordError.classList.add('show');
        return;
    }

    // UI State: Loading
    changePasswordButton.disabled = true;
    changePasswordContent.innerHTML = '<span class="spinner"></span>Updating...';

    try {
        const response = await fetch('/api/v1/users/change-password', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'x-requested-with': DASHBOARD_HEADER
            },
            body: JSON.stringify({
                username: currentUsername,
                new_password: newPassword
            })
        });

        if (response.ok) {
            const data = await response.json();

            // Store JWT and user info
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('user_role', data.role);
            localStorage.setItem('username', currentUsername);

            changePasswordContent.innerHTML = '✓ Password Updated!';

            // Redirect to dashboard
            setTimeout(() => {
                window.location.href = '/home';
            }, 1000);

        } else {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to update password');
        }
    } catch (err) {
        passwordError.textContent = err.message;
        passwordError.classList.add('show');
        changePasswordButton.disabled = false;
        changePasswordContent.innerHTML = 'Update Password';
    }
});

/* ========================================
   FORGOT PASSWORD MODAL
   ======================================== */

let forgotPasswordStep = 1; // 1: Enter username, 2: Enter new password

function showForgotPasswordModal() {
    forgotPasswordStep = 1;
    document.getElementById('forgotPasswordModal').style.display = 'block';
    document.getElementById('newPasswordGroup').style.display = 'none';
    document.getElementById('confirmPasswordGroup').style.display = 'none';
    document.getElementById('resetPasswordReqs').style.display = 'none';
    document.getElementById('forgotPasswordButton').querySelector('.button-content').textContent = 'Continue';
    document.getElementById('resetUsername').value = '';
    document.getElementById('forgotPasswordError').classList.remove('show');
    document.getElementById('forgotPasswordSuccess').classList.remove('show');
}

function closeForgotPasswordModal() {
    document.getElementById('forgotPasswordModal').style.display = 'none';
    forgotPasswordStep = 1;
}

const forgotPasswordForm = document.getElementById('forgotPasswordForm');
const forgotPasswordError = document.getElementById('forgotPasswordError');
const forgotPasswordSuccess = document.getElementById('forgotPasswordSuccess');
const forgotPasswordButton = document.getElementById('forgotPasswordButton');
const forgotPasswordContent = document.getElementById('forgotPasswordContent');

forgotPasswordForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    forgotPasswordError.classList.remove('show');
    forgotPasswordSuccess.classList.remove('show');

    if (forgotPasswordStep === 1) {
        // Step 1: Validate username
        const username = document.getElementById('resetUsername').value;

        forgotPasswordButton.disabled = true;
        forgotPasswordContent.innerHTML = '<span class="spinner"></span>Validating...';

        try {
            const response = await fetch('/api/v1/users/validate-reset', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-requested-with': DASHBOARD_HEADER
                },
                body: JSON.stringify({ username })
            });

            if (response.ok) {
                const data = await response.json();

                // User validated, show password fields
                forgotPasswordStep = 2;
                document.getElementById('newPasswordGroup').style.display = 'block';
                document.getElementById('confirmPasswordGroup').style.display = 'block';
                document.getElementById('resetPasswordReqs').style.display = 'block';
                forgotPasswordContent.textContent = 'Reset Password';
                forgotPasswordButton.disabled = false;

                forgotPasswordSuccess.textContent = 'Username validated. Please enter your new password.';
                forgotPasswordSuccess.classList.add('show');

            } else {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'User validation failed');
            }
        } catch (err) {
            forgotPasswordError.textContent = err.message;
            forgotPasswordError.classList.add('show');
            forgotPasswordButton.disabled = false;
            forgotPasswordContent.textContent = 'Continue';
        }

    } else {
        // Step 2: Reset password
        const username = document.getElementById('resetUsername').value;
        const newPassword = document.getElementById('resetNewPassword').value;
        const confirmPassword = document.getElementById('resetConfirmPassword').value;

        // Validate passwords match
        if (newPassword !== confirmPassword) {
            forgotPasswordError.textContent = 'Passwords do not match';
            forgotPasswordError.classList.add('show');
            return;
        }

        // Validate password requirements
        const validation = validatePassword(newPassword);
        if (!validation.valid) {
            forgotPasswordError.textContent = validation.errors.join('. ');
            forgotPasswordError.classList.add('show');
            return;
        }

        forgotPasswordButton.disabled = true;
        forgotPasswordContent.innerHTML = '<span class="spinner"></span>Resetting...';

        try {
            const response = await fetch('/api/v1/users/reset-password', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'x-requested-with': DASHBOARD_HEADER
                },
                body: JSON.stringify({
                    username,
                    new_password: newPassword
                })
            });

            if (response.ok) {
                forgotPasswordSuccess.textContent = '✓ Password reset successfully! Redirecting to login...';
                forgotPasswordSuccess.classList.add('show');
                forgotPasswordContent.textContent = 'Success!';

                setTimeout(() => {
                    closeForgotPasswordModal();
                    successMessage.textContent = 'Password reset successfully. Please login with your new password.';
                    successMessage.classList.add('show');
                }, 2000);

            } else {
                const errorData = await response.json();
                throw new Error(errorData.detail || 'Failed to reset password');
            }
        } catch (err) {
            forgotPasswordError.textContent = err.message;
            forgotPasswordError.classList.add('show');
            forgotPasswordButton.disabled = false;
            forgotPasswordContent.textContent = 'Reset Password';
        }
    }
});
