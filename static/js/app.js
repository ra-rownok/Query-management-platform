/**
 * Multi-Database Query Management Platform - Client Application Script
 */

document.addEventListener('DOMContentLoaded', () => {
    try {
        initTargetingControls();
        initSqlEditor();
        initQuickTemplates();
        initAutoToasts();
    } catch (e) {
        console.error('Initialization error:', e);
    }
});

// Toast Notification Engine
window.showToast = function(message, type = 'info', duration = 4500, title = null) {
    try {
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

        let progressHtml = '';
        if (duration > 0) {
            progressHtml = `
                <div class="toast-progress-track">
                    <div class="toast-progress-bar" style="animation-duration: ${duration}ms !important;"></div>
                </div>
            `;
        }

        toast.innerHTML = `
            <div class="toast-icon">${icon}</div>
            <div class="toast-content">
                <div class="toast-title">${escapeHtml(defaultTitle)}</div>
                <div class="toast-message">${escapeHtml(message)}</div>
            </div>
            <button type="button" class="toast-close" aria-label="Close">&times;</button>
            ${progressHtml}
        `;

        container.appendChild(toast);
        setupToastDismiss(toast, duration);
        return toast;
    } catch (err) {
        console.error('Failed to show toast:', err);
    }
};

function setupToastDismiss(toast, duration = 4500) {
    try {
        if (!toast) return;
        let dismissTimeout;
        let remainingTime = duration;
        let startTime = Date.now();

        if (duration > 0) {
            let progressBar = toast.querySelector('.toast-progress-bar');
            if (!progressBar) {
                const track = document.createElement('div');
                track.className = 'toast-progress-track';
                track.innerHTML = `<div class="toast-progress-bar" style="animation-duration: ${duration}ms !important;"></div>`;
                toast.appendChild(track);
            } else {
                progressBar.style.setProperty('animation-duration', `${duration}ms`, 'important');
            }
        }

        function dismiss() {
            try {
                toast.classList.add('toast-hiding');
                setTimeout(() => {
                    if (toast && toast.parentNode) {
                        toast.parentNode.removeChild(toast);
                    }
                }, 280);
            } catch (e) {
                console.error('Error during toast dismissal:', e);
            }
        }

        const startTimer = () => {
            try {
                startTime = Date.now();
                dismissTimeout = setTimeout(dismiss, remainingTime);
            } catch (e) {
                console.error('Error starting toast timer:', e);
            }
        };

        const pauseTimer = () => {
            try {
                clearTimeout(dismissTimeout);
                remainingTime -= (Date.now() - startTime);
                if (remainingTime < 500) remainingTime = 500;
            } catch (e) {
                console.error('Error pausing toast timer:', e);
            }
        };

        const closeBtn = toast.querySelector('.toast-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', (e) => {
                try {
                    e.stopPropagation();
                    clearTimeout(dismissTimeout);
                    dismiss();
                } catch (err) {
                    console.error('Error in toast close handler:', err);
                }
            });
        }

        toast.addEventListener('mouseenter', pauseTimer);
        toast.addEventListener('mouseleave', () => {
            if (remainingTime > 0) startTimer();
        });

        if (duration > 0) {
            startTimer();
        }
    } catch (err) {
        console.error('Error setting up toast dismiss:', err);
    }
}

function initAutoToasts() {
    try {
        document.querySelectorAll('[data-auto-toast="true"]').forEach(toast => {
            setupToastDismiss(toast, 4500);
        });
    } catch (err) {
        console.error('Error initializing auto toasts:', err);
    }
}

// Global state
let currentTargetType = 'single'; // 'single' | 'category'
let allDatabases = [];
let allCategories = [];
let confirmModalOpenedAt = 0;

window.setTargetScope = function(targetType, targetIdentifier) {
    try {
        if (!targetType) return;
        currentTargetType = targetType;
        const targetPills = document.querySelectorAll('.target-segment-btn');
        targetPills.forEach(b => {
            if (b.dataset.targetType === targetType) {
                b.classList.add('active');
            } else {
                b.classList.remove('active');
            }
        });

        const singleSelectContainer = document.getElementById('single-db-container');
        const categorySelectContainer = document.getElementById('category-container');
        if (singleSelectContainer) singleSelectContainer.style.display = targetType === 'single' ? 'block' : 'none';
        if (categorySelectContainer) categorySelectContainer.style.display = targetType === 'category' ? 'block' : 'none';

        if (targetIdentifier && targetIdentifier !== 'None' && targetIdentifier !== 'null' && targetIdentifier !== 'undefined') {
            if (targetType === 'single') {
                const dbSelect = document.getElementById('target-db-select');
                if (dbSelect) {
                    dbSelect.value = targetIdentifier;
                }
            } else if (targetType === 'category') {
                const catSelect = document.getElementById('target-category-select');
                if (catSelect) {
                    catSelect.value = targetIdentifier;
                }
            }
        }
        updateTargetSummary();
    } catch (err) {
        console.error('Error setting target scope:', err);
    }
};

window.rerunQuery = function(queryText, targetType, targetIdentifier) {
    try {
        const editor = document.getElementById('sql-query-input');
        if (editor) {
            editor.value = queryText;
            checkEngineDialect();
            editor.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
        if (targetType) {
            window.setTargetScope(targetType, targetIdentifier);
        }
        runQuery();
    } catch (err) {
        console.error('Error in rerunQuery:', err);
        showToast('Failed to rerun query: ' + err.message, 'error');
    }
};

function initTargetingControls() {
    try {
        const singleSelectContainer = document.getElementById('single-db-container');
        const categorySelectContainer = document.getElementById('category-container');
        const targetPills = document.querySelectorAll('.target-segment-btn');
        const engineFilterSelect = document.getElementById('engine-filter-select');
        const targetDbSelect = document.getElementById('target-db-select');
        const targetCategorySelect = document.getElementById('target-category-select');

        if (!targetPills.length) return; // Not on dashboard page

        // Sync initial target type from active pill in DOM
        const initialActiveBtn = document.querySelector('.target-segment-btn.active');
        if (initialActiveBtn && initialActiveBtn.dataset.targetType) {
            currentTargetType = initialActiveBtn.dataset.targetType;
        } else {
            currentTargetType = 'single';
        }

        if (singleSelectContainer && categorySelectContainer) {
            singleSelectContainer.style.display = currentTargetType === 'single' ? 'block' : 'none';
            categorySelectContainer.style.display = currentTargetType === 'category' ? 'block' : 'none';
        }

        targetPills.forEach(btn => {
            btn.addEventListener('click', (e) => {
                try {
                    targetPills.forEach(b => b.classList.remove('active'));
                    btn.classList.add('active');
                    currentTargetType = btn.dataset.targetType;

                    if (currentTargetType === 'single') {
                        if (singleSelectContainer) singleSelectContainer.style.display = 'block';
                        if (categorySelectContainer) categorySelectContainer.style.display = 'none';
                    } else {
                        if (singleSelectContainer) singleSelectContainer.style.display = 'none';
                        if (categorySelectContainer) categorySelectContainer.style.display = 'block';
                    }
                    updateTargetSummary();
                } catch (pillErr) {
                    console.error('Error changing target type:', pillErr);
                }
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
    } catch (err) {
        console.error('Error initializing targeting controls:', err);
    }
}

function updateTargetSummary() {
    try {
        const summaryBadge = document.getElementById('target-count-badge');
        const dbTagsContainer = document.getElementById('targeted-db-tags');
        if (!summaryBadge || !window.PLATFORM_DATABASES) return;

        const dbs = window.PLATFORM_DATABASES;
        const engineFilter = document.getElementById('engine-filter-select')?.value || 'all';
        
        let matchedDbs = [];

        if (currentTargetType === 'single') {
            const selectedDbId = document.getElementById('target-db-select')?.value;
            matchedDbs = dbs.filter(d => d.id == selectedDbId);
        } else {
            const selectedCatId = document.getElementById('target-category-select')?.value;
            matchedDbs = dbs.filter(d => d.category_id == selectedCatId && d.is_enabled == 1);
        }

        if (engineFilter !== 'all') {
            matchedDbs = matchedDbs.filter(d => (d.engine || '').toLowerCase() === engineFilter.toLowerCase());
        }

        const enginesInTargets = [...new Set(matchedDbs.map(d => (d.engine || '').toUpperCase()))];
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
                    tag.innerHTML = `<strong>${escapeHtml(d.name)}</strong> <span style="opacity: 0.7;">(${escapeHtml((d.engine || '').toUpperCase())})</span> ${permBadge}`;
                    dbTagsContainer.appendChild(tag);
                });
            }
        }

        checkEngineDialect();
    } catch (err) {
        console.error('Error updating target summary:', err);
    }
}

// Engine dialect compatibility checking
let analyzeDebounceTimer = null;
function checkEngineDialect() {
    try {
        clearTimeout(analyzeDebounceTimer);
        analyzeDebounceTimer = setTimeout(() => {
            try {
                const queryText = document.getElementById('sql-query-input')?.value || '';
                const warningContainer = document.getElementById('engine-warnings-area');
                if (!warningContainer) return;

                const activeTargetBtn = document.querySelector('.target-segment-btn.active');
                if (activeTargetBtn && activeTargetBtn.dataset.targetType) {
                    currentTargetType = activeTargetBtn.dataset.targetType;
                }

                let targetId = null;
                if (currentTargetType === 'single') {
                    targetId = document.getElementById('target-db-select')?.value;
                } else {
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
                    try {
                        if (data && data.warnings && data.warnings.length > 0) {
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
                    } catch (renderErr) {
                        console.error('Error rendering engine warnings:', renderErr);
                    }
                })
                .catch(() => {});
            } catch (innerErr) {
                console.error('Error preparing query analysis:', innerErr);
            }
        }, 350);
    } catch (err) {
        console.error('Error in checkEngineDialect:', err);
    }
}

function initSqlEditor() {
    try {
        const editor = document.getElementById('sql-query-input');
        const runBtn = document.getElementById('btn-run-query');
        if (!editor || !runBtn) return;

        editor.addEventListener('input', checkEngineDialect);

        // Keyboard shortcut: Ctrl+Enter or Cmd+Enter to open confirmation modal
        editor.addEventListener('keydown', (e) => {
            try {
                if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                    e.preventDefault();
                    e.stopPropagation();
                    e.stopImmediatePropagation();
                    runQuery();
                }
            } catch (keyErr) {
                console.error('Error in editor keydown:', keyErr);
            }
        });

        // Modal keyboard shortcuts: Escape key to dismiss confirmation modal
        document.addEventListener('keydown', (e) => {
            try {
                const modal = document.getElementById('confirm-execute-modal');
                if (modal && modal.classList.contains('active')) {
                    if (e.key === 'Escape') {
                        e.preventDefault();
                        closeModal('confirm-execute-modal');
                    }
                }
            } catch (kErr) {
                console.error('Error handling modal keydown:', kErr);
            }
        });

        runBtn.addEventListener('click', runQuery);

        const clearBtn = document.getElementById('btn-clear-query');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                try {
                    editor.value = '';
                    checkEngineDialect();
                    editor.focus();
                } catch (clearErr) {
                    console.error('Error clearing editor:', clearErr);
                }
            });
        }
    } catch (err) {
        console.error('Error initializing SQL editor:', err);
    }
}

function initQuickTemplates() {
    try {
        const templateButtons = document.querySelectorAll('.btn-template');
        const editor = document.getElementById('sql-query-input');
        if (!editor) return;

        templateButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                try {
                    const sql = btn.dataset.sql;
                    if (sql) {
                        editor.value = sql.trim();
                        checkEngineDialect();
                        editor.focus();
                    }
                } catch (tErr) {
                    console.error('Error setting query template:', tErr);
                }
            });
        });
    } catch (err) {
        console.error('Error initializing quick templates:', err);
    }
}

let lastRunQueryTime = 0;
window.runQuery = runQuery;
function runQuery() {
    try {
        const now = Date.now();
        if (now - lastRunQueryTime < 350) return;
        lastRunQueryTime = now;

        const editor = document.getElementById('sql-query-input');
        if (!editor) return;
        const query = editor.value.trim();
        if (!query) {
            showToast('Please enter a SQL query to execute.', 'warning', 4000, 'Query Required');
            editor.focus();
            return;
        }

        const dbs = window.PLATFORM_DATABASES || [];
        const engineFilter = document.getElementById('engine-filter-select')?.value || 'all';
        let matchedDbs = [];

        // Always ensure currentTargetType matches the active tab in the DOM
        const activeTargetBtn = document.querySelector('.target-segment-btn.active');
        if (activeTargetBtn && activeTargetBtn.dataset.targetType) {
            currentTargetType = activeTargetBtn.dataset.targetType;
        }

        let targetSummaryText = '';
        if (currentTargetType === 'single') {
            const selectedDbId = document.getElementById('target-db-select')?.value;
            matchedDbs = dbs.filter(d => d.id == selectedDbId);
            targetSummaryText = matchedDbs.length > 0 ? `Single Database: ${matchedDbs[0].name}` : 'Single Database (None selected)';
        } else {
            const selectedCatId = document.getElementById('target-category-select')?.value;
            matchedDbs = dbs.filter(d => d.category_id == selectedCatId && d.is_enabled == 1);
            const catName = document.getElementById('target-category-select')?.selectedOptions?.[0]?.text || 'Selected Category';
            targetSummaryText = `Category: ${catName}`;
        }

        if (engineFilter !== 'all') {
            matchedDbs = matchedDbs.filter(d => (d.engine || '').toLowerCase() === engineFilter.toLowerCase());
            targetSummaryText += ` [Filter: ${engineFilter.toUpperCase()}]`;
        }

        if (matchedDbs.length === 0) {
            showToast('No active databases match current target criteria.', 'warning', 4000, 'No Target Selected');
            return;
        }

        // Open Confirmation Window before executing
        showExecutionConfirmation(query, matchedDbs, targetSummaryText);
    } catch (err) {
        console.error('Error in runQuery:', err);
        showToast(`Unexpected error preparing query: ${err.message}`, 'error');
    }
}

function showExecutionConfirmation(query, matchedDbs, targetSummaryText) {
    try {
        const modal = document.getElementById('confirm-execute-modal');
        if (!modal) {
            console.error('Confirmation modal element #confirm-execute-modal not found');
            showToast('Confirmation dialog is missing. Query was not executed.', 'error');
            return;
        }

        const targetBadge = document.getElementById('confirm-target-badge');
        const targetSummary = document.getElementById('confirm-target-summary');
        const targetChips = document.getElementById('confirm-target-chips');
        const opBanner = document.getElementById('confirm-operation-banner');
        const queryPreview = document.getElementById('confirm-query-preview');
        const warningsBox = document.getElementById('confirm-warnings-box');
        const warningsContent = document.getElementById('confirm-warnings-content');

        if (targetBadge) {
            targetBadge.textContent = `${matchedDbs.length} DB${matchedDbs.length === 1 ? '' : 's'}`;
        }
        if (targetSummary) {
            targetSummary.textContent = targetSummaryText;
        }

        if (targetChips) {
            targetChips.innerHTML = matchedDbs.map(d => {
                const engineClass = `badge-engine-${(d.engine || '').toLowerCase()}`;
                const permBadge = d.permission_level === 'read_only' 
                    ? '<span class="badge" style="background: rgba(245, 158, 11, 0.2); color: #fbbf24; font-size: 0.62rem; padding: 0.05rem 0.3rem;">READ ONLY</span>' 
                    : '<span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #34d399; font-size: 0.62rem; padding: 0.05rem 0.3rem;">R/W</span>';
                return `<span class="db-tag" style="font-size: 0.76rem;"><strong>${escapeHtml(d.name)}</strong> <span class="badge ${engineClass}" style="font-size: 0.65rem;">${escapeHtml((d.engine || '').toUpperCase())}</span> ${permBadge}</span>`;
            }).join('');
        }

        // Check if write query
        const isWrite = /\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|GRANT|REVOKE|MERGE|UPSERT)\b/i.test(query);
        if (opBanner) {
            if (isWrite) {
                opBanner.style.background = 'rgba(239, 68, 68, 0.12)';
                opBanner.style.border = '1px solid rgba(239, 68, 68, 0.35)';
                opBanner.style.color = '#f87171';
                opBanner.innerHTML = `
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink: 0;">
                        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                        <line x1="12" y1="9" x2="12" y2="13"></line>
                        <line x1="12" y1="17" x2="12.01" y2="17"></line>
                    </svg>
                    <div>
                        <strong style="display: block;">Write Operation Detected</strong>
                        <span style="font-size: 0.78rem; opacity: 0.9;">This statement will modify data or schemas across <strong>${matchedDbs.length}</strong> database node(s).</span>
                    </div>
                `;
            } else {
                opBanner.style.background = 'rgba(16, 185, 129, 0.12)';
                opBanner.style.border = '1px solid rgba(16, 185, 129, 0.35)';
                opBanner.style.color = '#34d399';
                opBanner.innerHTML = `
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink: 0;">
                        <circle cx="12" cy="12" r="10"></circle>
                        <line x1="12" y1="16" x2="12" y2="12"></line>
                        <line x1="12" y1="8" x2="12.01" y2="8"></line>
                    </svg>
                    <div>
                        <strong style="display: block;">Read-Only Parallel Execution</strong>
                        <span style="font-size: 0.78rem; opacity: 0.9;">Query will execute concurrently across <strong>${matchedDbs.length}</strong> target database node(s).</span>
                    </div>
                `;
            }
        }

        if (queryPreview) {
            queryPreview.textContent = query;
        }

        // Check for active dialect warnings
        const warningContainer = document.getElementById('engine-warnings-area');
        if (warningsBox && warningsContent) {
            if (warningContainer && warningContainer.style.display !== 'none' && warningContainer.innerHTML.trim()) {
                warningsContent.innerHTML = warningContainer.innerHTML;
                warningsBox.style.display = 'block';
            } else {
                warningsBox.style.display = 'none';
            }
        }

        confirmModalOpenedAt = Date.now();
        openModal('confirm-execute-modal');
        setTimeout(() => {
            const cancelBtn = document.getElementById('btn-cancel-confirm-execute');
            if (cancelBtn) cancelBtn.focus();
        }, 100);
    } catch (err) {
        console.error('Error showing execution confirmation:', err);
        showToast(`Could not open execution confirmation: ${err.message}`, 'error');
    }
}

window.executeConfirmedQuery = executeConfirmedQuery;
function executeConfirmedQuery() {
    closeModal('confirm-execute-modal');

    const editor = document.getElementById('sql-query-input');
    const runBtn = document.getElementById('btn-run-query');
    const resultsCard = document.getElementById('query-results-card');
    const resultsContainer = document.getElementById('db-results-container');

    try {
        if (!editor) return;
        const query = editor.value.trim();
        if (!query) return;

        const activeTargetBtn = document.querySelector('.target-segment-btn.active');
        if (activeTargetBtn && activeTargetBtn.dataset.targetType) {
            currentTargetType = activeTargetBtn.dataset.targetType;
        }

        let targetId = null;
        if (currentTargetType === 'single') {
            targetId = document.getElementById('target-db-select')?.value;
        } else {
            targetId = document.getElementById('target-category-select')?.value;
        }
        const engineFilter = document.getElementById('engine-filter-select')?.value || 'all';

        // UI Loading state
        if (runBtn) {
            runBtn.disabled = true;
            runBtn.innerHTML = `<span class="executing-spinner"></span> Executing Across Databases...`;
        }
        
        if (resultsCard) {
            resultsCard.style.display = 'block';
            resultsCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        if (resultsContainer) {
            resultsContainer.innerHTML = `
                <div style="text-align: center; padding: 3rem 1rem;">
                    <div class="executing-spinner" style="width: 32px; height: 32px; border-width: 3px; border-color: rgba(99,102,241,0.25); border-top-color: #6366f1;"></div>
                    <div style="margin-top: 1rem; font-weight: 600; color: #cbd5e1;">Executing query across selected databases simultaneously...</div>
                    <div style="color: var(--text-dim); font-size: 0.8rem; margin-top: 0.3rem;">Engine connections and transactions running concurrently</div>
                </div>
            `;
        }

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
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                throw new Error(data.error || 'Query execution failed');
            }
            return data;
        })
        .then(data => {
            try {
                renderExecutionResults(data);
            } catch (renderErr) {
                console.error('Error rendering results:', renderErr);
                showToast(`Error displaying execution results: ${renderErr.message}`, 'error');
            }
        })
        .catch(err => {
            if (resultsContainer) {
                resultsContainer.innerHTML = `
                    <div class="flash-message flash-error">
                        <strong>Execution Error:</strong> ${escapeHtml(err.message)}
                    </div>
                `;
            }
            showToast(err.message || 'Execution error encountered', 'error', 5000, 'Query Execution Error');
        })
        .finally(() => {
            if (runBtn) {
                runBtn.disabled = false;
                runBtn.innerHTML = `
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                        <polygon points="5 3 19 12 5 21 5 3"></polygon>
                    </svg>
                    Execute Query
                `;
            }
        });
    } catch (err) {
        console.error('Error in executeConfirmedQuery:', err);
        showToast(`Unexpected error starting query: ${err.message}`, 'error');
        if (runBtn) {
            runBtn.disabled = false;
            runBtn.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
                    <polygon points="5 3 19 12 5 21 5 3"></polygon>
                </svg>
                Execute Query
            `;
        }
    }
}

function renderExecutionResults(data) {
    try {
        const summaryArea = document.getElementById('results-header-summary');
        const resultsContainer = document.getElementById('db-results-container');

        const totalTargets = data.total_targets || 0;
        const successCount = data.success_count || 0;
        const failedCount = data.failed_count || 0;
        const totalDuration = data.total_duration_ms || 0;
        const results = data.results || [];

        // Summary header
        if (summaryArea) {
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
        }

        if (!resultsContainer) return;
        resultsContainer.innerHTML = '';

        if (results.length === 0) {
            resultsContainer.innerHTML = '<div class="text-dim" style="padding: 1rem;">No database executions recorded.</div>';
            return;
        }

        results.forEach((res, idx) => {
            try {
                const isSuccess = res.status === 'SUCCESS';
                const engineClass = `badge-engine-${(res.engine || '').toLowerCase()}`;
                
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
                            <span class="badge ${engineClass}">${escapeHtml((res.engine || '').toUpperCase())}</span>
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
            } catch (cardErr) {
                console.error('Error rendering individual card:', cardErr);
            }
        });

        // Store results globally for export
        window.LAST_EXECUTION_RESULTS = results;
    } catch (err) {
        console.error('Error in renderExecutionResults:', err);
    }
}

// Result Exporters
window.exportResultToCSV = function(idx) {
    try {
        const res = window.LAST_EXECUTION_RESULTS?.[idx];
        if (!res || !res.rows) {
            showToast('No data available to export to CSV.', 'warning');
            return;
        }

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
    } catch (err) {
        console.error('Error exporting to CSV:', err);
        showToast(`Export failed: ${err.message}`, 'error');
    }
};

window.exportResultToJSON = function(idx) {
    try {
        const res = window.LAST_EXECUTION_RESULTS?.[idx];
        if (!res || !res.rows) {
            showToast('No data available to export to JSON.', 'warning');
            return;
        }
        const blob = new Blob([JSON.stringify(res.rows, null, 2)], { type: 'application/json' });
        downloadBlob(blob, `${res.db_name}_result_${Date.now()}.json`);
        showToast(`Exported ${res.db_name} results to JSON`, 'info', 3000, 'Export Complete');
    } catch (err) {
        console.error('Error exporting to JSON:', err);
        showToast(`Export failed: ${err.message}`, 'error');
    }
};

function downloadBlob(blob, filename) {
    try {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    } catch (err) {
        console.error('Error downloading file:', err);
        showToast(`Download failed: ${err.message}`, 'error');
    }
}

// Modal helper
window.openModal = function(modalId) {
    try {
        const modal = document.getElementById(modalId);
        if (modal) modal.classList.add('active');
    } catch (err) {
        console.error('Error opening modal:', err);
    }
};

window.closeModal = function(modalId) {
    try {
        const modal = document.getElementById(modalId);
        if (modal) modal.classList.remove('active');
    } catch (err) {
        console.error('Error closing modal:', err);
    }
};

// Test Connection for Registry Page
window.testDbConnection = function(dbId = null, btnElement = null) {
    let btn = btnElement || (typeof event !== 'undefined' ? event?.target : null);
    let originalText = '';
    try {
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
        .then(async res => {
            const data = await res.json().catch(() => ({}));
            if (data.success) {
                showToast(`${data.message} (${data.duration_ms} ms)`, 'success', 5000, 'Connection Successful');
            } else {
                showToast(`${data.message || 'Connection failed'} (${data.duration_ms || 0} ms)`, 'error', 6000, 'Connection Failed');
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
    } catch (err) {
        console.error('Error testing connection:', err);
        showToast(`Unexpected error testing connection: ${err.message}`, 'error');
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }
};

function escapeHtml(str) {
    try {
        if (str === null || str === undefined) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    } catch (err) {
        return '';
    }
}

