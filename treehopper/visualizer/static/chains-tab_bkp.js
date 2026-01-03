/**
 * Chain Testing Tab - JavaScript Logic
 * Add to your existing script.js or create chains-tab.js
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
       loadChainsList();
       loadRecentTests();
   }

   /**
    * Load available chains from API
    */
   async function loadChainsList() {
       try {
           showLoading('chains');

           const response = await fetch('/api/chains', {
               headers: {
                   'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
               }
           });

           if (!response.ok) throw new Error('Failed to load chains');

           const chains = await response.json();
           console.log("all chains:");
           console.log(chains);
           populateChainSelect(chains);

       } catch (error) {
           console.error('Error loading chains:', error);
           showError('Failed to load chains: ' + error.message);
       } finally {
           hideLoading('chains');
       }
   }

   /**
    * Populate chain select dropdown
    */
   function populateChainSelect(chains) {
       const select = document.getElementById('chainSelect');
       select.innerHTML = '<option value="">-- Select a chain --</option>';

       if (!chains || chains.length === 0) {
           select.innerHTML += '<option disabled>No chains available</option>';
           return;
       }

       chains.forEach(chain => {
           const option = document.createElement('option');
           option.value = chain.chain_id;
           option.textContent = `${chain.chain_name} (${chain.chain_id})`;
           option.dataset.chain = JSON.stringify(chain);
           select.appendChild(option);
       });
   }

   /**
    * Load chain details when selected
    */
   function loadChainDetails() {
       const select = document.getElementById('chainSelect');
       const selectedOption = select.options[select.selectedIndex];

       if (!selectedOption.value) {
           document.getElementById('chainInfo').style.display = 'none';
           document.getElementById('testConfigCard').style.display = 'none';
           currentChain = null;
           return;
       }

       currentChain = JSON.parse(selectedOption.dataset.chain);

       // Show chain info
       document.getElementById('chainId').textContent = currentChain.chain_id;
       document.getElementById('chainSteps').textContent = currentChain.stepCount;
       document.getElementById('chainStatus').textContent = currentChain.status || 'Active';
       document.getElementById('chainStatus').className = `status-badge ${currentChain.status?.toLowerCase() || 'running'}`;

       document.getElementById('chainInfo').style.display = 'block';
       document.getElementById('testConfigCard').style.display = 'block';

       // Load sample payload for this chain
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

       // Get first step's required inputs
       const firstStep = currentChain.steps?.[0];
       if (!firstStep || !firstStep.agents?.[0]) return;

       const firstAgent = firstStep.agents[0];
       const samplePayload = {};

       // Build sample payload from required inputs
       firstAgent.inputs?.forEach(input => {
           if (input.required !== false) {
               samplePayload[input.name] = getSampleValue(input);
           }
       });

       // Set textarea value
       const textarea = document.getElementById('testPayload');
       textarea.value = JSON.stringify(samplePayload, null, 2);
   }

   /**
    * Get sample value based on input type
    */
   function getSampleValue(input) {
       switch (input.type) {
           case 'string':
               return input.name === 'text' ? 'How do I reset my password?' :
                      input.name === 'folder' ? 'INBOX' :
                      'sample_value';
           case 'integer':
               return 10;
           case 'number':
               return 0.5;
           case 'boolean':
               return true;
           case 'object':
               if (input.name === 'email_config') {
                   return {
                       host: 'test.example.com',
                       port: 993,
                       username: 'test@test.com',
                       password: 'test123'
                   };
               }
               return {};
           case 'array':
               return [];
           default:
               return null;
       }
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
      TEST EXECUTION
      ======================================== */

   /**
    * Run chain test
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

           // Make API call
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
               const error = await response.json();
               throw new Error(error.detail || 'Chain execution failed');
           }

           const result = await response.json();
           currentTest = result;

           // Show results
           if (isAsync) {
               showTestQueued(result);
               // Poll for results
               pollTestResults(result.run_id);
           } else {
               showTestResults(result);
           }

           // Add to recent tests
           addRecentTest(result);

       } catch (error) {
           console.error('Error running test:', error);
           showTestError(error.message);
       } finally {
           // Re-enable run button
           runBtn.disabled = false;
           runBtn.innerHTML = '<span>▶️</span><span>Run Test</span>';
       }
   }

   /**
    * Show test running state
    */
   function showTestRunning() {
       document.getElementById('resultRunId').textContent = 'Initializing...';
       document.getElementById('resultTimestamp').textContent = new Date().toLocaleString();

       const statusIndicator = document.querySelector('.status-indicator');
       statusIndicator.className = 'status-indicator';
       statusIndicator.querySelector('.status-icon').textContent = '⏳';
       statusIndicator.querySelector('.status-text').textContent = 'Running...';

       document.getElementById('stepsContainer').innerHTML = '<p style="color: #94a3b8; text-align: center;">Executing chain...</p>';
       document.getElementById('rawResponse').style.display = 'none';
   }

   /**
    * Show test queued state (async)
    */
   function showTestQueued(result) {
       document.getElementById('resultRunId').textContent = result.run_id;

       const statusIndicator = document.querySelector('.status-indicator');
       statusIndicator.className = 'status-indicator';
       statusIndicator.querySelector('.status-icon').textContent = '📤';
       statusIndicator.querySelector('.status-text').textContent = 'Queued (checking results...)';
   }

   /**
    * Poll for async test results
    */
   async function pollTestResults(runId, attempts = 0, maxAttempts = 30) {
       if (attempts >= maxAttempts) {
           showTestError('Timeout waiting for results');
           return;
       }

       try {
           const response = await fetch(`/api/v1/chains/runs/${runId}`, {
               headers: {
                   'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
               }
           });

           if (!response.ok) throw new Error('Failed to fetch results');

           const result = await response.json();

           if (result.status === 'completed' || result.status === 'failed') {
               showTestResults(result);
               return;
           }

           // Still running, poll again
           setTimeout(() => pollTestResults(runId, attempts + 1, maxAttempts), 2000);

       } catch (error) {
           console.error('Error polling results:', error);
           showTestError('Failed to fetch results: ' + error.message);
       }
   }

   /**
    * Show test results
    */
   function showTestResults(result) {
       // Update run ID
       document.getElementById('resultRunId').textContent = result.run_id;

       // Update status
       const isSuccess = result.success || result.status === 'completed';
       const statusIndicator = document.querySelector('.status-indicator');
       statusIndicator.className = `status-indicator ${isSuccess ? 'success' : 'error'}`;
       statusIndicator.querySelector('.status-icon').textContent = isSuccess ? '✅' : '❌';
       statusIndicator.querySelector('.status-text').textContent = isSuccess ? 'Completed Successfully' : 'Failed';

       // Show steps
       displayStepResults(result.results || []);

       // Show raw response
       document.getElementById('rawResponse').textContent = JSON.stringify(result, null, 2);
   }

   /**
    * Display step results
    */
   function displayStepResults(steps) {
       const container = document.getElementById('stepsContainer');

       if (!steps || steps.length === 0) {
           container.innerHTML = '<p style="color: #94a3b8; text-align: center;">No step results available</p>';
           return;
       }

       container.innerHTML = steps.map((step, index) => {
           const isError = step.error || step.status === 'failed';
           return `
               <div class="step-result ${isError ? 'error' : ''}">
                   <div class="step-header">
                       <span class="step-name">
                           ${isError ? '❌' : '✅'} Step ${index + 1}: ${step.step || step.agent || 'Unknown'}
                       </span>
                       ${step.duration ? `<span class="step-duration">${step.duration}ms</span>` : ''}
                   </div>
                   <div class="step-output">${JSON.stringify(step.output || step.error || step, null, 2)}</div>
               </div>
           `;
       }).join('');
   }

   /**
    * Show test error
    */
   function showTestError(message) {
       const statusIndicator = document.querySelector('.status-indicator');
       statusIndicator.className = 'status-indicator error';
       statusIndicator.querySelector('.status-icon').textContent = '❌';
       statusIndicator.querySelector('.status-text').textContent = 'Error: ' + message;

       document.getElementById('stepsContainer').innerHTML = `
           <div style="padding: 20px; text-align: center; color: #ef4444;">
               <p><strong>Error</strong></p>
               <p style="margin-top: 8px; color: #94a3b8;">${message}</p>
           </div>
       `;
   }

   /**
    * Toggle raw response visibility
    */
   function toggleRawResponse() {
       const rawResponse = document.getElementById('rawResponse');
       const icon = document.getElementById('rawResponseIcon');

       if (rawResponse.style.display === 'none') {
           rawResponse.style.display = 'block';
           icon.textContent = '▲';
           icon.classList.add('rotated');
       } else {
           rawResponse.style.display = 'none';
           icon.textContent = '▼';
           icon.classList.remove('rotated');
       }
   }

   /**
    * Download test results
    */
   function downloadResults() {
       if (!currentTest) return;

       const blob = new Blob([JSON.stringify(currentTest, null, 2)], { type: 'application/json' });
       const url = URL.createObjectURL(blob);
       const a = document.createElement('a');
       a.href = url;
       a.download = `chain-test-${currentTest.run_id}.json`;
       document.body.appendChild(a);
       a.click();
       document.body.removeChild(a);
       URL.revokeObjectURL(url);
   }

   /* ========================================
      RECENT TESTS
      ======================================== */

   /**
    * Load recent tests from localStorage
    */
   function loadRecentTests() {
       const stored = localStorage.getItem('chain_recent_tests');
       recentTests = stored ? JSON.parse(stored) : [];
       displayRecentTests();
   }

   /**
    * Add test to recent tests
    */
   function addRecentTest(result) {
       const test = {
           run_id: result.run_id,
           chain_name: currentChain.chain_name,
           timestamp: new Date().toISOString(),
           status: result.success ? 'success' : 'failed'
       };

       recentTests.unshift(test);
       recentTests = recentTests.slice(0, 10); // Keep last 10

       localStorage.setItem('chain_recent_tests', JSON.stringify(recentTests));
       displayRecentTests();
   }

   /**
    * Display recent tests
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

       container.innerHTML = recentTests.map(test => `
           <div class="test-item" onclick="loadTestResult('${test.run_id}')">
               <div class="test-info">
                   <div class="test-run-id">${test.run_id}</div>
                   <div class="test-time">${new Date(test.timestamp).toLocaleString()}</div>
               </div>
               <span class="test-status-badge ${test.status}">${test.status}</span>
           </div>
       `).join('');
   }

   /**
    * Load a specific test result
    */
   async function loadTestResult(runId) {
       try {
           showLoading('chains');

           const response = await fetch(`/api/v1/chains/runs/${runId}`, {
               headers: {
                   'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
               }
           });

           if (!response.ok) throw new Error('Failed to load test result');

           const result = await response.json();
           currentTest = result;

           document.getElementById('testResultsCard').style.display = 'block';
           showTestResults(result);

           // Scroll to results
           document.getElementById('testResultsCard').scrollIntoView({ behavior: 'smooth' });

       } catch (error) {
           console.error('Error loading test result:', error);
           showError('Failed to load test result: ' + error.message);
       } finally {
           hideLoading('chains');
       }
   }

   /**
    * Refresh chains list
    */
   function refreshChainsList() {
       loadChainsList();
       showSuccess('Chains list refreshed');
   }

   /* ========================================
      HELPER FUNCTIONS
      ======================================== */

   function showLoading(context) {
       // Use existing loading overlay from your dashboard
       const overlay = document.querySelector('.loading-overlay');
       if (overlay) overlay.classList.add('active');
   }

   function hideLoading(context) {
       const overlay = document.querySelector('.loading-overlay');
       if (overlay) overlay.classList.remove('active');
   }

   function showError(message) {
       // Use existing notification system
       console.error(message);
       alert('Error: ' + message); // Replace with your notification system
   }

   function showSuccess(message) {
       // Use existing notification system
       console.log(message);
   }
