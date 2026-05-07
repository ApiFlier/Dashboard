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
    async getDashboard(icao) {
        return this._fetch(`/api/airport/${icao}/dashboard`);
    },
    async getReferenceStatus() {
        return this._fetch(`/api/reference/status`);
    },
    async getSettingsDefaults() {
        return this._fetch(`/api/settings/defaults`);
    },
    async searchAirports(q) {
        return this._fetch(`/api/airports/search?q=${q}`);
    }
};
