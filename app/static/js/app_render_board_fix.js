async function renderBoard(container) {
    const favorites = await api.getFavorites();
    
    if (favorites.length === 0) {
        container.innerHTML = `
            <div class="home-container">
                <h1>Your Airport Board</h1>
                <p>Save your favorite airports here for a compact overview.</p>
                <div class="card" style="max-width: 500px; margin: 1.5rem auto; text-align: left; background: var(--card-bg-alt);">
                    <p><strong>Add your first airport:</strong></p>
                    <div class="home-search" style="position: relative; margin-top: 1rem;">
                        <input type="text" id="board-search" placeholder="Search ICAO, IATA, or City" autocomplete="off">
                    </div>
                    <p style="font-size: 0.85rem; color: var(--text-muted); margin-top: 1.5rem;">
                        <strong>Privacy Note:</strong> Favorites are saved <strong>only in this browser</strong> on public instances.
                    </p>
                </div>
            </div>
        `;
        setupAutocomplete(document.getElementById('board-search'));
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
    }

    const grid = document.getElementById('board-grid');
    
    // Fetch all summaries using batch endpoint
    try {
        const idents = favorites.map(f => f.ident);
        const results = await api.getBatchSummaries(idents);
        
        grid.innerHTML = results.map(r => {
            if (r.error) {
                const icao = r.icao || '???';
                return `
                    <div class="card board-card danger" data-icao="${icao}">
                        <h3 style="margin: 0;">${icao}</h3>
                        <p style="font-size: 0.85rem; color: var(--danger-text);">Failed to load: ${r.message || r.error}</p>
                        <div class="board-card-actions" style="margin-top: auto;">
                            <button class="chip danger remove-favorite-btn" data-icao="${icao}" style="border: none; cursor: pointer; width: 100%;">Remove</button>
                        </div>
                    </div>
                `;
            }
            return cards.renderBoardCard(r);
        }).join('');

        // Attach remove handlers
        grid.querySelectorAll('.remove-favorite-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const icao = e.target.dataset.icao;
                if (confirm(`Remove ${icao} from board?`)) {
                    await api.removeFavorite(icao);
                    renderBoard(container); // Re-render
                }
            });
        });
    } catch (e) {
        console.error("Board batch fetch failed:", e);
        grid.innerHTML = `<div class="card danger"><h2>Error loading board</h2><p>${e.message}</p></div>`;
    }
}
