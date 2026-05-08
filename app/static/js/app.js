let refreshTimer = null;
let currentIcao = null;
let isRefreshing = false;
let settingsLoaded = false;
const DEBUG = false;
const DEBUG_ROUTER = false;

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
        refreshCurrentView(true); // Manual refresh
    });

    window.addEventListener('hashchange', handleRoute);
    
    // Visibility change handler for refresh pausing
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            stopRefreshTimer();
        } else {
            const hash = window.location.hash.substring(1) || '/';
            if (hash.startsWith('/airport/')) {
                startRefreshTimer();
            }
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
    let selectedIndex = -1;
    let suggestions = [];

    const renderSuggestions = () => {
        if (suggestions.length === 0) {
            container.style.display = 'none';
            return;
        }

        container.innerHTML = suggestions.map((a, i) => `
            <div class="suggestion-item ${i === selectedIndex ? 'selected' : ''}" data-icao="${a.ident}" data-index="${i}">
                <div class="suggestion-header">
                    <span class="suggestion-icao">${a.ident}</span>
                    ${a.iata_code ? `<span class="suggestion-iata">${a.iata_code}</span>` : ''}
                </div>
                <div class="suggestion-name">${a.name}</div>
                ${a.city ? `<div class="suggestion-location">${a.city}, ${a.state || ''}</div>` : ''}
            </div>
        `).join('');
        container.style.display = 'block';
    };

    const handleSelect = (icao) => {
        input.value = icao;
        container.style.display = 'none';
        
        // Handle selection based on which input it is
        if (input.id === 'setup-search') {
            // Home/Setup page logic
            const btn = document.getElementById('setup-save-btn');
            if (btn) btn.disabled = false;
        } else if (input.id === 'board-search') {
            // Board page logic
            api.addFavorite(icao).then(() => {
                input.value = '';
                const content = document.getElementById('app-content');
                renderBoard(content);
            });
        } else if (input.id === 'set-default-apt') {
            // Settings page logic - no auto-nav
        } else {
            // Header search logic
            navigateToAirport(icao);
        }
    };

    input.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        const q = input.value.trim();
        
        if (q.length < 2) {
            container.style.display = 'none';
            suggestions = [];
            selectedIndex = -1;
            return;
        }

        debounceTimer = setTimeout(async () => {
            try {
                // Fetch up to 10 suggestions
                const results = await api.searchAirports(q, 10);
                suggestions = results;
                selectedIndex = -1;
                renderSuggestions();
            } catch (e) {
                console.error('Search failed', e);
            }
        }, 250);
    });

    input.addEventListener('keydown', (e) => {
        if (container.style.display === 'none') return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            selectedIndex = (selectedIndex + 1) % suggestions.length;
            renderSuggestions();
            const selected = container.querySelector('.selected');
            if (selected) selected.scrollIntoView({ block: 'nearest' });
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            selectedIndex = (selectedIndex - 1 + suggestions.length) % suggestions.length;
            renderSuggestions();
            const selected = container.querySelector('.selected');
            if (selected) selected.scrollIntoView({ block: 'nearest' });
        } else if (e.key === 'Enter') {
            if (selectedIndex >= 0) {
                e.preventDefault();
                handleSelect(suggestions[selectedIndex].ident);
            }
        } else if (e.key === 'Escape') {
            container.style.display = 'none';
        }
    });

    container.addEventListener('click', (e) => {
        const item = e.target.closest('.suggestion-item');
        if (item) {
            const icao = item.dataset.icao;
            handleSelect(icao);
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
    
    const settings = utils.getSettings();
    if (!settings.refresh_interval_seconds) return;

    const refreshSeconds = Math.max(30, Math.min(3600, settings.refresh_interval_seconds));
    const intervalMs = refreshSeconds * 1000;

    if (DEBUG) console.log(`[Timer] Starting auto-refresh timer: ${refreshSeconds}s`);

    refreshTimer = setInterval(() => {
        const route = parseRoute();
        if (route.type !== 'airport' && route.type !== 'board') {
            stopRefreshTimer();
            return;
        }

        if (document.hidden) {
            if (DEBUG) console.log('[Timer] Tab hidden, skipping tick');
            return;
        }

        if (isRefreshing) {
            if (DEBUG) console.log('[Timer] Already refreshing, skipping tick');
            return;
        }

        if (DEBUG) console.log('[Timer] Auto-refresh tick');
        refreshCurrentView(false);
    }, intervalMs);
}

function stopRefreshTimer() {
    if (refreshTimer) {
        if (DEBUG) console.log('[Timer] Stopping auto-refresh timer');
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
}

function navigateToAirport(icao) {
    utils.addRecentAirport(icao);
    const settings = utils.getSettings();
    if (!settings.public_readonly_mode) {
        api.addRecent(icao).catch(e => console.warn('Failed to sync recent to backend', e));
    }
    window.location.hash = `/airport/${icao}`;
}

function parseRoute(hash) {
    const h = (hash || window.location.hash || '#/').substring(1);
    const parts = h.split('/').filter(p => p !== '');
    
    let res;
    if (parts.length === 0 || h === '/') res = { type: 'root' };
    else if (parts[0] === 'board') res = { type: 'board' };
    else if (parts[0] === 'settings') res = { type: 'settings' };
    else if (parts[0] === 'about') res = { type: 'about' };
    else if (parts[0] === 'search') res = { type: 'search' };
    else if (parts[0] === 'airport' && parts[1]) {
        res = {
            type: 'airport',
            icao: parts[1].toUpperCase(),
            view: parts[2] || 'dashboard'
        };
    } else res = { type: 'unknown' };

    if (DEBUG_ROUTER) console.log(`[Router] Parsed route from "${h}":`, res);
    return res;
}

function updateNavLinks(route) {
    const nav = document.getElementById('main-nav');
    const settings = utils.getSettings();
    
    // Always show nav if an airport is specified or if default_airport is set
    const targetIcao = route.icao || currentIcao || settings.default_airport;
    
    if (!targetIcao && route.type !== 'board' && route.type !== 'settings' && route.type !== 'about') {
        nav.style.display = 'none';
        return;
    }
    nav.style.display = 'flex';
    
    // Sub-nav links
    const links = {
        'nav-home': `#/airport/${targetIcao}`,
        'nav-board': `#/board`,
        'nav-brief': `#/airport/${targetIcao}/brief`,
        'nav-weather': `#/airport/${targetIcao}/weather`,
        'nav-runways': `#/airport/${targetIcao}/runways`,
        'nav-alternates': `#/airport/${targetIcao}/alternates`,
        'nav-hazards': `#/airport/${targetIcao}/hazards`,
        'nav-settings': `#/settings`
    };

    // Remove active class from all first
    document.querySelectorAll('nav a').forEach(a => a.classList.remove('active'));

    for (const [id, href] of Object.entries(links)) {
        const el = document.getElementById(id);
        if (el) {
            el.href = href;
            
            // Active state logic
            if (route.type === 'board' && id === 'nav-board') {
                el.classList.add('active');
            } else if (route.type === 'settings' && id === 'nav-settings') {
                el.classList.add('active');
            } else if (route.type === 'airport' && route.icao === targetIcao) {
                if (route.view === 'dashboard' && id === 'nav-home') {
                    el.classList.add('active');
                } else if (id === `nav-${route.view}`) {
                    el.classList.add('active');
                }
            }
        }
    }
}

async function handleRoute() {
    const route = parseRoute();
    if (DEBUG_ROUTER) console.log(`[Router] handleRoute:`, route);
    
    const content = document.getElementById('app-content');
    const statusBar = document.getElementById('status-bar');
    
    // 1. Sync backend settings ONLY IF NOT LOADED or on settings page
    if (!settingsLoaded || route.type === 'settings') {
        try {
            const backendSettings = await api.getSettings();
            utils.saveSettings(backendSettings);
            settingsLoaded = true;
        } catch (e) {
            console.warn('[Router] Failed to load settings from backend, using cache.', e);
        }
    }

    const settings = utils.getSettings();
    
    // Update nav links based on parsed route
    updateNavLinks(route);

    // Stop timer before rendering new view; view will start it if needed
    stopRefreshTimer();

    if (route.type === 'root') {
        if (settings.default_airport) {
            window.location.hash = `/airport/${settings.default_airport}`;
        } else {
            renderFirstRun(content);
        }
        return;
    }

    if (route.type === 'search') {
        statusBar.style.display = 'none';
        currentIcao = null;
        renderSearch(content);
        return;
    }

    if (route.type === 'settings') {
        statusBar.style.display = 'none';
        renderSettings(content);
        return;
    }

    if (route.type === 'about') {
        statusBar.style.display = 'none';
        renderAboutPage(content);
        return;
    }

    if (route.type === 'board') {
        if (content.innerHTML === '' || content.querySelector('.loading') || content.dataset.route !== 'board') {
             content.innerHTML = '<div class="loading">Loading Board...</div>';
             content.dataset.route = 'board';
        }
        await refreshCurrentView(false);
        return;
    }

    if (route.type === 'airport') {
        currentIcao = route.icao;
        await refreshCurrentView(false);
        return;
    }

    // Default: first run or search
    if (!settings.default_airport) {
        renderFirstRun(content);
    } else {
        window.location.hash = '/search';
    }
}

async function refreshCurrentView(isManual = false) {
    if (isRefreshing) return;
    
    const route = parseRoute();
    const content = document.getElementById('app-content');
    const statusBar = document.getElementById('status-bar');
    const lastUpdatedEl = document.getElementById('last-updated');

    if (route.type === 'board') {
        isRefreshing = true;
        try {
            await renderBoard(content);
            lastUpdatedEl.innerText = `Last updated: ${new Date().toLocaleTimeString()}`;
            statusBar.style.display = 'flex';
            if (!refreshTimer) startRefreshTimer();
        } catch (e) {
            console.error('Board refresh failed:', e);
            if (content.querySelector('.loading')) {
                content.innerHTML = `<div class="card danger"><h2>Error loading board</h2><p>${e.message}</p></div>`;
            }
        } finally {
            isRefreshing = false;
        }
        return;
    }

    if (route.type !== 'airport') {
        stopRefreshTimer();
        return;
    }

    const { icao, view } = route;

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
        
        // Re-start timer for this page if not already running
        if (!refreshTimer) {
            startRefreshTimer();
        }

    } catch (e) {
        console.error('Refresh failed:', e);
        
        if (content.querySelector('.loading')) {
            if (e.status === 404) {
                content.innerHTML = `
                    <div class="card" style="max-width: 600px; margin: 2rem auto; text-align: center;">
                        <h2>Airport Not Found in Reference Database</h2>
                        <p>The airport <strong>${icao}</strong> was not found in our current OurAirports dataset (16k+ fields).</p>
                        <p style="font-size: 0.9rem; color: var(--text-muted);">Please verify the ICAO code or try searching by city/name.</p>
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
                            Message: ${e.message || 'System error'}
                        </div>
                        <br>
                        <button onclick="window.location.hash = '/'" class="chip info" style="border:none; padding: 0.5rem 1rem; cursor:pointer;">Return to Dashboard</button>
                    </div>
                `;
            }
            statusBar.style.display = 'none';
            stopRefreshTimer();
        } else {
            const errorMsg = document.createElement('div');
            errorMsg.className = 'warning-callout';
            errorMsg.style.marginTop = '1rem';
            errorMsg.innerHTML = `⚠️ Refresh failed at ${new Date().toLocaleTimeString()}. Using cached data.`;
            
            if (!content.querySelector('.refresh-error')) {
                errorMsg.classList.add('refresh-error');
                content.prepend(errorMsg);
                setTimeout(() => errorMsg.remove(), 5000);
            }
        }
    } finally {
        isRefreshing = false;
    }
}


async function renderBoard(container) {
    const favorites = await api.getFavorites();
    
    if (favorites.length === 0) {
        container.innerHTML = `
            <div class="home-container" style="max-width: 800px; margin: 2rem auto; text-align: center;">
                <h1 style="font-size: 2.5rem; margin-bottom: 1rem;">Your Airport Board is empty</h1>
                <p style="color: var(--text-muted); font-size: 1.1rem; margin-bottom: 2rem;">Add airports here to monitor their live weather and favored runways in one view.</p>
                <div class="card" style="max-width: 500px; margin: 0 auto; text-align: left; background: var(--card-bg-alt); padding: 2rem; border: 1px solid var(--border-color);">
                    <p style="margin-bottom: 1rem; font-weight: bold;">Add your first airport:</p>
                    <div class="home-search" style="display: flex; gap: 0.5rem; position: relative;">
                        <input type="text" id="board-empty-search" placeholder="ICAO, City, or Name (e.g. KPHL)" autocomplete="off" style="flex: 1; padding: 0.75rem;">
                        <button id="board-empty-add-btn" class="chip info" style="border: none; cursor: pointer; padding: 0 1.5rem; font-weight: bold;">Add</button>
                    </div>
                    <div style="margin-top: 1.5rem; font-size: 0.85rem; color: var(--text-muted);">
                        Tip: You can search by ICAO code, city name, or airport name.
                    </div>
                </div>
            </div>
        `;
        const input = document.getElementById('board-empty-search');
        setupAutocomplete(input);
        
        const addFn = async () => {
            const val = input.value.trim().toUpperCase();
            if (val) {
                try {
                    await api.addFavorite(val);
                    input.value = '';
                    renderBoard(container);
                } catch (e) {
                    alert(`Failed to add ${val}: ${e.message}`);
                }
            }
        };
        
        document.getElementById('board-empty-add-btn').addEventListener('click', addFn);
        input.addEventListener('keypress', (e) => { if (e.key === 'Enter') addFn(); });
        
        container.dataset.route = 'board';
        return;
    }

    const isAlreadyRendered = container.querySelector('#board-grid');
    if (!isAlreadyRendered) {
        container.innerHTML = `
            <div class="page-header" style="display: flex; justify-content: space-between; align-items: center;">
                <h1>Airport Board</h1>
                <div class="search-container" style="width: 250px;">
                    <input type="text" id="board-search" placeholder="Add airport..." autocomplete="off">
                </div>
            </div>
            <div id="board-grid" class="grid" style="grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));">
                <div class="loading">Loading board summaries...</div>
            </div>
        `;
        setupAutocomplete(document.getElementById('board-search'));
        container.dataset.route = 'board';
    }

    const grid = document.getElementById('board-grid');
    
    try {
        const idents = favorites.map(f => f.ident);
        const results = await api.getBatchSummaries(idents);
        
        grid.innerHTML = results.map(r => {
            if (r.error) {
                const icao = r.icao || '???';
                return `
                    <div class="card board-card danger" data-icao="${icao}">
                        <h3 style="margin: 0;">${icao}</h3>
                        <p style="font-size: 0.85rem; color: var(--danger-text);">Failed to load: ${r.error}</p>
                        <div class="board-card-actions" style="margin-top: auto;">
                            <button class="chip danger remove-favorite-btn" data-icao="${icao}" style="border: none; cursor: pointer; width: 100%;">Remove</button>
                        </div>
                    </div>
                `;
            }
            return cards.renderBoardCard(r);
        }).join('') + `
            <div class="card" style="display: flex; flex-direction: column; justify-content: center; align-items: center; min-height: 200px; border: 2px dashed var(--border-color); background: transparent; box-shadow: none;">
                <p style="color: var(--text-muted); margin-bottom: 1rem;">Add another</p>
                <input type="text" id="board-inline-add" placeholder="ICAO..." style="width: 100px; text-align: center; text-transform: uppercase;">
            </div>
        `;

        setupAutocomplete(document.getElementById('board-inline-add'));

        // Attach remove handlers
        grid.querySelectorAll('.remove-favorite-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const icao = e.target.dataset.icao;
                if (confirm(`Remove ${icao} from board?`)) {
                    await api.removeFavorite(icao);
                    renderBoard(container);
                }
            });
        });
    } catch (e) {
        console.error("Board batch fetch failed:", e);
        grid.innerHTML = `<div class="card danger"><h2>Error loading board</h2><p>${e.message}</p></div>`;
    }
}

function renderAboutPage(container) {
    container.innerHTML = `
        <div class="card" style="max-width: 800px; margin: 2rem auto;">
            <h1>About AirfieldOps</h1>
            <p>AirfieldOps is a situational awareness tool designed for pilots, dispatchers, and aviation enthusiasts. It aggregates live weather, runway geometry, and regional hazards into a single, cohesive dashboard.</p>
            
            <div class="warning-callout" style="margin: 1.5rem 0;">
                <strong>⚠️ ADVISORY ONLY</strong>
                <p>This application is for situational awareness and advisory use only. It is NOT for certified flight planning, dispatch, release, navigation, or operational control. Always verify data in official publications and certified briefings.</p>
            </div>

            <h2>Data Sources</h2>
            <ul class="plain-english-list">
                <li><strong>Weather (METAR/TAF):</strong> Real-time data sourced from <a href="https://aviationweather.gov" target="_blank">AviationWeather.gov</a>.</li>
                <li><strong>Hazards (SIGMET/NWS):</strong> Regional alerts and SIGMETs sourced from <a href="https://weather.gov" target="_blank">NWS api.weather.gov</a>.</li>
                <li><strong>Reference Data:</strong> Airport locations, runways, and frequencies are sourced from the <a href="https://ourairports.com" target="_blank">OurAirports</a> community dataset and curated overrides.</li>
                <li><strong>Official Resources:</strong> Links provided to FAA Digital Terminal Procedures and Chart Supplements are for convenience and direct to official FAA servers.</li>
            </ul>

            <h2>System Behavior</h2>
            <ul class="plain-english-list">
                <li><strong>Public Mode:</strong> This instance is running in public read-only mode. User preferences like your default airport and theme are saved <strong>only in this browser</strong> using localStorage.</li>
                <li><strong>Airport Board:</strong> Favorites saved to your Board are stored locally in your browser. Clearing your browser data or using a different device will result in a fresh Board.</li>
                <li><strong>Operational Insights:</strong> Calculations such as crosswind components and favored runways are derived using standard trigonometry and are for advisory use only.</li>
                <li><strong>Privacy:</strong> No personal data is collected. Your search history and preferences remain local to your device.</li>
            </ul>
            
            <div style="margin-top: 2rem; text-align: center;">
                <button onclick="window.history.back()" class="chip info" style="border:none; padding: 0.5rem 1rem; cursor:pointer;">Go Back</button>
            </div>
        </div>
    `;
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
    console.log("Rendering first-run setup page");
    container.innerHTML = `
        <div class="home-container">
            <h1>Welcome to AirfieldOps</h1>
            <p>Your aviation situational awareness dashboard.</p>
            
            <div class="card" style="max-width: 500px; margin: 1.5rem auto; text-align: left; background: var(--card-bg-alt);">
                <p><strong>To get started, choose your home airport.</strong></p>
                <div class="home-search" style="position: relative; margin-top: 1rem;">
                    <input type="text" id="setup-search" placeholder="Search ICAO, IATA, or City (e.g. KAGC)" autocomplete="off">
                    <button id="setup-save-btn" disabled>Start</button>
                </div>
                <div id="setup-error" style="color: var(--danger-text); background: var(--danger-bg); border: 1px solid var(--danger-border); padding: 0.5rem; margin-top: 10px; display: none; border-radius: 4px;"></div>
                
                <p style="font-size: 0.85rem; color: var(--text-muted); margin-top: 1.5rem;">
                    <strong>Privacy Note:</strong> This preference is saved <strong>only in your browser</strong>. This public instance does not store your settings on the server.
                </p>
            </div>
            
            <p style="color: var(--text-muted); font-size: 0.8rem;">
                Advisory use only. <a href="#/about" style="color: inherit; text-decoration: underline;">Read more about our data sources.</a>
            </p>
        </div>
    `;

    const input = document.getElementById('setup-search');
    const btn = document.getElementById('setup-save-btn');
    const errorEl = document.getElementById('setup-error');
    setupAutocomplete(input);

    const validateAndEnable = () => {
        const val = input.value.trim().toUpperCase();
        console.log(`Setup input changed: "${val}"`);
        // Enable if it looks like a 4-char ICAO or if it's longer (name search)
        if (val.length >= 3) {
            btn.disabled = false;
        } else {
            btn.disabled = true;
        }
        errorEl.style.display = 'none';
    };

    input.addEventListener('input', validateAndEnable);

    input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !btn.disabled) {
            console.log("Enter key pressed in setup input");
            btn.click();
        }
    });

    btn.addEventListener('click', async () => {
        const icao = input.value.trim().toUpperCase();
        btn.disabled = true;
        btn.innerText = "Saving...";
        
        try {
            await api.getDirectory(icao);
            const settings = utils.getSettings();
            
            if (settings.public_readonly_mode) {
                // Public mode: Save only to localStorage
                utils.saveLocalSettings({ ...settings, default_airport: icao });
            } else {
                // Private mode: Save to backend
                const newSettings = { ...settings, default_airport: icao };
                const saved = await api.updateSettings(newSettings);
                utils.saveSettings(saved);
            }
            
            navigateToAirport(icao);
        } catch (e) {
            console.error("Setup save failed:", e);
            errorEl.innerText = `Failed to save ${icao}. ${e.message || 'Verify it is a valid airport.'}`;
            errorEl.style.display = 'block';
            btn.disabled = false;
            btn.innerText = "Save and Start";
        }
    });
}

async function renderDashboard(container, icao) {
    // Single aggregate call
    const data = await api.getDashboard(icao);
    const { brief, weather, runways, alternates: alts, hazards, airport: dir, coverage } = data;
    const favorites = await api.getFavorites();
    const isFavorite = favorites.some(f => f.ident === icao);

    const safeRender = (label, renderFn) => {
        try {
            return renderFn();
        } catch (e) {
            console.error(`${label} card render failed:`, e);
            return cards.renderUnavailableCard(label, "Unable to render this section.");
        }
    };

    container.innerHTML = `
        <div class="page-header" style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div>
                <h1>${icao} - ${dir.name}</h1>
                <div style="font-size: 0.9rem; color: var(--text-muted);">Dashboard Snapshot • ${utils.formatDate(new Date())}</div>
            </div>
            <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; justify-content: flex-end;">
                <button id="dashboard-toggle-favorite" class="chip ${isFavorite ? 'success' : 'info'}" style="border:none; padding: 0.5rem 1rem; cursor:pointer;">
                    ${isFavorite ? '★ On Board' : '☆ Add to Board'}
                </button>
                <button id="dashboard-set-default" class="chip info" style="border:none; padding: 0.5rem 1rem; cursor:pointer;">Use ${icao} as Default</button>
            </div>
        </div>
        <div id="dashboard-set-default-msg" style="text-align: right; color: var(--success); font-size: 0.85rem; margin-top: -0.5rem; margin-bottom: 1rem; display: none;">Saved!</div>
        <div class="grid">
            ${safeRender("Brief", () => cards.renderBriefCard(brief))}
            ${safeRender("Weather", () => cards.renderWeatherCard(weather))}
            ${safeRender("Runways", () => cards.renderRunwaysCard(runways))}
            ${safeRender("Hazards", () => cards.renderHazardsCard(hazards))}
            ${safeRender("Alternates", () => cards.renderAlternatesCard(alts, icao))}
            ${safeRender("Directory", () => cards.renderDirectoryCard(dir))}
            ${safeRender("Coverage", () => cards.renderCoverageCard(coverage))}
            ${safeRender("Official Resources", () => cards.renderOfficialResourcesCard(icao))}
        </div>
    `;

    document.getElementById('dashboard-toggle-favorite').addEventListener('click', async () => {
        const btn = document.getElementById('dashboard-toggle-favorite');
        const favorites = await api.getFavorites();
        const currentlyFavorite = favorites.some(f => f.ident === icao);
        
        if (currentlyFavorite) {
            await api.removeFavorite(icao);
            btn.innerText = '☆ Add to Board';
            btn.classList.remove('success');
            btn.classList.add('info');
        } else {
            await api.addFavorite(icao);
            btn.innerText = '★ On Board';
            btn.classList.remove('info');
            btn.classList.add('success');
        }
    });

    document.getElementById('dashboard-set-default').addEventListener('click', async () => {
        const btn = document.getElementById('dashboard-set-default');
        const msgEl = document.getElementById('dashboard-set-default-msg');
        btn.disabled = true;
        btn.innerText = "Saving...";
        
        try {
            const settings = utils.getSettings();
            if (settings.public_readonly_mode) {
                utils.saveLocalSettings({ ...settings, default_airport: icao });
            } else {
                const newSettings = { ...settings, default_airport: icao };
                const saved = await api.updateSettings(newSettings);
                utils.saveSettings(saved);
            }
            
            msgEl.innerText = "Default airport saved!";
            msgEl.style.display = 'block';
            setTimeout(() => { msgEl.style.display = 'none'; }, 3000);
        } catch (e) {
            console.error("Dashboard set-default failed:", e);
            alert('Failed to save default airport.');
        } finally {
            btn.disabled = false;
            btn.innerText = "Set as Default";
        }
    });
}

async function renderFullBrief(container, icao) {
    container.innerHTML = `
        <div class="page-header"><h1>${icao} Brief</h1></div>
        <div class="loading">Generating operational brief for ${icao}...</div>
    `;
    const data = await api.getBrief(icao);
    container.innerHTML = `
        <div class="page-header">
            <h1>${icao} Brief</h1>
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
                    <div style="font-size: 0.9rem;">${data.favored_runway.reason || 'Reason unavailable'}</div>
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
    container.innerHTML = `
        <div class="page-header"><h1>${icao} Weather</h1></div>
        <div class="loading">Fetching detailed weather for ${icao}...</div>
    `;
    const data = await api.getWeather(icao);
    const nearby = data.nearby_weather_stations || [];

    container.innerHTML = `
        <div class="page-header">
            <h1>${icao} Weather</h1>
        </div>

        ${utils.renderWarnings(data.warnings)}
        <div class="grid">
            <div class="card">
                <h2>Current Observation (METAR)</h2>
                ${data.metar ? `
                    <code style="display: block; background: var(--code-bg); color: var(--code-text); padding: 1rem; border-radius: 4px; margin-bottom: 1.5rem;">${data.metar.raw}</code>
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
                ` : `
                    <p style="color: var(--warning); font-weight: bold;">Field METAR unavailable at this time.</p>
                    ${nearby.length > 0 ? `
                        <h3>Nearby Reporting Weather</h3>
                        <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem;">Not field conditions. Use for situational awareness only.</p>
                        <div class="table-container">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Station</th>
                                        <th>Dist</th>
                                        <th>Rules</th>
                                        <th>Wind</th>
                                        <th>Observed</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${nearby.map(s => `
                                        <tr>
                                            <td><strong>${s.ident}</strong><br><small>${s.name}</small></td>
                                            <td>${s.distance_nm} nm<br><small>${s.bearing_deg}°</small></td>
                                            <td>${utils.getFlightCategoryChip(s.flight_category)}</td>
                                            <td>${s.wind || 'N/A'}</td>
                                            <td>${utils.formatDate(s.observed_at)}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    ` : '<p>No nearby reporting weather available.</p>'}
                `}
            </div>
            <div class="card">
                <h2>Forecast (TAF)</h2>
                ${data.taf ? `
                    <code style="display: block; background: var(--code-bg); color: var(--code-text); padding: 1rem; border-radius: 4px; margin-bottom: 1.5rem;">${data.taf.raw}</code>
                    <p><strong>Issued:</strong> ${utils.formatDate(data.taf.issued_at)}</p>
                    <p><strong>Valid:</strong> ${utils.formatDate(data.taf.valid_from)} to ${utils.formatDate(data.taf.valid_to)}</p>
                    <h3>Periods</h3>
                    <div style="font-size: 0.85rem;">
                        ${data.taf.forecast_periods.map(p => `
                            <div style="border-bottom: 1px solid var(--border-color); padding: 0.5rem 0;">
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
    container.innerHTML = `
        <div class="page-header"><h1>${icao} Runways</h1></div>
        <div class="loading">Analyzing runway wind components for ${icao}...</div>
    `;
    const data = await api.getRunways(icao);
    container.innerHTML = `
        <div class="page-header">
            <h1>${icao} Runways</h1>
        </div>
        ${utils.renderWarnings(data.warnings)}
        <div class="card">
            <h2>Wind Analysis</h2>
            <div style="margin-bottom: 1.5rem; padding: 1rem; background: var(--card-bg-alt); border: 1px solid var(--border-color); border-radius: 8px;">
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
                                    <td>${Math.round(r.heading)}°</td>
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

async function renderDetailedAlternates(container, icao, includeNonReporting = false) {
    const settings = utils.getSettings();
    const { radius_nm } = settings;

    try {
        // Fetch up to 25 alternates (hard cap in backend)
        const data = await api.getAlternates(icao, radius_nm, 25, includeNonReporting);
        
        const alternatesList = Array.isArray(data)
            ? data
            : Array.isArray(data?.alternates)
                ? data.alternates
                : [];
        
        const radius = data?.radius_nm || radius_nm;
        const reportingCount = data?.reporting_candidates_count ?? alternatesList.filter(a => a.flight_category !== 'UNKNOWN').length;
        const totalConsidered = data?.candidates_considered ?? alternatesList.length;
        const excluded = data?.excluded_summary || {};
        const noWeatherCount = excluded.no_weather || 0;

        container.innerHTML = `
            <div class="page-header" style="display: flex; justify-content: space-between; align-items: flex-end; flex-wrap: wrap; gap: 1rem;">
                <div>
                    <h1>${icao} Alternates</h1>
                    <div style="font-size: 0.9rem; color: var(--text-muted);">
                        Top ${includeNonReporting ? '' : 'reporting'} fields within ${radius} nm. 
                        (${reportingCount} reporting of ${totalConsidered} considered)
                    </div>
                </div>
                <div style="margin-bottom: 0.5rem; background: var(--card-bg-alt); padding: 0.5rem 1rem; border-radius: 20px; border: 1px solid var(--border-color);">
                    <label style="font-size: 0.85rem; cursor: pointer; display: flex; align-items: center; gap: 0.5rem;">
                        <input type="checkbox" id="toggle-non-reporting" ${includeNonReporting ? 'checked' : ''}>
                        Show non-reporting fields
                    </label>
                </div>
            </div>

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
                            ${alternatesList.length > 0 ? alternatesList.map(a => `
                                <tr>
                                    <td><span class="chip ${a.score > 70 ? 'success' : a.score > 30 ? 'info' : 'warning'}">${a.score}</span></td>
                                    <td>
                                        <div style="display: flex; align-items: center; gap: 0.4rem;">
                                            <strong>${a.icao}</strong>
                                            <span style="font-size: 0.65rem; color: var(--text-muted); text-transform: uppercase;">${a.type.replace('_airport', '')}</span>
                                        </div>
                                        <div style="font-size: 0.75rem; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px;">${a.name}</div>
                                    </td>
                                    <td>${a.distance_nm} nm<br><small>${a.bearing_deg}°</small></td>
                                    <td>${utils.getFlightCategoryChip(a.flight_category)}</td>
                                    <td>${a.wind || '<span style="color: var(--text-muted);">N/A</span>'}</td>
                                    <td>
                                        <div style="font-size: 0.8rem;">${a.rank_reason}</div>
                                        ${a.warnings.map(w => `<div style="color: var(--warning); font-size: 0.7rem;">⚠️ ${w}</div>`).join('')}
                                    </td>
                                </tr>
                            `).join('') : `
                                <tr><td colspan="6" style="text-align: center; padding: 3rem; color: var(--text-muted);">
                                    <div style="font-size: 1.2rem; margin-bottom: 0.5rem;">No strong reporting alternate candidates found within ${radius} NM</div>
                                    <p>Try increasing the search radius in settings or enabling non-reporting fields.</p>
                                </td></tr>
                            `}
                        </tbody>
                    </table>
                </div>

                <div style="margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem;">
                    <div style="font-size: 0.85rem; color: var(--text-muted);">
                        <strong>Exclusion Summary:</strong> 
                        ${noWeatherCount > 0 ? `${noWeatherCount} nearby fields were skipped because field weather was unavailable.` : 'No nearby fields were skipped.'}
                    </div>
                    <div class="warning-callout" style="font-size: 0.75rem; border-left-color: var(--text-muted); margin: 0; padding: 0.5rem 1rem;">
                        Operational awareness only. Always verify data in official publications.
                    </div>
                </div>
            </div>
        `;

        // Attach toggle handler
        const toggle = document.getElementById('toggle-non-reporting');
        if (toggle) {
            toggle.addEventListener('change', (e) => {
                renderDetailedAlternates(container, icao, e.target.checked);
            });
        }

    } catch (e) {
        console.error('Failed to render alternates:', e);
        container.innerHTML = `<div class="card danger"><h2>Failed to load alternates</h2><p>${e.message}</p></div>`;
    }
}

async function renderDetailedHazards(container, icao) {
    container.innerHTML = `
        <div class="page-header"><h1>${icao} Hazards & Alerts</h1></div>
        <div class="loading">Fetching regional hazards and convective awareness for ${icao}...</div>
    `;
    const data = await api.getHazards(icao);
    container.innerHTML = `
        <div class="page-header">
            <h1>${icao} Hazards & Alerts</h1>
        </div>
        ${utils.renderWarnings(data.warnings)}
        
        ${cards.renderConvectiveCard(data.convective_awareness)}

        <div class="card" style="margin-bottom: 2rem;">
            <h2>Regional Risk Level: ${utils.getRiskLevelChip(data.risk_level)}</h2>
            <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); margin-top: 1rem;">
                <div class="card" style="background: var(--card-bg-alt); box-shadow: none; border: 1px solid var(--border-color);">
                    <strong>NWS Alerts</strong>
                    <div style="font-size: 2rem;">${data.counts.nws_alerts}</div>
                </div>
                <div class="card" style="background: var(--card-bg-alt); box-shadow: none; border: 1px solid var(--border-color);">
                    <strong>SIGMETs</strong>
                    <div style="font-size: 2rem;">${data.counts.sigmets}</div>
                </div>
                <div class="card" style="background: var(--card-bg-alt); box-shadow: none; border: 1px solid var(--border-color);">
                    <strong>G-AIRMETs</strong>
                    <div style="font-size: 2rem;">${data.counts.gairmets}</div>
                </div>
                <div class="card" style="background: var(--card-bg-alt); box-shadow: none; border: 1px solid var(--border-color);">
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
            <h1>${icao} Directory</h1>
        </div>
        <div class="grid">
            <div class="card">
                <h2>General Information</h2>
                <table>
                    <thead><tr><th>Field</th><th>Value</th></tr></thead>
                    <tbody>
                        <tr><td><strong>Name</strong></td><td>${data.name}</td></tr>
                        <tr><td><strong>ICAO</strong></td><td>${data.icao}</td></tr>
                        <tr><td><strong>Elevation</strong></td><td>${data.elevation_ft} FT</td></tr>
                        <tr><td><strong>Latitude</strong></td><td>${data.lat.toFixed(6)}</td></tr>
                        <tr><td><strong>Longitude</strong></td><td>${data.lon.toFixed(6)}</td></tr>
                    </tbody>
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

async function renderSettings(content) {
    const settings = utils.getSettings();
    const refStatus = await api.getReferenceStatus();
    
    const publicModeNotice = settings.public_readonly_mode ? `
        <div class="warning-callout" style="margin-bottom: 1.5rem; border-left-color: var(--accent);">
            <strong>Public Read-Only Mode Active</strong>
            <p style="font-size: 0.85rem; margin-top: 0.25rem;">Preferences are saved in this browser only. Shared backend settings cannot be modified publicly.</p>
        </div>
    ` : '';

    content.innerHTML = `
        <div class="page-header">
            <h1>Settings</h1>
        </div>
        
        <div class="grid">
            <div class="card">
                <h2>Preferences</h2>
                ${publicModeNotice}
                <div style="margin-bottom: 1.5rem;">
                    <label style="display: block; margin-bottom: 0.25rem; font-weight: bold;">Default Airport (ICAO)</label>
                    <input type="text" id="set-default-apt" value="${settings.default_airport}" style="width: 100%; padding: 0.5rem; background: var(--input-bg); color: var(--input-text); border: 1px solid var(--input-border); border-radius: 4px;">
                </div>
                <div style="margin-bottom: 1.5rem;">
                    <label style="display: block; margin-bottom: 0.25rem; font-weight: bold;">Alternate Search Radius (NM)</label>
                    <input type="number" id="set-radius" value="${settings.alternate_radius_nm}" style="width: 100%; padding: 0.5rem; background: var(--input-bg); color: var(--input-text); border: 1px solid var(--input-border); border-radius: 4px;">
                </div>
                <div style="margin-bottom: 2rem;">
                    <label style="display: block; margin-bottom: 0.25rem; font-weight: bold;">Refresh Interval (Seconds)</label>
                    <input type="number" id="set-refresh" value="${settings.refresh_interval_seconds}" style="width: 100%; padding: 0.5rem; background: var(--input-bg); color: var(--input-text); border: 1px solid var(--input-border); border-radius: 4px;">
                </div>
                
                ${currentIcao ? `<button id="set-current-default-btn" class="chip info" style="margin-bottom: 1rem; width: 100%; cursor:pointer;">Use ${currentIcao} as Default</button>` : ''}

                <button id="save-settings-btn" class="chip info" style="padding: 1rem; width: 100%; cursor:pointer; font-size: 1rem;">Save Settings</button>
                <div id="settings-msg" style="margin-top: 1rem; text-align: center; font-weight: bold;"></div>
            </div>

            <div class="card">
                <h2>System & Data Status</h2>
                <div style="font-size: 0.9rem;">
                    <table style="width: 100%;">
                        <tr><td><strong>Airports</strong></td><td style="text-align: right;">${refStatus.airport_count.toLocaleString()}</td></tr>
                        <tr><td><strong>Runways</strong></td><td style="text-align: right;">${refStatus.runway_count.toLocaleString()}</td></tr>
                        <tr><td><strong>Frequencies</strong></td><td style="text-align: right;">${refStatus.frequency_count.toLocaleString()}</td></tr>
                        <tr><td><strong>Source</strong></td><td style="text-align: right;">${refStatus.source}</td></tr>
                        <tr><td><strong>Last Import</strong></td><td style="text-align: right;">${refStatus.last_imported_at === 'unknown' ? 'N/A' : utils.formatDate(refStatus.last_imported_at)}</td></tr>
                        <tr><td><strong>Mode</strong></td><td style="text-align: right;">${refStatus.public_readonly_mode ? 'Public Read-Only' : 'Private'}</td></tr>
                        <tr><td><strong>Debug APIs</strong></td><td style="text-align: right;">${refStatus.debug_public_endpoints ? 'Enabled' : 'Disabled'}</td></tr>
                    </table>
                </div>
                <div style="margin-top: 1rem; font-size: 0.75rem; color: var(--text-muted);">
                    <a href="#/about" style="color: inherit; text-decoration: underline;">Learn more about our data sources →</a>
                </div>
                <h2 style="margin-top: 2rem;">Official Resources</h2>
                <ul class="plain-english-list">
                    <li><a href="https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/dtpp/search/" target="_blank">FAA Terminal Procedures</a></li>
                    <li><a href="https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/dafd/" target="_blank">FAA Chart Supplements</a></li>
                </ul>
            </div>
        </div>
    `;

    document.getElementById('save-settings-btn').addEventListener('click', async () => {
        const msgEl = document.getElementById('settings-msg');
        const icao = document.getElementById('set-default-apt').value.trim().toUpperCase();
        const btn = document.getElementById('save-settings-btn');
        
        msgEl.style.color = 'var(--text-muted)';
        msgEl.innerText = 'Validating airport...';
        btn.disabled = true;

        try {
            await api.getDirectory(icao);
            const current = utils.getSettings();
            const newSettings = {
                ...current,
                default_airport: icao,
                alternate_radius_nm: parseInt(document.getElementById('set-radius').value),
                refresh_interval_seconds: parseInt(document.getElementById('set-refresh').value)
            };
            
            if (current.public_readonly_mode) {
                utils.saveLocalSettings(newSettings);
            } else {
                const saved = await api.updateSettings(newSettings);
                utils.saveSettings(saved);
            }
            
            msgEl.style.color = 'var(--success)';
            msgEl.innerText = 'Settings saved locally!';
        } catch (e) {
            msgEl.style.color = 'var(--danger)';
            msgEl.innerText = `Error: ${e.message}`;
        } finally {
            btn.disabled = false;
        }
    });

    if (currentIcao) {
        document.getElementById('set-current-default-btn').addEventListener('click', () => {
            document.getElementById('set-default-apt').value = currentIcao;
        });
    }

    setupAutocomplete(document.getElementById('set-default-apt'));
}
