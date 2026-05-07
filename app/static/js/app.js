let refreshTimer = null;
let currentIcao = null;
let isRefreshing = false;

document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

function initApp() {
    const searchBtn = document.getElementById('search-btn');
    const searchInput = document.getElementById('airport-search');
    const logo = document.querySelector('.logo');
    const refreshBtn = document.getElementById('refresh-btn');
    
    // Apply initial theme from cache
    const initialSettings = utils.getSettings();
    utils.applyTheme(initialSettings.theme_mode);

    
    logo.addEventListener('click', (e) => {
        e.preventDefault();
        const settings = utils.getSettings();
        window.location.hash = `/airport/${settings.default_airport}`;
    });

    searchBtn.addEventListener('click', () => {
        const val = searchInput.value.trim().toUpperCase();
        if (val) {
            navigateToAirport(val);
        }
    });

    searchInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            const val = searchInput.value.trim().toUpperCase();
            if (val) navigateToAirport(val);
        }
    });

    // Autocomplete implementation
    setupAutocomplete(searchInput);

    refreshBtn.addEventListener('click', () => {
        refreshCurrentView();
    });

    window.addEventListener('hashchange', handleRoute);
    
    // Visibility change handler for refresh pausing
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            stopRefreshTimer();
        } else {
            startRefreshTimer();
        }
    });

    handleRoute();
}

function setupAutocomplete(input) {
    const container = document.createElement('div');
    container.className = 'autocomplete-suggestions';
    container.style.display = 'none';
    input.parentNode.appendChild(container);

    let debounceTimer = null;

    input.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        const q = input.value.trim();
        if (q.length < 2) {
            container.style.display = 'none';
            return;
        }

        debounceTimer = setTimeout(async () => {
            try {
                const results = await api.searchAirports(q);
                if (results.length > 0) {
                    container.innerHTML = results.map(a => `
                        <div class="suggestion-item" data-icao="${a.icao}">
                            <span class="suggestion-icao">${a.icao}</span>
                            <span class="suggestion-name">${a.name}</span>
                        </div>
                    `).join('');
                    container.style.display = 'block';
                } else {
                    container.style.display = 'none';
                }
            } catch (e) {
                console.error('Search failed', e);
            }
        }, 300);
    });

    container.addEventListener('click', (e) => {
        const item = e.target.closest('.suggestion-item');
        if (item) {
            const icao = item.dataset.icao;
            input.value = icao;
            container.style.display = 'none';
            navigateToAirport(icao);
        }
    });

    // Close on click outside
    document.addEventListener('click', (e) => {
        if (!input.contains(e.target) && !container.contains(e.target)) {
            container.style.display = 'none';
        }
    });
}

function startRefreshTimer() {
    stopRefreshTimer();
    // Temporarily disabled for stability
}

function stopRefreshTimer() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
}

function navigateToAirport(icao) {
    utils.addRecentAirport(icao);
    api.addRecent(icao).catch(e => console.warn('Failed to sync recent to backend', e));
    window.location.hash = `/airport/${icao}`;
}

function updateNavLinks(icao) {
    const nav = document.getElementById('main-nav');
    const dashboardLink = document.getElementById('nav-home');
    const settings = utils.getSettings();
    
    // Always show nav if an airport is specified or if default_airport is set
    if (!icao && !settings.default_airport) {
        nav.style.display = 'none';
        return;
    }
    nav.style.display = 'flex';
    
    // Dashboard link behavior: current airport if exists, else default
    const targetIcao = icao || settings.default_airport;
    dashboardLink.href = `#/airport/${targetIcao}`;

    // Sub-nav links
    const links = {
        'nav-brief': 'brief',
        'nav-weather': 'weather',
        'nav-runways': 'runways',
        'nav-alternates': 'alternates',
        'nav-hazards': 'hazards'
    };

    for (const [id, view] of Object.entries(links)) {
        const el = document.getElementById(id);
        if (el) el.href = `#/airport/${targetIcao}/${view}`;
    }
}

async function handleRoute() {
    const hash = window.location.hash.substring(1) || '/';
    const content = document.getElementById('app-content');
    const statusBar = document.getElementById('status-bar');
    
    // 1. Sync settings from backend
    let settings;
    let backendSuccess = false;
    try {
        settings = await api.getSettings();
        console.log('Settings loaded from backend', settings);
        utils.saveSettings(settings); // cache to local
        backendSuccess = true;
    } catch (e) {
        console.warn('Using cached settings');
        settings = utils.getSettings();
    }
    
    // Direct airport route check - bypass setup redirect
    if (hash.startsWith('/airport/')) {
        const parts = hash.split('/');
        const icao = parts[2];
        currentIcao = icao;
        updateNavLinks(icao);
        
        content.innerHTML = '<div class="loading">Loading airport data...</div>';
        
        await refreshCurrentView();
        return;
    }

    // Check for first-run
    // Show setup if no default airport is configured
    if (!settings.default_airport && hash !== '/settings' && hash !== '/search') {
        console.log("Showing first-run setup: no default airport");
        stopRefreshTimer();
        renderFirstRun(content);
        return;
    }

    if (hash === '/') {
        console.log(`Routing to dashboard: ${settings.default_airport}`);
        window.location.hash = `/airport/${settings.default_airport}`;
        return;
    }

    if (hash === '/search') {
        stopRefreshTimer();
        statusBar.style.display = 'none';
        currentIcao = null;
        updateNavLinks(null);
        renderSearch(content);
        return;
    }

    if (hash === '/settings') {
        stopRefreshTimer();
        statusBar.style.display = 'none';
        // Keep currentIcao for sub-nav persistence
        updateNavLinks(currentIcao);
        renderSettings(content);
        return;
    }
}

async function refreshCurrentView() {
    if (isRefreshing) return;
    
    const hash = window.location.hash.substring(1) || '/';
    if (!hash.startsWith('/airport/')) return;
    
    const parts = hash.split('/');
    const icao = parts[2];
    const view = parts[3] || 'dashboard';
    
    const content = document.getElementById('app-content');
    const statusBar = document.getElementById('status-bar');
    const lastUpdatedEl = document.getElementById('last-updated');

    isRefreshing = true;
    try {
        if (view === 'dashboard') {
            await renderDashboard(content, icao);
        } else if (view === 'brief') {
            await renderFullBrief(content, icao);
        } else if (view === 'weather') {
            await renderDetailedWeather(content, icao);
        } else if (view === 'runways') {
            await renderDetailedRunways(content, icao);
        } else if (view === 'alternates') {
            await renderDetailedAlternates(content, icao);
        } else if (view === 'hazards') {
            await renderDetailedHazards(content, icao);
        } else if (view === 'directory') {
            await renderDetailedDirectory(content, icao);
        }

        // Update status bar
        lastUpdatedEl.innerText = `Last updated: ${new Date().toLocaleTimeString()}`;
        statusBar.style.display = 'flex';
        
        // Re-start timer for this page
        startRefreshTimer();

    } catch (e) {
        console.error(e);
        stopRefreshTimer();
        statusBar.style.display = 'none';
        
        if (e.status === 404) {
            content.innerHTML = `
                <div class="card" style="max-width: 600px; margin: 2rem auto; text-align: center;">
                    <h2>Airport Not Found</h2>
                    <p>The airport <strong>${icao}</strong> was not found in our database.</p>
                    <p style="font-size: 0.9rem; color: var(--text-muted);">Please verify the ICAO code and try again.</p>
                    <br>
                    <button onclick="window.location.hash = '/search'" class="chip info" style="border:none; padding: 0.5rem 1rem; cursor:pointer;">Return to Search</button>
                </div>
            `;
        } else {
            content.innerHTML = `
                <div class="card" style="max-width: 600px; margin: 2rem auto; text-align: center;">
                    <h2>Unable to load airport data</h2>
                    <p>Something went wrong while fetching data for <strong>${icao}</strong>.</p>
                    <div style="background: var(--danger-bg); color: var(--danger-text); padding: 1rem; border-radius: 4px; text-align: left; margin-top: 1rem; font-family: monospace; font-size: 0.85rem; border: 1px solid var(--danger-border);">
                        <strong>Technical Details:</strong><br>
                        Status: ${e.status || 'Network Error'}<br>
                        Endpoint: ${e.url || 'N/A'}<br>
                        Message: ${e.message || 'Unknown failure'}
                    </div>
                    <br>
                    <button onclick="window.location.hash = '/'" class="chip info" style="border:none; padding: 0.5rem 1rem; cursor:pointer;">Return to Dashboard</button>
                </div>
            `;
        }
    } finally {
        isRefreshing = false;
    }
}

function renderSearch(container) {
    const recent = utils.getRecentAirports();
    let recentHtml = '';
    if (recent.length > 0) {
        recentHtml = `
            <div style="margin-top: 2rem;">
                <p>Recent Airports</p>
                <div class="recent-airports">
                    ${recent.map(a => `<div class="recent-chip" onclick="navigateToAirport('${a}')">${a}</div>`).join('')}
                </div>
            </div>
        `;
    }

    container.innerHTML = `
        <div class="home-container">
            <h1>Airport Search</h1>
            <div class="home-search">
                <input type="text" id="home-search-input" placeholder="Enter Airport ICAO (e.g. KAGC)">
                <button id="home-search-btn">Open Dashboard</button>
            </div>
            <p style="color: var(--text-muted); font-size: 0.9rem;">
                Try: KAGC, KPIT, KERI, KAVP
            </p>
            ${recentHtml}
        </div>
    `;

    const btn = document.getElementById('home-search-btn');
    const input = document.getElementById('home-search-input');
    
    const go = () => {
        const val = input.value.trim().toUpperCase();
        if (val) navigateToAirport(val);
    };

    btn.addEventListener('click', go);
    input.addEventListener('keypress', (e) => { if (e.key === 'Enter') go(); });
}

function renderFirstRun(container) {
    container.innerHTML = `
        <div class="home-container">
            <h1>Welcome to AirfieldOps</h1>
            <p>To get started, please choose your default airport.</p>
            <div class="home-search" style="position: relative;">
                <input type="text" id="setup-search" placeholder="Enter Airport ICAO or Name (e.g. KAGC)" autocomplete="off">
                <button id="setup-save-btn" disabled>Save and Start</button>
            </div>
            <div id="setup-error" style="color: red; margin-top: 10px; display: none;"></div>
            <p style="color: var(--text-muted); font-size: 0.85rem; margin-top: 1rem;">
                This can be changed later in Settings.
            </p>
        </div>
    `;

    const input = document.getElementById('setup-search');
    const btn = document.getElementById('setup-save-btn');
    const errorEl = document.getElementById('setup-error');
    setupAutocomplete(input);

    input.addEventListener('input', () => {
        btn.disabled = input.value.trim().length < 3;
        errorEl.style.display = 'none';
    });

    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !btn.disabled) {
            btn.click();
        }
    });

    btn.addEventListener('click', async () => {
        const icao = input.value.trim().toUpperCase();
        try {
            // Validate airport exists
            await api.getDirectory(icao);
            
            const defaults = {
                default_airport: icao,
                alternate_radius_nm: 75,
                refresh_interval_seconds: 300
            };
            
            // Save to backend
            await api.updateSettings(defaults);
            
            // Confirm from backend
            const updated = await api.getSettings();
            if (updated.default_airport !== icao) {
                throw new Error("Backend confirmation failed");
            }
            
            utils.saveSettings(updated);
            navigateToAirport(icao);
        } catch (e) {
            errorEl.innerText = `Failed to save ${icao}. Verify it is a valid airport.`;
            errorEl.style.display = 'block';
        }
    });
}

async function renderDashboard(container, icao) {
    // Single aggregate call
    const data = await api.getDashboard(icao);
    const { brief, weather, runways, alternates: alts, hazards, airport: dir } = data;

    container.innerHTML = `
        <div class="page-header" style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div>
                <h1>${icao} - ${dir.name}</h1>
                <div style="font-size: 0.9rem; color: var(--text-muted);">Dashboard Snapshot • ${utils.formatDate(new Date())}</div>
            </div>
            <button id="dashboard-set-default" class="chip info" style="border:none; padding: 0.5rem 1rem; cursor:pointer;">Set as Default</button>
        </div>
        <div id="dashboard-set-default-msg" style="text-align: right; color: var(--success); font-size: 0.85rem; margin-top: -0.5rem; margin-bottom: 1rem; display: none;">Saved!</div>
        <div class="grid">
            ${cards.renderBriefCard(brief)}
            ${cards.renderWeatherCard(weather)}
            ${cards.renderRunwaysCard(runways)}
            ${cards.renderHazardsCard(hazards)}
            ${cards.renderAlternatesCard(alts, icao)}
            ${cards.renderDirectoryCard(dir)}
            ${cards.renderOfficialResourcesCard(icao)}
        </div>
    `;

    document.getElementById('dashboard-set-default').addEventListener('click', async () => {
        try {
            const settings = utils.getSettings();
            const newSettings = { ...settings, default_airport: icao };
            await api.updateSettings(newSettings);
            const updated = await api.getSettings();
            utils.saveSettings(updated);
            const msgEl = document.getElementById('dashboard-set-default-msg');
            msgEl.style.display = 'block';
            setTimeout(() => { msgEl.style.display = 'none'; }, 3000);
        } catch (e) {
            alert('Failed to save default airport.');
        }
    });
}

async function renderFullBrief(container, icao) {
    const data = await api.getBrief(icao);
    container.innerHTML = `
        <div class="page-header">
            <h1>Operational Brief: ${icao}</h1>
            <a href="#/airport/${icao}">← Return to Dashboard</a>
        </div>
        <div class="card" style="max-width: 800px; margin: 0 auto;">
            <h2>Airport Snapshot</h2>
            ${utils.renderWarnings(data.warnings)}
            <div class="grid" style="grid-template-columns: 1fr 1fr; margin-bottom: 2rem;">
                <div>
                    <strong>Conditions</strong>
                    <div style="margin-top: 0.5rem;">Rules: ${utils.getFlightCategoryChip(data.condition.flight_category)}</div>
                    <div>Weather Risk: ${utils.getRiskLevelChip(data.condition.weather_risk)}</div>
                    <div>Hazard Risk: ${utils.getRiskLevelChip(data.condition.hazard_risk)}</div>
                </div>
                <div>
                    <strong>Favored Runway</strong>
                    <div style="font-size: 1.5rem; font-weight: bold; color: var(--accent);">${data.favored_runway.end || 'None'}</div>
                    <div style="font-size: 0.9rem;">${data.favored_runway.reason}</div>
                </div>
            </div>

            <div style="margin-bottom: 2rem;">
                <h3>Main Concerns</h3>
                <ul class="plain-english-list">
                    ${data.main_concerns.length > 0 ? data.main_concerns.map(c => `<li>${c}</li>`).join('') : '<li>No major concerns identified</li>'}
                </ul>
            </div>

            <div style="margin-bottom: 2rem;">
                <h3>Plain-English Notes</h3>
                <ul class="plain-english-list">
                    ${data.plain_english.map(p => `<li>${p}</li>`).join('')}
                </ul>
            </div>

            <div style="margin-bottom: 2rem;">
                <h3>Best Alternates</h3>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Airport</th>
                                <th>Dist</th>
                                <th>Rules</th>
                                <th>Reason</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.best_alternates.map(a => `
                                <tr>
                                    <td><strong>${a.icao}</strong></td>
                                    <td>${a.distance_nm} nm</td>
                                    <td>${utils.getFlightCategoryChip(a.flight_category)}</td>
                                    <td style="font-size: 0.85rem;">${a.rank_reason}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>

            <div class="warning-callout" style="font-size: 0.8rem; border-left-color: var(--text-muted);">
                <strong>Advisory Only:</strong> ${data.disclaimer}
            </div>

            <div style="margin-top: 2rem;">
                ${cards.renderOfficialResourcesCard(icao)}
            </div>
        </div>
    `;
}

async function renderDetailedWeather(container, icao) {
    const data = await api.getWeather(icao);
    container.innerHTML = `
        <div class="page-header">
            <h1>Detailed Weather: ${icao}</h1>
            <a href="#/airport/${icao}">← Return to Dashboard</a>
        </div>
        ${utils.renderWarnings(data.warnings)}
        <div class="grid">
            <div class="card">
                <h2>Current Observation (METAR)</h2>
                ${data.metar ? `
                    <code style="display: block; background: var(--code-bg); padding: 1rem; border-radius: 4px; margin-bottom: 1.5rem;">${data.metar.raw}</code>
                    <table class="table-container">
                        <tr><th>Flight Category</th><td>${utils.getFlightCategoryChip(data.metar.flight_category)}</td></tr>
                        <tr><th>Wind</th><td>${utils.formatWind(data.metar.wind)}</td></tr>
                        <tr><th>Visibility</th><td>${data.metar.visibility_sm ?? 'N/A'} SM</td></tr>
                        <tr><th>Ceiling</th><td>${data.metar.ceiling_ft_agl ?? 'None'} FT AGL</td></tr>
                        <tr><th>Temperature</th><td>${data.metar.temperature_c ?? 'N/A'} °C</td></tr>
                        <tr><th>Dewpoint</th><td>${data.metar.dewpoint_c ?? 'N/A'} °C</td></tr>
                        <tr><th>Altimeter</th><td>${data.metar.altimeter_in_hg ?? 'N/A'} IN HG</td></tr>
                        <tr><th>Observed At</th><td>${utils.formatDate(data.metar.observed_at)}</td></tr>
                    </table>
                ` : '<p>No METAR available</p>'}
            </div>
            <div class="card">
                <h2>Forecast (TAF)</h2>
                ${data.taf ? `
                    <code style="display: block; background: var(--code-bg); padding: 1rem; border-radius: 4px; margin-bottom: 1.5rem;">${data.taf.raw}</code>
                    <p><strong>Issued:</strong> ${utils.formatDate(data.taf.issued_at)}</p>
                    <p><strong>Valid:</strong> ${utils.formatDate(data.taf.valid_from)} to ${utils.formatDate(data.taf.valid_to)}</p>
                    <h3>Periods</h3>
                    <div style="font-size: 0.85rem;">
                        ${data.taf.forecast_periods.map(p => `
                            <div style="border-bottom: 1px solid #eee; padding: 0.5rem 0;">
                                <strong>${utils.formatDate(p.fcst_from)}:</strong> ${p.rawFcst || 'N/A'}
                            </div>
                        `).join('')}
                    </div>
                ` : '<p>No TAF available</p>'}
            </div>
        </div>
    `;
}

async function renderDetailedRunways(container, icao) {
    const data = await api.getRunways(icao);
    container.innerHTML = `
        <div class="page-header">
            <h1>Runway Intelligence: ${icao}</h1>
            <a href="#/airport/${icao}">← Return to Dashboard</a>
        </div>
        ${utils.renderWarnings(data.warnings)}
        <div class="card">
            <h2>Wind Analysis</h2>
            <div style="margin-bottom: 1.5rem; padding: 1rem; background: var(--light); border-radius: 8px;">
                <strong>Favored Runway: ${data.favored_runway.id || 'None'}</strong>
                <p style="margin: 0.5rem 0 0 0;">Reason: ${data.favored_runway.reason}</p>
            </div>

            ${cards.renderRunwaySketch(data.runways, data.favored_runway.id, data.wind_direction_deg)}

            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Runway</th>
                            <th>Heading</th>
                            <th>Length</th>
                            <th>Headwind</th>
                            <th>Tailwind</th>
                            <th>Crosswind</th>
                            <th>Risks</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.runways.map(r => {
                            const risks = [];
                            if (r.risk_flags.calm_wind) risks.push('Calm');
                            if (r.risk_flags.variable_wind) risks.push('Variable');
                            if (r.risk_flags.gusty) risks.push('Gusty');
                            if (r.risk_flags.strong_crosswind) risks.push('Strong XW');
                            else if (r.risk_flags.crosswind) risks.push('XW');
                            if (r.risk_flags.strong_tailwind) risks.push('Strong TW');
                            else if (r.risk_flags.tailwind) risks.push('TW');

                            return `
                                <tr class="${r.id === data.favored_runway.id ? 'favored' : ''}">
                                    <td><strong>${r.id}</strong></td>
                                    <td>${r.heading}°</td>
                                    <td>${r.length_ft} ft</td>
                                    <td>${r.headwind_kt ?? 0} kt</td>
                                    <td>${r.tailwind_kt ?? 0} kt</td>
                                    <td>${r.crosswind_kt ?? 0}${r.crosswind_gust_kt ? ` (${r.crosswind_gust_kt})` : ''} kt</td>
                                    <td class="risk-flag">${risks.join(', ')}</td>
                                </tr>
                            `;
                        }).join('')}
                    </tbody>
                </table>
            </div>
            <div style="margin-top: 1rem; font-size: 0.85rem; color: var(--text-muted);">
                <p>Note: Headwind/Tailwind values are relative to the runway heading. Crosswind is absolute.</p>
            </div>
            
            <div style="margin-top: 2rem;">
                ${cards.renderOfficialResourcesCard(icao)}
            </div>
        </div>
    `;
}

async function renderDetailedAlternates(container, icao) {
    const settings = utils.getSettings();
    const data = await api.getAlternates(icao, settings.alternate_radius);
    container.innerHTML = `
        <div class="page-header">
            <h1>Ranked Alternates: ${icao}</h1>
            <a href="#/airport/${icao}">← Return to Dashboard</a>
        </div>
        <p style="margin-bottom: 1rem; font-style: italic;">Showing airports within ${settings.alternate_radius} nm radius.</p>
        <div class="card">
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Score</th>
                            <th>Airport</th>
                            <th>Distance</th>
                            <th>Rules</th>
                            <th>Winds</th>
                            <th>Details</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${data.map(a => `
                            <tr>
                                <td><span class="chip info">${a.score}</span></td>
                                <td><strong>${a.icao}</strong><br><small>${a.name}</small></td>
                                <td>${a.distance_nm} nm<br><small>${a.bearing_deg}°</small></td>
                                <td>${utils.getFlightCategoryChip(a.flight_category)}</td>
                                <td>${a.wind || 'N/A'}</td>
                                <td>
                                    <div style="font-size: 0.85rem;">${a.rank_reason}</div>
                                    ${a.warnings.map(w => `<div style="color: var(--warning); font-size: 0.75rem;">⚠️ ${w}</div>`).join('')}
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
            <div class="warning-callout" style="margin-top: 2rem; font-size: 0.8rem;">
                Operational comparison only. Not legal alternate planning.
            </div>
        </div>
    `;
}

async function renderDetailedHazards(container, icao) {
    const data = await api.getHazards(icao);
    container.innerHTML = `
        <div class="page-header">
            <h1>Weather Hazards & Alerts: ${icao}</h1>
            <a href="#/airport/${icao}">← Return to Dashboard</a>
        </div>
        ${utils.renderWarnings(data.warnings)}
        <div class="card" style="margin-bottom: 2rem;">
            <h2>Regional Risk Level: ${utils.getRiskLevelChip(data.risk_level)}</h2>
            <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); margin-top: 1rem;">
                <div class="card" style="background: var(--light); box-shadow: none;">
                    <strong>NWS Alerts</strong>
                    <div style="font-size: 2rem;">${data.counts.nws_alerts}</div>
                </div>
                <div class="card" style="background: var(--light); box-shadow: none;">
                    <strong>SIGMETs</strong>
                    <div style="font-size: 2rem;">${data.counts.sigmets}</div>
                </div>
                <div class="card" style="background: var(--light); box-shadow: none;">
                    <strong>G-AIRMETs</strong>
                    <div style="font-size: 2rem;">${data.counts.gairmets}</div>
                </div>
                <div class="card" style="background: var(--light); box-shadow: none;">
                    <strong>CWAs</strong>
                    <div style="font-size: 2rem;">${data.counts.cwas}</div>
                </div>
            </div>
        </div>

        <div class="card">
            <h2>Active NWS Alerts</h2>
            ${data.nws_alerts.length > 0 ? `
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Event</th>
                                <th>Severity</th>
                                <th>Area</th>
                                <th>Expires</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.nws_alerts.map(alert => `
                                <tr>
                                    <td><strong>${alert.properties.event}</strong></td>
                                    <td>${alert.properties.severity}</td>
                                    <td>${alert.properties.areaDesc}</td>
                                    <td>${utils.formatDate(alert.properties.expires)}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            ` : '<p>No active NWS alerts for this location.</p>'}
        </div>
        
        <div style="margin-top: 2rem; color: var(--text-muted); font-size: 0.85rem;">
            <p>Sources: ${data.sources.join(', ')}</p>
            <p>Note: SIGMET/G-AIRMET/CWA parsing is currently limited. Always check official aviation weather sources.</p>
        </div>
    `;
}

async function renderDetailedDirectory(container, icao) {
    const data = await api.getDirectory(icao);
    container.innerHTML = `
        <div class="page-header">
            <h1>Airport Directory: ${icao}</h1>
            <a href="#/airport/${icao}">← Return to Dashboard</a>
        </div>
        <div class="grid">
            <div class="card">
                <h2>General Information</h2>
                <table>
                    <tr><th>Name</th><td>${data.name}</td></tr>
                    <tr><th>ICAO</th><td>${data.icao}</td></tr>
                    <tr><th>Elevation</th><td>${data.elevation_ft} FT</td></tr>
                    <tr><th>Latitude</th><td>${data.lat.toFixed(6)}</td></tr>
                    <tr><th>Longitude</th><td>${data.lon.toFixed(6)}</td></tr>
                </table>
            </div>
            <div class="card">
                <h2>Communication</h2>
                <table>
                    <thead><tr><th>Type</th><th>Frequency</th></tr></thead>
                    <tbody>
                        ${data.frequencies.map(f => `<tr><td>${f.type}</td><td>${f.frequency} MHz</td></tr>`).join('')}
                    </tbody>
                </table>
            </div>
        </div>
    `;
}

async function renderSettings(container) {
    const settings = utils.getSettings();
    const refStatus = await api.getReferenceStatus();
    
    container.innerHTML = `
        <div class="page-header">
            <h1>App Settings</h1>
            <a href="#/">← Return to Dashboard</a>
        </div>
        
        <div class="grid">
            <div class="card">
                <h2>Preferences</h2>
                <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1.5rem;">
                    Configure how AirfieldOps behaves on startup and during active monitoring.
                </p>
                <div style="margin-bottom: 1.5rem;">
                    <label style="display: block; margin-bottom: 0.25rem; font-weight: bold;">Default Airport (ICAO)</label>
                    <small style="display: block; color: var(--text-muted); margin-bottom: 0.5rem;">The dashboard that loads when you first open the app.</small>
                    <input type="text" id="set-default-apt" value="${settings.default_airport}" style="width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px;">
                </div>
                <div style="margin-bottom: 1.5rem;">
                    <label style="display: block; margin-bottom: 0.25rem; font-weight: bold;">Alternate Search Radius (NM)</label>
                    <input type="number" id="set-radius" value="${settings.alternate_radius}" style="width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px;">
                </div>
                <div style="margin-bottom: 2rem;">
                    <label style="display: block; margin-bottom: 0.25rem; font-weight: bold;">Refresh Interval (Seconds)</label>
                    <small style="display: block; color: var(--text-muted); margin-bottom: 0.5rem;">Automatically refreshes the current dashboard/page while the tab is visible (min: 30s).</small>
                    <input type="number" id="set-refresh" value="${settings.refresh_interval}" style="width: 100%; padding: 0.5rem; border: 1px solid #ccc; border-radius: 4px;">
                </div>
                
                ${currentIcao ? `
                    <div style="margin-bottom: 1.5rem;">
                        <button id="set-current-default-btn" class="chip info" style="border:none; padding: 0.5rem 1rem; width: 100%; cursor:pointer; font-size: 0.85rem; background: var(--secondary);">Use ${currentIcao} as Default</button>
                    </div>
                ` : ''}

                <button id="save-settings-btn" class="chip info" style="border:none; padding: 1rem 2rem; width: 100%; cursor:pointer; font-size: 1rem;">Save Settings</button>
                <div id="settings-msg" style="margin-top: 1rem; text-align: center; font-weight: bold;"></div>
            </div>

            <div class="card">
                <h2>System State</h2>
                <div style="font-size: 0.9rem;">
                    <table style="width: 100%;">
                        <tr><td style="padding: 0.25rem 0;"><strong>Airports</strong></td><td style="text-align: right;">${refStatus.airport_count}</td></tr>
                        <tr><td style="padding: 0.25rem 0;"><strong>Runways</strong></td><td style="text-align: right;">${refStatus.runway_count}</td></tr>
                        <tr><td style="padding: 0.25rem 0;"><strong>Frequencies</strong></td><td style="text-align: right;">${refStatus.frequency_count}</td></tr>
                        <tr><td style="padding: 0.25rem 0;"><strong>Data Version</strong></td><td style="text-align: right;">${refStatus.data_version}</td></tr>
                        <tr><td style="padding: 0.25rem 0;"><strong>Schema Version</strong></td><td style="text-align: right;">${refStatus.schema_version}</td></tr>
                        <tr><td style="padding: 0.25rem 0;"><strong>Last Seeded</strong></td><td style="text-align: right; font-size: 0.75rem;">${utils.formatDate(refStatus.last_seeded_at)}</td></tr>
                    </table>
                </div>
                
                <h2 style="margin-top: 2rem;">Official Resources</h2>
                <p style="font-size: 0.85rem;">Links to external regulatory and aeronautical charts.</p>
                <ul class="plain-english-list">
                    <li><a href="https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/dtpp/search/" target="_blank">FAA Digital Terminal Procedures (Diagrams)</a></li>
                    <li><a href="https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/dafd/" target="_blank">FAA Chart Supplements (d-AFD)</a></li>
                </ul>
            </div>
        </div>
    `;

    document.getElementById('save-settings-btn').addEventListener('click', async () => {
        const msgEl = document.getElementById('settings-msg');
        const icao = document.getElementById('set-default-apt').value.trim().toUpperCase();
        
        msgEl.style.color = 'var(--gray)';
        msgEl.innerText = 'Validating airport...';

        try {
            // Validate airport exists
            await api.getDirectory(icao);
            
            const newSettings = {
                default_airport: icao,
                alternate_radius: Math.max(1, parseInt(document.getElementById('set-radius').value)),
                refresh_interval: Math.max(30, parseInt(document.getElementById('set-refresh').value))
            };
            utils.saveSettings(newSettings);
            
            msgEl.style.color = 'var(--success)';
            msgEl.innerHTML = `Settings saved! <a href="#/airport/${icao}" style="color: var(--accent);">Go to ${icao} Dashboard</a>`;
        } catch (e) {
            msgEl.style.color = 'var(--danger)';
            msgEl.innerText = `Error: Airport ${icao} not found in reference data.`;
        }
    });

    if (currentIcao) {
        document.getElementById('set-current-default-btn').addEventListener('click', () => {
            document.getElementById('set-default-apt').value = currentIcao;
        });
    }
}
