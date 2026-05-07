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
        recent = recent.slice(0, 5);
        localStorage.setItem('recent_airports', JSON.stringify(recent));
    },

    getSettings() {
        const defaults = {
            default_airport: 'KAGC',
            alternate_radius: 75,
            refresh_interval: 300
        };
        const saved = localStorage.getItem('app_settings');
        return saved ? { ...defaults, ...JSON.parse(saved) } : defaults;
    },

    saveSettings(settings) {
        localStorage.setItem('app_settings', JSON.stringify(settings));
    }
};
