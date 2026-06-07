const socket = io();
let currentHand = [];
let selectedCards = [];
let globalState = {};

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
    socket.emit('join_game', { name: name });
}

function startGame() {
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
        soundEffect('draw');
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
    div.className = 'card';
    if(card.suit === 'Hearts' || card.suit === 'Diamonds') div.classList.add('red');
    
    const suitSymbol = SUIT_EMOJIS[card.suit] || card.suit[0];
    let displayVal = card.value;
    if(displayVal === 'Ace') displayVal = 'A';
    if(displayVal === 'Jack') displayVal = 'J';
    if(displayVal === 'Queen') displayVal = 'Q';
    if(displayVal === 'King') displayVal = 'K';

    div.innerHTML = `
        <div class="badge"></div>
        <div class="pip-tl">${displayVal}<br>${suitSymbol}</div>
        <div class="suit-center">${suitSymbol}</div>
        <div class="pip-br">${displayVal}<br>${suitSymbol}</div>
    `;
    return div;
}

function updateBadges(container) {
    const cardsInDOM = container.getElementsByClassName('card');
    selectedCards.forEach((sc, idx) => {
        for(let element of cardsInDOM) {
            const rawText = element.querySelector('.pip-tl').innerText;
            const shortVal = sc.value === 'Ace' ? 'A' : sc.value === 'Jack' ? 'J' : sc.value === 'Queen' ? 'Q' : sc.value === 'King' ? 'K' : sc.value;
            
            if(rawText.includes(shortVal) && rawText.includes(SUIT_EMOJIS[sc.suit])) {
                if(element.classList.contains('selected') && !element.querySelector('.badge').innerText) {
                    element.querySelector('.badge').innerText = idx + 1;
                    break;
                }
            }
        }
    });
    for(let element of cardsInDOM) {
        if(!element.classList.contains('selected')) {
            element.querySelector('.badge').innerText = '';
        }
    }
}

function playSelected() {
    if (selectedCards.length === 0) return;
    socket.emit('play_cards', { cards: selectedCards });
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
        
        if (state.current_player === clientName) {
            turnContainer.classList.add('my-turn');
            turnMessage.innerHTML = `⚔️ <span><b>YOUR TURN!</b> Drop your combo.</span>`;
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
        frame.className = 'card';
        if(state.top_card.suit === 'Hearts' || state.top_card.suit === 'Diamonds') frame.classList.add('red');
        
        const suitSymbol = SUIT_EMOJIS[state.top_card.suit];
        let val = state.top_card.value;
        if(val === 'Ace') val = 'A';
        if(val === 'Jack') val = 'J';
        if(val === 'Queen') val = 'Q';
        if(val === 'King') val = 'K';

        frame.innerHTML = `
            <div class="pip-tl">${val}<br>${suitSymbol}</div>
            <div class="suit-center">${suitSymbol}</div>
            <div class="pip-br">${val}<br>${suitSymbol}</div>
        `;
        document.getElementById('active-suit-indicator').innerText = `Active Match Suit: ${state.active_suit}`;
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
        
        row.innerHTML = `
            <div class="player-meta">
                <span>${pLabel} ${state.is_started ? `🃏 (${cardCount} left)` : '⏳ Ready'}</span>
                ${(p !== clientName && state.is_started) ? `<button class="nudge-btn" onclick="triggerNudge('${p}')">⏰</button>` : ''}
            </div>
        `;
        listContainer.appendChild(row);
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
    document.getElementById('game-over-text').innerText = `Winner: ${data.winner}!`;
    document.getElementById('game-over-modal').style.display = 'flex';
});

function closeGameOverModal() {
    document.getElementById('game-over-modal').style.display = 'none';
}

socket.on('receive_nudge', (data) => {
    showToast(`⏰ NUDGE from ${data.sender}! Speed up!`);
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

function soundEffect(type) {
    console.log(`Tactile Operational Execution: ${type}`);
}