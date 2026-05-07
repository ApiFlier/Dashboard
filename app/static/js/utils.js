const utils = {
    formatDate(isoString) {
        if (!isoString) return 'N/A';
        const date = new Date(isoString);
        return date.toLocaleString();
    },

    formatWind(wind) {
        if (!wind || (wind.speed_kt === null && !wind.variable)) return 'N/A';
        if (wind.speed_kt === 0) return 'Calm';
        
        let str = '';
        if (wind.variable) {
            str = 'VRB';
        } else {
            str = String(wind.direction_deg).padStart(3, '0');
        }
        
        str += `@${wind.speed_kt}`;
        if (wind.gust_kt) {
            str += `G${wind.gust_kt}`;
        }
        str += ' KT';
        return str;
    },

    getFlightCategoryChip(category) {
        const cat = (category || 'UNKNOWN').toUpperCase();
        let className = cat.toLowerCase().replace(/\s+/g, '-');
        
        // Map special labels to a neutral class if not standard rules
        const standardRules = ['VFR', 'MVFR', 'IFR', 'LIFR'];
        if (!standardRules.includes(cat)) {
            className = 'info';
        }
        
        return `<span class="chip ${className}">${cat}</span>`;
    },

    getRiskLevelChip(level) {
        const l = (level || 'unknown').toLowerCase();
        return `<span class="chip risk-${l}">${l}</span>`;
    },

    renderWarnings(warnings) {
        if (!warnings || warnings.length === 0) return '';
        return warnings.map(w => `<div class="warning-callout">⚠️ ${w}</div>`).join('');
    },

    getRecentAirports() {
        const recent = localStorage.getItem('recent_airports');
        return recent ? JSON.parse(recent) : [];
    },

    addRecentAirport(icao) {
        let recent = this.getRecentAirports();
        recent = recent.filter(a => a !== icao);
        recent.unshift(icao);
        recent = recent.slice(0, 10);
        localStorage.setItem('recent_airports', JSON.stringify(recent));
    },

    getFavorites() {
        const favs = localStorage.getItem('favorites');
        return favs ? JSON.parse(favs) : [];
    },

    addFavorite(icao) {
        let favs = this.getFavorites();
        if (!favs.includes(icao)) {
            favs.push(icao);
            localStorage.setItem('favorites', JSON.stringify(favs));
        }
    },

    removeFavorite(icao) {
        let favs = this.getFavorites();
        favs = favs.filter(a => a !== icao);
        localStorage.setItem('favorites', JSON.stringify(favs));
    },

    getSettings() {
        const defaults = {
            default_airport: '',
            alternate_radius_nm: 75,
            refresh_interval_seconds: 300,
            theme_mode: 'system',
            monitor_mode: false,
            accent_color: 'blue',
            public_readonly_mode: true
        };
        
        // 1. Get backend settings (cached in localStorage)
        const savedBackend = localStorage.getItem('app_settings');
        const backendSettings = savedBackend ? JSON.parse(savedBackend) : {};
        
        // 2. Get local overrides (only applied if public_readonly_mode is true)
        const savedLocal = localStorage.getItem('local_settings');
        const localSettings = savedLocal ? JSON.parse(savedLocal) : {};
        
        const isPublic = backendSettings.public_readonly_mode !== false; // Default to true if unknown
        
        if (isPublic) {
            // Merge: local overrides take precedence over backend defaults
            return { ...defaults, ...backendSettings, ...localSettings };
        } else {
            // Local/private mode: backend settings are authoritative
            return { ...defaults, ...backendSettings };
        }
    },

    saveSettings(settings) {
        // This caches backend settings
        localStorage.setItem('app_settings', JSON.stringify(settings));
        this.applyTheme(settings.theme_mode);
    },

    saveLocalSettings(settings) {
        // This saves user's browser-specific overrides
        localStorage.setItem('local_settings', JSON.stringify(settings));
        this.applyTheme(settings.theme_mode);
    },

    applyTheme(mode) {
        if (mode === 'dark') {
            document.body.classList.add('theme-dark');
            document.body.classList.remove('theme-light');
        } else if (mode === 'light') {
            document.body.classList.add('theme-light');
            document.body.classList.remove('theme-dark');
        } else {
            document.body.classList.remove('theme-light', 'theme-dark');
        }
    },

    renderStatusLabel(status) {
        const labels = {
            'live': { class: 'vfr', text: 'Live' },
            'cached': { class: 'info', text: 'Cached' },
            'stale': { class: 'warning', text: 'Stale' },
            'unavailable': { class: 'unknown', text: 'Unavailable' },
            'error': { class: 'danger', text: 'Error' }
        };
        const s = status ? status.toLowerCase() : 'unknown';
        const config = labels[s] || { class: 'unknown', text: s.toUpperCase() };
        return `<span class="chip ${config.class}" style="font-size: 0.6rem; padding: 0.1rem 0.4rem; margin-left: 0.5rem; vertical-align: middle;">${config.text}</span>`;
    }
};
