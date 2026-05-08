const cards = {
    renderRunwaySketch(runways, favoredId, windDir) {
        if (!runways || runways.length === 0) return '';
        
        const size = 300;
        const center = size / 2;
        const padding = 40;
        const drawSize = size - (padding * 2);
        
        // 1. Group runways by physical pavement
        const physicalRunways = [];
        const processedIds = new Set();

        // Separate runways with coordinates for accurate layout
        const runwaysWithCoords = runways.filter(r => 
            Number.isFinite(r.le_latitude_deg) && Number.isFinite(r.le_longitude_deg) &&
            Number.isFinite(r.he_latitude_deg) && Number.isFinite(r.he_longitude_deg)
        );

        runwaysWithCoords.forEach(r => {
            if (processedIds.has(r.id)) return;

            // Find reciprocal
            const reciprocal = runwaysWithCoords.find(other => 
                other.id !== r.id &&
                Math.abs(other.le_latitude_deg - r.he_latitude_deg) < 0.0001 &&
                Math.abs(other.le_longitude_deg - r.he_longitude_deg) < 0.0001 &&
                Math.abs(other.he_latitude_deg - r.le_latitude_deg) < 0.0001 &&
                Math.abs(other.he_longitude_deg - r.le_longitude_deg) < 0.0001
            );

            physicalRunways.push({
                le_id: r.id,
                he_id: reciprocal ? reciprocal.id : null,
                le_lat: r.le_latitude_deg,
                le_lon: r.le_longitude_deg,
                he_lat: r.he_latitude_deg,
                he_lon: r.he_longitude_deg,
                is_favored_le: r.id === favoredId,
                is_favored_he: reciprocal ? reciprocal.id === favoredId : false
            });

            processedIds.add(r.id);
            if (reciprocal) processedIds.add(reciprocal.id);
        });

        let paths = '';
        let labels = '';
        let hasInvalidGeometry = false;
        let drawnCount = 0;
        let isAccurate = physicalRunways.length > 0;

        if (isAccurate) {
            // Accurate Layout Logic
            const points = [];
            physicalRunways.forEach(r => {
                points.push({ lat: r.le_lat, lon: r.le_lon });
                points.push({ lat: r.he_lat, lon: r.he_lon });
            });

            const avgLat = points.reduce((sum, p) => sum + p.lat, 0) / points.length;
            const avgLon = points.reduce((sum, p) => sum + p.lon, 0) / points.length;
            const latRad = avgLat * (Math.PI / 180);

            const project = (lat, lon) => {
                const x = (lon - avgLon) * 111320 * Math.cos(latRad);
                const y = (lat - avgLat) * 111320;
                return { x, y: -y };
            };

            const projectedPoints = points.map(p => project(p.lat, p.lon));
            const minX = Math.min(...projectedPoints.map(p => p.x));
            const maxX = Math.max(...projectedPoints.map(p => p.x));
            const minY = Math.min(...projectedPoints.map(p => p.y));
            const maxY = Math.max(...projectedPoints.map(p => p.y));

            const width = maxX - minX || 1;
            const height = maxY - minY || 1;
            const scale = Math.min(drawSize / width, drawSize / height);

            const toSvg = (p) => ({
                x: center + (p.x - (minX + maxX) / 2) * scale,
                y: center + (p.y - (minY + maxY) / 2) * scale
            });

            physicalRunways.forEach(r => {
                const p1 = toSvg(project(r.le_lat, r.le_lon));
                const p2 = toSvg(project(r.he_lat, r.he_lon));
                const anyFavored = r.is_favored_le || r.is_favored_he;

                paths += `
                    <line x1="${p1.x}" y1="${p1.y}" x2="${p2.x}" y2="${p2.y}" 
                        stroke="${anyFavored ? 'var(--accent)' : 'var(--border-color)'}" 
                        stroke-width="${anyFavored ? 8 : 5}" 
                        stroke-linecap="round" opacity="0.8" />
                `;

                // Labels at both ends
                const angle = Math.atan2(p1.y - p2.y, p1.x - p2.x);
                const offset = 18;
                
                const l1 = { x: p1.x + Math.cos(angle) * offset, y: p1.y + Math.sin(angle) * offset };
                const l2 = { x: p2.x - Math.cos(angle) * offset, y: p2.y - Math.sin(angle) * offset };

                if (Number.isFinite(l1.x) && Number.isFinite(l1.y)) {
                    labels += `<text x="${l1.x}" y="${l1.y}" font-size="10" font-weight="bold" fill="${r.is_favored_le ? 'var(--accent)' : 'var(--text-muted)'}" text-anchor="middle" alignment-baseline="middle">${r.le_id}</text>`;
                }
                if (r.he_id && Number.isFinite(l2.x) && Number.isFinite(l2.y)) {
                    labels += `<text x="${l2.x}" y="${l2.y}" font-size="10" font-weight="bold" fill="${r.is_favored_he ? 'var(--accent)' : 'var(--text-muted)'}" text-anchor="middle" alignment-baseline="middle">${r.he_id}</text>`;
                }
                drawnCount++;
            });
        } else {
            // Fallback Heading-based Logic
            const rwayLength = 120;
            const processedFallbackIds = new Set();

            runways.forEach(r => {
                if (processedFallbackIds.has(r.id)) return;
                
                const heading = Number(r.heading ?? r.heading_deg ?? r.le_heading_deg ?? r.true_heading_deg);
                if (!Number.isFinite(heading)) {
                    hasInvalidGeometry = true;
                    return;
                }

                // Find reciprocal for fallback grouping
                const reciprocal = runways.find(other => 
                    other.id !== r.id && 
                    Math.abs(((Number(other.heading ?? other.le_heading_deg) + 180) % 360) - heading) < 5
                );

                const isFavoredLe = r.id === favoredId;
                const isFavoredHe = reciprocal ? reciprocal.id === favoredId : false;
                const anyFavored = isFavoredLe || isFavoredHe;

                const angleRad = (heading - 90) * (Math.PI / 180);
                const x1 = center + Math.cos(angleRad) * rwayLength;
                const y1 = center + Math.sin(angleRad) * rwayLength;
                const x2 = center - Math.cos(angleRad) * rwayLength;
                const y2 = center - Math.sin(angleRad) * rwayLength;
                
                if ([x1, y1, x2, y2].every(Number.isFinite)) {
                    paths += `
                        <line x1="${x2}" y1="${y2}" x2="${x1}" y2="${y1}" 
                            stroke="${anyFavored ? 'var(--accent)' : 'var(--border-color)'}" 
                            stroke-width="${anyFavored ? 8 : 5}" 
                            stroke-linecap="round" opacity="0.8" />
                    `;
                    
                    const l1 = { x: center + Math.cos(angleRad) * (rwayLength + 15), y: center + Math.sin(angleRad) * (rwayLength + 15) };
                    const l2 = { x: center - Math.cos(angleRad) * (rwayLength + 15), y: center - Math.sin(angleRad) * (rwayLength + 15) };
                    
                    if (Number.isFinite(l1.x) && Number.isFinite(l1.y)) {
                        labels += `<text x="${l1.x}" y="${l1.y}" font-size="12" font-weight="bold" fill="${isFavoredLe ? 'var(--accent)' : 'var(--text-muted)'}" text-anchor="middle" alignment-baseline="middle">${r.id}</text>`;
                    }
                    if (reciprocal && Number.isFinite(l2.x) && Number.isFinite(l2.y)) {
                        labels += `<text x="${l2.x}" y="${l2.y}" font-size="12" font-weight="bold" fill="${isFavoredHe ? 'var(--accent)' : 'var(--text-muted)'}" text-anchor="middle" alignment-baseline="middle">${reciprocal.id}</text>`;
                    }
                    drawnCount++;
                } else {
                    hasInvalidGeometry = true;
                }
                
                processedFallbackIds.add(r.id);
                if (reciprocal) processedFallbackIds.add(reciprocal.id);
            });
        }

        if (drawnCount === 0) {
            return `
                <div class="runway-sketch-container" style="text-align: center; margin: 1rem 0; background: var(--card-bg-alt); border: 1px solid var(--border-color); border-radius: 8px; padding: 1rem; color: var(--text);">
                    <p>Interactive runway sketch unavailable due to missing reference coordinates. See runway table below.</p>
                </div>
            `;
        }

        let windArrow = '';
        if (windDir !== null && windDir !== undefined && Number.isFinite(Number(windDir))) {
            const windRad = (Number(windDir) - 90 + 180) * (Math.PI / 180); 
            const wx = center + Math.cos(windRad) * 60;
            const wy = center + Math.sin(windRad) * 60;
            
            if (Number.isFinite(wx) && Number.isFinite(wy)) {
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
        }

        return `
            <div class="runway-sketch-container" style="text-align: center; margin: 1rem 0; background: var(--card-bg-alt); border: 1px solid var(--border-color); border-radius: 8px; padding: 1rem;">
                <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
                    <text x="${center}" y="20" font-size="12" fill="var(--text-muted)" text-anchor="middle">N</text>
                    <line x1="${center}" y1="25" x2="${center}" y2="35" stroke="var(--border-color)" />
                    ${paths}
                    ${labels}
                    ${windArrow}
                </svg>
                <div style="display: flex; justify-content: center; gap: 1rem; margin-top: 0.5rem; font-size: 0.7rem; color: var(--text-muted);">
                    <div style="display: flex; align-items: center; gap: 0.25rem;">
                        <span style="width: 10px; height: 10px; background: var(--accent); border-radius: 2px;"></span> Favored End
                    </div>
                    <div style="display: flex; align-items: center; gap: 0.25rem;">
                        <span style="width: 10px; height: 2px; background: var(--danger);"></span> Wind Arrow
                    </div>
                </div>
                <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.5rem; font-style: italic;">
                    ${isAccurate ? 'Layout based on stored runway geometry.' : 'Layout based on heading/length only. Geometry is approximate.'}
                </div>
                ${hasInvalidGeometry ? '<div style="font-size: 0.75rem; color: var(--warning); margin-top: 0.25rem;">Reference geometry missing for some runways.</div>' : ''}
                <div style="font-size: 0.65rem; color: var(--text-muted); margin-top: 0.25rem; opacity: 0.8;">
                    Simplified airport layout. Not for navigation.
                </div>
            </div>
        `;
    },

    renderBriefCard(brief) {
        if (!brief) {
            return `
                <div class="card">
                    <h2>Operational Brief</h2>
                    <p>Brief data unavailable.</p>
                </div>
            `;
        }

        const condition = brief.condition || {};
        const favored = brief.favored_runway || {};
        const airport = brief.airport || {};
        const concerns = Array.isArray(brief.main_concerns) ? brief.main_concerns : [];
        const plainEnglish = Array.isArray(brief.plain_english) ? brief.plain_english : [];
        const warnings = Array.isArray(brief.warnings) ? brief.warnings : [];

        return `
            <div class="card">
                <h2>Operational Brief</h2>
                ${utils.renderWarnings(warnings)}
                <div style="display: flex; gap: 1rem; margin-bottom: 1rem; flex-wrap: wrap;">
                    <div>Rules: ${utils.getFlightCategoryChip(condition.flight_category)}</div>
                    <div>Weather: ${utils.getRiskLevelChip(condition.weather_risk)}</div>
                    <div>Hazards: ${utils.getRiskLevelChip(condition.hazard_risk)}</div>
                </div>
                <p><strong>Favored Runway:</strong> ${favored.end || 'None'} (${favored.reason || 'Reason unavailable'})</p>
                
                <h3>Concerns</h3>
                <ul class="plain-english-list">
                    ${concerns.length > 0 ? concerns.map(c => `<li>${c}</li>`).join('') : '<li>No major concerns</li>'}
                </ul>

                <h3>Summary</h3>
                <ul class="plain-english-list">
                    ${plainEnglish.length > 0 ? plainEnglish.map(p => `<li>${p}</li>`).join('') : '<li>No summary available</li>'}
                </ul>

                <div class="card-footer">
                    <a href="#/airport/${airport.icao || ''}/brief">View Full Brief →</a>
                </div>
            </div>
        `;
    },

    renderWeatherCard(weather) {
        if (!weather) {
            return `
                <div class="card">
                    <h2>Weather</h2>
                    <p>Weather data unavailable.</p>
                </div>
            `;
        }
        const metar = weather.metar;
        const taf = weather.taf;
        const nearby = weather.nearby_weather_stations || [];
        
        let html = `
            <div class="card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <h2 style="margin: 0;">Weather</h2>
                    <a href="#/about" style="font-size: 0.75rem; color: var(--text-muted); text-decoration: underline;">About this data</a>
                </div>
                ${utils.renderWarnings(weather.warnings)}
        `;

        if (metar) {
            html += `
                <div style="margin-bottom: 1rem;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                        <strong>Field METAR</strong>
                        ${utils.getFlightCategoryChip(metar.flight_category)}
                    </div>
                    <code style="display: block; background: var(--code-bg); color: var(--code-text); padding: 0.5rem; margin-bottom: 0.5rem; font-size: 0.85rem; border-radius: 4px;">${metar.raw}</code>
                    <div class="grid" style="grid-template-columns: 1fr 1fr; gap: 0.5rem; font-size: 0.9rem;">
                        <div>Wind: ${utils.formatWind(metar.wind)}</div>
                        <div>Visibility: ${metar.visibility_sm ?? 'N/A'} SM</div>
                        <div>Ceiling: ${metar.ceiling_ft_agl ?? 'None'} FT</div>
                        <div>Altimeter: ${metar.altimeter_in_hg ?? 'N/A'} IN</div>
                    </div>
                    <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.5rem;">Observed: ${utils.formatDate(metar.observed_at)}</div>
                </div>
            `;
        } else {
            html += `
                <div style="margin-bottom: 1rem;">
                    <p style="color: var(--warning); font-weight: bold; margin-bottom: 0.5rem;">Field METAR unavailable at this time.</p>
                    ${nearby.length > 0 ? `
                        <p style="font-size: 0.9rem; margin-bottom: 0.5rem;"><strong>Nearby reporting weather:</strong> (Not field conditions)</p>
                        <div class="table-container">
                            <table style="font-size: 0.85rem;">
                                <thead>
                                    <tr>
                                        <th>ID</th>
                                        <th>Dist</th>
                                        <th>Rules</th>
                                        <th>Wind</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${nearby.map(s => `
                                        <tr>
                                            <td><strong>${s.ident}</strong></td>
                                            <td>${s.distance_nm}nm</td>
                                            <td>${utils.getFlightCategoryChip(s.flight_category)}</td>
                                            <td>${s.wind || 'N/A'}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    ` : '<p>No nearby weather reporting available.</p>'}
                </div>
            `;
        }

        if (taf) {
            html += `
                <div>
                    <strong>TAF</strong>
                    <code style="display: block; background: var(--code-bg); color: var(--code-text); padding: 0.5rem; font-size: 0.85rem; border-radius: 4px; margin-top: 0.5rem;">${taf.raw}</code>
                    <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.5rem;">Issued: ${utils.formatDate(taf.issued_at)}</div>
                </div>
            `;
        } else if (!metar && nearby.length === 0) {
             // Already showed unavailable message
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

    renderCoverageCard(coverage) {
        if (!coverage) return '';
        
        const statusIcon = (avail) => avail ? '✅' : '❌';
        
        return `
            <div class="card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <h2 style="margin: 0;">Data Coverage</h2>
                    <a href="#/about" style="font-size: 0.75rem; color: var(--text-muted); text-decoration: underline;">About this data</a>
                </div>
                <div class="grid" style="grid-template-columns: 1fr 1fr; gap: 0.5rem; font-size: 0.9rem;">
                    <div>Field METAR: ${statusIcon(coverage.has_field_metar)}</div>
                    <div>TAF: ${statusIcon(coverage.has_taf)}</div>
                    <div>Runways: ${statusIcon(coverage.has_runways)}</div>
                    <div>Frequencies: ${statusIcon(coverage.has_frequencies)}</div>
                    <div>Runway Geometry: ${coverage.has_runway_geometry ? '✅ Accurate' : '⚠️ Approx'}</div>
                </div>
                ${coverage.nearby_weather_stations && coverage.nearby_weather_stations.length > 0 && !coverage.has_field_metar ? `
                    <div style="margin-top: 1rem; padding-top: 0.5rem; border-top: 1px solid var(--border-color);">
                        <strong>Nearby Reporting Stations:</strong>
                        <ul style="padding-left: 1.2rem; font-size: 0.85rem; margin-top: 0.5rem;">
                            ${coverage.nearby_weather_stations.map(s => `<li>${s.ident} (${s.distance_nm} nm): ${utils.getFlightCategoryChip(s.flight_category)}</li>`).join('')}
                        </ul>
                    </div>
                ` : ''}
                <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.5rem;">Data source: ${coverage.source}</div>
            </div>
        `;
    },

    renderRunwaysCard(analysis) {
        if (!analysis) {
            return `
                <div class="card">
                    <h2>Runway Analysis</h2>
                    <p>Runway data unavailable.</p>
                </div>
            `;
        }
        const favoredId = analysis.favored_runway.id || 'None';
        const favoredReason = analysis.favored_runway.reason || 'Reason unavailable';

        let html = `
            <div class="card">
                <h2>Runway Analysis</h2>
                ${utils.renderWarnings(analysis.warnings)}
                <p><strong>Favored:</strong> ${favoredId} — ${favoredReason}</p>
                
                <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.5rem; text-align:center;">
                    Simplified sketch below. <strong>Use official FAA diagrams for navigation.</strong>
                </div>
                ${cards.renderRunwaySketch(analysis.runways, analysis.favored_runway.id, analysis.wind_direction_deg)}

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
        if (!alternates || alternates.error) {
            return `
                <div class="card">
                    <h2>Top Alternates</h2>
                    <p>Alternate data unavailable.</p>
                </div>
            `;
        }
        
        const alternatesList = Array.isArray(alternates)
            ? alternates
            : Array.isArray(alternates?.alternates)
                ? alternates.alternates
                : [];
        
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

        if (alternatesList.length === 0) {
            html += '<tr><td colspan="4" style="text-align: center; padding: 2rem; color: var(--text-muted);">No strong reporting alternate candidates found nearby.</td></tr>';
        } else {
            alternatesList.slice(0, 5).forEach(a => {
                html += `
                    <tr>
                        <td><strong>${a.icao}</strong></td>
                        <td>${a.distance_nm}nm</td>
                        <td>${utils.getFlightCategoryChip(a.flight_category)}</td>
                        <td style="font-size: 0.8rem;">${a.wind || 'N/A'}</td>
                    </tr>
                `;
            });
        }

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

    renderConvectiveCard(convective) {
        if (!convective) return '';
        
        const isHigh = convective.risk_level === 'high';
        const isMod = convective.risk_level === 'moderate';
        const borderStyle = isHigh ? 'border: 2px solid var(--danger);' : isMod ? 'border: 2px solid var(--warning);' : 'border: 1px solid var(--border-color);';
        const bgStyle = isHigh ? 'background: rgba(239, 68, 68, 0.1);' : isMod ? 'background: rgba(245, 158, 11, 0.1);' : 'background: var(--card-bg-alt);';

        return `
            <div style="margin-bottom: 1rem; padding: 1rem; border-radius: 8px; ${borderStyle} ${bgStyle}">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <strong style="font-size: 1rem;">Convective / Lightning Awareness</strong>
                    ${utils.getRiskLevelChip(convective.risk_level)}
                </div>
                <p style="margin: 0.5rem 0; font-weight: bold; font-size: 0.95rem;">${convective.summary}</p>
                ${convective.indicators.length > 0 ? `
                    <ul style="margin: 0.5rem 0; padding-left: 1.2rem; font-size: 0.85rem;">
                        ${convective.indicators.map(ind => `<li>${ind}</li>`).join('')}
                    </ul>
                ` : ''}
                <div style="font-size: 0.7rem; color: var(--text-muted); font-style: italic; margin-top: 0.5rem;">
                    ${convective.disclaimer}
                </div>
            </div>
        `;
    },

    renderHazardsCard(hazards) {
        if (!hazards) {
            return `
                <div class="card">
                    <h2>Hazards</h2>
                    <p>Hazard data unavailable.</p>
                </div>
            `;
        }
        let html = `
            <div class="card">
                <h2>Hazards & Alerts</h2>
                ${utils.renderWarnings(hazards.warnings)}

                ${cards.renderConvectiveCard(hazards.convective_awareness)}

                <div style="margin-bottom: 1rem;">
                    <strong>Alert Status:</strong> ${utils.getRiskLevelChip(hazards.risk_level)}
                </div>

                <div class="grid" style="grid-template-columns: repeat(2, 1fr); gap: 0.5rem; font-size: 0.85rem; margin-bottom: 1rem;">
                    <div style="background: var(--card-bg-alt); color: var(--text); padding: 0.5rem; border-radius: 4px; border: 1px solid var(--border-color);">NWS Alerts: ${hazards.counts.nws_alerts}</div>
                    <div style="background: var(--card-bg-alt); color: var(--text); padding: 0.5rem; border-radius: 4px; border: 1px solid var(--border-color);">SIGMETs: ${hazards.counts.sigmets}</div>
                    <div style="background: var(--card-bg-alt); color: var(--text); padding: 0.5rem; border-radius: 4px; border: 1px solid var(--border-color);">G-AIRMETs: ${hazards.counts.gairmets}</div>
                    <div style="background: var(--card-bg-alt); color: var(--text); padding: 0.5rem; border-radius: 4px; border: 1px solid var(--border-color);">CWAs: ${hazards.counts.cwas}</div>
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
    if (!airport) {
        return `
            <div class="card">
                <h2>Airport Directory</h2>
                <p class="warning">Reference directory information unavailable for this airport.</p>
            </div>
        `;
    }

    const icao = airport.icao || airport.ident || airport.airport || "";
    const name = airport.name || "Information unavailable";
    const city = airport.city || "";
    const state = airport.state || "";
    const elevation = airport.elevation_ft ?? airport.elevation ?? "N/A";
    const lat = airport.lat ?? airport.latitude;
    const lon = airport.lon ?? airport.lng ?? airport.longitude;

    const frequencies = airport.frequencies || [];
    const freqItems = Array.isArray(frequencies) && frequencies.length
        ? frequencies.slice(0, 5).map(freq => {
            const type = freq.type || freq.description || "Frequency";
            const mhz = freq.frequency_mhz || freq.frequency || freq.value || "";
            return `<li>${type}: ${mhz}</li>`;
        }).join("")
        : `<li>No frequency data available</li>`;

    return `
        <div class="card">
            <h2>Airport Directory</h2>
            <p style="margin-bottom: 0.5rem;"><strong>${name}</strong></p>
            <div style="font-size: 0.9rem; margin-bottom: 1rem;">
                <div>ICAO: ${icao || "N/A"}</div>
                ${city || state ? `<div>Location: ${city}${city && state ? ", " : ""}${state}</div>` : ""}
                <div>Elev: ${elevation} FT</div>
                <div>Pos: ${lat ?? "N/A"}, ${lon ?? "N/A"}</div>
            </div>

            <strong>Frequencies</strong>
            <ul style="padding-left: 1.2rem; font-size: 0.85rem; margin-top: 0.5rem;">
                ${freqItems}
            </ul>

            <div class="card-footer">
                <a href="#/airport/${icao}/directory">Full Directory Info →</a>
            </div>
        </div>
    `;
},

    renderOfficialResourcesCard(icao) {
        // Remove 'K' for search if it's a 4-letter ICAO starting with K (common for US)
        const searchId = icao.startsWith('K') && icao.length === 4 ? icao.substring(1) : icao;
        
        return `
            <div class="card official-resources-card">
                <h2>Official FAA Resources</h2>
                <p style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 1rem;">Certified aeronautical data and diagrams.</p>
                
                <a href="https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/dtpp/search/results/?cycle=current&ident=${searchId}" target="_blank">
                    <span>Airport Diagrams & Terminal Procedures</span>
                </a>
                <a href="https://www.faa.gov/air_traffic/flight_info/aeronav/digital_products/dafd/search/results/?cycle=current&ident=${searchId}" target="_blank">
                    <span>Chart Supplement (d-AFD)</span>
                </a>
                
                <div class="warning-callout" style="margin-top: 1rem; font-size: 0.75rem; border-left-color: var(--text-muted);">
                    Always verify data in official publications. This app is for advisory use only.
                </div>
            </div>
        `;
    },

    renderBoardCard(summary) {
        const icao = summary.icao;
        const fltCat = summary.flight_category;
        const wind = summary.wind_summary || 'N/A';
        const name = summary.name || "Information unavailable";
        const favored = summary.favored_runway_end || summary.favored_runway_reason || 'N/A';
        
        return `
            <div class="card board-card" data-icao="${icao}">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.5rem;">
                    <div>
                        <h3 style="margin: 0; font-size: 1.25rem;">${icao}${summary.iata_code ? ` (${summary.iata_code})` : ''}</h3>
                        <div style="font-size: 0.75rem; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 150px;">${name}</div>
                    </div>
                    ${utils.getFlightCategoryChip(fltCat)}
                </div>
                
                <div style="font-size: 0.9rem; margin-bottom: 0.75rem;">
                    <div style="display: flex; justify-content: space-between;">
                        <span>Wind:</span>
                        <strong>${wind}</strong>
                    </div>
                    <div style="display: flex; justify-content: space-between;">
                        <span>Favored:</span>
                        <strong>${favored}</strong>
                    </div>
                    <div style="display: flex; justify-content: space-between;">
                        <span>Risk:</span>
                        <strong>${utils.getRiskLevelChip(summary.hazard_risk || 'unknown')}</strong>
                    </div>
                </div>

                ${summary.nearby_weather_used ? `
                    <div style="font-size: 0.7rem; color: var(--warning); margin-bottom: 0.5rem;">⚠️ Field METAR unavailable. Using nearby weather.</div>
                ` : ''}
                
                <div style="font-size: 0.65rem; color: var(--text-muted); margin-bottom: 0.75rem;">
                    Updated: ${utils.formatDate(summary.generated_at)}
                </div>

                <div class="board-card-actions" style="display: flex; gap: 0.5rem; margin-top: auto;">
                    <a href="#/airport/${icao}" class="chip info" style="flex: 1; text-align: center; text-decoration: none;">Dash</a>
                    <a href="#/airport/${icao}/weather" class="chip info" style="flex: 1; text-align: center; text-decoration: none;">WX</a>
                    <a href="#/airport/${icao}/runways" class="chip info" style="flex: 1; text-align: center; text-decoration: none;">RWY</a>
                    <button class="chip danger remove-favorite-btn" data-icao="${icao}" style="border: none; cursor: pointer; flex: 0.5;">×</button>
                </div>
            </div>
        `;
    },

    renderUnavailableCard(title, message) {
        return `
            <div class="card error">
                <h2>${title}</h2>
                <p style="color: var(--danger-text);">${message}</p>
                <div style="font-size: 0.8rem; margin-top: 1rem; color: var(--text-muted);">
                    The system encountered an error while rendering this component.
                </div>
            </div>
        `;
    }
};
