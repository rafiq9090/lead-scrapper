function switchTab(tab) {
    const batchBtn = document.getElementById('tab-batch-btn');
    const singleBtn = document.getElementById('tab-single-btn');
    const batchForm = document.getElementById('batch-form');
    const singleForm = document.getElementById('single-form');

    if (tab === 'batch') {
        batchBtn.classList.add('active');
        singleBtn.classList.remove('active');
        batchForm.style.display = 'block';
        singleForm.style.display = 'none';
    } else {
        singleBtn.classList.add('active');
        batchBtn.classList.remove('active');
        batchForm.style.display = 'none';
        singleForm.style.display = 'block';
    }
}

function toggleCountryChip(checkbox) {
    const label = checkbox.closest('.country-chip');
    if (checkbox.checked) {
        label.classList.add('active');
    } else {
        label.classList.remove('active');
    }
    const checked = Array.from(document.querySelectorAll('input[name="country_choice"]:checked')).map(el => el.value);
    const dropdown = document.getElementById('country-dropdown-select');
    if (dropdown) {
        if (checked.length === 1) {
            dropdown.value = checked[0];
        } else {
            dropdown.value = '';
        }
    }
}

function handleDropdownCountryChange(val) {
    const customInput = document.getElementById('custom-country-input');
    if (!val) {
        if (customInput) customInput.value = '';
        return;
    }
    let matchedChip = false;
    document.querySelectorAll('input[name="country_choice"]').forEach(cb => {
        const parent = cb.closest('.country-chip');
        if (cb.value.toLowerCase() === val.toLowerCase()) {
            cb.checked = true;
            if (parent) parent.classList.add('active');
            matchedChip = true;
        } else {
            cb.checked = false;
            if (parent) parent.classList.remove('active');
        }
    });
    if (customInput) {
        customInput.value = matchedChip ? '' : val;
    }
}

function filterByCountry(countryVal) {
    const url = new URL(window.location.href);
    if (countryVal) {
        url.searchParams.set('country', countryVal);
        url.searchParams.delete('page');
    } else {
        url.searchParams.delete('country');
    }
    window.location.href = url.toString();
}

function appendLog(message) {
    const term = document.getElementById('terminal-box');
    term.style.display = 'block';
    const line = document.createElement('div');
    line.className = 'terminal-line';
    line.innerText = `[${new Date().toLocaleTimeString()}] ${message}`;
    term.appendChild(line);
    term.scrollTop = term.scrollHeight;
}

let runningTimerInterval = null;
let batchStartTime = null;

function formatDuration(ms) {
    const totalSecs = Math.floor(ms / 1000);
    const mins = Math.floor(totalSecs / 60);
    const secs = totalSecs % 60;
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
}

function startRunningTimer() {
    if (runningTimerInterval) clearInterval(runningTimerInterval);
    batchStartTime = Date.now();
    const display = document.getElementById('running-time-display');
    const dot = document.getElementById('timer-dot');
    if (dot) dot.classList.remove('finished');
    if (display) display.innerText = '00:00';

    runningTimerInterval = setInterval(() => {
        if (!batchStartTime) return;
        const elapsedMs = Date.now() - batchStartTime;
        if (display) display.innerText = formatDuration(elapsedMs);
    }, 500);
}

function stopRunningTimer(finalDurationStr = null) {
    if (runningTimerInterval) {
        clearInterval(runningTimerInterval);
        runningTimerInterval = null;
    }
    const dot = document.getElementById('timer-dot');
    if (dot) dot.classList.add('finished');
    const display = document.getElementById('running-time-display');
    if (display) {
        if (finalDurationStr) {
            display.innerText = finalDurationStr;
        } else if (batchStartTime) {
            const elapsedSecs = ((Date.now() - batchStartTime) / 1000).toFixed(1);
            display.innerText = `${elapsedSecs}s`;
        }
    }
}

function toggleFastScrapMode(checkbox) {
    const isFast = checkbox.checked;
    const fastBadge = document.getElementById('fast-badge');
    const submitBtn = document.getElementById('batch-submit-btn');
    const fastPill = document.getElementById('fast-mode-active-pill');

    if (fastBadge) {
        if (isFast) {
            fastBadge.classList.add('active');
            fastBadge.innerText = 'Fast';
        } else {
            fastBadge.classList.remove('active');
            fastBadge.innerText = 'Standard';
        }
    }
    if (fastPill) {
        fastPill.style.display = isFast ? 'inline-block' : 'none';
    }
    if (submitBtn && !submitBtn.disabled) {
        submitBtn.innerHTML = isFast ? '<span>Launch Fast Scrape</span>' : '<span>Launch Prospector</span>';
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function escapeJs(str) {
    if (!str) return '';
    return String(str).replace(/'/g, "\\'").replace(/"/g, '\\"');
}

function createLeadRow(lead) {
    const tr = document.createElement('tr');
    tr.id = `lead-row-${lead.id}`;
    tr.style.animation = 'fadeIn 0.25s ease';

    const companyHtml = `
        <div style="font-weight: 700;"><a href="${lead.detail_url}">${escapeHtml(lead.company_name)}</a></div>
        <div class="badge">${escapeHtml(lead.audit_status_display || 'Verified')}</div>
        ${lead.country ? `<div style="font-size: 0.72rem; color: var(--accent-secondary); margin-top: 1px;">${escapeHtml(lead.country)}</div>` : ''}
        ${lead.has_website && lead.website ? `
            <div style="font-size: 0.75rem; color: var(--text-secondary); margin-top: 2px;">
                <a href="${escapeHtml(lead.website)}" target="_blank" rel="noopener noreferrer" style="color: var(--accent-secondary); text-decoration: none;">
                    ${escapeHtml(lead.domain)}
                </a>
            </div>
        ` : `
            <span class="badge badge-gap-red" style="font-size: 0.7rem; margin-top: 4px;">No website listed</span>
        `}
    `;

    const contactHtml = `
        ${lead.primary_email ? `<div style="font-weight: 600; color: var(--text-primary); font-family: monospace;">${escapeHtml(lead.primary_email)}</div>` : `<span style="color: var(--text-muted); font-style: italic;">No email found</span>`}
        ${lead.phone ? `<div style="font-size: 0.75rem; color: var(--text-secondary);">${escapeHtml(lead.phone)}</div>` : ''}
        ${lead.linkedin_url ? `<a href="${escapeHtml(lead.linkedin_url)}" target="_blank" rel="noopener noreferrer" style="font-size: 0.72rem; color: var(--accent-secondary); text-decoration: none;">LinkedIn</a>` : ''}
    `;

    const appBadge = lead.android_status === 'detected'
        ? '<span class="badge badge-gap-green">App Found</span>'
        : (lead.android_status === 'not_detected' ? '<span class="badge badge-gap-amber">Not detected</span>' : '<span class="badge">Unknown</span>');

    const chatBadge = lead.chatbot_status === 'detected'
        ? `<span class="badge badge-gap-green">${escapeHtml(lead.detected_chat_widget || 'Detected')}</span>`
        : (lead.chatbot_status === 'not_detected' ? '<span class="badge badge-gap-amber">Not detected</span>' : '<span class="badge">Unknown</span>');

    const serverMs = (lead.server_status === 'measured' || lead.server_response_time_ms > 0)
        ? `<span class="badge ${lead.server_response_time_ms > 800 ? 'badge-gap-red' : 'badge-gap-green'}">${lead.server_response_time_ms}ms</span>`
        : '<span class="badge">Unknown</span>';

    const cvAngle = lead.cv_opportunity
        ? `<span class="badge badge-pill" title="${escapeHtml(lead.cv_opportunity)}">${escapeHtml(lead.cv_opportunity.slice(0, 28))}</span>`
        : '<span style="color: var(--text-muted);">-</span>';

    const scoreClass = lead.lead_score >= 70 ? 'score-high' : '';

    tr.innerHTML = `
        <td>${companyHtml}</td>
        <td>${contactHtml}</td>
        <td>${appBadge}</td>
        <td>${chatBadge}</td>
        <td>${serverMs}</td>
        <td>${cvAngle}</td>
        <td><span class="lead-score ${scoreClass}">${lead.lead_score}</span></td>
        <td>
            <select class="status-select" onchange="updateLeadStatus('${lead.id}', this.value)">
                <option value="NEW" ${lead.status === 'NEW' ? 'selected' : ''}>New</option>
                <option value="CONTACTED" ${lead.status === 'CONTACTED' ? 'selected' : ''}>Contacted</option>
                <option value="MEETING" ${lead.status === 'MEETING' ? 'selected' : ''}>Meeting</option>
                <option value="WON" ${lead.status === 'WON' ? 'selected' : ''}>Won Client</option>
                <option value="ARCHIVED" ${lead.status === 'ARCHIVED' ? 'selected' : ''}>Archived</option>
            </select>
        </td>
        <td>
            <button class="btn btn-secondary" style="padding: 0.35rem 0.75rem; font-size: 0.78rem;" onclick="openPitchModal('${lead.id}', '${escapeJs(lead.company_name)}', '${escapeJs(lead.pitch_subject)}', '${escapeJs(lead.pitch_email)}', '${escapeJs(lead.primary_email)}')">
                View Pitch
            </button>
        </td>
    `;
    return tr;
}

function parseGoogleUrl(raw) {
    if (!raw || typeof raw !== 'string') return null;
    raw = raw.trim();
    if (!raw.startsWith('http://') && !raw.startsWith('https://')) return null;
    if (!raw.includes('google.') && !raw.includes('goo.gl')) return null;

    try {
        const url = new URL(raw);
        let extracted = '';
        if (url.searchParams.has('q')) {
            extracted = url.searchParams.get('q');
        } else if (url.searchParams.has('query')) {
            extracted = url.searchParams.get('query');
        } else if (url.pathname.includes('/maps/search/')) {
            const parts = url.pathname.split('/maps/search/')[1].split('/');
            extracted = decodeURIComponent(parts[0]).replace(/\+/g, ' ');
        } else if (url.pathname.includes('/maps/place/')) {
            const parts = url.pathname.split('/maps/place/')[1].split('/');
            extracted = decodeURIComponent(parts[0]).replace(/\+/g, ' ');
        } else if (url.pathname.includes('/search/')) {
            const parts = url.pathname.split('/search/')[1].split('/');
            extracted = decodeURIComponent(parts[0]).replace(/\+/g, ' ');
        }

        if (extracted) {
            extracted = extracted.replace(/@[-\d.,]+z?/g, '').trim();
            let niche = extracted;
            let location = '';
            const inMatch = niche.match(/\b(?:in|at|near)\s+([A-Za-z\s]+)$/i);
            if (inMatch) {
                location = inMatch[1].trim();
                niche = niche.substring(0, inMatch.index).trim();
            } else if (niche.includes(',')) {
                const parts = niche.split(',');
                niche = parts[0].trim();
                location = parts.slice(1).join(',').trim();
            }
            return { niche, location };
        }
    } catch (e) {
        console.error(e);
    }
    return null;
}

async function handleBatchProspecting(e) {
    e.preventDefault();
    const btn = document.getElementById('batch-submit-btn');
    let niche = document.getElementById('niche-input').value.trim();
    let location = document.getElementById('location-input').value.trim();

    // Automatically parse pasted Google search or maps URLs
    const parsedGoogle = parseGoogleUrl(niche);
    if (parsedGoogle && parsedGoogle.niche) {
        niche = parsedGoogle.niche;
        document.getElementById('niche-input').value = niche;
        if (parsedGoogle.location && !location) {
            location = parsedGoogle.location;
            document.getElementById('location-input').value = location;
        }
    }

    const maxResults = document.getElementById('max-results-input').value;
    const isFastScrap = document.getElementById('fast-scrape-toggle') ? document.getElementById('fast-scrape-toggle').checked : true;

    // Collect selected countries
    const checkedCountries = Array.from(document.querySelectorAll('input[name="country_choice"]:checked')).map(el => el.value);
    const customCountry = document.getElementById('custom-country-input').value.trim();
    if (customCountry && !checkedCountries.includes(customCountry)) {
        checkedCountries.push(customCountry);
    }

    // Immediately clear Identified Leads section
    const tableBody = document.getElementById('leads-table-body');
    const leadsCountBadge = document.getElementById('leads-count-badge');
    if (leadsCountBadge) {
        leadsCountBadge.innerText = '(0 shown — Scraping fresh leads...)';
    }
    if (tableBody) {
        tableBody.innerHTML = `
            <tr id="scraping-placeholder-row">
                <td colspan="9" style="text-align: center; padding: 3rem 1rem; color: var(--text-secondary);">
                    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 0.5rem;">
                        <div style="font-weight: 700; font-size: 0.92rem; color: var(--text-primary);">
                            Searching and auditing leads...
                        </div>
                        <div style="font-size: 0.8rem; color: var(--text-muted); max-width: 480px;">
                            Previous leads cleared. Newly verified businesses will appear here live.
                        </div>
                    </div>
                </td>
            </tr>
        `;
    }

    btn.disabled = true;
    btn.innerHTML = isFastScrap ? '<span>Scraping Leads...</span>' : '<span>Prospecting...</span>';
    const countryDesc = checkedCountries.length > 0 ? checkedCountries.join(', ') : 'Global';
    const modeLabel = isFastScrap ? 'Fast Mode' : 'Standard';
    appendLog(`[${modeLabel}] Launching batch for '${niche}' in '${location || 'All Locations'}' across [${countryDesc}]...`);

    const progressContainer = document.getElementById('progress-container');
    const progressText = document.getElementById('progress-text');
    const progressPercent = document.getElementById('progress-percent');
    const progressBarFill = document.getElementById('progress-bar-fill');
    const fastPill = document.getElementById('fast-mode-active-pill');

    if (progressContainer) progressContainer.style.display = 'block';
    if (fastPill) fastPill.style.display = isFastScrap ? 'inline-block' : 'none';
    startRunningTimer();

    const knownLeadIds = new Set();

    try {
        const resp = await fetch(document.body.dataset.prospectUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value },
            body: JSON.stringify({
                query: niche,
                location: location,
                countries: checkedCountries,
                max_results: maxResults,
                fast_mode: isFastScrap
            })
        });
        const data = await resp.json();

        if (data.success && data.task_id) {
            const taskId = data.task_id;
            appendLog(`Background task [${taskId}] launched (${isFastScrap ? 'Fast Mode' : 'Standard'}). Streaming live updates...`);

            const pollInterval = setInterval(async () => {
                try {
                    const statusResp = await fetch(document.body.dataset.taskUrl.replace('TASK_ID', taskId));
                    const statusData = await statusResp.json();

                    const progress = statusData.progress || 0;
                    const harvested = statusData.harvested_count || statusData.total || maxResults;
                    const target = statusData.target_total || maxResults;
                    const pct = harvested > 0 ? Math.min(Math.round((progress / harvested) * 100), 100) : 0;

                    if (harvested < target) {
                        progressText.innerText = `Auditing: ${progress} / ${harvested} verified businesses (Target: ${target} Leads) · ${statusData.current_lead || 'Scanning...'}`;
                    } else {
                        progressText.innerText = `Prospecting: ${progress} / ${target} leads (${statusData.current_lead || 'Scanning...'})`;
                    }
                    progressPercent.innerText = `${pct}%`;
                    progressBarFill.style.width = `${pct}%`;

                    // Live stream new leads into the cleared table
                    if (statusData.new_leads && statusData.new_leads.length > 0) {
                        const placeholder = document.getElementById('scraping-placeholder-row');
                        for (const lead of statusData.new_leads) {
                            if (!knownLeadIds.has(lead.id)) {
                                if (placeholder && placeholder.parentNode) {
                                    placeholder.parentNode.removeChild(placeholder);
                                }
                                knownLeadIds.add(lead.id);
                                const row = createLeadRow(lead);
                                if (tableBody) tableBody.appendChild(row);
                                if (leadsCountBadge) {
                                    leadsCountBadge.innerText = `(${knownLeadIds.size} shown · live)`;
                                }
                            }
                        }
                    }

                    if (statusData.logs && statusData.logs.length > 0) {
                        const latestLog = statusData.logs[statusData.logs.length - 1];
                        if (window.lastLoggedMsg !== latestLog) {
                            window.lastLoggedMsg = latestLog;
                            appendLog(latestLog);
                        }
                    }

                    if (!statusData.success || statusData.status === 'error') {
                        clearInterval(pollInterval);
                        stopRunningTimer();
                        appendLog(`Task failed: ${statusData.error || 'Task unavailable'}`);
                        btn.disabled = false;
                        btn.innerHTML = isFastScrap ? '<span>Launch Fast Scrape</span>' : '<span>Launch Prospector</span>';
                        return;
                    }
                    if (statusData.completed) {
                        clearInterval(pollInterval);
                        progressBarFill.style.width = '100%';
                        progressPercent.innerText = '100%';
                        const finalTime = statusData.elapsed_seconds ? `${statusData.elapsed_seconds}s` : null;
                        stopRunningTimer(finalTime ? `${finalTime}` : null);
                        const durationMsg = finalTime ? ` in ${finalTime}` : '';
                        if (leadsCountBadge) {
                            leadsCountBadge.innerText = `(${knownLeadIds.size || statusData.total_found} shown — Batch Complete)`;
                        }
                        appendLog(`Finished${durationMsg}. Saved ${statusData.total_found} leads.`);
                        btn.disabled = false;
                        btn.innerHTML = isFastScrap ? '<span>Launch Fast Scrape</span>' : '<span>Launch Prospector</span>';

                        if (statusData.batch_id) {
                            setTimeout(() => {
                                window.location.href = `/?batch=${statusData.batch_id}`;
                            }, 1800);
                        }
                    }
                } catch (pollErr) {
                    console.error(pollErr);
                }
            }, 1000);

        } else {
            stopRunningTimer();
            appendLog(`Error: ${data.error}`);
            btn.disabled = false;
            btn.innerHTML = isFastScrap ? '<span>Launch Fast Scrape</span>' : '<span>Launch Prospector</span>';
        }
    } catch (err) {
        stopRunningTimer();
        appendLog(`Network error: ${err.message}`);
        btn.disabled = false;
        btn.innerHTML = isFastScrap ? '<span>Launch Fast Scrape</span>' : '<span>Launch Prospector</span>';
    }
}

async function handleSingleAudit(e) {
    e.preventDefault();
    const btn = document.getElementById('single-submit-btn');
    const url = document.getElementById('single-url-input').value;
    const niche = document.getElementById('single-niche-input').value;

    btn.disabled = true;
    btn.innerHTML = '<span>Auditing Domain...</span>';
    appendLog(`Auditing target URL: ${url}...`);

    try {
        const resp = await fetch(document.body.dataset.auditUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value },
            body: JSON.stringify({ url: url, niche: niche })
        });
        const data = await resp.json();

        if (data.success) {
            appendLog(`Audit complete for ${data.lead.company_name}.`);
            openPitchModal(
                data.lead.id,
                data.lead.company_name,
                data.lead.pitch_subject,
                data.lead.pitch_email,
                data.lead.primary_email
            );
            btn.disabled = false;
            btn.innerHTML = '<span>Audit and Generate Pitch</span>';
            window.location.href = data.lead.detail_url;
        } else {
            appendLog(`Audit failed: ${data.error}`);
            btn.disabled = false;
            btn.innerHTML = '<span>Audit and Generate Pitch</span>';
        }
    } catch (err) {
        appendLog(`Network error: ${err.message}`);
        btn.disabled = false;
        btn.innerHTML = '<span>Audit and Generate Pitch</span>';
    }
}

async function updateLeadStatus(leadId, newStatus) {
    try {
        const response = await fetch(document.body.dataset.statusUrl.replace('/0/', `/${leadId}/`), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value },
            body: JSON.stringify({ status: newStatus })
        });
        const result = await response.json();
        if (!response.ok || !result.success) appendLog(`Status update failed: ${result.error || response.status}`);
    } catch (err) {
        console.error(err);
    }
}

function openPitchModal(id, company, subject, emailText, primaryEmail) {
    document.getElementById('modal-company-title').innerText = `Cold Outreach: ${company}`;
    document.getElementById('modal-company-email').innerText = primaryEmail ? `Recipient: ${primaryEmail}` : 'Recipient: Contact via Website or LinkedIn';
    document.getElementById('modal-subject').value = subject;
    document.getElementById('modal-body-text').innerText = emailText;
    document.getElementById('pitch-modal').style.display = 'flex';
}

function closePitchModal() {
    document.getElementById('pitch-modal').style.display = 'none';
}

function copyPitchToClipboard() {
    const subject = document.getElementById('modal-subject').value;
    const body = document.getElementById('modal-body-text').innerText;
    const fullContent = `Subject: ${subject}\n\n${body}`;

    navigator.clipboard.writeText(fullContent).then(() => {
        const btn = document.getElementById('copy-pitch-btn');
        const oldText = btn.innerText;
        btn.innerText = 'Copied to clipboard';
        btn.style.background = 'var(--accent-secondary)';
        btn.style.color = '#FFFFFF';
        setTimeout(() => {
            btn.innerText = oldText;
            btn.style.background = '';
            btn.style.color = '';
        }, 2000);
    });
}

// Theme Management (Simple clean Light / Dark toggle)
function initTheme() {
    const savedTheme = localStorage.getItem('devlead-theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeToggleBtn(savedTheme);
}

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('devlead-theme', newTheme);
    updateThemeToggleBtn(newTheme);
}

function updateThemeToggleBtn(theme) {
    const btn = document.getElementById('theme-toggle-btn');
    if (!btn) return;
    btn.innerText = theme === 'dark' ? 'Dark' : 'Light';
}

function setupGoogleUrlListener() {
    const nicheInput = document.getElementById('niche-input');
    const locInput = document.getElementById('location-input');
    if (!nicheInput) return;

    function checkAndCleanInput() {
        const val = nicheInput.value.trim();
        const parsed = parseGoogleUrl(val);
        if (parsed && parsed.niche) {
            nicheInput.value = parsed.niche;
            if (parsed.location && locInput && !locInput.value) {
                locInput.value = parsed.location;
            }
        }
    }

    nicheInput.addEventListener('input', checkAndCleanInput);
    nicheInput.addEventListener('paste', () => setTimeout(checkAndCleanInput, 20));
}

// Initialize immediately
initTheme();
setupGoogleUrlListener();
