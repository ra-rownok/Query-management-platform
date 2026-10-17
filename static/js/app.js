/**
 * Multi-Database Query Management Platform - Client Application Script
 */

document.addEventListener('DOMContentLoaded', () => {
    initTargetingControls();
    initSqlEditor();
    initQuickTemplates();
    initAutoToasts();
});

// Toast Notification Engine
window.showToast = function(message, type = 'info', duration = 4500, title = null) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        container.setAttribute('aria-live', 'polite');
        container.setAttribute('aria-atomic', 'true');
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast-item toast-${type}`;
    
    let icon = 'ℹ';
    let defaultTitle = 'Notification';
    if (type === 'success') {
        icon = '✓';
        defaultTitle = title || 'Success';
    } else if (type === 'error' || type === 'danger') {
        icon = '✕';
        defaultTitle = title || 'Error';
    } else if (type === 'warning') {
        icon = '⚠';
        defaultTitle = title || 'Warning';
    } else {
        icon = 'ℹ';
        defaultTitle = title || 'Information';
    }

    toast.innerHTML = `
        <div class="toast-icon">${icon}</div>
        <div class="toast-content">
            <div class="toast-title">${escapeHtml(defaultTitle)}</div>
            <div class="toast-message">${escapeHtml(message)}</div>
        </div>
        <button type="button" class="toast-close" aria-label="Close">&times;</button>
    `;

    container.appendChild(toast);
    setupToastDismiss(toast, duration);
    return toast;
};

function setupToastDismiss(toast, duration = 4500) {
    if (!toast) return;
    let dismissTimeout;
    let remainingTime = duration;
    let startTime = Date.now();

    function dismiss() {
        toast.classList.add('toast-hiding');
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 280);
    }

    const startTimer = () => {
        startTime = Date.now();
        dismissTimeout = setTimeout(dismiss, remainingTime);
    };

    const pauseTimer = () => {
        clearTimeout(dismissTimeout);
        remainingTime -= (Date.now() - startTime);
        if (remainingTime < 500) remainingTime = 500;
    };

    const closeBtn = toast.querySelector('.toast-close');
    if (closeBtn) {
        closeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            clearTimeout(dismissTimeout);
            dismiss();
        });
    }

    toast.addEventListener('mouseenter', pauseTimer);
    toast.addEventListener('mouseleave', () => {
        if (remainingTime > 0) startTimer();
    });

    if (duration > 0) {
        startTimer();
    }
}

function initAutoToasts() {
    document.querySelectorAll('[data-auto-toast="true"]').forEach(toast => {
        setupToastDismiss(toast, 4500);
    });
}


// Global state
let currentTargetType = 'category'; // 'single' | 'category' | 'all'
let allDatabases = [];
let allCategories = [];

function initTargetingControls() {
    const singleSelectContainer = document.getElementById('single-db-container');
    const categorySelectContainer = document.getElementById('category-container');
    const targetPills = document.querySelectorAll('.target-segment-btn');
    const engineFilterSelect = document.getElementById('engine-filter-select');
    const targetDbSelect = document.getElementById('target-db-select');
    const targetCategorySelect = document.getElementById('target-category-select');

    if (!targetPills.length) return; // Not on dashboard page

    targetPills.forEach(btn => {
        btn.addEventListener('click', (e) => {
            targetPills.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            currentTargetType = btn.dataset.targetType;

            if (currentTargetType === 'single') {
                if (singleSelectContainer) singleSelectContainer.style.display = 'block';
                if (categorySelectContainer) categorySelectContainer.style.display = 'none';
            } else if (currentTargetType === 'category') {
                if (singleSelectContainer) singleSelectContainer.style.display = 'none';
                if (categorySelectContainer) categorySelectContainer.style.display = 'block';
            } else {
                if (singleSelectContainer) singleSelectContainer.style.display = 'none';
                if (categorySelectContainer) categorySelectContainer.style.display = 'none';
            }
            updateTargetSummary();
        });
    });

    if (engineFilterSelect) {
        engineFilterSelect.addEventListener('change', updateTargetSummary);
    }
    if (targetDbSelect) {
        targetDbSelect.addEventListener('change', updateTargetSummary);
    }
    if (targetCategorySelect) {
        targetCategorySelect.addEventListener('change', updateTargetSummary);
    }

    // Initial update
    updateTargetSummary();
}

function updateTargetSummary() {
    const summaryBadge = document.getElementById('target-count-badge');
    const dbTagsContainer = document.getElementById('targeted-db-tags');
    if (!summaryBadge || !window.PLATFORM_DATABASES) return;

    const dbs = window.PLATFORM_DATABASES;
    const engineFilter = document.getElementById('engine-filter-select')?.value || 'all';
    
    let matchedDbs = [];

    if (currentTargetType === 'single') {
        const selectedDbId = document.getElementById('target-db-select')?.value;
        matchedDbs = dbs.filter(d => d.id == selectedDbId);
    } else if (currentTargetType === 'category') {
        const selectedCatId = document.getElementById('target-category-select')?.value;
        matchedDbs = dbs.filter(d => d.category_id == selectedCatId && d.is_enabled == 1);
    } else { // 'all'
        matchedDbs = dbs.filter(d => d.is_enabled == 1);
    }

    if (engineFilter !== 'all') {
        matchedDbs = matchedDbs.filter(d => d.engine.toLowerCase() === engineFilter.toLowerCase());
    }

    const enginesInTargets = [...new Set(matchedDbs.map(d => d.engine.toUpperCase()))];
    summaryBadge.textContent = `${matchedDbs.length} DB${matchedDbs.length === 1 ? '' : 's'} (${enginesInTargets.join(', ') || 'None'})`;

    if (dbTagsContainer) {
        dbTagsContainer.innerHTML = '';
        if (matchedDbs.length === 0) {
            dbTagsContainer.innerHTML = '<span class="text-dim" style="font-size: 0.78rem;">No active databases match current target criteria</span>';
        } else {
            matchedDbs.forEach(d => {
                const tag = document.createElement('span');
                tag.className = 'db-tag';
                const permBadge = d.permission_level === 'read_only' 
                    ? '<span class="badge" style="background: rgba(245, 158, 11, 0.2); color: #fbbf24; font-size: 0.65rem; padding: 0.05rem 0.35rem; margin-left: 0.25rem;">READ ONLY</span>' 
                    : '<span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #34d399; font-size: 0.65rem; padding: 0.05rem 0.35rem; margin-left: 0.25rem;">R/W</span>';
                tag.innerHTML = `<strong>${escapeHtml(d.name)}</strong> <span style="opacity: 0.7;">(${escapeHtml(d.engine.toUpperCase())})</span> ${permBadge}`;
                dbTagsContainer.appendChild(tag);
            });
        }
    }

    checkEngineDialect();
}

// Engine dialect compatibility checking
let analyzeDebounceTimer = null;
function checkEngineDialect() {
    clearTimeout(analyzeDebounceTimer);
    analyzeDebounceTimer = setTimeout(() => {
        const queryText = document.getElementById('sql-query-input')?.value || '';
        const warningContainer = document.getElementById('engine-warnings-area');
        if (!warningContainer) return;

        let targetId = null;
        if (currentTargetType === 'single') {
            targetId = document.getElementById('target-db-select')?.value;
        } else if (currentTargetType === 'category') {
            targetId = document.getElementById('target-category-select')?.value;
        }
        const engineFilter = document.getElementById('engine-filter-select')?.value || 'all';

        if (!queryText.trim()) {
            warningContainer.innerHTML = '';
            warningContainer.style.display = 'none';
            return;
        }

        fetch('/api/analyze-query', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: queryText,
                target_type: currentTargetType,
                target_id: targetId,
                engine_filter: engineFilter
            })
        })
        .then(res => res.json())
        .then(data => {
            if (data.warnings && data.warnings.length > 0) {
                warningContainer.style.display = 'block';
                warningContainer.innerHTML = `
                    <div class="engine-warning-banner">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink:0;">
                            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                            <line x1="12" y1="9" x2="12" y2="13"></line>
                            <line x1="12" y1="17" x2="12.01" y2="17"></line>
                        </svg>
                        <div>
                            <strong>Engine Dialect Warning:</strong>
                            <ul style="margin: 0.3rem 0 0 1.2rem; font-size: 0.78rem;">
                                ${data.warnings.map(w => `<li>${escapeHtml(w)}</li>`).join('')}
                            </ul>
                        </div>
                    </div>
                `;
            } else {
                warningContainer.innerHTML = '';
                warningContainer.style.display = 'none';
            }
        })
        .catch(() => {});
    }, 350);
}

function initSqlEditor() {
    const editor = document.getElementById('sql-query-input');
    const runBtn = document.getElementById('btn-run-query');
    if (!editor || !runBtn) return;

    editor.addEventListener('input', checkEngineDialect);

    // Keyboard shortcut: Ctrl+Enter or Cmd+Enter
    editor.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            runQuery();
        }
    });

    runBtn.addEventListener('click', runQuery);

    const clearBtn = document.getElementById('btn-clear-query');
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            editor.value = '';
            checkEngineDialect();
            editor.focus();
        });
    }
}

function initQuickTemplates() {
    const templateButtons = document.querySelectorAll('.btn-template');
    const editor = document.getElementById('sql-query-input');
    if (!editor) return;

    templateButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            const sql = btn.dataset.sql;
            if (sql) {
                editor.value = sql.trim();
                checkEngineDialect();
                editor.focus();
            }
        });
    });
}

window.runQuery = runQuery;
function runQuery() {
    const editor = document.getElementById('sql-query-input');
    const runBtn = document.getElementById('btn-run-query');
    const resultsCard = document.getElementById('query-results-card');
    const resultsContainer = document.getElementById('db-results-container');
    const summaryArea = document.getElementById('results-header-summary');

    if (!editor) return;
    const query = editor.value.trim();
    if (!query) {
        showToast('Please enter a SQL query to execute.', 'warning', 4000, 'Query Required');
        editor.focus();
        return;
    }

    let targetId = null;
    if (currentTargetType === 'single') {
        targetId = document.getElementById('target-db-select')?.value;
    } else if (currentTargetType === 'category') {
        targetId = document.getElementById('target-category-select')?.value;
    }
    const engineFilter = document.getElementById('engine-filter-select')?.value || 'all';

    // UI Loading state
    runBtn.disabled = true;
    runBtn.innerHTML = `<span class="executing-spinner"></span> Executing Across Databases...`;
    
    resultsCard.style.display = 'block';
    resultsCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    resultsContainer.innerHTML = `
        <div style="text-align: center; padding: 3rem 1rem;">
            <div class="executing-spinner" style="width: 32px; height: 32px; border-width: 3px; border-color: rgba(99,102,241,0.25); border-top-color: #6366f1;"></div>
            <div style="margin-top: 1rem; font-weight: 600; color: #cbd5e1;">Executing query across selected databases simultaneously...</div>
            <div style="color: var(--text-dim); font-size: 0.8rem; margin-top: 0.3rem;">Engine connections and transactions running concurrently</div>
        </div>
    `;

    fetch('/api/execute-query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            query: query,
            target_type: currentTargetType,
            target_id: targetId,
            engine_filter: engineFilter,
            max_rows: 300
        })
    })
    .then(async res => {
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.error || 'Query execution failed');
        }
        return data;
    })
    .then(data => {
        renderExecutionResults(data);
    })
    .catch(err => {
        resultsContainer.innerHTML = `
            <div class="flash-message flash-error">
                <strong>Execution Error:</strong> ${escapeHtml(err.message)}
            </div>
        `;
    })
    .finally(() => {
        runBtn.disabled = false;
        runBtn.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                <polygon points="5 3 19 12 5 21 5 3"></polygon>
            </svg>
            Execute Query
        `;
    });
}

function renderExecutionResults(data) {
    const summaryArea = document.getElementById('results-header-summary');
    const resultsContainer = document.getElementById('db-results-container');

    const totalTargets = data.total_targets || 0;
    const successCount = data.success_count || 0;
    const failedCount = data.failed_count || 0;
    const totalDuration = data.total_duration_ms || 0;
    const results = data.results || [];

    // Summary header
    summaryArea.innerHTML = `
        <div style="display: flex; align-items: center; gap: 0.75rem;">
            <h3 style="font-size: 1.15rem; font-weight: 700;">Execution Summary</h3>
            <span class="badge ${failedCount === 0 ? 'badge-status-success' : (successCount > 0 ? 'badge-status-partial' : 'badge-status-failed')}">
                ${failedCount === 0 ? 'ALL SUCCESSFUL' : (successCount > 0 ? 'PARTIAL SUCCESS' : 'ALL FAILED')}
            </span>
        </div>
        <div class="summary-stat-chips">
            <div class="stat-chip">
                <span style="color: var(--text-dim);">Targets:</span>
                <span class="val">${totalTargets}</span>
            </div>
            <div class="stat-chip" style="border-color: rgba(16, 185, 129, 0.4);">
                <span style="color: #34d399;">✓ Succeeded:</span>
                <span class="val" style="color: #34d399;">${successCount}</span>
            </div>
            <div class="stat-chip" style="border-color: rgba(239, 68, 68, 0.4);">
                <span style="color: #f87171;">✗ Failed:</span>
                <span class="val" style="color: #f87171;">${failedCount}</span>
            </div>
            <div class="stat-chip">
                <span style="color: var(--text-dim);">Duration:</span>
                <span class="val">${totalDuration} ms</span>
            </div>
        </div>
    `;

    resultsContainer.innerHTML = '';

    if (results.length === 0) {
        resultsContainer.innerHTML = '<div class="text-dim" style="padding: 1rem;">No database executions recorded.</div>';
        return;
    }

    results.forEach((res, idx) => {
        const isSuccess = res.status === 'SUCCESS';
        const engineClass = `badge-engine-${res.engine.toLowerCase()}`;
        
        const card = document.createElement('div');
        card.className = `db-result-box ${isSuccess ? 'status-success-box' : 'status-failed-box'}`;

        let contentHtml = '';

        if (isSuccess) {
            if (res.is_select) {
                // Table of rows
                const cols = res.columns || [];
                const rows = res.rows || [];

                let tableHeaderHtml = cols.map(c => `<th>${escapeHtml(c)}</th>`).join('');
                let tableRowsHtml = '';

                if (rows.length === 0) {
                    tableRowsHtml = `<tr><td colspan="${cols.length || 1}" style="text-align: center; color: var(--text-dim); padding: 1.5rem;">Query executed successfully with 0 rows returned.</td></tr>`;
                } else {
                    tableRowsHtml = rows.map(r => {
                        const cells = cols.map(c => {
                            const val = r[c];
                            return `<td>${val === null ? '<span style="color: #64748b; font-style: italic;">NULL</span>' : escapeHtml(String(val))}</td>`;
                        }).join('');
                        return `<tr>${cells}</tr>`;
                    }).join('');
                }

                contentHtml = `
                    <div style="padding: 0.6rem 1.25rem; display: flex; align-items: center; justify-content: space-between; background: rgba(0,0,0,0.15);">
                        <span style="font-size: 0.8rem; color: var(--text-muted);">${res.row_count} rows retrieved</span>
                        <div style="display: flex; gap: 0.5rem;">
                            <button class="btn btn-secondary btn-sm" onclick="exportResultToCSV(${idx})">Export CSV</button>
                            <button class="btn btn-secondary btn-sm" onclick="exportResultToJSON(${idx})">Export JSON</button>
                        </div>
                    </div>
                    <div class="table-responsive">
                        <table class="data-table">
                            <thead><tr>${tableHeaderHtml}</tr></thead>
                            <tbody>${tableRowsHtml}</tbody>
                        </table>
                    </div>
                `;
            } else {
                contentHtml = `
                    <div style="padding: 1.25rem; color: #34d399; font-size: 0.9rem; display: flex; align-items: center; gap: 0.5rem;">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                            <polyline points="20 6 9 17 4 12"></polyline>
                        </svg>
                        <span>Command executed successfully. <strong>${res.affected_rows}</strong> row(s) affected.</span>
                    </div>
                `;
            }
        } else {
            // Failed: show reason and error message
            contentHtml = `
                <div class="error-detail-box">
                    <div class="error-title">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="10"></circle>
                            <line x1="12" y1="8" x2="12" y2="12"></line>
                            <line x1="12" y1="16" x2="12.01" y2="16"></line>
                        </svg>
                        Failure Reason & Exception Details (${escapeHtml(res.error_type || 'Execution Error')}):
                    </div>
                    <div class="error-text">${escapeHtml(res.error_message || 'Unknown database execution failure.')}</div>
                </div>
            `;
        }

        card.innerHTML = `
            <div class="db-result-header">
                <div class="db-result-title">
                    <span class="badge ${engineClass}">${escapeHtml(res.engine.toUpperCase())}</span>
                    <span class="db-name-title">${escapeHtml(res.db_name)}</span>
                    <span class="db-tag" style="background: rgba(99,102,241,0.15); color: #818cf8;">${escapeHtml(res.category_name)}</span>
                </div>
                <div class="db-result-meta">
                    <span style="font-size: 0.8rem; color: var(--text-dim); font-family: var(--font-mono);">${res.duration_ms} ms</span>
                    <span class="badge ${isSuccess ? 'badge-status-success' : 'badge-status-failed'}">
                        ${isSuccess ? 'SUCCESS' : 'FAILED'}
                    </span>
                </div>
            </div>
            ${contentHtml}
        `;

        resultsContainer.appendChild(card);
    });

    // Store results globally for export
    window.LAST_EXECUTION_RESULTS = results;
}

// Result Exporters
window.exportResultToCSV = function(idx) {
    const res = window.LAST_EXECUTION_RESULTS?.[idx];
    if (!res || !res.rows) return;

    const cols = res.columns || [];
    const csvRows = [];
    csvRows.push(cols.map(c => `"${String(c).replace(/"/g, '""')}"`).join(','));

    res.rows.forEach(row => {
        const line = cols.map(c => {
            const v = row[c] === null ? '' : String(row[c]);
            return `"${v.replace(/"/g, '""')}"`;
        }).join(',');
        csvRows.push(line);
    });

    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' });
    downloadBlob(blob, `${res.db_name}_result_${Date.now()}.csv`);
    showToast(`Exported ${res.db_name} results to CSV`, 'info', 3000, 'Export Complete');
};

window.exportResultToJSON = function(idx) {
    const res = window.LAST_EXECUTION_RESULTS?.[idx];
    if (!res || !res.rows) return;
    const blob = new Blob([JSON.stringify(res.rows, null, 2)], { type: 'application/json' });
    downloadBlob(blob, `${res.db_name}_result_${Date.now()}.json`);
    showToast(`Exported ${res.db_name} results to JSON`, 'info', 3000, 'Export Complete');
};

function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// Modal helper
window.openModal = function(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.add('active');
};

window.closeModal = function(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.remove('active');
};

// Test Connection for Registry Page
window.testDbConnection = function(dbId = null, btnElement = null) {
    const btn = btnElement || (typeof event !== 'undefined' ? event?.target : null);
    let originalText = '';
    if (btn) {
        originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = 'Testing...';
    }

    let payload = {};
    if (dbId) {
        payload = { db_id: dbId };
    } else {
        payload = {
            name: document.getElementById('add-db-name')?.value,
            engine: document.getElementById('add-db-engine')?.value,
            host: document.getElementById('add-db-host')?.value,
            port: document.getElementById('add-db-port')?.value,
            database_name: document.getElementById('add-db-database')?.value,
            username: document.getElementById('add-db-username')?.value,
            password: document.getElementById('add-db-password')?.value,
            options: document.getElementById('add-db-options')?.value
        };
    }

    fetch('/api/test-connection', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            showToast(`${data.message} (${data.duration_ms} ms)`, 'success', 5000, 'Connection Successful');
        } else {
            showToast(`${data.message} (${data.duration_ms} ms)`, 'error', 6000, 'Connection Failed');
        }
    })
    .catch(err => {
        showToast(`Connection test error: ${err.message}`, 'error', 6000, 'Connection Test Error');
    })
    .finally(() => {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    });
};

function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
