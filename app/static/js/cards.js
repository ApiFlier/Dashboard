const cards = {
    renderRunwaySketch(runways, favoredId, windDir) {
        if (!runways || runways.length === 0) return '';
        
        const size = 300;
        const center = size / 2;
        const rwayLength = 120; // max half-length in pixels
        
        let paths = '';
        let labels = '';
        
        runways.forEach(r => {
            const isFavored = r.id === favoredId;
            // le_heading_deg is the direction you ARE heading when on that runway.
            // 0 is North (up in SVG). SVG angles are clockwise from positive X (East).
            // So North is -90 deg.
            const angleRad = (r.le_heading_deg - 90) * (Math.PI / 180);
            
            const x1 = center + Math.cos(angleRad) * rwayLength;
            const y1 = center + Math.sin(angleRad) * rwayLength;
            const x2 = center - Math.cos(angleRad) * rwayLength;
            const y2 = center - Math.sin(angleRad) * rwayLength;
            
            paths += `
                <line x1="${x2}" y1="${y2}" x2="${x1}" y2="${y1}" 
                    stroke="${isFavored ? 'var(--accent)' : '#ccc'}" 
                    stroke-width="${isFavored ? 8 : 5}" 
                    stroke-linecap="round" />
            `;
            
            // Label at the 'arrival' end (the end you are pointing towards)
            const lx = center + Math.cos(angleRad) * (rwayLength + 15);
            const ly = center + Math.sin(angleRad) * (rwayLength + 15);
            
            labels += `
                <text x="${lx}" y="${ly}" font-size="12" font-weight="bold" 
                    fill="${isFavored ? 'var(--accent)' : '#666'}" 
                    text-anchor="middle" alignment-baseline="middle">${r.id}</text>
            `;
        });

        let windArrow = '';
        if (windDir !== null && windDir !== undefined) {
            const windRad = (windDir - 90 + 180) * (Math.PI / 180); // point FROM direction
            const wx = center + Math.cos(windRad) * 60;
            const wy = center + Math.sin(windRad) * 60;
            
            windArrow = `
                <g transform="translate(${wx}, ${wy}) rotate(${windDir})">
                    <line x1="0" y1="20" x2="0" y2="-20" stroke="var(--danger)" stroke-width="2" marker-end="url(#arrowhead)" />
                </g>
                <defs>
                    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="0" refY="3.5" orient="auto">
                        <polygon points="0 0, 10 3.5, 0 7" fill="var(--danger)" />
                    </marker>
                </defs>
            `;
        }

        return `
            <div class="runway-sketch-container" style="text-align: center; margin: 1rem 0; background: #fcfcfc; border: 1px solid #eee; border-radius: 8px; padding: 1rem;">
                <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
                    <!-- N indicator -->
                    <text x="${center}" y="20" font-size="12" fill="#aaa" text-anchor="middle">N</text>
                    <line x1="${center}" y1="25" x2="${center}" y2="35" stroke="#eee" />
                    
                    ${paths}
                    ${labels}
                    ${windArrow}
                </svg>
                <div style="font-size: 0.7rem; color: var(--gray); margin-top: 0.5rem;">
                    Simplified runway sketch. Not for navigation.
                </div>
            </div>
        `;
    },

    renderBriefCard(brief) {
        return `
            <div class="card">
                <h2>Operational Brief</h2>
                ${utils.renderWarnings(brief.warnings)}
                <div style="display: flex; gap: 1rem; margin-bottom: 1rem;">
                    <div>Rules: ${utils.getFlightCategoryChip(brief.condition.flight_category)}</div>
                    <div>Weather: ${utils.getRiskLevelChip(brief.condition.weather_risk)}</div>
                    <div>Hazards: ${utils.getRiskLevelChip(brief.condition.hazard_risk)}</div>
                </div>
                <p><strong>Favored Runway:</strong> ${brief.favored_runway.end || 'None'} (${brief.favored_runway.reason})</p>
                
                <h3>Concerns</h3>
                <ul class="plain-english-list">
                    ${brief.main_concerns.length > 0 ? brief.main_concerns.map(c => `<li>${c}</li>`).join('') : '<li>No major concerns</li>'}
                </ul>

                <h3>Summary</h3>
                <ul class="plain-english-list">
                    ${brief.plain_english.map(p => `<li>${p}</li>`).join('')}
                </ul>

                <div class="card-footer">
                    <a href="#/airport/${brief.airport.icao}/brief">View Full Brief →</a>
                </div>
            </div>
        `;
    },

    renderWeatherCard(weather) {
        const metar = weather.metar;
        const taf = weather.taf;
        
        let html = `
            <div class="card">
                <h2>Weather</h2>
                ${utils.renderWarnings(weather.warnings)}
        `;

        if (metar) {
            html += `
                <div style="margin-bottom: 1rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                        <strong>METAR</strong>
                        ${utils.getFlightCategoryChip(metar.flight_category)}
                    </div>
                    <code style="display: block; background: #f8f9fa; padding: 0.5rem; margin-bottom: 0.5rem; font-size: 0.85rem; border-radius: 4px;">${metar.raw}</code>
                    <div class="grid" style="grid-template-columns: 1fr 1fr; gap: 0.5rem; font-size: 0.9rem;">
                        <div>Wind: ${utils.formatWind(metar.wind)}</div>
                        <div>Visibility: ${metar.visibility_sm ?? 'N/A'} SM</div>
                        <div>Ceiling: ${metar.ceiling_ft_agl ?? 'None'} FT</div>
                        <div>Altimeter: ${metar.altimeter_in_hg ?? 'N/A'} IN</div>
                    </div>
                    <div style="font-size: 0.75rem; color: #666; margin-top: 0.5rem;">Observed: ${utils.formatDate(metar.observed_at)}</div>
                </div>
            `;
        } else {
            html += '<p>METAR not available</p>';
        }

        if (taf) {
            html += `
                <div>
                    <strong>TAF</strong>
                    <code style="display: block; background: #f8f9fa; padding: 0.5rem; font-size: 0.85rem; border-radius: 4px; margin-top: 0.5rem;">${taf.raw}</code>
                    <div style="font-size: 0.75rem; color: #666; margin-top: 0.5rem;">Issued: ${utils.formatDate(taf.issued_at)}</div>
                </div>
            `;
        } else {
            html += '<p>TAF not available</p>';
        }

        html += `
                <div class="card-footer">
                    <a href="#/airport/${weather.airport}/weather">Detailed Weather →</a>
                </div>
            </div>
        `;
        return html;
    },

    renderRunwaysCard(analysis) {
        let html = `
            <div class="card">
                <h2>Runway Analysis</h2>
                ${utils.renderWarnings(analysis.warnings)}
                <p><strong>Favored:</strong> ${analysis.favored_runway.id || 'None'} - ${analysis.favored_runway.reason}</p>
                
                <div style="font-size: 0.8rem; color: var(--gray); margin-bottom: 0.5rem; text-align:center;">
                    Simplified sketch below. <strong>Use official FAA diagrams for navigation.</strong>
                </div>
                ${this.renderRunwaySketch(analysis.runways, analysis.favored_runway.id, analysis.wind_direction_deg)}

                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>HW</th>
                                <th>TW</th>
                                <th>XW</th>
                                <th>Risks</th>
                            </tr>
                        </thead>
                        <tbody>
        `;

        analysis.runways.forEach(r => {
            const isFavored = r.id === analysis.favored_runway.id;
            const risks = [];
            if (r.risk_flags.strong_crosswind) risks.push('Strong XW');
            else if (r.risk_flags.crosswind) risks.push('XW');
            if (r.risk_flags.strong_tailwind) risks.push('Strong TW');
            else if (r.risk_flags.tailwind) risks.push('TW');
            if (r.risk_flags.gusty) risks.push('Gusty');

            html += `
                <tr class="${isFavored ? 'favored' : ''}">
                    <td>${r.id}</td>
                    <td>${r.headwind_kt ?? 0}</td>
                    <td>${r.tailwind_kt ?? 0}</td>
                    <td>${r.crosswind_kt ?? 0}${r.crosswind_gust_kt ? ` (${r.crosswind_gust_kt})` : ''}</td>
                    <td class="risk-flag">${risks.join(', ')}</td>
                </tr>
            `;
        });

        html += `
                        </tbody>
                    </table>
                </div>
                <div class="card-footer">
                    <a href="#/airport/${analysis.airport}/runways">All Runways →</a>
                </div>
            </div>
        `;
        return html;
    },

    renderAlternatesCard(alternates, icao) {
        let html = `
            <div class="card">
                <h2>Top Alternates</h2>
                <div class="table-container">
                    <table>
                        <thead>
                            <tr>
                                <th>Airport</th>
                                <th>Dist</th>
                                <th>Rules</th>
                                <th>Wind</th>
                            </tr>
                        </thead>
                        <tbody>
        `;

        alternates.slice(0, 5).forEach(a => {
            html += `
                <tr>
                    <td><strong>${a.icao}</strong></td>
                    <td>${a.distance_nm}nm</td>
                    <td>${utils.getFlightCategoryChip(a.flight_category)}</td>
                    <td style="font-size: 0.8rem;">${a.wind || 'N/A'}</td>
                </tr>
            `;
        });

        html += `
                        </tbody>
                    </table>
                </div>
                <div class="card-footer">
                    <a href="#/airport/${icao}/alternates">View All Alternates →</a>
                </div>
            </div>
        `;
        return html;
    },

    renderHazardsCard(hazards) {
        let html = `
            <div class="card">
                <h2>Hazards & Alerts</h2>
                ${utils.renderWarnings(hazards.warnings)}
                <div style="margin-bottom: 1rem;">
                    Risk Level: ${utils.getRiskLevelChip(hazards.risk_level)}
                </div>
                <div class="grid" style="grid-template-columns: repeat(2, 1fr); gap: 0.5rem; font-size: 0.85rem; margin-bottom: 1rem;">
                    <div style="background: #f8f9fa; padding: 0.5rem; border-radius: 4px;">NWS Alerts: ${hazards.counts.nws_alerts}</div>
                    <div style="background: #f8f9fa; padding: 0.5rem; border-radius: 4px;">SIGMETs: ${hazards.counts.sigmets}</div>
                    <div style="background: #f8f9fa; padding: 0.5rem; border-radius: 4px;">G-AIRMETs: ${hazards.counts.gairmets}</div>
                    <div style="background: #f8f9fa; padding: 0.5rem; border-radius: 4px;">CWAs: ${hazards.counts.cwas}</div>
                </div>
        `;

        if (hazards.nws_alerts.length > 0) {
            html += '<strong>NWS Alerts</strong><ul style="padding-left: 1.2rem; font-size: 0.85rem; margin-top: 0.5rem;">';
            hazards.nws_alerts.slice(0, 3).forEach(alert => {
                html += `<li>${alert.properties.event}</li>`;
            });
            if (hazards.nws_alerts.length > 3) html += '<li>...</li>';
            html += '</ul>';
        }

        html += `
                <div class="card-footer">
                    <a href="#/airport/${hazards.airport}/hazards">View All Hazards →</a>
                </div>
            </div>
        `;
        return html;
    },

    renderDirectoryCard(airport) {
...
        html += `
                </ul>
                <div class="card-footer">
                    <a href="#/airport/${airport.icao}/directory">Full Directory Info →</a>
                </div>
            </div>
        `;
        return html;
    },

    renderOfficialResourcesCard(icao) {
        // Remove 'K' for search if it's a 4-letter ICAO starting with K (common for US)
        const searchId = icao.startsWith('K') && icao.length === 4 ? icao.substring(1) : icao;
        
        return `
            <div class="card official-resources-card">
                <h2>Official FAA Resources</h2>
                <p style="font-size: 0.8rem; color: var(--gray); margin-bottom: 1rem;">Certified aeronautical data and diagrams.</p>
                
                <a href="https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/dtpp/search/results/?cycle=current&ident=${searchId}" target="_blank">
                    <span>Airport Diagrams & Terminal Procedures</span>
                </a>
                <a href="https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/dafd/search/results/?cycle=current&ident=${searchId}" target="_blank">
                    <span>Chart Supplement (d-AFD)</span>
                </a>
                
                <div class="warning-callout" style="margin-top: 1rem; font-size: 0.75rem; border-left-color: var(--gray);">
                    Always verify data in official publications. This app is for advisory use only.
                </div>
            </div>
        `;
    }
};
