/**
 * Unified Theme System - TreehopperAI
 * Synchronizes theme across all pages: dashboard, login, error
 * Store in: theme-manager.js
 */

/* ========================================
   THEME CONSTANTS
   ======================================== */

   const THEME_STORAGE_KEY = 'treehopper-theme'; // Unified key
   const THEME_DARK = 'dark';
   const THEME_LIGHT = 'light';

   /* ========================================
      CORE THEME FUNCTIONS
      ======================================== */

   /**
    * Get current theme from localStorage
    * @returns {string} 'dark' or 'light'
    */
   function getTheme() {
       return localStorage.getItem(THEME_STORAGE_KEY) || THEME_DARK;
   }

   /**
    * Set theme in localStorage and apply to current page
    * @param {string} theme - 'dark' or 'light'
    */
   function setTheme(theme) {
       localStorage.setItem(THEME_STORAGE_KEY, theme);
       applyTheme(theme);

       // Broadcast theme change to other tabs
       broadcastThemeChange(theme);
   }

   /**
    * Apply theme to current page
    * @param {string} theme - 'dark' or 'light'
    */
   function applyTheme(theme) {
       if (theme === THEME_LIGHT) {
           document.body.classList.add('light-mode');
       } else {
           document.body.classList.remove('light-mode');
       }

       // Update theme toggle icon if present
       updateThemeIcon(theme);
   }

   /**
    * Toggle between dark and light theme
    */
   function toggleTheme() {
       const currentTheme = getTheme();
       const newTheme = currentTheme === THEME_DARK ? THEME_LIGHT : THEME_DARK;
       setTheme(newTheme);
   }

   /**
    * Update theme toggle icon
    * @param {string} theme - 'dark' or 'light'
    */
   function updateThemeIcon(theme) {
       // Dashboard theme icon
       const dashboardIcon = document.getElementById('themeToggleIcon');
       if (dashboardIcon) {
           dashboardIcon.textContent = theme === THEME_LIGHT ? '🌙' : '☀️';
       }

       // Login page theme icon
       const loginIcon = document.getElementById('themeIcon');
       if (loginIcon) {
           loginIcon.textContent = theme === THEME_LIGHT ? '🌙' : '☀️';
       }
   }

   /**
    * Initialize theme on page load
    */
   function initTheme() {
       const theme = getTheme();
       applyTheme(theme);

       // Listen for theme changes from other tabs
       listenForThemeChanges();
   }

   /* ========================================
      CROSS-TAB SYNCHRONIZATION
      ======================================== */

   /**
    * Broadcast theme change to other tabs/windows
    * @param {string} theme - 'dark' or 'light'
    */
   function broadcastThemeChange(theme) {
       // Use localStorage event to sync across tabs
       localStorage.setItem('theme-timestamp', Date.now().toString());
   }

   /**
    * Listen for theme changes from other tabs
    */
   function listenForThemeChanges() {
       window.addEventListener('storage', (e) => {
           if (e.key === THEME_STORAGE_KEY) {
               const newTheme = e.newValue || THEME_DARK;
               applyTheme(newTheme);
               console.log('Theme synced from another tab:', newTheme);
           }
       });
   }

   /* ========================================
      INITIALIZATION
      ======================================== */

   // Auto-initialize when DOM is ready
   if (document.readyState === 'loading') {
       document.addEventListener('DOMContentLoaded', initTheme);
   } else {
       initTheme();
   }

   // Make functions globally available
   window.getTheme = getTheme;
   window.setTheme = setTheme;
   window.toggleTheme = toggleTheme;
   window.applyTheme = applyTheme;
   window.initTheme = initTheme;
