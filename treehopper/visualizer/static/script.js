/**
 * SECURE API FETCH HELPER
 */
async function apiFetch(url) {
    const response = await fetch(url, {
        headers: { 'X-Requested-With': 'TreehopperDash' }
    });
    if (!response.ok) throw new Error(`API Error: ${response.status}`);
    return response.json();
}
let currentPage = 1;
const logsPerPage = 50;
const maxPages = 10;

let updateInterval;
let allLogs = [];
let runWs;
let wsEvents;

let activeFilters = {
    agentsList: "",
    chainsList: "",
    pidsList: "",
    inputFilesList: ""
};

/* --- UI HELPERS --- */

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

function closeModal(id) {
    document.getElementById(id).style.display = "none";
}

window.onclick = (e) => {
    if (e.target.classList.contains('modal')) e.target.style.display = "none";
}

/* --- THEME MANAGEMENT --- */

function toggleTheme() {
    const isLight = document.body.classList.toggle('light-mode');
    document.getElementById('themeIcon').textContent = isLight ? '🌙' : '☀️';
    localStorage.setItem('theme', isLight ? 'light' : 'dark');
}

function loadTheme() {
    if (localStorage.getItem('theme') === 'light') {
        document.body.classList.add('light-mode');
        document.getElementById('themeIcon').textContent = '🌙';
    }
}

/* --- DATA LOADING --- */

async function loadState() {
    try {
        const data = await apiFetch('/api/state');
        const statusText = document.getElementById('statusText');
        const statusMonitor = document.getElementById('liveStatus');
        statusText.textContent = 'Online';
        statusMonitor.classList.add('online'); // Starts the green blink

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

        // Update PIDs (FIXED: Added list-item class for search)
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
        statusMonitor.classList.remove('online'); // Turns off the green blink
    }
}

/* --- LOGGING SYSTEM --- */


// function renderLogs(logs) {
//     const logsContainer = document.getElementById('logsContainer');
//     const paginationContainer = document.getElementById('logPagination');

//     if (!logs?.length) {
//         logsContainer.innerHTML = '<div class="no-results">No logs match your search</div>';
//         paginationContainer.innerHTML = '';
//         return;
//     }

//     // --- PAGINATION LOGIC ---
//     const totalLogs = logs.length;
//     const totalPages = Math.min(Math.ceil(totalLogs / logsPerPage), maxPages);

//     // Safety check for bounds
//     if (currentPage > totalPages) currentPage = totalPages;
//     if (currentPage < 1) currentPage = 1;

//     const startIndex = (currentPage - 1) * logsPerPage;
//     const endIndex = startIndex + logsPerPage;
//     const paginatedLogs = logs.slice(startIndex, endIndex);

//     console.log(`📑 Rendering Page ${currentPage} of ${totalPages} (Indices ${startIndex} to ${endIndex})`);

//     // --- RENDER TABLE ---
//     let tableHTML = `<table class="log-table"><thead><tr><th>Timestamp</th><th>Level</th><th>Logger</th><th>Message</th></tr></thead><tbody>`;
//     paginatedLogs.forEach(log => {
//         const levelClass = log.level.toLowerCase();
//         tableHTML += `
//           <tr class="${['error', 'warning', 'success'].includes(levelClass) ? levelClass : ''}">
//             <td class="log-timestamp">${log.timestamp}</td>
//             <td><span class="log-level ${levelClass}">${log.level}</span></td>
//             <td class="log-logger">${escapeHtml(log.logger)}</td>
//             <td class="log-message">${escapeHtml(log.message)}</td>
//           </tr>`;
//     });
//     logsContainer.innerHTML = tableHTML + `</tbody></table>`;

//     // --- RENDER PAGINATION BUTTONS ---
//     let paginationHTML = '<span style="color: #64748b; font-size: 12px; margin-right: 10px;">Page:</span>';
//     if (totalPages > 1) {
//         for (let i = 1; i <= totalPages; i++) {
//             paginationHTML += `
//                 <button class="page-btn ${i === currentPage ? 'active' : ''}"
//                         onclick="changePage(${i})">${i}</button>`;
//         }
//     }
//     paginationContainer.innerHTML = paginationHTML;
// }

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

    // Render Table
    let tableHTML = `<table class="log-table"><thead><tr><th>Timestamp</th><th>Level</th><th>Logger</th><th>Message</th></tr></thead><tbody>`;
    paginatedLogs.forEach(log => {
        const levelClass = log.level.toLowerCase();
        tableHTML += `
          <tr class="${['error', 'warning', 'success'].includes(levelClass) ? levelClass : ''}">
            <td class="log-timestamp">${log.timestamp}</td>
            <td><span class="log-level ${levelClass}">${log.level}</span></td>
            <td class="log-logger">${escapeHtml(log.logger)}</td>
            <td class="log-message">${escapeHtml(log.message)}</td>
          </tr>`;
    });
    logsContainer.innerHTML = tableHTML + `</tbody></table>`;

    // --- RENDER PAGINATION (Aligned Right) ---
    let paginationHTML = `
        <span style="color: #64748b; font-size: 12px; margin-right: auto; padding-left: 10px;">
            Showing ${startIndex + 1}-${Math.min(endIndex, totalLogs)} of ${totalLogs}
        </span>
    `;

    if (totalPages > 1) {
        // Prev Button
        paginationHTML += `<button class="page-btn" ${currentPage === 1 ? 'disabled' : ''}
                            onclick="changePage(${currentPage - 1})">❮</button>`;

        // Page Numbers
        for (let i = 1; i <= totalPages; i++) {
            paginationHTML += `
                <button class="page-btn ${i === currentPage ? 'active' : ''}"
                        onclick="changePage(${i})">${i}</button>`;
        }

        // Next Button
        paginationHTML += `<button class="page-btn" ${currentPage === totalPages ? 'disabled' : ''}
                            onclick="changePage(${currentPage + 1})">❯</button>`;
    }

    paginationContainer.innerHTML = paginationHTML;
}

function changePage(page) {
    console.log(`🖱️ User clicked page: ${page}`);
    currentPage = page;
    filterLogs();
    // Scroll logs header into view so user sees the top of the new page
    document.querySelector('.logs-card').scrollIntoView({ behavior: 'smooth' });
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

async function loadLogs() {
    console.log("📂 Fetching logs from API...");
    try {
        const data = await apiFetch('/api/logs');
        console.log(`📥 Received ${data.length} raw log entries`);

        if (Array.isArray(data) && data.length > 0) {
            allLogs = data.map(log => {
                let ts = log.ts || 0;
                if (ts < 10000000000) ts *= 1000;
                const date = new Date(ts);
                return {
                    timestamp: isNaN(date.getTime()) ? '-' : date.toISOString().replace('T', ' ').split('.')[0],
                    level: log.level || 'INFO',
                    logger: log.logger || '-',
                    message: log.msg || JSON.stringify(log)
                };
            }).sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

            console.log("✅ Logs processed and sorted. Triggering filter/render.");
            filterLogs();
        } else {
            console.warn("⚠️ No logs returned from server.");
            document.getElementById('logsContainer').innerHTML = '<div class="empty-state">No logs available</div>';
        }
    } catch (e) {
        console.error('❌ Log Load Error:', e);
    }
}

// async function loadLogs() {
//     try {
//         const data = await apiFetch('/api/logs');
//         if (Array.isArray(data) && data.length > 0) {
//             allLogs = data.map(log => {
//                 let ts = log.ts || 0;
//                 if (ts < 10000000000) ts *= 1000;
//                 const date = new Date(ts);
//                 return {
//                     timestamp: isNaN(date.getTime()) ? '-' : date.toISOString().replace('T', ' ').split('.')[0],
//                     level: log.level || 'INFO',
//                     logger: log.logger || '-',
//                     message: log.msg || JSON.stringify(log)
//                 };
//             }).sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
//             filterLogs();
//         } else {
//             document.getElementById('logsContainer').innerHTML = '<div class="empty-state">No logs available</div>';
//         }
//     } catch (e) { console.error('Log Load Error:', e); }
// }

// function filterLogs() {
//     const term = document.getElementById('logSearch').value.toLowerCase();
//     renderLogs(!term ? allLogs : allLogs.filter(l => Object.values(l).some(v => v.toLowerCase().includes(term))));
// }



// Update this in your existing filterLogs to reset to page 1 when searching
// function filterLogs() {
//     currentPage = 1; // Reset to first page on search
//     const searchTerm = document.getElementById('logSearch').value.toLowerCase();

//     const filtered = !searchTerm
//         ? allLogs
//         : allLogs.filter(l => Object.values(l).some(v => String(v).toLowerCase().includes(searchTerm)));

//     renderLogs(filtered);
// }

function filterLogs() {
    const searchTerm = document.getElementById('logSearch').value.toLowerCase();
    console.log(`🔍 Filtering logs with term: "${searchTerm}"`);

    const filtered = !searchTerm
        ? allLogs
        : allLogs.filter(l => Object.values(l).some(v => String(v).toLowerCase().includes(searchTerm)));

    console.log(`📊 Filtered results count: ${filtered.length}`);
    renderLogs(filtered);
}


/* --- MODAL ACTIONS (Subscription/YAML) --- */
async function showSubscription() {
    try {
        const j = await apiFetch("/api/v1/sys/subscription");
        document.getElementById("subscriptionContent").textContent = `ID: ${j.subscription_id}\nCreated: ${new Date(j.created_at * 1000)}`;
        openModal("subscriptionModal");
    } catch (e) { console.error(e); }
}

async function showChainYaml(name) {
    try {
        const j = await apiFetch(`/api/v1/chains/${name}/yaml`);
        document.getElementById("chainYamlTitle").innerText = name;
        document.getElementById("chainYamlBody").textContent = j.yaml;
        openModal("chainYamlModal");
    } catch (e) { console.error(e); }
}

async function showChainFlow(name) {
    try {
        const j = await apiFetch(`/api/v1/chains/${name}/flow`);
        document.getElementById("chainFlowTitle").innerText = name;
        document.getElementById("chainFlowBody").textContent = JSON.stringify(j, null, 2);
        openModal('chainFlowModal');
    } catch (e) { console.error(e); }
}

async function showLastRun(name) {
    try {
        const j = await apiFetch(`/api/v1/chains/${name}/lastrun`);
        document.getElementById("lastRunTitle").innerText = name;
        document.getElementById("lastRunBody").textContent = JSON.stringify(j, null, 2);
        openModal('lastRunModal');
    } catch (e) { console.error(e); }
}

async function showAgentYaml(name) {
    try {
        const j = await apiFetch(`/api/v1/agents/${name}/yaml`);
        document.getElementById("agentYamlTitle").innerText = name;
        document.getElementById("agentYamlBody").textContent = j.yaml;
        openModal("agentYamlModal");
    } catch (e) { console.error(e); }
}

/* --- WEBSOCKETS (FIXED RECONNECTION) --- */

function initLiveEvents() {
    const eventsBox = document.getElementById("liveEvents");

    // Clean up existing socket before creating a new one
    if (wsEvents) {
        wsEvents.onclose = null; // Prevent the close listener from firing a retry
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
    if (!runId) return alert("Enter run_id");

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

/* --- DOWNLOAD & CLEAR --- */

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
    let csv = "Timestamp,Level,Logger,Message\n" + allLogs.map(l => `"${l.timestamp}","${l.level}","${l.logger}","${l.message.replace(/"/g, '""')}"`).join("\n");
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
    a.download = "logs.csv";
    a.click();
}

/* --- SHARED FILES --- */

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
        applyFilter('inputFilesList'); // Apply search persistence
    } catch (e) { console.error(e); }
}

/* --- SEARCH FILTER LOGIC --- */

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

/* --- INITIALIZATION --- */

function init() {
    loadTheme();
    loadState();
    loadLogs();
    loadInputFiles();
    initLiveEvents();

    updateInterval = setInterval(() => {
        loadState();
        loadInputFiles();
    }, 30000);
}

init();
