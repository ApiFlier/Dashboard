const api = {
    async _fetch(url) {
        const res = await fetch(url);
        if (!res.ok) {
            const error = new Error(`Request failed for ${url}`);
            error.status = res.status;
            error.url = url;
            try {
                const data = await res.json();
                error.message = data.detail || `HTTP ${res.status}: ${res.statusText}`;
            } catch (e) {
                error.message = `HTTP ${res.status}: ${res.statusText}`;
            }
            throw error;
        }
        return res.json();
    },

    async getBrief(icao) {
        return this._fetch(`/api/airport/${icao}/brief`);
    },
    async getWeather(icao) {
        return this._fetch(`/api/airport/${icao}/weather`);
    },
    async getRunways(icao) {
        return this._fetch(`/api/airport/${icao}/runways`);
    },
    async getAlternates(icao, radius = 75, limit = 10, includeNonReporting = false) {
        return this._fetch(`/api/airport/${icao}/alternates?radius_nm=${radius}&limit=${limit}&include_non_reporting=${includeNonReporting}`);
    },
    async getHazards(icao, radius = 75) {
        return this._fetch(`/api/airport/${icao}/hazards?radius_nm=${radius}`);
    },
    async getDirectory(icao) {
        return this._fetch(`/api/airport/${icao}/directory`);
    },
    async getCoverage(icao) {
        return this._fetch(`/api/airport/${icao}/coverage`);
    },
    async getDashboard(icao) {
        return this._fetch(`/api/airport/${icao}/dashboard`);
    },
    async getSummary(icao) {
        return this._fetch(`/api/airport/${icao}/summary`);
    },
    async getBatchSummaries(idents) {
        if (!idents || idents.length === 0) return [];
        return this._fetch(`/api/airports/summary?idents=${idents.join(',')}`);
    },
    async getReferenceStatus() {
        return this._fetch(`/api/reference/status`);
    },
    async getSettings() {
        return this._fetch(`/api/settings?t=${Date.now()}`);
    },
    async updateSettings(settings) {
        const res = await fetch(`/api/settings`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        if (!res.ok) throw new Error('Failed to update settings');
        return res.json();
    },
    async getRecent() {
        return this._fetch(`/api/recent`);
    },
    async addRecent(icao) {
        return fetch(`/api/recent/${icao}`, { method: 'POST' });
    },
    async clearRecent() {
        return fetch(`/api/recent`, { method: 'DELETE' });
    },
    async getFavorites() {
        const settings = utils.getSettings();
        if (settings.public_readonly_mode) {
            return utils.getFavorites().map(ident => ({ ident, created_at: new Date().toISOString() }));
        }
        return this._fetch(`/api/favorites`);
    },
    async addFavorite(icao) {
        const settings = utils.getSettings();
        if (settings.public_readonly_mode) {
            utils.addFavorite(icao);
            return { status: "ok" };
        }
        return fetch(`/api/favorites/${icao}`, { method: 'POST' });
    },
    async removeFavorite(icao) {
        const settings = utils.getSettings();
        if (settings.public_readonly_mode) {
            utils.removeFavorite(icao);
            return { status: "ok" };
        }
        return fetch(`/api/favorites/${icao}`, { method: 'DELETE' });
    },
    async getSettingsDefaults() {
        return this._fetch(`/api/settings/defaults`);
    },
    async searchAirports(q, limit = 10) {
        return this._fetch(`/api/airports/search?q=${q}&limit=${limit}`);
    },

    _opsHeaders() {
        const token = localStorage.getItem('ops_session_token');
        return token ? { 'Authorization': `Bearer ${token}` } : {};
    },

    async _opsGet(url) {
        const res = await fetch(url, { headers: this._opsHeaders() });
        if (!res.ok) {
            const err = new Error(`Request failed for ${url}`);
            err.status = res.status;
            try { const d = await res.json(); err.message = d.detail || `HTTP ${res.status}`; } catch (e) { err.message = `HTTP ${res.status}`; }
            throw err;
        }
        return res.json();
    },

    async _opsPost(url, body) {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...this._opsHeaders() },
            body: JSON.stringify(body)
        });
        if (!res.ok) {
            const err = new Error(`Request failed for ${url}`);
            err.status = res.status;
            try { const d = await res.json(); err.message = d.detail || `HTTP ${res.status}`; } catch (e) { err.message = `HTTP ${res.status}`; }
            throw err;
        }
        return res.json();
    },

    async opsLogin(username, password) {
        return this._opsPost('/api/ops/auth/login', { username, password });
    },

    async opsStatus() {
        return this._opsGet('/api/ops/status');
    },

    async opsGetLogs(airportIdent, limit = 50) {
        const params = new URLSearchParams({ limit });
        if (airportIdent) params.set('airport_ident', airportIdent);
        return this._opsGet(`/api/ops/logs?${params}`);
    },

    async opsCreateLog(entry) {
        return this._opsPost('/api/ops/logs', entry);
    },

    async opsChangeCredentials(currentPassword, newUsername, newPassword) {
        const body = { current_password: currentPassword };
        if (newUsername) body.new_username = newUsername;
        if (newPassword) body.new_password = newPassword;
        return this._opsPost('/api/ops/auth/change-credentials', body);
    }
};
