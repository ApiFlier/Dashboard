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
    async getAlternates(icao, radius = 75) {
        return this._fetch(`/api/airport/${icao}/alternates?radius_nm=${radius}`);
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
    }
};
