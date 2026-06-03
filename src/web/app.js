(function() {
    let ws = null;
    let reconnectDelay = 1000;
    const maxReconnectDelay = 30000;
    let reconnectTimer = null;
    
    // Application State
    let state = {
        soundboards: [],
        sounds: {} // maps board_id -> list of sounds, and "favorites" -> list of sounds
    };
    let activeBoardId = "favorites";

    // DOM Elements
    const statusBadge = document.getElementById("status-badge");
    const tabsContainer = document.getElementById("tabs-container");
    const cardsGrid = document.getElementById("cards-grid");
    const btnStopAll = document.getElementById("btn-stop-all");
    const errorOverlay = document.getElementById("error-overlay");

    // 1. Get Token from URL or LocalStorage
    const urlParams = new URLSearchParams(window.location.search);
    let token = urlParams.get("token");
    if (token) {
        localStorage.setItem("remote_pairing_token", token);
    } else {
        token = localStorage.getItem("remote_pairing_token");
    }

    if (!token) {
        console.error("No pairing token found. Please connect using the full link displayed on the desktop app.");
        showOverlay("Auth Required", "Please open the pairing URL from your ErosSoundX dashboard.");
        return;
    }

    // 2. Initialize WebSocket Connection
    function connect() {
        if (ws) {
            ws.close();
        }

        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws?token=${token}`;
        
        console.log(`Connecting to remote WebSocket: ${wsUrl}`);
        ws = new WebSocket(wsUrl);

        ws.onopen = function() {
            console.log("WebSocket connected successfully.");
            setOnlineStatus(true);
            reconnectDelay = 1000; // Reset reconnect delay
            hideOverlay();
        };

        ws.onmessage = function(event) {
            try {
                const message = JSON.parse(event.data);
                if (message.type === "init" || message.type === "update") {
                    state = message.data;
                    renderTabs();
                    renderGrid();
                }
            } catch (err) {
                console.error("Error parsing WebSocket message:", err);
            }
        };

        ws.onclose = function(event) {
            console.log("WebSocket connection closed.", event);
            setOnlineStatus(false);
            
            if (event.code === 4001) {
                showOverlay("Unauthorized", "Session token is invalid or expired. Reconnect from desktop app.");
            } else if (event.code === 4003) {
                showOverlay("Security Block", "This server is restricted to local network connections only.");
            } else {
                showOverlay("Searching...", "Lost connection to ErosSoundX desktop app. Reconnecting...");
                scheduleReconnect();
            }
        };

        ws.onerror = function(err) {
            console.error("WebSocket encountered error:", err);
            ws.close();
        };
    }

    function scheduleReconnect() {
        if (reconnectTimer) clearTimeout(reconnectTimer);
        reconnectTimer = setTimeout(function() {
            connect();
            // Exponential backoff
            reconnectDelay = Math.min(reconnectDelay * 1.5, maxReconnectDelay);
        }, reconnectDelay);
    }

    // 3. UI Render Functions
    function setOnlineStatus(isOnline) {
        if (isOnline) {
            statusBadge.className = "badge online";
            statusBadge.querySelector(".badge-text").textContent = "Connected";
        } else {
            statusBadge.className = "badge offline";
            statusBadge.querySelector(".badge-text").textContent = "Offline";
        }
    }

    function showOverlay(title, description) {
        errorOverlay.classList.remove("hidden");
        errorOverlay.querySelector("h2").textContent = title;
        errorOverlay.querySelector("p").textContent = description;
    }

    function hideOverlay() {
        errorOverlay.classList.add("hidden");
    }

    function renderTabs() {
        tabsContainer.innerHTML = "";
        
        // Render Favorites tab first
        const favTab = document.createElement("button");
        favTab.className = `tab-btn ${activeBoardId === "favorites" ? "active" : ""}`;
        favTab.textContent = "★ Favorites";
        favTab.onclick = () => selectTab("favorites");
        tabsContainer.appendChild(favTab);

        // Render User tabs
        state.soundboards.forEach(board => {
            const star = board.is_favorite ? "★ " : "";
            const cat = board.category && board.category !== "General" ? ` [${board.category}]` : "";
            const btn = document.createElement("button");
            btn.className = `tab-btn ${activeBoardId === board.id ? "active" : ""}`;
            btn.textContent = `${star}${board.name}${cat}`;
            btn.onclick = () => selectTab(board.id);
            tabsContainer.appendChild(btn);
        });
    }

    function selectTab(boardId) {
        activeBoardId = boardId;
        renderTabs();
        renderGrid();
    }

    function renderGrid() {
        cardsGrid.innerHTML = "";
        const sounds = state.sounds[activeBoardId] || [];

        if (sounds.length === 0) {
            const empty = document.createElement("div");
            empty.className = "empty-state-card";
            empty.innerHTML = `
                <div style="font-size: 32px; margin-bottom: 8px;">🎵</div>
                <div style="font-weight: 600; color: var(--color-muted);">Empty Board</div>
                <div style="font-size: 11px; color: rgba(142, 154, 175, 0.6); margin-top: 4px;">Add sounds in the desktop app.</div>
            `;
            empty.style.gridColumn = "span 2";
            empty.style.textAlign = "center";
            empty.style.padding = "40px 20px";
            empty.style.background = "var(--bg-card)";
            empty.style.borderRadius = "12px";
            empty.style.border = "1px solid var(--border-color)";
            cardsGrid.appendChild(empty);
            return;
        }

        sounds.forEach(sound => {
            const card = document.createElement("div");
            card.className = "sound-tile";
            card.dataset.id = sound.id;

            // Title
            const title = document.createElement("span");
            title.className = "sound-title";
            title.textContent = sound.name;
            card.appendChild(title);

            // Metadata row
            const meta = document.createElement("div");
            meta.className = "sound-meta";

            // Ext Badge & Duration
            const leftMeta = document.createElement("div");
            leftMeta.style.display = "flex";
            leftMeta.style.alignItems = "center";
            leftMeta.style.gap = "6px";

            // File extension
            const fileParts = sound.file_path.split(".");
            const ext = fileParts[fileParts.length - 1].toUpperCase();
            const extBadge = document.createElement("span");
            extBadge.className = "ext-badge";
            extBadge.textContent = ext;
            leftMeta.appendChild(extBadge);

            // Duration
            const dur = sound.duration || 0;
            const mins = Math.floor(dur / 60);
            const secs = Math.floor(dur % 60);
            const durStr = dur > 0 ? `${mins}:${secs.toString().padStart(2, '0')}` : "--:--";
            const durLabel = document.createElement("span");
            durLabel.className = "duration-tag";
            durLabel.textContent = durStr;
            leftMeta.appendChild(durLabel);

            // Favorite star (optional display on tile)
            if (sound.is_favorite) {
                const favStar = document.createElement("span");
                favStar.className = "tile-fav-star";
                favStar.textContent = "★";
                leftMeta.appendChild(favStar);
            }

            meta.appendChild(leftMeta);

            // Inline Stop Button
            const btnStop = document.createElement("button");
            btnStop.className = "stop-btn";
            btnStop.textContent = "■";
            btnStop.style.background = "rgba(255, 0, 85, 0.1)";
            btnStop.style.border = "1px solid var(--color-pink)";
            btnStop.style.color = "var(--color-pink)";
            btnStop.style.borderRadius = "4px";
            btnStop.style.padding = "4px 10px";
            btnStop.style.fontSize = "12px";
            btnStop.style.fontWeight = "bold";
            btnStop.onclick = function(e) {
                e.stopPropagation(); // Prevent trigger play event
                stopSound(sound.id);
            };
            meta.appendChild(btnStop);

            card.appendChild(meta);

            // Tile Click Handler: Triggers sound
            card.onclick = function() {
                playSound(sound.id);
                // Simple feedback class animation
                card.classList.add("playing");
                setTimeout(() => card.classList.remove("playing"), 200);
            };

            cardsGrid.appendChild(card);
        });
    }

    // 4. WebSocket Actions
    function playSound(soundId) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                action: "play",
                sound_id: soundId
            }));
        }
    }

    function stopSound(soundId) {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                action: "stop",
                sound_id: soundId
            }));
        }
    }

    function stopAllSounds() {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({
                action: "stop_all"
            }));
        }
    }

    // 5. Global Action Listeners
    btnStopAll.onclick = function() {
        stopAllSounds();
    };

    // Run connection on boot
    connect();
})();
