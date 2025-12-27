/**
 * Storage Inspector - TreehopperAI Dashboard
 * Real-time storage monitoring with CLI maintenance guidance
 * Admin-only feature
 */

/* ========================================
   GLOBAL STATE
   ======================================== */

   let storageData = null;
   let autoRefreshInterval = null;
   const AUTO_REFRESH_SECONDS = 30;

   /* ========================================
      ADMIN CHECK
      ======================================== */

   /**
    * Check if current user is admin
    * Called on page load to show/hide storage button
    */
   function checkAdminAccess() {
       const userRole = localStorage.getItem('user_role');
       const storageBtn = document.querySelector('.storage-inspector-btn');

       if (storageBtn) {
           if (userRole === 'admin') {
               storageBtn.style.display = 'flex';
           } else {
               storageBtn.style.display = 'none';
           }
       }
   }

   // Run on page load
   if (document.readyState === 'loading') {
       document.addEventListener('DOMContentLoaded', checkAdminAccess);
   } else {
       checkAdminAccess();
   }

   /* ========================================
      CORE FUNCTIONS
      ======================================== */

   /**
    * Open the storage inspector modal
    */
   async function openStorageInspector() {
       // Double-check admin access
       const userRole = localStorage.getItem('user_role');
       if (userRole !== 'admin') {
           showError('Access Denied', 'Admin Access Required');
           return;
       }

       const modal = document.getElementById('storageInspectorModal');
       if (!modal) {
           console.error('Storage Inspector modal not found in DOM');
           showError('Storage Inspector modal not found. Please check your HTML.', 'Configuration Error');
           return;
       }

       modal.classList.add('active');

       // Load data immediately
       await loadStorageData();

       // Start auto-refresh
       startAutoRefresh();
   }

   /**
    * Close the storage inspector modal
    */
   function closeStorageInspector() {
       const modal = document.getElementById('storageInspectorModal');
       if (modal) {
           modal.classList.remove('active');
       }

       // Stop auto-refresh
       stopAutoRefresh();
   }

   /**
    * Load storage data from API
    */
   async function loadStorageData() {
       const inspectorBody = document.getElementById('inspectorBody');

       // Show loading state
       inspectorBody.innerHTML = `
           <div class="inspector-loading">
               <div class="inspector-spinner"></div>
               <div class="inspector-loading-text">Loading storage metrics...</div>
           </div>
       `;

       try {
           const response = await fetch('/admin/storage', {
               headers: {
                   'Authorization': `Bearer ${localStorage.getItem('access_token')}`,
                   'x-requested-with': 'TreehopperDash'
               }
           });

           if (!response.ok) {
               throw new Error(`HTTP ${response.status}: ${response.statusText}`);
           }

           storageData = await response.json();
           renderStorageData();

       } catch (error) {
           console.error('Storage metrics error:', error);
           renderError(error.message);
       }
   }

   /**
    * Render storage data in the modal
    */
   function renderStorageData() {
       if (!storageData) return;

       const inspectorBody = document.getElementById('inspectorBody');

       // Calculate totals
       const dbUsagePct = storageData.db.usage_pct;
       const dbSizeMB = storageData.db.size_mb;
       const dbLimitMB = storageData.db.limit_mb;

       // Determine health status
       let healthStatus = 'ok';
       let healthLabel = 'Healthy';
       let healthIcon = '✅';

       if (dbUsagePct >= storageData.thresholds.critical_pct) {
           healthStatus = 'critical';
           healthLabel = 'Critical';
           healthIcon = '🚨';
       } else if (dbUsagePct >= storageData.thresholds.warning_pct) {
           healthStatus = 'warning';
           healthLabel = 'Warning';
           healthIcon = '⚠️';
       }

       // Progress bar class
       const progressClass = healthStatus === 'critical' ? 'progress-critical' :
                            healthStatus === 'warning' ? 'progress-warning' : 'progress-ok';

       inspectorBody.innerHTML = `
           <!-- Overview Cards -->
           <div class="storage-overview">
               <div class="storage-card">
                   <div class="storage-card-header">
                       <span class="storage-card-title">Database Size</span>
                       <span class="storage-card-icon">💾</span>
                   </div>
                   <div class="storage-card-value">${dbSizeMB.toFixed(1)}</div>
                   <div class="storage-card-label">MB / ${dbLimitMB} MB limit</div>
                   <div class="db-health-indicator db-health-${healthStatus}">
                       ${healthIcon} ${healthLabel}
                   </div>
               </div>

               <div class="storage-card">
                   <div class="storage-card-header">
                       <span class="storage-card-title">Runtime Files</span>
                       <span class="storage-card-icon">📁</span>
                   </div>
                   <div class="storage-card-value">${storageData.files.runtime_mb.toFixed(1)}</div>
                   <div class="storage-card-label">MB</div>
               </div>

               <div class="storage-card">
                   <div class="storage-card-header">
                       <span class="storage-card-title">Registry Data</span>
                       <span class="storage-card-icon">📋</span>
                   </div>
                   <div class="storage-card-value">${storageData.files.events_mb.toFixed(1)}</div>
                   <div class="storage-card-label">MB</div>
               </div>

               <div class="storage-card">
                   <div class="storage-card-header">
                       <span class="storage-card-title">Archive</span>
                       <span class="storage-card-icon">🗂️</span>
                   </div>
                   <div class="storage-card-value">${storageData.files.archive_mb.toFixed(1)}</div>
                   <div class="storage-card-label">MB</div>
               </div>
           </div>

           <!-- Database Usage Progress -->
           <div class="storage-progress-section">
               <div class="storage-section-title">
                   <span>💾</span>
                   Database Usage
               </div>

               <div class="storage-progress-item">
                   <div class="storage-progress-header">
                       <span class="storage-progress-label">Analytics Database</span>
                       <span class="storage-progress-value">${dbUsagePct.toFixed(1)}%</span>
                   </div>
                   <div class="storage-progress-bar-container">
                       <div class="storage-progress-bar ${progressClass}" style="width: ${Math.min(dbUsagePct, 100)}%"></div>
                   </div>
               </div>
           </div>

           <!-- Storage Details -->
           <div class="storage-progress-section">
               <div class="storage-section-title">
                   <span>📊</span>
                   Storage Breakdown
               </div>

               <div class="storage-details-grid">
                   <div class="storage-detail-item">
                       <div class="storage-detail-label">Database Path</div>
                       <div class="storage-detail-value">${dbSizeMB.toFixed(2)} MB</div>
                       <div class="storage-detail-path">${storageData.db.path}</div>
                   </div>

                   <div class="storage-detail-item">
                       <div class="storage-detail-label">Total TreehopperAI</div>
                       <div class="storage-detail-value">${storageData.files.treehopper_mb.toFixed(2)} MB</div>
                       <div class="storage-detail-path">~/.treehopper</div>
                   </div>

                   <div class="storage-detail-item">
                       <div class="storage-detail-label">Runtime Directory</div>
                       <div class="storage-detail-value">${storageData.files.runtime_mb.toFixed(2)} MB</div>
                       <div class="storage-detail-path">~/.treehopper/runtime</div>
                   </div>

                   <div class="storage-detail-item">
                       <div class="storage-detail-label">Events & Logs</div>
                       <div class="storage-detail-value">${storageData.files.events_mb.toFixed(2)} MB</div>
                       <div class="storage-detail-path">~/.treehopper/registry</div>
                   </div>

                   <div class="storage-detail-item">
                       <div class="storage-detail-label">Archived Data</div>
                       <div class="storage-detail-value">${storageData.files.archive_mb.toFixed(2)} MB</div>
                       <div class="storage-detail-path">~/.treehopper/archive</div>
                   </div>

                   <div class="storage-detail-item">
                       <div class="storage-detail-label">Warning Threshold</div>
                       <div class="storage-detail-value">${storageData.thresholds.warning_pct}%</div>
                       <div class="storage-detail-path">Triggers maintenance warning</div>
                   </div>

                   <div class="storage-detail-item">
                       <div class="storage-detail-label">Critical Threshold</div>
                       <div class="storage-detail-value">${storageData.thresholds.critical_pct}%</div>
                       <div class="storage-detail-path">Triggers automatic pruning</div>
                   </div>

                   <div class="storage-detail-item">
                       <div class="storage-detail-label">Remaining Space</div>
                       <div class="storage-detail-value">${(dbLimitMB - dbSizeMB).toFixed(1)} MB</div>
                       <div class="storage-detail-path">${(100 - dbUsagePct).toFixed(1)}% available</div>
                   </div>
               </div>
           </div>

           <!-- Recommendations -->
           ${renderRecommendations(healthStatus, dbUsagePct)}
       `;

       // Update footer info
       updateFooterInfo();
   }

   /**
    * Render maintenance recommendations with CLI commands
    */

   function renderRecommendations(healthStatus, usagePct) {
    // CLI Commands HTML (used in all states)
    const cliCommandsHTML = `
        <div class="storage-section-title" style="margin-top: 20px;">
            <span>🖥️</span>
            CLI Maintenance Commands
        </div>

        <div class="cli-commands-container">
            <div class="cli-command-item">
                <div class="cli-command-header">
                    <span class="cli-command-icon">📊</span>
                    <span class="cli-command-title">Check Storage Metrics</span>
                </div>
                <div class="cli-command-code">
                    <code>treehopper admin storage</code>
                    <button class="cli-copy-btn" onclick="copyToClipboard('treehopper admin storage')" title="Copy command">
                        📋
                    </button>
                </div>
                <div class="cli-command-desc">View detailed storage metrics in terminal</div>
            </div>

            <div class="cli-command-item">
                <div class="cli-command-header">
                    <span class="cli-command-icon">🧹</span>
                    <span class="cli-command-title">Prune Database</span>
                </div>
                <div class="cli-command-code">
                    <code>treehopper admin prune-db</code>
                    <button class="cli-copy-btn" onclick="copyToClipboard('treehopper admin prune-db')" title="Copy command">
                        📋
                    </button>
                </div>
                <div class="cli-command-desc">Remove old analytics data (keeps last 7 days)</div>
            </div>

            <div class="cli-command-item">
                <div class="cli-command-header">
                    <span class="cli-command-icon">🔄</span>
                    <span class="cli-command-title">Rotate Runtime Files</span>
                </div>
                <div class="cli-command-code">
                    <code>treehopper admin rotate-files</code>
                    <button class="cli-copy-btn" onclick="copyToClipboard('treehopper admin rotate-files')" title="Copy command">
                        📋
                    </button>
                </div>
                <div class="cli-command-desc">Archive old log files (.log, .jsonl, .cancel)</div>
            </div>

            <div class="cli-command-item">
                <div class="cli-command-header">
                    <span class="cli-command-icon">💾</span>
                    <span class="cli-command-title">Snapshot Database</span>
                </div>
                <div class="cli-command-code">
                    <code>treehopper admin snapshot-db</code>
                    <button class="cli-copy-btn" onclick="copyToClipboard('treehopper admin snapshot-db')" title="Copy command">
                        📋
                    </button>
                </div>
                <div class="cli-command-desc">Create database backup snapshot</div>
            </div>

            <div class="cli-command-item">
                <div class="cli-command-header">
                    <span class="cli-command-icon">🗑️</span>
                    <span class="cli-command-title">Cleanup Old Archives</span>
                </div>
                <div class="cli-command-code">
                    <code>treehopper admin cleanup-archives</code>
                    <button class="cli-copy-btn" onclick="copyToClipboard('treehopper admin cleanup-archives')" title="Copy command">
                        📋
                    </button>
                </div>
                <div class="cli-command-desc">Remove archives older than 90 days</div>
            </div>
        </div>

        <div class="cli-info-box">
            <strong>ℹ️ Note:</strong> Run these commands in your terminal where TreehopperAI is installed.
            After running maintenance, click the Refresh button to see updated metrics.
        </div>
    `;

    // Show CLI commands in ALL states (ok, warning, critical)
    if (healthStatus === 'ok') {
        return `
            <div class="storage-progress-section">
                <div class="storage-section-title">
                    <span>✅</span>
                    System Status
                </div>
                <div class="cli-command-box cli-status-ok">
                    <strong>✅ Storage is healthy!</strong> No maintenance required at this time.
                    <div class="cli-info-text">
                        You can still run maintenance commands below if needed.
                    </div>
                </div>
                ${cliCommandsHTML}
            </div>
        `;
    }

    const urgencyClass = healthStatus === 'critical' ? 'cli-status-critical' : 'cli-status-warning';
    const urgencyIcon = healthStatus === 'critical' ? '🚨' : '⚠️';
    const urgencyText = healthStatus === 'critical' ?
        `<strong>🚨 Storage is critically full (${usagePct.toFixed(1)}%)</strong><br>Maintenance required immediately!` :
        `<strong>⚠️ Storage approaching limit (${usagePct.toFixed(1)}%)</strong><br>Consider running maintenance soon.`;

    return `
        <div class="storage-progress-section">
            <div class="storage-section-title">
                <span>${urgencyIcon}</span>
                Maintenance Required
            </div>

            <div class="cli-command-box ${urgencyClass}">
                ${urgencyText}
            </div>

            ${cliCommandsHTML}
        </div>
    `;
}

   /**
    * Copy command to clipboard
    */
   function copyToClipboard(text) {
       navigator.clipboard.writeText(text).then(() => {
           showSuccess('Command copied to clipboard!', 'Copied');
       }).catch(err => {
           console.error('Failed to copy:', err);
           showError('Failed to copy command', 'Copy Error');
       });
   }

   /**
    * Render error state
    */
   function renderError(message) {
       const inspectorBody = document.getElementById('inspectorBody');

       inspectorBody.innerHTML = `
           <div class="inspector-error">
               <div class="inspector-error-icon">⚠️</div>
               <div class="inspector-error-title">Failed to Load Storage Data</div>
               <div class="inspector-error-message">${message}</div>
               <button class="inspector-btn inspector-btn-refresh" onclick="loadStorageData()">
                   <span>🔄</span>
                   Retry
               </button>
           </div>
       `;
   }

   /**
    * Update footer information
    */
   function updateFooterInfo() {
       const footerInfo = document.getElementById('inspectorFooterInfo');
       const now = new Date();
       const timeStr = now.toLocaleTimeString();

       footerInfo.textContent = `Last updated: ${timeStr} • Auto-refresh in ${AUTO_REFRESH_SECONDS}s`;
   }

   /**
    * Refresh storage data
    */
   async function refreshStorageData() {
       const btn = document.querySelector('.inspector-btn-refresh');
       const originalContent = btn.innerHTML;

       btn.innerHTML = '<div class="inspector-spinner" style="width: 16px; height: 16px; border-width: 2px;"></div> Refreshing...';
       btn.disabled = true;

       await loadStorageData();

       btn.innerHTML = originalContent;
       btn.disabled = false;
   }

   /* ========================================
      AUTO-REFRESH
      ======================================== */

   function startAutoRefresh() {
       stopAutoRefresh(); // Clear any existing interval

       let countdown = AUTO_REFRESH_SECONDS;

       autoRefreshInterval = setInterval(() => {
           countdown--;

           if (countdown <= 0) {
               loadStorageData();
               countdown = AUTO_REFRESH_SECONDS;
           }

           const footerInfo = document.getElementById('inspectorFooterInfo');
           if (footerInfo) {
               const now = new Date();
               const timeStr = now.toLocaleTimeString();
               footerInfo.textContent = `Last updated: ${timeStr} • Auto-refresh in ${countdown}s`;
           }
       }, 1000);
   }

   function stopAutoRefresh() {
       if (autoRefreshInterval) {
           clearInterval(autoRefreshInterval);
           autoRefreshInterval = null;
       }
   }

   /* ========================================
      EVENT LISTENERS
      ======================================== */

   // Close modal when clicking outside
   document.addEventListener('click', (e) => {
       const modal = document.getElementById('storageInspectorModal');
       if (modal && e.target === modal) {
           closeStorageInspector();
       }
   });

   // Keyboard shortcuts
   document.addEventListener('keydown', (e) => {
       const modal = document.getElementById('storageInspectorModal');
       if (modal && modal.classList.contains('active')) {
           if (e.key === 'Escape') {
               closeStorageInspector();
           } else if (e.key === 'r' || e.key === 'R') {
               if (e.ctrlKey || e.metaKey) {
                   e.preventDefault();
                   refreshStorageData();
               }
           }
       }
   });

   /* ========================================
      GLOBAL EXPORTS
      ======================================== */

   window.openStorageInspector = openStorageInspector;
   window.closeStorageInspector = closeStorageInspector;
   window.refreshStorageData = refreshStorageData;
   window.copyToClipboard = copyToClipboard;

   console.log('💾 Storage Inspector loaded (Admin-only)');
