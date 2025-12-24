/**
 * TreehopperAI Dashboard - Complete Script
 * Includes: Core functionality, Analytics, Chain Flow Visualization, JWT Auth
 */

/* ========================================
   AUTHENTICATION & SESSION MANAGEMENT
   ======================================== */

   const DASHBOARD_HEADER = "TreehopperDash";

   // Check if user is authenticated
   function checkAuth() {
       const token = localStorage.getItem('access_token');
       const role = localStorage.getItem('user_role');

       if (!token) {
           // Not authenticated, redirect to login
           window.location.href = '/';
           return false;
       }

       // Show/hide admin tab based on role
       if (role === 'admin') {
           const usersTab = document.getElementById('usersTab');
           if (usersTab) {
               usersTab.style.display = 'flex';
           }
       }

       return true;
   }

   // Get auth headers for API calls
   function getAuthHeaders() {
       return {
           'Content-Type': 'application/json',
           'x-requested-with': DASHBOARD_HEADER,
           'Authorization': `Bearer ${localStorage.getItem('access_token')}`
       };
   }

   // Logout function
   async function logout() {
       const confirmed = await showConfirm('Are you sure you want to logout?', 'Logout');
       if (confirmed) {
           localStorage.removeItem('access_token');
           localStorage.removeItem('user_role');
           localStorage.removeItem('username');
           localStorage.removeItem('activeTab');
           window.location.href = '/';
       }
   }

   // Make logout available globally
   window.logout = logout;

   // User Management Variables
   let allUsers = [];

   /* ========================================
      TAB NAVIGATION (Define first for inline onclick)
      ======================================== */

   function switchTab(tabName) {
       // Show loading overlay
       showLoader();

       // Hide all tab contents
       document.querySelectorAll('.tab-content').forEach(tab => {
           tab.classList.remove('active');
       });

       // Remove active class from all tab buttons
       document.querySelectorAll('.tab-btn').forEach(btn => {
           btn.classList.remove('active');
       });

       // Show selected tab content
       const selectedTab = document.getElementById(`tab-${tabName}`);
       if (selectedTab) {
           selectedTab.classList.add('active');
       }

       // Add active class to clicked button
       const selectedBtn = document.querySelector(`[data-tab="${tabName}"]`);
       if (selectedBtn) {
           selectedBtn.classList.add('active');
       }

       // If switching to analytics, reload charts to ensure proper rendering
       if (tabName === 'analytics') {
           setTimeout(() => {
               if (typeof loadAnalytics === 'function') {
                   loadAnalytics().finally(() => {
                       setTimeout(hideLoader, 300);
                   });
               } else {
                   setTimeout(hideLoader, 300);
               }
           }, 200); // Increased delay to ensure DOM is fully visible
       } else {
           // Hide loader after tab switch
           setTimeout(hideLoader, 300);
       }

       // Save active tab to localStorage
       localStorage.setItem('activeTab', tabName);
   }

   // Load saved tab on page load
   function loadSavedTab() {
       const savedTab = localStorage.getItem('activeTab') || 'overview';
       switchTab(savedTab);
   }

   // Make functions globally available for inline onclick handlers
   window.switchTab = switchTab;
   window.loadSavedTab = loadSavedTab;

   /* ========================================
      GLOBAL VARIABLES
      ======================================== */

   // Core variables
   let updateInterval;
   let allLogs = [];
   let runWs;
   let wsEvents;
   let currentPage = 1;
   const logsPerPage = 50;
   const maxPages = 10;

   let activeFilters = {
       agentsList: "",
       chainsList: "",
       pidsList: "",
       inputFilesList: ""
   };

   // Graphviz variables
   let graphvizInstance = null;
   let currentZoom = null;

   // Analytics variables
   let charts = {};
   let currentTimeWindow = '24h';

   // Color schemes for analytics
   const COLORS = {
       dark: {
           // Vibrant varied colors for pie charts and bar charts
           primary: [
               '#10b981',  // Green
               '#3b82f6',  // Blue
               '#f59e0b',  // Orange
               '#ef4444',  // Red
               '#a78bfa',  // Purple
               '#ec4899',  // Pink
               '#14b8a6',  // Teal
               '#f97316',  // Orange-Red
               '#8b5cf6',  // Violet
               '#06b6d4',  // Cyan
               '#84cc16',  // Lime
               '#eab308'   // Yellow
           ],
           success: '#10b981',
           error: '#ef4444',
           warning: '#f59e0b',
           info: '#3b82f6',
           purple: '#a78bfa',
           pink: '#ec4899',
           teal: '#14b8a6',
           cyan: '#06b6d4',
           gridColor: 'rgba(148, 163, 184, 0.1)',
           textColor: '#e2e8f0',
           subTextColor: '#94a3b8'
       },
       light: {
           // Vibrant varied colors for light mode
           primary: [
               '#059669',  // Green
               '#2563eb',  // Blue
               '#d97706',  // Orange
               '#dc2626',  // Red
               '#7c3aed',  // Purple
               '#db2777',  // Pink
               '#0d9488',  // Teal
               '#ea580c',  // Orange-Red
               '#7c3aed',  // Violet
               '#0891b2',  // Cyan
               '#65a30d',  // Lime
               '#ca8a04'   // Yellow
           ],
           success: '#059669',
           error: '#dc2626',
           warning: '#d97706',
           info: '#2563eb',
           purple: '#7c3aed',
           pink: '#db2777',
           teal: '#0d9488',
           cyan: '#0891b2',
           gridColor: 'rgba(148, 163, 184, 0.2)',
           textColor: '#1e293b',
           subTextColor: '#64748b'
       }
   };

   function getColorScheme() {
       return document.body.classList.contains('light-mode') ? COLORS.light : COLORS.dark;
   }

   /* ========================================
      API HELPER
      ======================================== */

   async function apiFetch(url, options = {}) {
       const defaultOptions = {
           headers: getAuthHeaders()
       };

       const mergedOptions = {
           ...defaultOptions,
           ...options,
           headers: {
               ...defaultOptions.headers,
               ...(options.headers || {})
           }
       };

       const response = await fetch(url, mergedOptions);

       // Handle 401 - Unauthorized (token expired or invalid)
       if (response.status === 401) {
           showError('Session expired. Please login again.', 'Authentication Error');
           setTimeout(() => logout(), 2000);
           return;
       }

       if (!response.ok) {
           throw new Error(`API Error: ${response.status}`);
       }

       return response.json();
   }

   /* ========================================
      UI HELPERS
      ======================================== */

   function toggleMenu() {
       document.getElementById('dropdownMenu').classList.toggle('active');
   }

   document.addEventListener('click', (e) => {
       const menu = document.getElementById('dropdownMenu');
       const burger = document.querySelector('.hamburger-btn');
       if (menu && !menu.contains(e.target) && !burger.contains(e.target)) {
           menu.classList.remove('active');
       }
   });

   function openModal(id) {
       document.getElementById(id).style.display = "block";
       document.getElementById('dropdownMenu').classList.remove('active');
   }

   function closeModal(modalId) {
       const modal = document.getElementById(modalId);
       if (modal) {
         modal.style.display = "none";

         // Clean up graphviz instance if closing chain flow modal
         if (modalId === 'chainFlowModal') {
           document.getElementById("chainFlowBody").innerHTML = '';
           graphvizInstance = null;
           currentZoom = null;
         }
       }
   }

   window.onclick = (e) => {
       if (e.target.classList.contains('modal')) e.target.style.display = "none";
   }

   /* ========================================
      THEME MANAGEMENT
      ======================================== */

   // Theme management is now handled by theme-manager.js
   // This provides unified theme sync across all pages (dashboard, login, error)

   function toggleTheme() {
       // Get the global theme manager functions
       const themeManager = {
           getTheme: window.getTheme,
           setTheme: window.setTheme,
           applyTheme: window.applyTheme
       };

       // Toggle theme using theme manager
       if (themeManager.getTheme && themeManager.setTheme) {
           const currentTheme = themeManager.getTheme();
           const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
           themeManager.setTheme(newTheme);

           // Reload analytics charts with new color scheme
           setTimeout(() => {
               if (typeof loadAnalytics === 'function') {
                   loadAnalytics();
               }
           }, 100);
       }
   }

   function loadTheme() {
       // Theme auto-initializes from theme-manager.js
       // No action needed here
   }

   /* ========================================
      TIMESTAMP FORMATTING
      ======================================== */

   function formatTimestamp(ts) {
       if (!ts || ts === 'N/A') return 'N/A';

       try {
           // Check if ts is a Unix timestamp (number)
           if (typeof ts === 'number') {
               const date = new Date(ts * 1000);
               return date.toLocaleString('en-US', {
                   year: 'numeric',
                   month: '2-digit',
                   day: '2-digit',
                   hour: '2-digit',
                   minute: '2-digit',
                   second: '2-digit',
                   hour12: false
               });
           }

           // Check if ts is a string that looks like a Unix timestamp
           if (typeof ts === 'string' && /^\d+$/.test(ts)) {
               const timestamp = parseInt(ts);
               const date = timestamp > 9999999999
                   ? new Date(timestamp)
                   : new Date(timestamp * 1000);
               return date.toLocaleString('en-US', {
                   year: 'numeric',
                   month: '2-digit',
                   day: '2-digit',
                   hour: '2-digit',
                   minute: '2-digit',
                   second: '2-digit',
                   hour12: false
               });
           }

           // Try to parse as ISO date string
           const date = new Date(ts);
           if (!isNaN(date.getTime())) {
               return date.toLocaleString('en-US', {
                   year: 'numeric',
                   month: '2-digit',
                   day: '2-digit',
                   hour: '2-digit',
                   minute: '2-digit',
                   second: '2-digit',
                   hour12: false
               });
           }

           return ts;
       } catch (e) {
           console.error('Error formatting timestamp:', e, ts);
           return ts;
       }
   }

   /* ========================================
      DATA LOADING
      ======================================== */

   async function loadState() {
       try {
           const data = await apiFetch('/api/state');
           const statusText = document.getElementById('statusText');
           const statusMonitor = document.getElementById('liveStatus');
           statusText.textContent = 'Online';
           statusMonitor.classList.add('online');

           // Update agents
           const agentsList = document.getElementById('agentsList');
           if (data.agents?.length > 0) {
               agentsList.innerHTML = data.agents.map(agent => `
                   <div class="list-item">
                       <div style="flex: 1;">
                           <div class="list-item-name">${agent.name || 'Unknown'}</div>
                           <div class="list-item-id">${agent.id || 'N/A'}</div>
                       </div>
                       <button class="action-btn icon-btn" onclick="showAgentYaml('${agent.name}')" title="YAML">📄</button>
                   </div>
               `).join('');
               document.getElementById('agentCount').textContent = data.agents.length;
           } else {
               agentsList.innerHTML = '<div class="empty-state">No agents found</div>';
               document.getElementById('agentCount').textContent = '0';
           }

           // Update chains
           const chainsList = document.getElementById('chainsList');
           if (data.chains?.length > 0) {
               chainsList.innerHTML = data.chains.map(chain => `
                   <div class="list-item">
                       <div style="flex: 1;">
                           <div class="list-item-name">${chain.name || 'Unknown'}</div>
                           <div class="list-item-id">${chain.id || 'N/A'}</div>
                       </div>
                       <div class="item-actions">
                           <button class="action-btn icon-btn"
                                   onclick="showChainYaml('${chain.name}')"
                                   title="YAML">📄</button>
                           <button class="action-btn icon-btn"
                                   onclick="showChainFlow('${chain.name}')"
                                   title="Flow">🌿</button>
                           <button class="action-btn icon-btn"
                                   onclick="showLastRun('${chain.name}')"
                                   title="Last Run">⏱️</button>
                       </div>
                   </div>
               `).join('');
               document.getElementById('chainCount').textContent = data.chains.length;
           } else {
               chainsList.innerHTML = '<div class="empty-state">No chains found</div>';
               document.getElementById('chainCount').textContent = '0';
           }

           // Update PIDs
           const pidsList = document.getElementById('pidsList');
           const pEntries = Object.entries(data.pids || {});
           if (pEntries.length > 0) {
               pidsList.innerHTML = pEntries.map(([name, pid]) => `
                   <div class="list-item">
                       <div style="flex:1">
                           <div class="list-item-name">⚙️ ${name}</div>
                           <div class="list-item-id">PID: ${pid}</div>
                       </div>
                   </div>
               `).join('');
               document.getElementById('pidCount').textContent = pEntries.length;
           } else {
               pidsList.innerHTML = '<div class="empty-state">No processes found</div>';
               document.getElementById('pidCount').textContent = '0';
           }

           // Re-apply filters after content update
           applyFilter('agentsList');
           applyFilter('chainsList');
           applyFilter('pidsList');

       } catch (error) {
           console.error('Error loading state:', error);
           const statusText = document.getElementById('statusText');
           const statusMonitor = document.getElementById('liveStatus');
           statusText.textContent = 'Error';
           statusMonitor.classList.remove('online');
       }
   }

   /* ========================================
      LOGGING SYSTEM
      ======================================== */

   function renderLogs(logs) {
       const logsContainer = document.getElementById('logsContainer');
       const paginationContainer = document.getElementById('logPagination');

       if (!logs?.length) {
           logsContainer.innerHTML = '<div class="no-results">No logs match your search</div>';
           paginationContainer.innerHTML = '';
           return;
       }

       const totalLogs = logs.length;
       const totalPages = Math.min(Math.ceil(totalLogs / logsPerPage), maxPages);

       if (currentPage > totalPages) currentPage = totalPages;
       if (currentPage < 1) currentPage = 1;

       const startIndex = (currentPage - 1) * logsPerPage;
       const endIndex = startIndex + logsPerPage;
       const paginatedLogs = logs.slice(startIndex, endIndex);

       let tableHTML = `<table class="log-table"><thead><tr><th>Timestamp</th><th>Level</th><th>Logger</th><th>Message</th></tr></thead><tbody>`;
       paginatedLogs.forEach(log => {
           const levelClass = (log.level || '').toLowerCase();
           const timestamp = formatTimestamp(log.ts);
           const level = log.level || 'N/A';
           const logger = log.logger || 'N/A';
           const message = log.msg || 'N/A';

           tableHTML += `
             <tr class="${['error', 'warning', 'success'].includes(levelClass) ? levelClass : ''}">
               <td class="log-timestamp">${timestamp}</td>
               <td class="log-level ${levelClass}">${level}</td>
               <td class="log-logger">${logger}</td>
               <td class="log-message">${message}</td>
             </tr>`;
       });
       tableHTML += `</tbody></table>`;
       logsContainer.innerHTML = tableHTML;

       let paginationHTML = `
         <button onclick="currentPage=1; renderLogs(allLogs)" ${currentPage === 1 ? 'disabled' : ''}>First</button>
         <button onclick="currentPage--; renderLogs(allLogs)" ${currentPage === 1 ? 'disabled' : ''}>Previous</button>
         <span>Page ${currentPage} of ${totalPages}</span>
         <button onclick="currentPage++; renderLogs(allLogs)" ${currentPage === totalPages ? 'disabled' : ''}>Next</button>
         <button onclick="currentPage=${totalPages}; renderLogs(allLogs)" ${currentPage === totalPages ? 'disabled' : ''}>Last</button>
       `;
       paginationContainer.innerHTML = paginationHTML;
   }

   async function loadLogs() {
       try {
           allLogs = await apiFetch('/api/logs');
           renderLogs(allLogs);
       } catch (e) { console.error(e); }
   }

   function filterLogs() {
       const query = document.getElementById('logSearch').value.toLowerCase();
       if (!query) {
           currentPage = 1;
           renderLogs(allLogs);
           return;
       }

       const filtered = allLogs.filter(log => {
           const formattedTs = formatTimestamp(log.ts);
           const rawTs = String(log.ts || '');

           return (formattedTs.toLowerCase().includes(query) ||
                   rawTs.toLowerCase().includes(query) ||
                   (log.level || '').toLowerCase().includes(query) ||
                   (log.logger || '').toLowerCase().includes(query) ||
                   (log.msg || '').toLowerCase().includes(query));
       });
       currentPage = 1;
       renderLogs(filtered);
   }

   /* ========================================
      ANALYTICS DASHBOARD
      ======================================== */

   /* ========================================
      LOADING INDICATORS
      ======================================== */

   // Full overlay loader (for main tabs)
   function showLoader() {
       const overlay = document.getElementById('loadingOverlay');
       if (overlay) {
           overlay.classList.add('active');
       }
   }

   function hideLoader() {
       const overlay = document.getElementById('loadingOverlay');
       if (overlay) {
           overlay.classList.remove('active');
       }
   }

   // Progress bar (for time windows)
   function showProgressBar() {
       const container = document.getElementById('progressBar');
       if (!container) return;

       container.classList.add('active');
       // Reset animation
       const bar = container.querySelector('.progress-bar');
       if (bar) {
           bar.style.animation = 'none';
           setTimeout(() => {
               bar.style.animation = 'progress 0.8s ease-out';
           }, 10);
       }
   }

   function hideProgressBar() {
       setTimeout(() => {
           const container = document.getElementById('progressBar');
           if (container) {
               container.classList.remove('active');
           }
       }, 800);
   }

   // Make functions globally available
   window.showLoader = showLoader;
   window.hideLoader = hideLoader;
   window.showProgressBar = showProgressBar;
   window.hideProgressBar = hideProgressBar;

   /* ========================================
      ANALYTICS DATA LOADING
      ======================================== */

   function changeTimeWindow(window) {
       // Check if analytics tab is active
       const analyticsTab = document.getElementById('tab-analytics');
       if (!analyticsTab || !analyticsTab.classList.contains('active')) {
           console.warn('Analytics tab not active, skipping time window change');
           return;
       }

       console.log('🔄 Changing time window to:', window);
       console.log('📊 Analytics tab active:', analyticsTab.classList.contains('active'));
       console.log('🎨 Canvas before load:', document.getElementById('eventsPieChart') ? 'EXISTS' : 'MISSING');

       // Show loader
       showLoader();

       currentTimeWindow = window;

       document.querySelectorAll('.window-btn').forEach(btn => {
           btn.classList.remove('active');
           if (btn.dataset.window === window) {
               btn.classList.add('active');
           }
       });

       loadAnalytics().finally(() => {
           console.log('🎨 Canvas after load:', document.getElementById('eventsPieChart') ? 'EXISTS' : 'MISSING');
           setTimeout(hideLoader, 400);
       });
   }

   // Make changeTimeWindow globally available
   window.changeTimeWindow = changeTimeWindow;

   async function loadAnalytics() {
       try {
           const data = await apiFetch(`/api/v1/summary?window=${currentTimeWindow}`);
           console.log("recieved analytics");
           console.log(data);

           // Check if data exists
           if (!data) {
               console.warn('No analytics data received');
               return;
           }

           updateKPIs(data);
           renderEventsPieChart(data.events?.by_type || {});

           // Only render files chart if data exists
           if (data.files?.by_extension) {
               renderFilesPieChart(data.files.by_extension);
           } else {
               showEmptyChart('filesPieChart', 'File tracking not enabled');
           }

           renderRunsDonutChart(data.runs || {});
           renderChainsBarChart(data.chains?.by_chain || {});
           renderAgentsBarChart(data.agents?.invocations || {});
           renderTimelineChart(data.timeline?.runs_per_hour || []);

       } catch (e) {
           console.error('Failed to load analytics:', e);
           showError('Failed to load analytics data. Please try again.', 'Analytics Error');
       }
   }

   function updateKPIs(data) {
       // Safely access nested properties with fallbacks
       const runs = data?.runs || { total: 0, success: 0, failed: 0 };
       const files = data?.files || { count: 0, total_size_mb: 0 };
       const events = data?.events || { by_type: {} };

       document.getElementById('kpi-total-runs').textContent = (runs.total || 0).toLocaleString();

       document.getElementById('kpi-success-runs').textContent = (runs.success || 0).toLocaleString();
       const successRate = runs.total > 0
           ? Math.round((runs.success / runs.total) * 100)
           : 0;
       document.getElementById('kpi-success-rate').textContent = `${successRate}% success rate`;

       document.getElementById('kpi-failed-runs').textContent = (runs.failed || 0).toLocaleString();
       const errorCount = events.by_type?.error || 0;
       document.getElementById('kpi-error-count').textContent = `${errorCount} total errors`;

       document.getElementById('kpi-file-count').textContent = (files.count || 0).toLocaleString();
       document.getElementById('kpi-file-size').textContent = `${files.total_size_mb || 0} MB total`;
   }

   function destroyChart(chartId) {
       if (charts[chartId]) {
           charts[chartId].destroy();
           delete charts[chartId];
       }
   }

   // Helper function to safely get chart canvas and show empty state
   function getChartCanvas(chartId, emptyMessage = 'No data available') {
       const canvas = document.getElementById(chartId);
       if (!canvas) {
           console.warn(`Chart canvas '${chartId}' not found in DOM`);
           return null;
       }

       // Show canvas and hide empty message if it exists
       canvas.style.display = 'block';
       const parent = canvas.parentElement;
       if (parent) {
           const emptyDiv = parent.querySelector('.chart-empty');
           if (emptyDiv) {
               emptyDiv.style.display = 'none';
           }
       }

       return canvas;
   }

   function showEmptyChart(chartId, message) {
       const canvas = document.getElementById(chartId);
       if (!canvas) return;

       const parent = canvas.parentElement;
       if (!parent) return;

       // Don't destroy the canvas! Just hide it and show message
       // Check if empty message div already exists
       let emptyDiv = parent.querySelector('.chart-empty');
       if (!emptyDiv) {
           emptyDiv = document.createElement('div');
           emptyDiv.className = 'chart-empty';
           parent.appendChild(emptyDiv);
       }

       emptyDiv.textContent = message;
       emptyDiv.style.display = 'flex';
       canvas.style.display = 'none';
   }

   function renderEventsPieChart(data) {
       const chartId = 'eventsPieChart';
       destroyChart(chartId);

       if (!data || Object.keys(data).length === 0) {
           showEmptyChart(chartId, 'No event data available');
           return;
       }

       const canvas = getChartCanvas(chartId);
       if (!canvas) return;

       const colors = getColorScheme();

       charts[chartId] = new Chart(canvas, {
           type: 'pie',
           data: {
               labels: Object.keys(data),
               datasets: [{
                   data: Object.values(data),
                   backgroundColor: colors.primary,
                   borderWidth: 2,
                   borderColor: colors.gridColor
               }]
           },
           options: {
               responsive: true,
               maintainAspectRatio: true,
               plugins: {
                   legend: {
                       position: 'bottom',
                       labels: {
                           color: colors.textColor,
                           padding: 15,
                           font: { size: 12 }
                       }
                   },
                   tooltip: {
                       backgroundColor: 'rgba(15, 23, 42, 0.95)',
                       titleColor: '#10b981',
                       bodyColor: '#e2e8f0',
                       borderColor: '#10b981',
                       borderWidth: 1,
                       padding: 12,
                       cornerRadius: 8
                   }
               }
           }
       });
   }

   function renderFilesPieChart(data) {
       const chartId = 'filesPieChart';
       destroyChart(chartId);

       if (!data || Object.keys(data).length === 0) {
           showEmptyChart(chartId, 'No file data available');
           return;
       }

       const canvas = getChartCanvas(chartId);
       if (!canvas) return;

       const colors = getColorScheme();

       charts[chartId] = new Chart(canvas, {
           type: 'pie',
           data: {
               labels: Object.keys(data),
               datasets: [{
                   data: Object.values(data),
                   backgroundColor: colors.primary,
                   borderWidth: 2,
                   borderColor: colors.gridColor
               }]
           },
           options: {
               responsive: true,
               maintainAspectRatio: true,
               plugins: {
                   legend: {
                       position: 'bottom',
                       labels: {
                           color: colors.textColor,
                           padding: 15,
                           font: { size: 12 }
                       }
                   },
                   tooltip: {
                       backgroundColor: 'rgba(15, 23, 42, 0.95)',
                       titleColor: '#10b981',
                       bodyColor: '#e2e8f0',
                       borderColor: '#10b981',
                       borderWidth: 1,
                       padding: 12,
                       cornerRadius: 8
                   }
               }
           }
       });
   }

   function renderRunsDonutChart(data) {
       const chartId = 'runsDonutChart';
       destroyChart(chartId);

       if (!data || data.total === 0) {
           showEmptyChart(chartId, 'No run data available');
           return;
       }

       const canvas = getChartCanvas(chartId);
       if (!canvas) return;

       const colors = getColorScheme();

       charts[chartId] = new Chart(canvas, {
           type: 'doughnut',
           data: {
               labels: ['Success', 'Failed'],
               datasets: [{
                   data: [data.success, data.failed],
                   backgroundColor: [colors.success, colors.error],
                   borderWidth: 2,
                   borderColor: colors.gridColor
               }]
           },
           options: {
               responsive: true,
               maintainAspectRatio: true,
               plugins: {
                   legend: {
                       position: 'bottom',
                       labels: {
                           color: colors.textColor,
                           padding: 15,
                           font: { size: 12 }
                       }
                   },
                   tooltip: {
                       backgroundColor: 'rgba(15, 23, 42, 0.95)',
                       titleColor: '#10b981',
                       bodyColor: '#e2e8f0',
                       borderColor: '#10b981',
                       borderWidth: 1,
                       padding: 12,
                       cornerRadius: 8,
                       callbacks: {
                           label: function(context) {
                               const total = data.total;
                               const value = context.parsed;
                               const percentage = Math.round((value / total) * 100);
                               return `${context.label}: ${value} (${percentage}%)`;
                           }
                       }
                   }
               }
           }
       });
   }

   function renderChainsBarChart(data) {
       const chartId = 'chainsBarChart';
       destroyChart(chartId);

       if (!data || Object.keys(data).length === 0) {
           showEmptyChart(chartId, 'No chain data available');
           return;
       }

       const canvas = getChartCanvas(chartId);
       if (!canvas) return;

       const colors = getColorScheme();

       const sorted = Object.entries(data).sort((a, b) => b[1] - a[1]);
       const labels = sorted.map(([name]) => name);
       const values = sorted.map(([, count]) => count);

       charts[chartId] = new Chart(canvas, {
           type: 'bar',
           data: {
               labels: labels,
               datasets: [{
                   label: 'Invocations',
                   data: values,
                   backgroundColor: colors.primary[1],
                   borderColor: colors.primary[0],
                   borderWidth: 2,
                   borderRadius: 6
               }]
           },
           options: {
               responsive: true,
               maintainAspectRatio: true,
               indexAxis: 'y',
               plugins: {
                   legend: { display: false },
                   tooltip: {
                       backgroundColor: 'rgba(15, 23, 42, 0.95)',
                       titleColor: '#10b981',
                       bodyColor: '#e2e8f0',
                       borderColor: '#10b981',
                       borderWidth: 1,
                       padding: 12,
                       cornerRadius: 8
                   }
               },
               scales: {
                   x: {
                       grid: { color: colors.gridColor },
                       ticks: { color: colors.subTextColor }
                   },
                   y: {
                       grid: { display: false },
                       ticks: { color: colors.textColor, font: { size: 12 } }
                   }
               }
           }
       });
   }

   function renderAgentsBarChart(data) {
       const chartId = 'agentsBarChart';
       destroyChart(chartId);

       if (!data || Object.keys(data).length === 0) {
           showEmptyChart(chartId, 'No agent data available');
           return;
       }

       const canvas = getChartCanvas(chartId);
       if (!canvas) return;

       const colors = getColorScheme();

       const sorted = Object.entries(data).sort((a, b) => b[1] - a[1]);
       const labels = sorted.map(([name]) => name);
       const values = sorted.map(([, count]) => count);

       charts[chartId] = new Chart(canvas, {
           type: 'bar',
           data: {
               labels: labels,
               datasets: [{
                   label: 'Invocations',
                   data: values,
                   backgroundColor: colors.primary[2],
                   borderColor: colors.primary[0],
                   borderWidth: 2,
                   borderRadius: 6
               }]
           },
           options: {
               responsive: true,
               maintainAspectRatio: true,
               indexAxis: 'y',
               plugins: {
                   legend: { display: false },
                   tooltip: {
                       backgroundColor: 'rgba(15, 23, 42, 0.95)',
                       titleColor: '#10b981',
                       bodyColor: '#e2e8f0',
                       borderColor: '#10b981',
                       borderWidth: 1,
                       padding: 12,
                       cornerRadius: 8
                   }
               },
               scales: {
                   x: {
                       grid: { color: colors.gridColor },
                       ticks: { color: colors.subTextColor }
                   },
                   y: {
                       grid: { display: false },
                       ticks: { color: colors.textColor, font: { size: 12 } }
                   }
               }
           }
       });
   }

   function renderTimelineChart(data) {
       const chartId = 'timelineChart';
       destroyChart(chartId);

       if (!data || data.length === 0) {
           showEmptyChart(chartId, 'No timeline data available');
           return;
       }

       const canvas = getChartCanvas(chartId);
       if (!canvas) return;

       const colors = getColorScheme();

       const labels = data.map(d => d.hour);
       const values = data.map(d => d.count);

       charts[chartId] = new Chart(canvas, {
           type: 'line',
           data: {
               labels: labels,
               datasets: [{
                   label: 'Runs per Hour',
                   data: values,
                   borderColor: colors.primary[0],
                   backgroundColor: colors.primary[0] + '33',
                   borderWidth: 3,
                   fill: true,
                   tension: 0.4,
                   pointRadius: 5,
                   pointBackgroundColor: colors.primary[0],
                   pointBorderColor: colors.textColor,
                   pointBorderWidth: 2,
                   pointHoverRadius: 7
               }]
           },
           options: {
               responsive: true,
               maintainAspectRatio: true,
               plugins: {
                   legend: { display: false },
                   tooltip: {
                       backgroundColor: 'rgba(15, 23, 42, 0.95)',
                       titleColor: '#10b981',
                       bodyColor: '#e2e8f0',
                       borderColor: '#10b981',
                       borderWidth: 1,
                       padding: 12,
                       cornerRadius: 8
                   }
               },
               scales: {
                   x: {
                       grid: { color: colors.gridColor },
                       ticks: { color: colors.subTextColor }
                   },
                   y: {
                       grid: { color: colors.gridColor },
                       ticks: {
                           color: colors.subTextColor,
                           stepSize: 1
                       },
                       beginAtZero: true
                   }
               }
           }
       });
   }

   /* ========================================
      CHAIN FLOW VISUALIZATION
      ======================================== */

   function checkGraphvizLibraries() {
       console.log('=== D3/Graphviz Library Diagnostic ===');
       console.log('D3 loaded:', typeof d3 !== 'undefined');
       if (typeof d3 !== 'undefined') {
           console.log('D3 version:', d3.version);
           console.log('d3.select:', typeof d3.select);
           console.log('d3.graphviz:', typeof d3.graphviz);

           try {
               const test = d3.select('body');
               console.log('d3.select().graphviz:', typeof test.graphviz);
           } catch (e) {
               console.error('Error creating d3 selection:', e);
           }
       }

       console.log('@hpcc-js/wasm loaded:', typeof window['@hpcc-js/wasm'] !== 'undefined');
       console.log('window.d3 exists:', typeof window.d3 !== 'undefined');
       console.log('===================================');
   }

   window.checkGraphvizLibraries = checkGraphvizLibraries;

   function zoomIn() {
       if (currentZoom) {
           const svg = d3.select('#chainFlowBody svg');
           if (svg.node()) {
               svg.transition()
                   .duration(300)
                   .call(currentZoom.scaleBy, 1.3);
           }
       }
   }

   function zoomOut() {
       if (currentZoom) {
           const svg = d3.select('#chainFlowBody svg');
           if (svg.node()) {
               svg.transition()
                   .duration(300)
                   .call(currentZoom.scaleBy, 0.7);
           }
       }
   }

   function resetZoom() {
       if (currentZoom && graphvizInstance) {
           const svg = d3.select('#chainFlowBody svg');
           const container = document.getElementById("chainFlowBody");
           if (svg.node() && container) {
               const g = svg.select("g");
               if (g.node()) {
                   try {
                       const bbox = g.node().getBBox();
                       const centerX = (container.clientWidth - bbox.width * 0.9) / 2;
                       const centerY = (container.clientHeight - bbox.height * 0.9) / 2;

                       const resetTransform = d3.zoomIdentity
                           .translate(centerX, centerY)
                           .scale(0.9);

                       svg.transition()
                           .duration(500)
                           .call(currentZoom.transform, resetTransform);
                   } catch (e) {
                       svg.transition()
                           .duration(500)
                           .call(currentZoom.transform, d3.zoomIdentity);
                   }
               }
           }
       }
   }

   async function showChainFlow(name) {
       document.getElementById("chainFlowTitle").innerText = `${name} - Flow Diagram`;

       try {
           const data = await apiFetch(`/api/v1/chains/${name}/flow`);

           if (!data.dot) {
               throw new Error('No flow data available for this chain');
           }

           const container = document.getElementById("chainFlowBody");
           container.innerHTML = '<div class="loading-indicator">🔄 Rendering flow diagram...</div>';

           openModal('chainFlowModal');
           await new Promise(resolve => setTimeout(resolve, 300));

           if (typeof d3 === 'undefined') {
               throw new Error('D3.js library not loaded. Please check console and refresh the page.');
           }

           console.log('D3 version:', d3.version);
           console.log('d3.graphviz type:', typeof d3.graphviz);
           console.log('d3.select type:', typeof d3.select);

           try {
               const testSelection = d3.select("body");
               if (typeof testSelection.graphviz !== 'function') {
                   throw new Error('d3-graphviz not properly loaded.');
               }
               console.log('d3-graphviz is available on selections');
           } catch (checkError) {
               console.error('Graphviz check error:', checkError);
               throw new Error('d3-graphviz not available. Please ensure all libraries loaded.');
           }

           container.innerHTML = '';

           try {
               graphvizInstance = d3.select("#chainFlowBody")
                   .graphviz()
                   .fit(true)
                   .zoom(true)
                   .scale(0.9)
                   .width(container.clientWidth || 800)
                   .height(container.clientHeight || 600)
                   .engine("dot")
                   .transition(() => d3.transition().duration(500))
                   .on("end", () => {
                       try {
                           const svg = d3.select("#chainFlowBody svg");

                           if (!svg.node()) {
                               console.error('SVG not found after rendering');
                               return;
                           }

                           // Force white text in light mode
                           if (document.body.classList.contains('light-mode')) {
                               svg.selectAll('.node text').each(function() {
                                   d3.select(this)
                                       .attr('fill', '#ffffff')
                                       .attr('style', 'fill: #ffffff !important; font-weight: 700 !important;');
                               });
                           }

                           const zoom = d3.zoom()
                               .scaleExtent([0.1, 4])
                               .on("zoom", (event) => {
                                   const g = svg.select("g");
                                   if (g.node()) {
                                       g.attr("transform", event.transform);
                                   }
                               });

                           svg.call(zoom);
                           currentZoom = zoom;

                           svg.on("wheel", (event) => {
                               event.preventDefault();
                           });

                           const g = svg.select("g");
                           if (g.node()) {
                               try {
                                   const bbox = g.node().getBBox();
                                   const centerX = (container.clientWidth - bbox.width * 0.9) / 2;
                                   const centerY = (container.clientHeight - bbox.height * 0.9) / 2;

                                   const initialTransform = d3.zoomIdentity
                                       .translate(centerX, centerY)
                                       .scale(0.9);

                                   svg.call(zoom.transform, initialTransform);
                               } catch (bboxError) {
                                   console.warn('Could not center graph:', bboxError);
                               }
                           }
                       } catch (zoomError) {
                           console.error('Zoom setup error:', zoomError);
                       }
                   });

               console.log('Rendering DOT for chain:', name);
               graphvizInstance.renderDot(data.dot);

           } catch (renderError) {
               console.error('Graphviz render error:', renderError);
               container.innerHTML =
                   `<div class="error-message">❌ Failed to render diagram: ${renderError.message}</div>`;
           }

       } catch (e) {
           console.error('Chain flow error:', e);
           const container = document.getElementById("chainFlowBody");
           if (container) {
               container.innerHTML =
                   `<div class="error-message">❌ ${e.message}<br><br>Chain: ${name}</div>`;
           }
           openModal('chainFlowModal');
       }
   }

   document.addEventListener('keydown', function(e) {
       const modal = document.getElementById('chainFlowModal');
       if (modal && modal.style.display === 'block') {
           if (e.key === '+' || e.key === '=') {
               zoomIn();
               e.preventDefault();
           } else if (e.key === '-' || e.key === '_') {
               zoomOut();
               e.preventDefault();
           } else if (e.key === '0') {
               resetZoom();
               e.preventDefault();
           }
       }
   });

   /* ========================================
      MODALS
      ======================================== */

   async function showChainYaml(name) {
       try {
           const j = await apiFetch(`/api/v1/chains/${name}/yaml`);
           document.getElementById("chainYamlTitle").innerText = name;
           document.getElementById("chainYamlBody").textContent = j.yaml;
           openModal("chainYamlModal");
       } catch (e) { console.error(e); }
   }

   async function showLastRun(name) {
       try {
           const j = await apiFetch(`/api/v1/chains/${name}/lastrun`);
           document.getElementById("lastRunTitle").innerText = name;
           document.getElementById("lastRunBody").textContent = JSON.stringify(j, null, 2);
           openModal('lastRunModal');
       } catch (e) {
           console.error('Last run error:', e);
           if (e.message.includes('404')) {
               showError(`No run history available for chain: ${name}\n\nThis chain hasn't been executed yet or the run history file is missing.`, 'No Run History');
           } else {
               showError(`Failed to load run history for: ${name}\n\nError: ${e.message}`, 'Load Failed');
           }
       }
   }

   async function showAgentYaml(name) {
       try {
           const j = await apiFetch(`/api/v1/agents/${name}/yaml`);
           document.getElementById("agentYamlTitle").innerText = name;
           document.getElementById("agentYamlBody").textContent = j.yaml;
           openModal("agentYamlModal");
       } catch (e) { console.error(e); }
   }

   async function showSubscription() {
       try {
           const data = await apiFetch(`/api/v1/sys/subscription`);

           const subscriptionId = data.subscription_id || 'N/A';
           const createdAt = data.created_at ? formatTimestamp(data.created_at) : 'N/A';

           const formattedContent = `Subscription ID: ${subscriptionId}

   Created At: ${createdAt}

   Status: Active ✓`;

           document.getElementById("subscriptionContent").textContent = formattedContent;
           openModal("subscriptionModal");
       } catch (e) {
           console.error('Subscription error:', e);
           document.getElementById("subscriptionContent").textContent = `Error loading subscription information.\n\n${e.message}`;
           openModal("subscriptionModal");
       }
   }

   /* ========================================
      WEBSOCKETS
      ======================================== */

   function initLiveEvents() {
       const eventsBox = document.getElementById("liveEvents");

       if (wsEvents) {
           wsEvents.onclose = null;
           wsEvents.close();
       }

       const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
       const wsurl = `${protocol}//${location.host}/api/v1/ws/events`;

       try {
           wsEvents = new WebSocket(wsurl);

           wsEvents.onopen = () => console.log("✅ Live Events Connected");

           wsEvents.onmessage = e => {
               const ev = JSON.parse(e.data);
               eventsBox.textContent += JSON.stringify(ev, null, 2) + "\n---\n";
               eventsBox.scrollTop = eventsBox.scrollHeight;
               if (eventsBox.textContent.length > 50000) eventsBox.textContent = eventsBox.textContent.slice(-25000);
           };

           wsEvents.onclose = () => {
               console.warn("⚠️ Live Events Closed. Reconnecting in 5s...");
               setTimeout(initLiveEvents, 5000);
           };

           wsEvents.onerror = (err) => console.error("❌ Live Events Error");

       } catch (error) {
           console.error('WS Setup Error:', error);
       }
   }

   function connectRunWs() {
       const runId = document.getElementById("runIdInput").value;
       const box = document.getElementById("runEvents");
       if (!runId) {
           showError("Please enter a run_id to monitor events", "Run ID Required");
           return;
       }

       if (runWs) runWs.close();
       box.textContent = `Connecting to Run ${runId}...\n`;

       const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
       runWs = new WebSocket(`${protocol}//${location.host}/api/v1/ws/replay/${runId}`);

       runWs.onopen = () => box.textContent = `✅ Connected: ${runId}\n---\n`;
       runWs.onmessage = e => {
           box.textContent += JSON.stringify(JSON.parse(e.data)) + "\n---\n";
           box.scrollTop = box.scrollHeight;
       };
       runWs.onerror = () => box.textContent += "\n❌ Error: Connection failed.";
   }

   /* ========================================
      DOWNLOAD & UTILITIES
      ======================================== */

   function downloadContent(id, name) {
       const content = document.getElementById(id).textContent;
       if (!content) return;
       const a = document.createElement('a');
       a.href = URL.createObjectURL(new Blob([content], { type: 'text/plain' }));
       a.download = name;
       a.click();
   }

   function clearBox(id) {
       const box = document.getElementById(id);
       if (box) box.textContent = (id === 'runEvents') ? "Logs cleared. Ready...\n" : "";
   }

   function downloadLogsCSV() {
       if (!allLogs.length) return;
       let csv = "Timestamp,Level,Logger,Message\n" + allLogs.map(l => {
           const timestamp = formatTimestamp(l.ts);
           const level = l.level || 'N/A';
           const logger = l.logger || 'N/A';
           const message = (l.msg || 'N/A').replace(/"/g, '""');
           return `"${timestamp}","${level}","${logger}","${message}"`;
       }).join("\n");
       const a = document.createElement('a');
       a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
       a.download = "logs.csv";
       a.click();
   }

   /* ========================================
      SHARED FILES
      ======================================== */

   async function loadInputFiles() {
       const listContainer = document.getElementById('inputFilesList');
       try {
           const data = await apiFetch('/api/v1/fs/shared');
           const files = data.files || [];

           if (files.length > 0) {
               listContainer.innerHTML = files.map(file => {
                   const dateStr = new Date(file.modified * 1000).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
                   return `
                   <div class="list-item">
                       <div style="flex: 1;">
                           <div class="list-item-name">📄 ${file.path}</div>
                           <div class="list-item-id">${(file.size / 1024).toFixed(1)} KB • ${dateStr}</div>
                       </div>
                       <button class="action-btn" onclick="window.location.href='/api/v1/fs/shared/download?path=' + encodeURIComponent('${file.path}')">⬇️</button>
                   </div>`;
               }).join('');
           } else {
               listContainer.innerHTML = '<div class="empty-state">No input files found</div>';
           }
           applyFilter('inputFilesList');
       } catch (e) { console.error(e); }
   }

   /* ========================================
      SEARCH FILTERS
      ======================================== */

   function filterCardList(listId, query) {
       activeFilters[listId] = query.toLowerCase();
       applyFilter(listId);
   }

   function applyFilter(listId) {
       const container = document.getElementById(listId);
       if (!container) return;
       const items = container.getElementsByClassName('list-item');
       const term = activeFilters[listId] || "";

       Array.from(items).forEach(item => {
           item.style.display = item.textContent.toLowerCase().includes(term) ? "" : "none";
       });
   }

   /* ========================================
      USER MANAGEMENT (Admin Only)
      ======================================== */

   async function loadUsers() {
       try {
           const response = await fetch('/api/v1/users/list', {
               headers: getAuthHeaders()
           });

           if (!response.ok) throw new Error('Failed to load users');

           allUsers = await response.json();
           renderUsers(allUsers);
       } catch (e) {
           console.error('Error loading users:', e);
           document.getElementById('usersContainer').innerHTML =
               '<div class="error-message">Failed to load users. ' + e.message + '</div>';
       }
   }

   function renderUsers(users) {
       const container = document.getElementById('usersContainer');

       if (!users || users.length === 0) {
           container.innerHTML = '<div class="empty-state">No users found</div>';
           return;
       }

       let tableHTML = `
           <table class="log-table">
               <thead>
                   <tr>
                       <th>Username</th>
                       <th>Role</th>
                       <th>Created</th>
                       <th>Actions</th>
                   </tr>
               </thead>
               <tbody>
       `;

       users.forEach(user => {
           const createdDate = new Date(user.created_at).toLocaleString('en-US', {
               year: 'numeric',
               month: 'short',
               day: 'numeric',
               hour: '2-digit',
               minute: '2-digit'
           });

           const editBtn = `<button class="action-btn" onclick="showEditUserModal('${user.username}', '${user.role}')" title="Edit">✏️</button>`;

           const deleteBtn = user.username === 'admin'
               ? '<button class="action-btn" disabled title="Cannot delete admin">🔒</button>'
               : `<button class="action-btn" onclick="deleteUser('${user.username}')" title="Delete">🗑️</button>`;

           tableHTML += `
               <tr>
                   <td class="log-timestamp">${user.username}</td>
                   <td class="log-level">${user.role}</td>
                   <td class="log-logger">${createdDate}</td>
                   <td>${editBtn} ${deleteBtn}</td>
               </tr>
           `;
       });

       tableHTML += `</tbody></table>`;
       container.innerHTML = tableHTML;
   }

   function filterUsers() {
       const query = document.getElementById('userSearch').value.toLowerCase();
       if (!query) {
           renderUsers(allUsers);
           return;
       }

       const filtered = allUsers.filter(user =>
           user.username.toLowerCase().includes(query) ||
           user.role.toLowerCase().includes(query)
       );

       renderUsers(filtered);
   }

   async function showAddUserModal() {
       const result = await showInput({
           title: 'Add New User',
           subtitle: 'Create a new user account',
           fields: [
               {
                   name: 'username',
                   label: 'Username',
                   type: 'text',
                   placeholder: 'Enter username',
                   required: true
               },
               {
                   name: 'password',
                   label: 'Password',
                   type: 'password',
                   placeholder: 'Enter password',
                   required: true
               },
               {
                   name: 'role',
                   label: 'Role',
                   type: 'select',
                   defaultValue: 'developer',
                   required: true,
                   options: [
                       { value: 'developer', label: 'Developer' },
                       { value: 'admin', label: 'Admin' }
                   ]
               }
           ]
       });

       if (result) {
           addUser(result.username, result.password, result.role);
       }
   }

   async function addUser(username, password, role) {
       try {
           const response = await fetch('/api/v1/users/add', {
               method: 'POST',
               headers: getAuthHeaders(),
               body: JSON.stringify({ username, password, role })
           });

           if (!response.ok) {
               const error = await response.json();
               throw new Error(error.detail || 'Failed to add user');
           }

           showSuccess(`User "${username}" created successfully! User will be prompted to change password on first login.`);
           loadUsers();
       } catch (e) {
           showError('Error adding user: ' + e.message, 'Add User Failed');
       }
   }

   async function deleteUser(username) {
       const confirmed = await showConfirm(
           `Are you sure you want to delete user "${username}"? This action cannot be undone.`,
           'Delete User'
       );

       if (!confirmed) return;

       try {
           const response = await fetch(`/api/v1/users/${username}`, {
               method: 'DELETE',
               headers: getAuthHeaders()
           });

           if (!response.ok) {
               const error = await response.json();
               throw new Error(error.detail || 'Failed to delete user');
           }

           showSuccess(`User "${username}" deleted successfully!`);
           loadUsers();
       } catch (e) {
           showError('Error deleting user: ' + e.message, 'Delete User Failed');
       }
   }

   async function showEditUserModal(username, currentRole) {
       const result = await showInput({
           title: `Edit User: ${username}`,
           subtitle: 'Update role and/or reset password',
           fields: [
               {
                   name: 'role',
                   label: 'Role',
                   type: 'select',
                   defaultValue: currentRole,
                   required: false,
                   options: [
                       { value: currentRole, label: `Keep as ${currentRole}` },
                       { value: 'admin', label: 'Admin' },
                       { value: 'developer', label: 'Developer' }
                   ]
               },
               {
                   name: 'password',
                   label: 'New Password (leave empty to keep current)',
                   type: 'password',
                   placeholder: 'Enter new password or leave empty',
                   required: false
               }
           ]
       });

       if (!result) return;

       // Check if admin role change
       if (username === 'admin' && result.role !== 'admin' && result.role !== currentRole) {
           showError('Cannot change admin user role', 'Invalid Operation');
           return;
       }

       // Build updates object
       const updates = {};
       if (result.role && result.role !== currentRole && !result.role.includes('Keep as')) {
           updates.role = result.role;
       }
       if (result.password && result.password.trim()) {
           updates.password = result.password;
       }

       // Check if anything changed
       if (Object.keys(updates).length === 0) {
           showError('No changes made', 'Edit User');
           return;
       }

       updateUser(username, updates.role || null, updates.password || null);
   }

   async function updateUser(username, newRole, newPassword) {
       try {
           const updates = {};
           if (newRole) updates.role = newRole;
           if (newPassword) updates.password = newPassword;

           const response = await fetch(`/api/v1/users/${username}`, {
               method: 'PUT',
               headers: getAuthHeaders(),
               body: JSON.stringify(updates)
           });

           if (!response.ok) {
               const error = await response.json();
               throw new Error(error.detail || 'Failed to update user');
           }

           let message = `User "${username}" updated successfully!`;
           if (newPassword) {
               message += '\nUser will be prompted to change password on next login.';
           }

           showSuccess(message);
           loadUsers();
       } catch (e) {
           showError('Error updating user: ' + e.message, 'Update User Failed');
       }
   }

   // Make functions globally available
   window.showEditUserModal = showEditUserModal;
   window.updateUser = updateUser;

   // Make functions globally available
   window.loadUsers = loadUsers;
   window.filterUsers = filterUsers;
   window.showAddUserModal = showAddUserModal;
   window.deleteUser = deleteUser;

   /* ========================================
      SUBSCRIPTION VALIDATION
      ======================================== */

   async function validateSubscription() {
       try {
           const data = await apiFetch(`/api/v1/sys/subscription`);

           if (!data ||
               typeof data !== 'object' ||
               Object.keys(data).length === 0 ||
               !data.subscription_id ||
               data.subscription_id === '' ||
               data.subscription_id === 'none') {

               throw new Error('Invalid or missing subscription');
           }

           console.log('✅ Subscription validated:', data.subscription_id);
           return true;

       } catch (e) {
           console.error('❌ Subscription validation failed:', e);

           document.body.innerHTML = `
               <div style="
                   display: flex;
                   align-items: center;
                   justify-content: center;
                   min-height: 100vh;
                   background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
                   color: #e2e8f0;
                   font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                   padding: 20px;
               ">
                   <div style="
                       max-width: 500px;
                       text-align: center;
                       background: rgba(239, 68, 68, 0.1);
                       border: 2px solid #ef4444;
                       border-radius: 16px;
                       padding: 40px;
                       box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
                   ">
                       <div style="font-size: 64px; margin-bottom: 20px;">🚫</div>
                       <h1 style="
                           font-size: 28px;
                           font-weight: 600;
                           color: #ef4444;
                           margin-bottom: 20px;
                       ">Subscription Required</h1>
                       <p style="
                           font-size: 16px;
                           line-height: 1.6;
                           color: #cbd5e1;
                           margin-bottom: 30px;
                       ">
                           You need a valid TreehopperAI subscription to access this dashboard.
                       </p>
                       <div style="
                           background: rgba(15, 23, 42, 0.6);
                           border-radius: 8px;
                           padding: 20px;
                           margin-bottom: 30px;
                           text-align: left;
                           font-family: 'Courier New', monospace;
                           font-size: 14px;
                           color: #94a3b8;
                       ">
                           <strong style="color: #ef4444;">Error:</strong> ${e.message}<br><br>
                           Please contact your administrator or<br>
                           If you have run the CLI you must be having a subscription_id.txt in .treehopper directory.
                       </div>
                       <button onclick="location.reload()" style="
                           background: linear-gradient(135deg, #10b981, #059669);
                           color: white;
                           border: none;
                           padding: 12px 32px;
                           border-radius: 8px;
                           font-size: 16px;
                           font-weight: 600;
                           cursor: pointer;
                           transition: all 0.2s;
                       " onmouseover="this.style.transform='translateY(-2px)'"
                          onmouseout="this.style.transform='translateY(0)'">
                           Retry
                       </button>
                   </div>
               </div>
           `;

           return false;
       }
   }

   /* ========================================
      INITIALIZATION
      ======================================== */

   async function init() {
       // First, check authentication
       if (!checkAuth()) {
           return; // Will redirect to login
       }

       // Then validate subscription
       const isValid = await validateSubscription();

       if (!isValid) {
           return;
       }

       // Load core features
       loadTheme();
       loadSavedTab();
       loadState();
       loadLogs();
       loadInputFiles();
       initLiveEvents();

       // Sync time window button state with default (24h)
       setTimeout(() => {
           document.querySelectorAll('.window-btn').forEach(btn => {
               btn.classList.remove('active');
               if (btn.dataset.window === currentTimeWindow) {
                   btn.classList.add('active');
               }
           });
       }, 100);

       // Load analytics dashboard
       loadAnalytics();

       // Load users if admin
       const role = localStorage.getItem('user_role');
       if (role === 'admin') {
           loadUsers();
       }

       // Set up auto-refresh
       updateInterval = setInterval(() => {
           loadState();
           loadInputFiles();

           // Only refresh analytics if analytics tab is active
           const analyticsTab = document.getElementById('tab-analytics');
           if (analyticsTab && analyticsTab.classList.contains('active')) {
               loadAnalytics();
           }
       }, 30000);
   }

   init();
