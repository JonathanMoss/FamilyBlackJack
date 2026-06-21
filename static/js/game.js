const socket = io();
let currentHand = [];
let selectedCards = [];
let globalState = {};
let lastPenalized = { name: null, amount: 0 };
let spectatorHandsData = null;
let isDemoMode = false;

function escapeHTML(str) {
    if (!str) return '';
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

// Web Audio API context for synthesized game sounds
let audioCtx = null;
function initAudio() {
    if (!audioCtx && (window.AudioContext || window.webkitAudioContext)) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
}

// Unlock audio context on the first user interaction to ensure autoplay policies are satisfied
document.addEventListener('click', () => {
    initAudio();
    if (audioCtx && audioCtx.state === 'suspended') {
        audioCtx.resume();
    }
}, { once: true });

// Custom sorting rules to respect your layout sequence: 2-10, Ace, Queen, King, Jack
const RANK_HIERARCHY = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
    'Ace': 11, 'Queen': 12, 'King': 13, 'Jack': 14
};
const SUIT_HIERARCHY = { 'Hearts': 1, 'Diamonds': 2, 'Clubs': 3, 'Spades': 4 };
const SUIT_EMOJIS = { 'Hearts': '♥', 'Diamonds': '♦', 'Clubs': '♣', 'Spades': '♠' };

function joinGame() {
    const name = document.getElementById('username').value.trim();
    if(!name) {
        showToast("Please enter a username!");
        return;
    }
    initAudio();
    localStorage.setItem('blackjack_player_name', name);
    socket.emit('join_game', { name: name });
}

function startGame() {
    initAudio();
    socket.emit('start_match');
}

function organizeHand(mode) {
    if (!currentHand || currentHand.length === 0) return;

    if (mode === 'shuffle') {
        // High-entropy Fisher-Yates array permutation
        for (let i = currentHand.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [currentHand[i], currentHand[j]] = [currentHand[j], currentHand[i]];
        }
        soundEffect('shuffle');
    } 
    else if (mode === 'sort') {
        currentHand.sort((a, b) => {
            // First pass: Sort by suit grouping
            if (SUIT_HIERARCHY[a.suit] !== SUIT_HIERARCHY[b.suit]) {
                return SUIT_HIERARCHY[a.suit] - SUIT_HIERARCHY[b.suit];
            }
            // Second pass: Sort matching ranks based on custom hierarchy rules
            return RANK_HIERARCHY[a.value] - RANK_HIERARCHY[b.value];
        });
        soundEffect('play');
    }
    renderRearrangedHand();
}

function renderRearrangedHand() {
    const handDiv = document.getElementById('my-hand');
    handDiv.innerHTML = '';
    selectedCards = []; 
    
    currentHand.forEach((card) => {
        const cDiv = buildCardElement(card);
        cDiv.onclick = () => {
            cDiv.classList.toggle('selected');
            if(cDiv.classList.contains('selected')) {
                selectedCards.push(card);
            } else {
                selectedCards = selectedCards.filter(c => !(c.value === card.value && c.suit === card.suit));
            }
            updateBadges(handDiv);
            evaluateButtonAbilities();
        };
        handDiv.appendChild(cDiv);
    });
    evaluateButtonAbilities();
}

function buildCardElement(card) {
    const div = document.createElement('div');
    div.className = 'card image-card';
    if(card.suit === 'Hearts' || card.suit === 'Diamonds') div.classList.add('red');
    
    // Store metadata for reliable selection tracking via data attributes
    div.dataset.value = card.value;
    div.dataset.suit = card.suit;

    const imgPath = `/static/images/${card.value}_of_${card.suit}.png`.toLowerCase();

    div.innerHTML = `
        <div class="badge"></div>
        <img src="${imgPath}" class="card-img" alt="${card.value} of ${card.suit}">
    `;
    return div;
}

function updateBadges(container) {
    const cardsInDOM = container.getElementsByClassName('card');
    
    for (let element of cardsInDOM) {
        const badge = element.querySelector('.badge');
        if (!badge) continue;
        
        if (element.classList.contains('selected')) {
            const idx = selectedCards.findIndex(sc => sc.value === element.dataset.value && sc.suit === element.dataset.suit);
            badge.innerText = idx !== -1 ? idx + 1 : '';
        } else {
            badge.innerText = '';
        }
    }
}

function playSelected() {
    if (selectedCards.length === 0) return;
    socket.emit('play_cards', { cards: selectedCards.slice() });
}

function drawOrResolve() {
    socket.emit('take_penalty_or_draw');
}

function selectAceSuit(suit) {
    socket.emit('declare_ace_suit', { suit: suit });
    document.getElementById('ace-modal').style.display = 'none';
}

function triggerNudge(targetPlayer) {
    socket.emit('send_nudge', { target: targetPlayer, emoji: '🚨' });
}

function evaluateButtonAbilities() {
    const clientName = document.getElementById('username').value.trim();
    const isMyTurn = (globalState.current_player === clientName);
    document.getElementById('play-btn').disabled = !isMyTurn || selectedCards.length === 0;
    
    const drawBtn = document.getElementById('action-draw-btn');
    if(!isMyTurn) {
        drawBtn.disabled = true;
        drawBtn.innerText = "Draw Card";
    } else {
        drawBtn.disabled = false;
        drawBtn.innerText = (globalState.penalty > 0) ? `Take Penalty (+${globalState.penalty})` : "Draw Card";
    }

    const jokerBtn = document.getElementById('joker-btn');
    
    // Evaluate the Joker status and cooldown states
    const hasJoker = globalState.jokers_available && globalState.jokers_available[clientName];
    const cooldown = globalState.joker_cooldown || 0;
    
    let activePlayerCount = 0;
    if (globalState.is_started && globalState.hand_sizes) {
        for (const p in globalState.hand_sizes) {
            if (globalState.hand_sizes[p] > 0) activePlayerCount++;
        }
    } else {
        activePlayerCount = globalState.player_list ? globalState.player_list.length : 0;
    }
    const isTwoPlayer = activePlayerCount <= 2;
    
    if (globalState.is_started && jokerBtn) {
        jokerBtn.style.display = 'inline-block';
        if (isTwoPlayer) {
            jokerBtn.disabled = true;
            jokerBtn.innerText = '🃏 Disabled (2 Players)';
        } else if (!hasJoker) {
            jokerBtn.disabled = true;
            jokerBtn.innerText = '🃏 Joker Used';
        } else if (cooldown > 0) {
            jokerBtn.disabled = true;
            jokerBtn.innerText = `🃏 Wait (${cooldown})`;
        } else if (!isMyTurn) {
            jokerBtn.disabled = true;
            jokerBtn.innerText = `🃏 Not Your Turn`;
        } else {
            jokerBtn.disabled = false;
            jokerBtn.innerText = `🃏 Play Joker`;
        }
    } else if (jokerBtn) {
        jokerBtn.style.display = 'none';
    }
}

socket.on('your_hand', (data) => {
    // Only drop and wipe internal layout array if an operational card count difference occurs
    const incomingCountChange = data.hand.length !== currentHand.length;
    currentHand = data.hand;
    if (incomingCountChange || currentHand.length === 0) {
        renderRearrangedHand();
    }
});

socket.on('state_update', (state) => {
    globalState = state;
    const clientName = document.getElementById('username').value.trim();
    const isJoined = state.player_list.includes(clientName) || isDemoMode;
    
    // Auto-Lobby Setup Safety Valving
    if (isJoined) {
        document.body.classList.remove('not-joined');
        document.getElementById('setup-panel').style.display = 'none';
        const logoutBtn = document.getElementById('logout-btn');
        if (logoutBtn) logoutBtn.style.display = 'inline-block';
    } else {
        document.body.classList.add('not-joined');
        document.getElementById('setup-panel').style.display = 'block';
        const logoutBtn = document.getElementById('logout-btn');
        if (logoutBtn) logoutBtn.style.display = 'none';
    }

    if (state.is_started && !isDemoMode) {
        document.getElementById('lobby-controls').style.display = 'none';
    } else if (isJoined) {
        document.getElementById('lobby-controls').style.display = 'block';
        const addBotBtn = document.getElementById('add-bot-btn');
        const startGameBtn = document.getElementById('start-game-btn');
        const shufflePlayersBtn = document.getElementById('shuffle-players-btn');
        
        if (isDemoMode) {
            if (startGameBtn) startGameBtn.style.display = 'none';
            if (addBotBtn) addBotBtn.style.display = 'none';
            if (shufflePlayersBtn) shufflePlayersBtn.style.display = 'none';
        } else {
            if (startGameBtn) startGameBtn.style.display = 'inline-block';
            if (addBotBtn) addBotBtn.style.display = 'inline-block';
            if (shufflePlayersBtn) shufflePlayersBtn.style.display = 'inline-block';
        }
    } else {
        document.getElementById('lobby-controls').style.display = 'none';
    }

    let resetBtn = document.getElementById('reset-btn');
    let stopDemoBtn = document.getElementById('stop-demo-btn');
    
    // If the reset button doesn't exist, or is trapped inside the hidden lobby-controls container, dynamically inject/move it!
    if (!resetBtn || (resetBtn.parentElement && resetBtn.parentElement.id === 'lobby-controls')) {
        if (!resetBtn) {
            resetBtn = document.createElement('button');
            resetBtn.id = 'reset-btn';
            resetBtn.innerText = 'Stop Game';
            resetBtn.onclick = resetGame;
        }
        const logoutBtn = document.getElementById('logout-btn');
        if (logoutBtn && logoutBtn.parentElement) {
            logoutBtn.parentElement.insertBefore(resetBtn, logoutBtn);
        }
    }

    // Always ensure the reset button matches the logout button's styling and layout constraints
    const logoutBtnRef = document.getElementById('logout-btn');
    if (resetBtn && logoutBtnRef) {
        if (logoutBtnRef.className) {
            resetBtn.className = logoutBtnRef.className;
        }
        resetBtn.style.width = 'auto';
        resetBtn.style.flex = 'none';
        resetBtn.style.marginRight = '10px';
    }

    if (resetBtn) {
        if (state.is_started && !isDemoMode && state.host_name === clientName) {
            resetBtn.style.display = 'inline-block';
            resetBtn.disabled = false;
            resetBtn.style.opacity = '1';
            resetBtn.style.cursor = 'pointer';
        } else {
            resetBtn.style.display = 'none';
        }
    }

    let startDemoBtn = document.getElementById('start-demo-btn');
    if (startDemoBtn) {
        if (isDemoMode) {
            startDemoBtn.style.display = 'none';
        } else {
            startDemoBtn.style.display = 'inline-block';
        }
    }

    if (stopDemoBtn) {
        if (isDemoMode) {
            stopDemoBtn.style.display = 'inline-block';
        } else {
            stopDemoBtn.style.display = 'none';
        }
    }

    // --- REFACTORED WORKFLOW: REPREMIUMIZED MATCH DASHBOARD SYSTEM ---
    const turnContainer = document.getElementById('turn-badge-container');
    const turnMessage = document.getElementById('turn-message');
    const statusDot = document.getElementById('game-status-dot');
    
    // Clear any existing turn warning timeout to prevent ghost prompts when state changes
    if (window.turnWarningTimeout) clearTimeout(window.turnWarningTimeout);

    if (!state.is_started) {
        statusDot.className = 'status-dot idle';
        turnContainer.classList.remove('my-turn');
        turnMessage.innerHTML = `⏳ <span>Lobby waiting to start...</span>`;
        document.getElementById('turn-timer').style.width = '100%';
    } else {
        statusDot.className = 'status-dot live';
        
        const myHandSize = state.hand_sizes[clientName] || 0;
        const isSpectator = myHandSize === 0;

        if (state.current_player !== clientName) {
            const aceModal = document.getElementById('ace-modal');
            if (aceModal) aceModal.style.display = 'none';
        }

        const timerBar = document.getElementById('turn-timer');

        if (isSpectator) {
            turnContainer.classList.remove('my-turn');
            turnMessage.innerHTML = `👀 <span><b>Spectating:</b> Waiting for next round...</span>`;
            if (timerBar) {
                timerBar.style.transition = 'none';
                timerBar.style.width = '0%';
            }
        } else if (state.current_player === clientName) {
            turnContainer.classList.add('my-turn');
            turnMessage.innerHTML = `⚔️ <span><b>YOUR TURN!</b> Play your hand.</span>`;
        } else {
            turnContainer.classList.remove('my-turn');
            turnMessage.innerHTML = `👤 <span>Action on <b>${escapeHTML(state.current_player)}</b></span>`;
        }

        if (!isSpectator && timerBar && state.turn_start_time) {
            const elapsed = state.server_time - state.turn_start_time;
            const remaining = Math.max(0, 30 - elapsed);
            const percent = (remaining / 30) * 100;
            timerBar.style.transition = 'none';
            timerBar.style.width = percent + '%';

            // Force DOM reflow so the browser picks up the width reset before applying the transition
            void timerBar.offsetWidth;
            timerBar.style.transition = `width ${remaining}s linear, background-color 0.3s`;
            timerBar.style.width = '0%';

            // Setup the 8-second remaining wobble nudge
            if (state.current_player === clientName && remaining > 8) {
                window.turnWarningTimeout = setTimeout(() => {
                    showToast(`⏰ Hurry up! 8 seconds left!`);
                    soundEffect('alert');
                    document.body.classList.add('wobble-effect');
                    setTimeout(() => document.body.classList.remove('wobble-effect'), 400);
                }, (remaining - 8) * 1000);
            }
        }
    }

    // Dynamic Penalty Strike Engine Rendering
    const battleBanner = document.getElementById('battle-strike-banner');
    const ammoValue = document.getElementById('battle-ammo-value');
    const battleTypeText = document.getElementById('battle-type-text');

    if (state.penalty > 0) {
        battleBanner.style.display = 'flex';
        ammoValue.innerText = `+${state.penalty}`;
        
        const cardSymbol = (state.penalty_type === 'BJ') ? 'Jacks 🃏' : 'Twos ✌️';
        battleTypeText.innerText = `Stacking payload contains active ${cardSymbol}!`;
        
        if (state.current_player === clientName) {
            document.getElementById('personal-penalty-alert').style.display = 'block';
            document.getElementById('penalty-alert-text').innerText = `Counter with a matching power card or draw +${state.penalty}!`;
        }
    } else {
        battleBanner.style.display = 'none';
        document.getElementById('personal-penalty-alert').style.display = 'none';
    }
    // --- END PREMIUM MATCH MONITOR BLOCK ---

    // Refresh Top Discard Card View layout
    if(state.top_card) {
        const frame = document.getElementById('top-card');
        frame.className = 'card image-card';
        if(state.top_card.suit === 'Hearts' || state.top_card.suit === 'Diamonds') frame.classList.add('red');
        
        const imgPath = `/static/images/${state.top_card.value}_of_${state.top_card.suit}.png`.toLowerCase();
        frame.innerHTML = `<img src="${imgPath}" class="card-img" alt="${state.top_card.value} of ${state.top_card.suit}">`;

        const suitIndicator = document.getElementById('active-suit-indicator');
        if (state.is_started) {
            suitIndicator.style.display = 'block';
            const dirIcon = state.direction === 1 ? '↻ Clockwise' : '↺ Counter-Clockwise';
            suitIndicator.innerHTML = `Active Match Suit: <b>${state.active_suit}</b> | <span style="color:#e0a800;">Direction: ${dirIcon}</span>`;
        } else {
            suitIndicator.style.display = 'none';
        }
    }

    // Refresh Room Active Table Roster
    const listContainer = document.getElementById('player-list-box');
    listContainer.innerHTML = '';
    state.player_list.forEach(p => {
        const row = document.createElement('div');
        row.className = 'player-row';
        if(state.is_started && state.current_player === p) row.classList.add('active-turn');

        const escapedP = escapeHTML(p);
        const cardCount = state.hand_sizes[p] || 0;
        let pLabel = (p === clientName) ? `<b>${escapedP} (You)</b>` : escapedP;

        const isSpectating = state.is_started && cardCount === 0;
        const statusText = isSpectating ? '👁️ Spectating' : `🃏 (${cardCount} left)`;

        const isLast = state.is_started && cardCount === 1;
        const lastIcon = isLast ? `<span class="last-card-icon" title="Last Card">🔥</span>` : '';
        const hostIcon = (p === state.host_name) ? `<span title="Host" style="margin-right: 5px;">👑</span>` : '';

        const rightControls = (p !== clientName && state.is_started) ? `<button class="nudge-btn" data-target="${escapedP}">⏰</button>` : '';

        // If there's an active penalty, highlight the current_player as the penalty target
        const isPenalized = state.penalty > 0 && state.current_player === p;
        const penaltyIcon = isPenalized ? `<span class="penalty-indicator" title="Penalty: +${state.penalty}">⚠️ +${state.penalty}</span>` : '';

        if (isPenalized) row.classList.add('penalty-target');

        const avatar = (state.avatars && state.avatars[p]) ? state.avatars[p] : ((state.bots && state.bots.includes(p)) ? '🤖' : '👤');
        const isMe = p === clientName;
        const isBot = state.bots && state.bots.includes(p);
        let avatarCursor = 'class="player-avatar"';
        if (isMe) {
            avatarCursor = 'style="cursor:pointer;" title="Click to change avatar" class="player-avatar interactive-avatar"';
        } else if (isBot && !state.is_started && !isDemoMode) {
            avatarCursor = 'style="cursor:pointer;" title="Click to remove bot" class="player-avatar removable-bot"';
        }
        const avatarHtml = `<span ${avatarCursor}>${avatar}</span>`;

        row.dataset.name = p;
        row.innerHTML = `
            <div class="player-meta">
                <span>${avatarHtml} ${pLabel} ${hostIcon} ${state.is_started ? statusText : '⏳ Ready'} ${lastIcon} ${penaltyIcon}</span>
                ${rightControls}
            </div>
            <div class="spectator-hand-tray" style="display:none;"></div>
        `;
        listContainer.appendChild(row);

        // Trigger a brief personal visual when *you* are the penalized player, but only when it changes
        if (isPenalized && p === clientName) {
            if (lastPenalized.name !== clientName || lastPenalized.amount !== state.penalty) {
                showToast(`⚠️ You have a penalty of +${state.penalty}!`);
                soundEffect('alert');
                document.body.classList.add('penalty-flash');
                setTimeout(() => document.body.classList.remove('penalty-flash'), 1000);
                lastPenalized.name = clientName;
                lastPenalized.amount = state.penalty;
            }
        }
        if (!isPenalized && lastPenalized.name === p) {
            // penalty cleared
            lastPenalized.name = null;
            lastPenalized.amount = 0;
        }
    });

    // Refresh Global Career Scoreboard Metrics
    const tbody = document.getElementById('league-rows');
    if (tbody && state.league_html) {
        tbody.innerHTML = state.league_html;
    }

    // Clear spectator data if we are actively playing
    const myHandSize = state.hand_sizes[clientName] || 0;
    if (state.is_started && myHandSize > 0) {
        spectatorHandsData = null;
    }
    renderSpectatorHands();

    evaluateButtonAbilities();
});

socket.on('spectator_hands', (data) => {
    spectatorHandsData = data.hands;
    renderSpectatorHands();
});

function renderSpectatorHands() {
    if (!spectatorHandsData) return;
    const listContainer = document.getElementById('player-list-box');
    if (!listContainer) return;
    const rows = listContainer.getElementsByClassName('player-row');
    
    for (let row of rows) {
        const pName = row.dataset.name;
        const tray = row.querySelector('.spectator-hand-tray');
        if (pName && tray && spectatorHandsData[pName]) {
            tray.innerHTML = '';
            tray.style.display = 'flex';
            spectatorHandsData[pName].forEach(card => {
                const cDiv = document.createElement('div');
                cDiv.className = 'mini-card';
                if (card.suit === 'Hearts' || card.suit === 'Diamonds') cDiv.classList.add('red');
                const valStr = card.value === '10' ? '10' : card.value[0];
                cDiv.innerHTML = `${valStr}${SUIT_EMOJIS[card.suit]}`;
                tray.appendChild(cDiv);
            });
        } else if (tray) {
            tray.style.display = 'none';
        }
    }
}

socket.on('prompt_ace_suit', () => {
    document.getElementById('ace-modal').style.display = 'flex';
});

socket.on('joker_played', (data) => {
    showToast(data.msg);
    soundEffect('alert');
    document.body.classList.add('joker-flash');
    setTimeout(() => document.body.classList.remove('joker-flash'), 1000);
});

socket.on('game_log', (data) => {
    const logBox = document.getElementById('game-log-box');
    logBox.insertAdjacentHTML('beforeend', `<div>${data.msg}</div>`);
    logBox.scrollTop = logBox.scrollHeight;
});

socket.on('game_over', (data) => {
    soundEffect('winner');
    triggerConfetti();

    document.getElementById('game-over-text').innerHTML = data.html;

    const clientName = document.getElementById('username').value.trim();
    if (data.winner && data.winner === clientName) {
        const h2 = document.querySelector('#game-over-text h2');
        if (h2) {
            h2.innerText = "You have won! 🎉";
        }
    }

    const closeBtn = document.getElementById('close-game-over-btn');
    if (closeBtn) {
        closeBtn.innerText = data.is_demo ? 'Next Demo Game!' : 'Back to Game!';
    }

    document.getElementById('game-over-modal').style.display = 'flex';

    if (data.is_demo) {
        if (window.demoNextGameTimeout) clearTimeout(window.demoNextGameTimeout);
        window.demoNextGameTimeout = setTimeout(() => {
            if (document.getElementById('game-over-modal').style.display === 'flex') {
                closeGameOverModal();
            }
        }, 10000);
    }
});

function closeGameOverModal() {
    document.getElementById('game-over-modal').style.display = 'none';
    if (isDemoMode) {
        socket.emit('start_demo');
    }
}

function showAvatarModal() {
    document.getElementById('avatar-modal').style.display = 'flex';
}

function selectAvatar(avatar) {
    socket.emit('change_avatar', { avatar: avatar });
    document.getElementById('avatar-modal').style.display = 'none';
}

// Retain dynamic modal functions for HTML snippets
window.confirmResetGame = confirmResetGame;
window.selectAvatar = selectAvatar;

function logout() {
    const modal = document.getElementById('confirm-logout-modal');
    if (modal) {
        modal.style.display = 'flex';
    }
}

function executeLogout() {
    localStorage.removeItem('blackjack_player_name');
    window.location.href = '/logout';
}

socket.on('receive_nudge', (data) => {
    showToast(`⏰ NUDGE from ${data.sender}! Speed up!`);
    soundEffect('alert');
    document.body.classList.add('wobble-effect');
    setTimeout(() => document.body.classList.remove('wobble-effect'), 400);
});

socket.on('error', (data) => {
    showToast(data.msg);
});

function showToast(message) {
    const toast = document.getElementById('toast-notification');
    toast.innerText = message;
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 3500);
}

async function soundEffect(type) {
    // Ensure audioCtx is initialized and resumed
    if (!audioCtx) initAudio();
    if (!audioCtx) return; // Fallback if unsupported
    if (audioCtx.state === 'suspended') {
        try {
            await audioCtx.resume();
        } catch (e) {
            return; // Context could not be resumed, likely due to autoplay policy
        }
    }

    const now = audioCtx.currentTime;

    // Standard helper to play a clean tone with exponential decay
    const playTone = (freq, type = 'sine', duration = 0.1, volume = 0.1, startTime = now) => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = type;
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        
        osc.frequency.setValueAtTime(freq, startTime);
        gain.gain.setValueAtTime(volume, startTime);
        gain.gain.exponentialRampToValueAtTime(0.0001, startTime + duration);
        
        osc.start(startTime);
        osc.stop(startTime + duration);
    };

    switch (type) {
        case 'play': {
            // Rapid downward frequency chirp: organic card-tap thump on a soft table
            const duration = 0.12;
            const osc = audioCtx.createOscillator();
            const gain = audioCtx.createGain();
            osc.type = 'sine';
            osc.connect(gain);
            gain.connect(audioCtx.destination);

            osc.frequency.setValueAtTime(260, now);
            osc.frequency.exponentialRampToValueAtTime(70, now + duration);

            gain.gain.setValueAtTime(0.18, now);
            gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);

            osc.start(now);
            osc.stop(now + duration);
            break;
        }
        case 'draw': {
            // Soft paper-like slide using overlapping sine waves (a perfect fifth harmony) with upward glide
            const duration = 0.14;
            [440.00, 659.25].forEach((freq, idx) => {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.type = 'sine';
                osc.connect(gain);
                gain.connect(audioCtx.destination);

                osc.frequency.setValueAtTime(freq, now);
                osc.frequency.exponentialRampToValueAtTime(freq * 1.15, now + duration);

                gain.gain.setValueAtTime(idx === 0 ? 0.05 : 0.03, now);
                gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);

                osc.start(now);
                osc.stop(now + duration);
            });
            break;
        }
        case 'shuffle': {
            // Gentle rhythmic riffle sound using triangle wave clicks with accelerating/decelerating schedule
            for (let i = 0; i < 9; i++) {
                const clickTime = now + (i * 0.04) + (Math.random() * 0.008);
                const clickDuration = 0.025;
                const freq = 140 + (i * 18);
                playTone(freq, 'triangle', clickDuration, 0.03, clickTime);
            }
            break;
        }
        case 'alert': {
            // High-end double bell-chime (a clean major third E6 and G#6) with exponential ring-out
            const duration = 0.5;
            [1318.51, 1661.22].forEach((freq, idx) => {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.type = 'sine';
                osc.connect(gain);
                gain.connect(audioCtx.destination);

                osc.frequency.setValueAtTime(freq, now);
                gain.gain.setValueAtTime(idx === 0 ? 0.04 : 0.02, now);
                gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);

                osc.start(now);
                osc.stop(now + duration);
            });
            // Play a second softer chime after 120ms to make it an elegant double-ping
            [1318.51, 1661.22].forEach((freq, idx) => {
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.type = 'sine';
                osc.connect(gain);
                gain.connect(audioCtx.destination);

                osc.frequency.setValueAtTime(freq, now + 0.12);
                gain.gain.setValueAtTime(idx === 0 ? 0.03 : 0.015, now + 0.12);
                gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.12 + duration);

                osc.start(now + 0.12);
                osc.stop(now + 0.12 + duration);
            });
            break;
        }
        case 'winner': {
            // Triumphant, warm chord resolution (C-Major triad + Maj7/9 extensions) played with staggered arpeggiated entry
            // Notes: C4 (261.63), G4 (392.00), C5 (523.25), E5 (659.25), B5 (987.77)
            const chords = [
                { f: 261.63, delay: 0.0 },  // C4
                { f: 392.00, delay: 0.08 }, // G4
                { f: 523.25, delay: 0.16 }, // C5
                { f: 659.25, delay: 0.24 }, // E5
                { f: 987.77, delay: 0.32 }  // B5
            ];
            chords.forEach(note => {
                const noteTime = now + note.delay;
                const duration = 0.8;
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();
                osc.type = 'sine';
                osc.connect(gain);
                gain.connect(audioCtx.destination);

                osc.frequency.setValueAtTime(note.f, noteTime);
                gain.gain.setValueAtTime(0.05, noteTime);
                gain.gain.exponentialRampToValueAtTime(0.0001, noteTime + duration);

                osc.start(noteTime);
                osc.stop(noteTime + duration);
            });
            break;
        }
        case 'penalty': // Map 'penalty' from server to 'alert' sound
            await soundEffect('alert');
            break;
        case 'victory': // Map 'victory' from server to 'winner' sound
            await soundEffect('winner');
            break;
        default:
            console.log(`Sound type ${type} not recognized.`);
    }
}

function resetGame() {
    const name = document.getElementById('username').value.trim();
    if(!name) {
        showToast('Enter your name to request a reset.');
        return;
    }
    const modal = document.getElementById('confirm-reset-modal');
    if (modal) {
        modal.style.display = 'flex';
    }
}

function confirmResetGame() {
    document.getElementById('confirm-reset-modal').style.display = 'none';
    socket.emit('reset_match');
}

function startDemo() {
    initAudio();
    isDemoMode = true;
    const startBtn = document.getElementById('start-demo-btn');
    const stopBtn = document.getElementById('stop-demo-btn');
    if (startBtn) startBtn.style.display = 'none';
    if (stopBtn) stopBtn.style.display = 'inline-block';
    socket.emit('start_demo');
}

function stopDemo() {
    isDemoMode = false;
    if (window.demoNextGameTimeout) clearTimeout(window.demoNextGameTimeout);
    const startBtn = document.getElementById('start-demo-btn');
    const stopBtn = document.getElementById('stop-demo-btn');
    if (startBtn) startBtn.style.display = 'inline-block';
    if (stopBtn) stopBtn.style.display = 'none';
    socket.emit('stop_demo');
}

// Initialize the lobby with a decorative placeholder before socket/join events
function initLobbyVisuals() {
    // Fetch HTML snippets for UI modals dynamically
    fetch('/snippets/modals')
        .then(response => response.text())
        .then(html => {
            document.body.insertAdjacentHTML('beforeend', html);
            
            // Bind modal buttons once they are available in the DOM
            const bindModal = (id, fn) => { const btn = document.getElementById(id); if(btn) btn.onclick = fn; };
            bindModal('ace-hearts-btn', () => selectAceSuit('Hearts'));
            bindModal('ace-diamonds-btn', () => selectAceSuit('Diamonds'));
            bindModal('ace-clubs-btn', () => selectAceSuit('Clubs'));
            bindModal('ace-spades-btn', () => selectAceSuit('Spades'));
            bindModal('close-game-over-btn', closeGameOverModal);
            bindModal('confirm-logout-btn', executeLogout);
            bindModal('cancel-logout-btn', () => document.getElementById('confirm-logout-modal').style.display = 'none');
            bindModal('confirm-reset-action-btn', confirmResetGame);
            bindModal('cancel-reset-btn', () => document.getElementById('confirm-reset-modal').style.display = 'none');
        });

    // Bind all buttons cleanly via JS to avoid inline handler conflicts
    const bind = (id, fn) => { const btn = document.getElementById(id); if(btn) btn.onclick = fn; };
    bind('join-btn', joinGame);
    bind('logout-btn', logout);
    bind('reset-btn', resetGame);
    bind('start-game-btn', startGame);
    bind('start-demo-btn', startDemo);
    bind('stop-demo-btn', stopDemo);
    bind('shuffle-players-btn', () => socket.emit('shuffle_players'));
    bind('shuffle-hand-btn', () => organizeHand('shuffle'));
    bind('sort-hand-btn', () => organizeHand('sort'));
    bind('play-btn', playSelected);
    bind('action-draw-btn', drawOrResolve);
    bind('add-bot-btn', () => socket.emit('add_bot'));
    bind('joker-btn', () => socket.emit('play_joker'));

    // Add Enter key support for the username input field
    const nameInput = document.getElementById('username');
    if (nameInput) {
        nameInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') joinGame();
        });
    }

    // Delegate clicks for dynamically rendered components (Avatars and Nudges)
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('nudge-btn')) {
            triggerNudge(e.target.dataset.target);
        } else if (e.target.classList.contains('interactive-avatar') || e.target.closest('.interactive-avatar')) {
            showAvatarModal();
        } else if (e.target.classList.contains('removable-bot') || e.target.closest('.removable-bot')) {
            const row = e.target.closest('.player-row');
            if (row && row.dataset.name) {
                socket.emit('remove_bot', { name: row.dataset.name });
            }
        }
    });

    const frame = document.getElementById('top-card');
    if (frame && !frame.innerHTML.trim()) {
        frame.className = 'card image-card';
        const imgPath = `/static/images/ace_of_spades.png`;
        frame.innerHTML = `<img src="${imgPath}" class="card-img" alt="Ace of Spades Placeholder">`;
    }

    // Ensure the reset button is hidden initially to prevent UI layout flashes
    let resetBtn = document.getElementById('reset-btn');
    if (resetBtn) resetBtn.style.display = 'none';

    let stopDemoBtn = document.getElementById('stop-demo-btn');
    if (stopDemoBtn) stopDemoBtn.style.display = 'none';

    // Auto-join if a name was previously saved
    const savedName = localStorage.getItem('blackjack_player_name');
    if (savedName) {
        const nameInput = document.getElementById('username');
        if (nameInput) {
            nameInput.value = savedName;
            socket.emit('join_game', { name: savedName });
        }
    }
    preloadCardImages();
}
initLobbyVisuals();

socket.on('room_reset', (data) => {
    showToast(data.msg || 'Match reset.');
    
    isDemoMode = false;
    if (window.demoNextGameTimeout) clearTimeout(window.demoNextGameTimeout);
    const startDemoBtn = document.getElementById('start-demo-btn');
    if (startDemoBtn) startDemoBtn.style.display = 'inline-block';
    const stopDemoBtn = document.getElementById('stop-demo-btn');
    if (stopDemoBtn) stopDemoBtn.style.display = 'none';
    
    // Close any open modals and clear hand UI
    document.getElementById('ace-modal').style.display = 'none';
    document.getElementById('game-over-modal').style.display = 'none';
    currentHand = [];
    renderRearrangedHand();
});

// Notification when cards are received (drawn) — includes penalty draws
socket.on('received_cards', (data) => {
    const count = data.count || 0;
    const reason = data.reason || '';
    const isPenalty = reason && reason.indexOf('penalty') !== -1;
    const source = data.source || null;
    const escapedSource = escapeHTML(source);
    const msg = isPenalty
        ? (escapedSource ? `You received ${count} penalty card(s) from ${escapedSource}.` : `You received ${count} penalty card(s).`)
        : `You received ${count} card(s).`;

    soundEffect('draw');
    showToast(msg);
    const logBox = document.getElementById('game-log-box');
    logBox.insertAdjacentHTML('beforeend', `<div>📥 ${msg}</div>`);
    logBox.scrollTop = logBox.scrollHeight;

    // brief visual on the hand area
    const handContainer = document.getElementById('hand-container');
    if (handContainer) {
        handContainer.classList.add('hand-receive-flash');
        setTimeout(() => handContainer.classList.remove('hand-receive-flash'), 900);
    }
    // animate small floating cards into the hand
    animateReceivedCards(count, data.cards || [], isPenalty);
});

function animateReceivedCards(count, cards, isPenalty) {
    const maxShow = 6;
    const toShow = Math.min(count, maxShow);
    const sourceEl = document.getElementById('top-card') || document.getElementById('turn-badge-container');
    const targetEl = document.getElementById('my-hand') || document.getElementById('hand-container');
    const srcRect = sourceEl ? sourceEl.getBoundingClientRect() : { left: window.innerWidth/2, top: 60 };
    const tgtRect = targetEl ? targetEl.getBoundingClientRect() : { left: window.innerWidth/2, top: window.innerHeight - 140 };

    for (let i = 0; i < toShow; i++) {
        const el = document.createElement('div');
        el.className = 'floating-card small';
        el.style.left = (srcRect.left + (srcRect.width/2) - 22) + 'px';
        el.style.top = (srcRect.top + (srcRect.height/2) - 32) + 'px';
        el.innerText = i === toShow - 1 && count > maxShow ? `+${count - (maxShow-1)}` : (cards[i] ? (cards[i].value === 'Ace' ? 'A' : cards[i].value[0]) : '🂠');

        if (i === toShow - 1 && count > maxShow) {
            const badge = document.createElement('div');
            badge.className = 'floating-count';
            badge.innerText = `+${count - (maxShow-1)}`;
            el.appendChild(badge);
        }

        document.body.appendChild(el);

        // force reflow so transition applies
        // eslint-disable-next-line no-unused-expressions
        el.offsetHeight;

        const offsetX = (tgtRect.left + tgtRect.width/2) - (srcRect.left + (srcRect.width/2));
        const offsetY = (tgtRect.top + tgtRect.height/2) - (srcRect.top + (srcRect.height/2));
        const rotate = (Math.random() * 40) - 20;
        const scale = 0.7 + Math.random() * 0.4;

        // stagger animation slightly
        setTimeout(() => {
            el.style.transform = `translate(${offsetX}px, ${offsetY}px) scale(${scale}) rotate(${rotate}deg)`;
            el.style.opacity = '0.95';
        }, i * 70);

        // remove after transition
        setTimeout(() => {
            el.classList.add('fade-out');
            setTimeout(() => el.remove(), 300);
        }, 900 + i * 70);
    }
}

// Listen for server-sent sound events
socket.on('play_sound', (data) => {
    if (data && data.type) {
        soundEffect(data.type);
    }
});

function preloadCardImages() {
    const suits = ['Hearts', 'Diamonds', 'Clubs', 'Spades'];
    const values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'Jack', 'Queen', 'King', 'Ace'];
    suits.forEach(suit => {
        values.forEach(value => {
            const img = new Image();
            img.src = `/static/images/${value}_of_${suit}.png`.toLowerCase();
        });
    });
    const placeholder = new Image();
    placeholder.src = '/static/images/ace_of_spades.png';
}

function triggerConfetti() {
    const duration = 3000;
    const end = Date.now() + duration;
    
    const container = document.createElement('div');
    container.style.position = 'fixed';
    container.style.top = '0';
    container.style.left = '0';
    container.style.width = '100vw';
    container.style.height = '100vh';
    container.style.pointerEvents = 'none';
    container.style.zIndex = '9999';
    document.body.appendChild(container);

    const colors = ['#f44336', '#e91e63', '#9c27b0', '#673ab7', '#3f51b5', '#2196f3', '#03a9f4', '#00bcd4', '#009688', '#4caf50', '#8bc34a', '#cddc39', '#ffeb3b', '#ffc107', '#ff9800', '#ff5722'];

    const interval = setInterval(() => {
        if (Date.now() > end) {
            clearInterval(interval);
            container.remove();
            return;
        }

        const particle = document.createElement('div');
        particle.style.position = 'absolute';
        particle.style.width = (Math.random() * 8 + 4) + 'px';
        particle.style.height = (Math.random() * 12 + 6) + 'px';
        particle.style.backgroundColor = colors[Math.floor(Math.random() * colors.length)];
        particle.style.left = (Math.random() * 100) + 'vw';
        particle.style.top = '-20px';
        particle.style.borderRadius = '2px';
        particle.style.opacity = Math.random() * 0.5 + 0.5;
        particle.style.transform = `rotate(${Math.random() * 360}deg)`;

        container.appendChild(particle);

        const destX = (Math.random() * 100 - 50);
        const animation = particle.animate([
            { top: '-20px', transform: 'rotate(0deg) translateX(0px)' },
            { top: '105vh', transform: `rotate(${Math.random() * 720 + 360}deg) translateX(${destX}px)` }
        ], {
            duration: Math.random() * 2000 + 1500,
            easing: 'ease-out'
        });

        animation.onfinish = () => particle.remove();
    }, 25);
}