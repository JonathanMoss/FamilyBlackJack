const socket = io();
let currentHand = [];
let selectedCards = [];
let globalState = {};
let lastPenalized = { name: null, amount: 0 };

// Web Audio API context for synthesized game sounds
let audioCtx = null;
function initAudio() {
    if (!audioCtx) {
        audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
}

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
    
    // Reset all badges
    for(let element of cardsInDOM) {
        const badge = element.querySelector('.badge');
        if (badge) badge.innerText = '';
    }

    selectedCards.forEach((sc, idx) => {
        for(let element of cardsInDOM) {
            // Match via dataset attributes instead of scraping text
            if(element.dataset.value === sc.value && element.dataset.suit === sc.suit) {
                if(element.classList.contains('selected')) {
                    const badge = element.querySelector('.badge');
                    if (badge) badge.innerText = idx + 1;
                    break;
                }
            }
        }
    });
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

function cascade(suit) {
    socket.emit('queen_cascade', { suit: suit });
}

function triggerNudge(targetPlayer) {
    socket.emit('send_nudge', { target: targetPlayer, emoji: '🚨' });
}

function evaluateButtonAbilities() {
    const isMyTurn = (globalState.current_player === document.getElementById('username').value.trim());
    document.getElementById('play-btn').disabled = !isMyTurn || selectedCards.length === 0;
    
    const drawBtn = document.getElementById('action-draw-btn');
    if(!isMyTurn) {
        drawBtn.disabled = true;
        drawBtn.innerText = "Draw Card";
    } else {
        drawBtn.disabled = false;
        drawBtn.innerText = (globalState.penalty > 0) ? `Take Penalty (+${globalState.penalty})` : "Draw Card";
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
    
    // Auto-Lobby Setup Safety Valving
    if (state.player_list.length === 0) {
        document.getElementById('setup-panel').style.display = 'block';
    } else if (state.player_list.includes(clientName)) {
        document.getElementById('setup-panel').style.display = 'none';
    }

    if (state.is_started) {
        document.getElementById('lobby-controls').style.display = 'none';
    } else {
        document.getElementById('lobby-controls').style.display = 'block';
    }

    // --- REFACTORED WORKFLOW: REPREMIUMIZED MATCH DASHBOARD SYSTEM ---
    const turnContainer = document.getElementById('turn-badge-container');
    const turnMessage = document.getElementById('turn-message');
    const statusDot = document.getElementById('game-status-dot');

    if (!state.is_started) {
        statusDot.style.background = '#dc3545'; // Dead/Idle Red
        turnContainer.classList.remove('my-turn');
        turnMessage.innerHTML = `⏳ <span>Lobby waiting to start...</span>`;
        document.getElementById('turn-timer').style.width = '100%';
    } else {
        statusDot.style.background = '#00ff66'; // Glowing Live Emerald Green
        
        const myHandSize = state.hand_sizes[clientName] || 0;
        const isSpectator = myHandSize === 0;

        if (isSpectator) {
            turnContainer.classList.remove('my-turn');
            turnMessage.innerHTML = `👀 <span><b>Spectating:</b> Waiting for next round...</span>`;
            document.getElementById('turn-timer').style.width = '0%';
        } else if (state.current_player === clientName) {
            turnContainer.classList.add('my-turn');
            turnMessage.innerHTML = `⚔️ <span><b>YOUR TURN!</b> Play your hand.</span>`;
            document.getElementById('turn-timer').style.width = '100%'; 
        } else {
            turnContainer.classList.remove('my-turn');
            turnMessage.innerHTML = `👤 <span>Action on <b>${state.current_player}</b></span>`;
            document.getElementById('turn-timer').style.width = '40%'; 
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
            suitIndicator.innerText = `Active Match Suit: ${state.active_suit}`;
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

        const cardCount = state.hand_sizes[p] || 0;
        let pLabel = (p === clientName) ? `<b>${p} (You)</b>` : p;

        const isSpectating = state.is_started && cardCount === 0;
        const statusText = isSpectating ? '👁️ Spectating' : `🃏 (${cardCount} left)`;

        const isLast = state.is_started && cardCount === 1;
        const lastIcon = isLast ? `<span class="last-card-icon" title="Last Card">🔥</span>` : '';

        const rightControls = (p !== clientName && state.is_started) ? `<button class="nudge-btn" onclick="triggerNudge('${p}')">⏰</button>` : '';

        // If there's an active penalty, highlight the current_player as the penalty target
        const isPenalized = state.penalty > 0 && state.current_player === p;
        const penaltyIcon = isPenalized ? `<span class="penalty-indicator" title="Penalty: +${state.penalty}">⚠️ +${state.penalty}</span>` : '';

        if (isPenalized) row.classList.add('penalty-target');

        row.innerHTML = `
            <div class="player-meta">
                <span>${pLabel} ${state.is_started ? statusText : '⏳ Ready'} ${lastIcon} ${penaltyIcon}</span>
                ${rightControls}
            </div>
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
    tbody.innerHTML = '';
    if(!state.league_table || state.league_table.length === 0) {
        tbody.innerHTML = `<tr><td colspan="3" style="color:#aaa;">No records found.</td></tr>`;
    } else {
        state.league_table.forEach(entry => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${entry.name}</td><td style="color:#28a745; font-weight:bold;">${entry.wins}</td><td style="color:#dc3545;">${entry.losses}</td>`;
            tbody.appendChild(tr);
        });
    }

    // Queen Cascade Control Drawer Visibility Hooks
    const qActions = document.getElementById('queen-actions');
    if(state.is_started && state.current_player === clientName && state.top_card && state.top_card.value === 'Queen') {
        qActions.style.display = 'block';
    } else {
        qActions.style.display = 'none';
    }

    evaluateButtonAbilities();
});

socket.on('prompt_ace_suit', () => {
    document.getElementById('ace-modal').style.display = 'flex';
});

socket.on('game_log', (data) => {
    const logBox = document.getElementById('game-log-box');
    logBox.innerHTML += `<div>${data.msg}</div>`;
    logBox.scrollTop = logBox.scrollHeight;
});

socket.on('game_over', (data) => {
    soundEffect('winner');
    document.getElementById('game-over-text').innerText = `Winner: ${data.winner}!`;
    document.getElementById('game-over-modal').style.display = 'flex';
});

function closeGameOverModal() {
    document.getElementById('game-over-modal').style.display = 'none';
}

// Expose core UI handlers globally for inline onclick attributes
window.organizeHand = organizeHand;
window.playSelected = playSelected;
window.drawOrResolve = drawOrResolve;
window.selectAceSuit = selectAceSuit;
window.cascade = cascade;
window.triggerNudge = triggerNudge;
window.resetGame = resetGame;
window.closeGameOverModal = closeGameOverModal;
window.joinGame = joinGame;
window.startGame = startGame;

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
    if (!audioCtx) return;
    if (audioCtx.state === 'suspended') {
        try {
            await audioCtx.resume();
        } catch (e) {
            return; // Context could not be resumed, likely due to autoplay policy
        }
    }

    const playTone = (freq, type = 'sine', duration = 0.1, volume = 0.1) => {
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = type;
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        
        const now = audioCtx.currentTime;
        osc.frequency.setValueAtTime(freq, now);
        gain.gain.setValueAtTime(volume, now);
        gain.gain.exponentialRampToValueAtTime(0.0001, now + duration);
        
        osc.start(now);
        osc.stop(now + duration);
    };

    // Helper for draw sound to avoid code duplication
    const _createAndPlayDrawSound = () => {
        // This function is only called if audioCtx is running or successfully resumed
        // so no need for additional audioCtx.resume() checks here.
        const drawNow = audioCtx.currentTime;
        const drawOsc = audioCtx.createOscillator();
        const drawGain = audioCtx.createGain();
        drawOsc.connect(drawGain);
        drawGain.connect(audioCtx.destination);
        drawOsc.frequency.setValueAtTime(400, drawNow);
        drawOsc.frequency.exponentialRampToValueAtTime(600, drawNow + 0.1);
        drawGain.gain.setValueAtTime(0.05, drawNow);
        drawGain.gain.linearRampToValueAtTime(0, drawNow + 0.1);
        drawOsc.start(drawNow);
        drawOsc.stop(drawNow + 0.1); // Corrected 'now' to 'drawNow'
    };

    switch(type) {
        case 'play':
            // Low "thump" for playing a card
            playTone(180, 'sine', 0.15, 0.2);
            break;
        case 'draw':
            // Rising blip for drawing
            _createAndPlayDrawSound();
            break;
        case 'shuffle':
            // Rapid sequence of short "clicks"
            for(let i=0; i<6; i++) {
                setTimeout(() => playTone(Math.random() * 200 + 200, 'square', 0.05, 0.02), i * 60);
            }
            break;
        case 'alert':
            // High pitched double-beep
            playTone(880, 'triangle', 0.1, 0.1);
            setTimeout(() => playTone(880, 'triangle', 0.1, 0.1), 150);
            break;
        case 'winner':
            // Simple C-Major Arpeggio (C4, E4, G4, C5)
            [261.63, 329.63, 392.00, 523.25].forEach((f, i) => {
                setTimeout(() => playTone(f, 'sine', 0.4, 0.1), i * 150);
            });
            break;
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
    if(!confirm('Are you sure you want to reset the current match? This will clear hands but keep league stats.')) return;
    socket.emit('reset_match');
}

// Initialize the lobby with a decorative placeholder before socket/join events
function initLobbyVisuals() {
    const frame = document.getElementById('top-card');
    if (frame && !frame.innerHTML.trim()) {
        frame.className = 'card image-card';
        const imgPath = `/static/images/ace_of_spades.png`;
        frame.innerHTML = `<img src="${imgPath}" class="card-img" alt="Ace of Spades Placeholder">`;
    }

    // Auto-join if a name was previously saved
    const savedName = localStorage.getItem('blackjack_player_name');
    if (savedName) {
        const nameInput = document.getElementById('username');
        if (nameInput) {
            nameInput.value = savedName;
            socket.emit('join_game', { name: savedName });
        }
    }
}
initLobbyVisuals();

socket.on('room_reset', (data) => {
    showToast(data.msg || 'Match reset.');
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
    const msg = isPenalty
        ? (source ? `You received ${count} penalty card(s) from ${source}.` : `You received ${count} penalty card(s).`)
        : `You received ${count} card(s).`;

    soundEffect('draw');
    showToast(msg);
    const logBox = document.getElementById('game-log-box');
    logBox.innerHTML += `<div>📥 ${msg}</div>`;
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
            setTimeout(() => { try { document.body.removeChild(el); } catch (e) {} }, 300);
        }, 900 + i * 70);
    }
}

// Listen for server-sent sound events
socket.on('play_sound', (data) => {
    if (data && data.type) {
        soundEffect(data.type);
    }
});