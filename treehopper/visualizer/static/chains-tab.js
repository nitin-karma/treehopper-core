/**
 * Chain Testing Tab - JavaScript Logic (UPDATED)
 * Uses new chain runtime API endpoints
 * FIXED: Shows toast when no chains are found
 */

/* ========================================
   STATE MANAGEMENT
   ======================================== */

   let currentChain = null;
   let currentTest = null;
   let recentTests = [];

   /* ========================================
      INITIALIZATION
      ======================================== */

   /**
    * Initialize chains tab when opened
    */
   function initChainsTab() {
       console.log('[Chains Tab] Initializing...');
       loadChainsList();
       loadRecentTests();
   }

   /**
    * Load available RUNNING chains from API (UPDATED)
    */
   async function loadChainsList() {
       try {
           showLoading('chains');

           // NEW: Use list-running endpoint instead of /api/chains
           const response = await fetch('/api/v1/chains/list-running', {
               headers: {
                   'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
               }
           });

           if (!response.ok) throw new Error('Failed to load running chains');

           const data = await response.json();
           console.log('[Chains Tab] Running chains:', data);

           if (data.success) {
               populateChainSelect(data.chains);
           } else {
               throw new Error('Invalid response from server');
           }

       } catch (error) {
           console.error('[Chains Tab] Error loading chains:', error);
           showError('Failed to load running chains: ' + error.message);

           // Show empty state
           const select = document.getElementById('chainSelect');
           select.innerHTML = '<option value="">-- No running chains found --</option>';
           select.innerHTML += '<option disabled>Start a chain with: th chain start <chain_name> --bg --port <PORT></option>';
       } finally {
           hideLoading('chains');
       }
   }

   /**
    * Refresh chains list
    */
   function refreshChainsList() {
       console.log('[Chains Tab] Refreshing chains list...');
       loadChainsList();
   }

   /**
    * Populate chain select dropdown (UPDATED + FIXED)
    */
   function populateChainSelect(chains) {
       const select = document.getElementById('chainSelect');
       select.innerHTML = '<option value="">-- Select a chain --</option>';

       if (!chains || chains.length === 0) {
           select.innerHTML += '<option disabled>No running chains found</option>';
           select.innerHTML += '<option disabled>Start a chain first: th chain start <name> --bg --port <PORT></option>';

           // FIXED: Show warning toast for no chains
           if (typeof Toast !== 'undefined') {
               Toast.warning('No running chains found. Start a chain first.', 'No Chains');
           }
           return;
       }

       chains.forEach(chain => {
           const option = document.createElement('option');
           option.value = chain.chain_name;

           // Display with port and status
           option.textContent = `${chain.chain_name} (Port ${chain.port})`;

           // Store all chain data
           option.dataset.chain = JSON.stringify(chain);
           option.dataset.port = chain.port;
           option.dataset.runEndpoint = chain.run_endpoint;

           select.appendChild(option);
       });

       console.log(`[Chains Tab] Populated ${chains.length} chains`);

       // Show success toast if chains loaded
       if (chains.length > 0 && typeof Toast !== 'undefined') {
           Toast.success(`Found ${chains.length} running chain${chains.length > 1 ? 's' : ''}`, 'Chains Loaded');
       }
   }

   /**
    * Load chain details when selected (UPDATED)
    */
   async function loadChainDetails() {
       const select = document.getElementById('chainSelect');
       const selectedOption = select.options[select.selectedIndex];

       if (!selectedOption.value) {
           document.getElementById('chainInfo').style.display = 'none';
           document.getElementById('testConfigCard').style.display = 'none';
           currentChain = null;
           return;
       }

       const chainData = JSON.parse(selectedOption.dataset.chain);
       currentChain = {
           chain_name: chainData.chain_name,
           chain_id: chainData.chain_id,
           port: chainData.port,
           run_endpoint: chainData.run_endpoint,
           runtime_url: chainData.runtime_url
       };

       console.log('[Chains Tab] Selected chain:', currentChain);

       // Fetch additional chain details from runtime
       try {
           const response = await fetch(`/api/v1/chains/${currentChain.chain_name}/runtime`, {
               headers: {
                   'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
               }
           });

           if (response.ok) {
               const runtimeInfo = await response.json();
               if (runtimeInfo.success) {
                   currentChain = {
                       ...currentChain,
                       ...runtimeInfo.data
                   };
                   console.log('[Chains Tab] Runtime info:', runtimeInfo.data);
               }
           }
       } catch (error) {
           console.warn('[Chains Tab] Could not fetch runtime info:', error);
       }

       // Show chain info
       document.getElementById('chainId').textContent = currentChain.chain_id || currentChain.chain_name;
       document.getElementById('chainSteps').textContent = currentChain.stepCount;
       document.getElementById('chainStatus').textContent = currentChain.runtime_status || 'Running';
       document.getElementById('chainStatus').className = `status-badge ${currentChain.runtime_status?.toLowerCase() || 'running'}`;

       document.getElementById('chainInfo').style.display = 'block';
       document.getElementById('testConfigCard').style.display = 'block';

       // Load sample payload
       loadSamplePayload();
   }

   /* ========================================
      PAYLOAD MANAGEMENT
      ======================================== */

   /**
    * Load sample payload for selected chain
    */
   function loadSamplePayload() {
       if (!currentChain) return;

       // Default sample payload (can be customized per chain)
       const samplePayload = {
           text: 'How do I reset my password?'
       };

       // Chain-specific samples
       if (currentChain.chain_name.includes('email')) {
           samplePayload.email_config = {
               host: 'test.example.com',
               port: 993,
               username: 'test@test.com',
               password: 'test123'
           };
           samplePayload.folder = 'INBOX';
           samplePayload.limit = 10;
           samplePayload.unread_only = true;
       }

       // Set textarea value
       const textarea = document.getElementById('testPayload');
       textarea.value = JSON.stringify(samplePayload, null, 2);
   }

   /**
    * Clear test form
    */
   function clearTestForm() {
       document.getElementById('testPayload').value = '';
       document.getElementById('testResultsCard').style.display = 'none';
       document.querySelector('input[name="executionMode"][value="sync"]').checked = true;
   }

   /* ========================================
      TEST EXECUTION (UPDATED)
      ======================================== */

   /**
    * Run chain test - UPDATED to use new endpoint
    */
   async function runChainTest() {
       if (!currentChain) {
           showError('Please select a chain first');
           return;
       }

       // Get payload
       const payloadText = document.getElementById('testPayload').value.trim();
       if (!payloadText) {
           showError('Please enter a request payload');
           return;
       }

       // Parse payload
       let payload;
       try {
           payload = JSON.parse(payloadText);
       } catch (error) {
           showError('Invalid JSON payload: ' + error.message);
           return;
       }

       // Get execution mode
       const executionMode = document.querySelector('input[name="executionMode"]:checked').value;
       const isAsync = executionMode === 'async';

       // Disable run button
       const runBtn = document.getElementById('runTestBtn');
       runBtn.disabled = true;
       runBtn.innerHTML = '<span>⏳</span><span>Running...</span>';

       try {
           // Show results card immediately
           document.getElementById('testResultsCard').style.display = 'block';
           showTestRunning();

           console.log(`[Chains Tab] Running chain: ${currentChain.chain_name}`);
           console.log('[Chains Tab] Payload:', payload);
           console.log('[Chains Tab] Async:', isAsync);

           // NEW: Use dashboard proxy endpoint instead of direct chain runtime
           const response = await fetch(`/api/v1/chains/${currentChain.chain_name}/run`, {
               method: 'POST',
               headers: {
                   'Content-Type': 'application/json',
                   'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
               },
               body: JSON.stringify({
                   ...payload,
                   detached: isAsync
               })
           });

           if (!response.ok) {
               const errorData = await response.json();
               console.error('[Chains Tab] Execution error:', errorData);
               throw new Error(errorData.detail || 'Chain execution failed');
           }

           const result = await response.json();
           console.log('[Chains Tab] Execution result:', result);
           currentTest = result;

           // Show results
           if (isAsync) {
               showTestQueued(result);
               // Poll for results if run_id provided
               if (result.run_id) {
                   pollTestResults(result.run_id);
               }
           } else {
               showTestResults(result);
           }

           // Add to recent tests
           addRecentTest(result);

       } catch (error) {
           console.error('[Chains Tab] Test execution error:', error);
           showTestError(error.message);
       } finally {
           // Re-enable run button
           runBtn.disabled = false;
           runBtn.innerHTML = '<span>▶️</span><span>Run Test</span>';
       }
   }

   /**
    * Poll for async test results
    */
   async function pollTestResults(runId, maxAttempts = 60) {
       let attempts = 0;

       const poll = setInterval(async () => {
           attempts++;

           if (attempts > maxAttempts) {
               clearInterval(poll);
               showTestError('Polling timeout - check logs for run_id: ' + runId);
               return;
           }

           try {
               // Try to get results from runs API
               const response = await fetch(`/api/runs/recent?limit=100`, {
                   headers: {
                       'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
                   }
               });

               if (response.ok) {
                   const runs = await response.json();
                   const run = runs.find(r => r.run_id === runId);

                   if (run && run.status === 'completed') {
                       clearInterval(poll);
                       showTestResults(run);
                   } else if (run && run.status === 'failed') {
                       clearInterval(poll);
                       showTestError('Chain execution failed: ' + (run.error || 'Unknown error'));
                   }
               }
           } catch (error) {
               console.warn('[Chains Tab] Polling error:', error);
           }
       }, 2000); // Poll every 2 seconds
   }

   /* ========================================
      RESULTS DISPLAY
      ======================================== */

   /**
    * Show test is running
    */
   function showTestRunning() {
       document.getElementById('resultRunId').textContent = 'Starting...';
       document.getElementById('resultTimestamp').textContent = new Date().toLocaleString();

       const statusDiv = document.getElementById('resultStatus');
       statusDiv.querySelector('.status-indicator').className = 'status-indicator';
       statusDiv.querySelector('.status-icon').textContent = '⏳';
       statusDiv.querySelector('.status-text').textContent = 'Running...';

       document.getElementById('stepsContainer').innerHTML = '';
       document.getElementById('rawResponse').textContent = '';
   }

   /**
    * Show test queued (async)
    */
   function showTestQueued(result) {
       document.getElementById('resultRunId').textContent = result.run_id || 'Unknown';
       document.getElementById('resultTimestamp').textContent = new Date().toLocaleString();

       const statusDiv = document.getElementById('resultStatus');
       statusDiv.querySelector('.status-indicator').className = 'status-indicator';
       statusDiv.querySelector('.status-icon').textContent = '📋';
       statusDiv.querySelector('.status-text').textContent = 'Queued - Polling for results...';

       document.getElementById('rawResponse').textContent = JSON.stringify(result, null, 2);
   }

   /**
    * Show test results
    */
   function showTestResults(result) {
       console.log('[Chains Tab] Showing results:', result);

       // Update run ID and timestamp
       document.getElementById('resultRunId').textContent = result.run_id || 'Unknown';
       document.getElementById('resultTimestamp').textContent = new Date().toLocaleString();

       // Update status
       const statusDiv = document.getElementById('resultStatus');
       const isSuccess = result.success || result.status === 'completed';

       statusDiv.querySelector('.status-indicator').className = isSuccess ?
           'status-indicator success' : 'status-indicator error';
       statusDiv.querySelector('.status-icon').textContent = isSuccess ? '✅' : '❌';
       statusDiv.querySelector('.status-text').textContent = isSuccess ?
           'Completed Successfully' : 'Execution Failed';

       // Display step results if available
       if (result.results || result.step_results) {
           displayStepResults(result.results || result.step_results);
       }

       // Display raw response
       document.getElementById('rawResponse').textContent = JSON.stringify(result, null, 2);
   }

   /**
    * Show test error
    */
   function showTestError(message) {
       const statusDiv = document.getElementById('resultStatus');
       statusDiv.querySelector('.status-indicator').className = 'status-indicator error';
       statusDiv.querySelector('.status-icon').textContent = '❌';
       statusDiv.querySelector('.status-text').textContent = 'Error: ' + message;

       document.getElementById('rawResponse').textContent = JSON.stringify({
           error: message,
           timestamp: new Date().toISOString()
       }, null, 2);
   }

   /**
    * Display step-by-step results
    */
   function displayStepResults(results) {
       const container = document.getElementById('stepsContainer');
       container.innerHTML = '';

       if (!results || typeof results !== 'object') {
           return;
       }

       Object.entries(results).forEach(([stepName, stepData]) => {
           const stepDiv = document.createElement('div');
           stepDiv.className = 'step-result';

           const headerDiv = document.createElement('div');
           headerDiv.className = 'step-header';

           const nameSpan = document.createElement('span');
           nameSpan.className = 'step-name';
           nameSpan.textContent = stepName;

           const durationSpan = document.createElement('span');
           durationSpan.className = 'step-duration';
           durationSpan.textContent = stepData.duration ? `${stepData.duration}ms` : '';

           headerDiv.appendChild(nameSpan);
           headerDiv.appendChild(durationSpan);

           const outputPre = document.createElement('pre');
           outputPre.className = 'step-output';
           outputPre.textContent = JSON.stringify(stepData, null, 2);

           stepDiv.appendChild(headerDiv);
           stepDiv.appendChild(outputPre);
           container.appendChild(stepDiv);
       });
   }

   /**
    * Toggle raw response visibility
    */
   function toggleRawResponse() {
       const raw = document.getElementById('rawResponse');
       const icon = document.getElementById('rawResponseIcon');

       if (raw.style.display === 'none') {
           raw.style.display = 'block';
           icon.classList.add('rotated');
       } else {
           raw.style.display = 'none';
           icon.classList.remove('rotated');
       }
   }

   /**
    * Download results as JSON
    */
   function downloadResults() {
       if (!currentTest) return;

       const blob = new Blob([JSON.stringify(currentTest, null, 2)], {
           type: 'application/json'
       });

       const url = URL.createObjectURL(blob);
       const a = document.createElement('a');
       a.href = url;
       a.download = `chain_test_${currentTest.run_id || Date.now()}.json`;
       a.click();
       URL.revokeObjectURL(url);
   }

   /* ========================================
      RECENT TESTS
      ======================================== */

   /**
    * Add test to recent tests
    */
   function addRecentTest(result) {
       const test = {
           run_id: result.run_id,
           chain_name: currentChain.chain_name,
           timestamp: Date.now(),
           status: result.success ? 'success' : 'failed',
           result: result
       };

       recentTests.unshift(test);
       if (recentTests.length > 10) {
           recentTests = recentTests.slice(0, 10);
       }

       // Save to localStorage
       localStorage.setItem('recentChainTests', JSON.stringify(recentTests));

       displayRecentTests();
   }

   /**
    * Load recent tests from localStorage
    */
   function loadRecentTests() {
       const stored = localStorage.getItem('recentChainTests');
       if (stored) {
           recentTests = JSON.parse(stored);
           displayRecentTests();
       }
   }

   /**
    * Display recent tests list
    */
   function displayRecentTests() {
       const container = document.getElementById('recentTestsList');

       if (recentTests.length === 0) {
           container.innerHTML = `
               <div class="empty-state">
                   <span class="empty-icon">📋</span>
                   <p>No recent tests</p>
               </div>
           `;
           return;
       }

       container.innerHTML = '';

       recentTests.forEach(test => {
           const item = document.createElement('div');
           item.className = 'test-item';
           item.onclick = () => showTestResults(test.result);

           const info = document.createElement('div');
           info.className = 'test-info';

           const runId = document.createElement('div');
           runId.className = 'test-run-id';
           runId.textContent = test.run_id || 'Unknown';

           const time = document.createElement('div');
           time.className = 'test-time';
           time.textContent = formatTimeAgo(test.timestamp);

           info.appendChild(runId);
           info.appendChild(time);

           const badge = document.createElement('span');
           badge.className = `test-status-badge ${test.status}`;
           badge.textContent = test.status;

           item.appendChild(info);
           item.appendChild(badge);
           container.appendChild(item);
       });
   }

   /**
    * Format timestamp as "X minutes ago"
    */
   function formatTimeAgo(timestamp) {
       const seconds = Math.floor((Date.now() - timestamp) / 1000);

       if (seconds < 60) return 'Just now';
       if (seconds < 3600) return `${Math.floor(seconds / 60)} minutes ago`;
       if (seconds < 86400) return `${Math.floor(seconds / 3600)} hours ago`;
       return `${Math.floor(seconds / 86400)} days ago`;
   }

   /* ========================================
      UTILITY FUNCTIONS
      ======================================== */

   /**
    * Show loading state
    */
   function showLoading(context) {
       console.log(`[Chains Tab] Loading ${context}...`);
   }

   /**
    * Hide loading state
    */
   function hideLoading(context) {
       console.log(`[Chains Tab] Loaded ${context}`);
   }

   /**
    * Show error message
    */
   function showError(message) {
       console.error('[Chains Tab] Error:', message);
       // Use toast notification instead of alert
       if (typeof Toast !== 'undefined') {
           Toast.error(message);
       } else {
           // Fallback to console if toast not available
           console.error('Toast not available:', message);
       }
   }

   // Export for use in other scripts
   window.initChainsTab = initChainsTab;
   window.loadChainDetails = loadChainDetails;
   window.runChainTest = runChainTest;
   window.clearTestForm = clearTestForm;
   window.refreshChainsList = refreshChainsList;
   window.toggleRawResponse = toggleRawResponse;
   window.downloadResults = downloadResults;
