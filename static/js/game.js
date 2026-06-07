const socket = io();
let selectedCards = []; 
let currentHand = [];
let globalState = null;
let myTurn = false;
let toastTimeout = null;

function triggerMobileToast(message) {
    const toast = document.getElementById('toast-notification');
    toast.innerText = message;
    toast.className = "show";
    clearTimeout(toastTimeout);
    toastTimeout = setTimeout(() => { toast.className = ""; }, 4000);
}

function getShortValue(fullValString) {
    const mapping = { 'Ace': 'A', 'Jack': 'J', 'Queen': 'Q', 'King': 'K' };
    return mapping[fullValString] || fullValString;
}

function getSuitSymbol(suit) { 
    return suit === 'Hearts' ? '♥' : suit === 'Diamonds' ? '♦' : suit === 'Clubs' ? '♣' : '♠'; 
}

function buildCardElement(cardData) {
    const cardDiv = document.createElement('div');
    const shortVal = getShortValue(cardData.value);
    const suitSym = getSuitSymbol(cardData.suit);
    
    cardDiv.className = `card ${['Hearts','Diamonds'].includes(cardData.suit) ? 'red' : ''}`;
    cardDiv.innerHTML = `
        <div class="pip-tl">${shortVal}<br>${suitSym}</div>
        <div class="suit-center">${suitSym}</div>
        <div class="pip-br">${shortVal}<br>${suitSym}</div>
        <span class="badge"></span>
    `;
    return cardDiv;
}

/* Socket Listeners */
socket.on('receive_nudge', (data) => {
    soundEffect('nudge_vibe');
    document.body.classList.add('wobble-effect');
    triggerMobileToast(`💥 Nudge from ${data.sender}: ${data.emoji}`);
    setTimeout(() => { document.body.classList.remove('wobble-effect'); }, 450); 
});

socket.on('play_sound', (data) => { soundEffect(data.type); });

socket.on('state_update', (state) => {
    globalState = state;
    const clientName = document.getElementById('username').value.trim();
    
    if (state.is_started) {
        document.getElementById('lobby-controls').style.display = 'none';
        document.getElementById('turn-indicator').innerText = `Turn: ${state.current_player}`;
        myTurn = (state.current_player && clientName === state.current_player);
    } else {
        document.getElementById('lobby-controls').style.display = 'block';
        document.getElementById('turn-indicator').innerText = `Lobby (Not started)`;
        myTurn = false;
    }
    
    if (state.penalty > 0) {
        document.getElementById('penalty-tracker').innerText = `⚠️ Stacked Penalty: +${state.penalty} (${state.penalty_type}s)`;
    } else {
        document.getElementById('penalty-tracker').innerText = "No active penalties.";
    }

    const alertBox = document.getElementById('personal-penalty-alert');
    const drawBtn = document.getElementById('action-draw-btn');
    
    if (state.penalty > 0 && myTurn) {
        alertBox.style.display = 'block';
        drawBtn.innerText = `Take Penalty (+${state.penalty})`;
        drawBtn.style.background = '#d9534f';
        if (state.penalty_type === '2') {
            document.getElementById('penalty-alert-text').innerHTML = `Facing <b>+${state.penalty}</b>! Counter with a <b>2</b> or accept.`;
        } else if (state.penalty_type === 'BJ') {
            document.getElementById('penalty-alert-text').innerHTML = `Facing <b>+${state.penalty}</b> from Jacks! Counter with a <b>Jack</b> or accept.`;
        }
    } else {
        alertBox.style.display = 'none';
        drawBtn.innerText = "Draw Card";
        drawBtn.style.background = '#e0a800';
    }

    const topCardDiv = document.getElementById('top-card');
    const suitIndicator = document.getElementById('active-suit-indicator');
    if (state.top_card) {
        const shortVal = getShortValue(state.top_card.value);
        const suitSym = getSuitSymbol(state.top_card.suit);
        
        topCardDiv.className = `card ${['Hearts','Diamonds'].includes(state.top_card.suit) ? 'red' : ''}`;
        topCardDiv.innerHTML = `
            <div class="pip-tl">${shortVal}<br>${suitSym}</div>
            <div class="suit-center">${suitSym}</div>
            <div class="pip-br">${shortVal}<br>${suitSym}</div>
        `;
        suitIndicator.innerText = state.active_suit ? `Suit: ${state.active_suit} ${getSuitSymbol(state.active_suit)}` : "";
        document.getElementById('queen-actions').style.display = (state.top_card.value === 'Queen' && myTurn) ? 'block' : 'none';
    }

    const listBox = document.getElementById('player-list-box');
    listBox.innerHTML = '';
    
    state.player_list.forEach(p => {
        const rowDiv = document.createElement('div');
        rowDiv.className = `player-row ${p === state.current_player ? 'active-turn' : ''}`;
        
        let statusText = "Ready";
        let lastCardBadge = "";
        if (state.is_started && state.hand_sizes && state.hand_sizes[p] !== undefined) {
            const count = state.hand_sizes[p];
            statusText = `${count} cards`;
            if (count === 1) lastCardBadge = ` <span class="last-card-warning">⚠️</span>`;
        }

        const metaDiv = document.createElement('div');
        metaDiv.className = 'player-meta';
        metaDiv.innerHTML = `<span>👤 <b>${p}</b>: ${statusText} ${lastCardBadge}</span> <span>${p === state.current_player ? '⚡ Turn' : ''}</span>`;
        if (p === state.current_player) metaDiv.style.color = '#ffeb3b';
        rowDiv.appendChild(metaDiv);

        if (p !== clientName) {
            const tray = document.createElement('div');
            tray.className = 'nudge-tray';
            const emojis = ['⏰', '🤔', '👀', '😂', '🃏'];
            emojis.forEach(emo => {
                const btn = document.createElement('button');
                btn.className = 'nudge-btn';
                btn.innerText = emo;
                btn.onclick = () => fireNudge(p, emo);
                tray.appendChild(btn);
            });
            rowDiv.appendChild(tray);
        }
        listBox.appendChild(rowDiv);
    });

    const leagueBody = document.getElementById('league-rows');
    if (state.league_table && state.league_table.length > 0) {
        leagueBody.innerHTML = '';
        state.league_table.forEach(row => {
            const tr = document.createElement('tr');
            tr.innerHTML = `<td><b>${row.name}</b></td><td>${row.wins}</td><td>${row.losses}</td>`;
            leagueBody.appendChild(tr);
        });
    }
    evaluateButtonAbilities();
});

socket.on('your_hand', (data) => {
    currentHand = data.hand;
    const handDiv = document.getElementById('my-hand');
    handDiv.innerHTML = '';
    selectedCards = []; 
    
    data.hand.forEach((card) => {
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
});

function evaluateButtonAbilities() {
    const playBtn = document.getElementById('play-btn');
    playBtn.disabled = (!globalState || !globalState.is_started || !myTurn || selectedCards.length === 0);
}

function updateBadges(handDiv) {
    const cardsInDOM = handDiv.getElementsByClassName('card');
    for (let div of cardsInDOM) {
        const b = div.getElementsByClassName('badge')[0];
        const pipText = div.getElementsByClassName('pip-tl')[0].innerText;
        const val = pipText.split('\n')[0];
        const suitSym = pipText.split('\n')[1];
        
        const idx = selectedCards.findIndex(c => getShortValue(c.value) === val && getSuitSymbol(c.suit) === suitSym);
        if (idx !== -1) {
            b.innerText = idx + 1;
        } else {
            b.innerText = "";
        }
    }
}

socket.on('prompt_ace_suit', () => { document.getElementById('ace-modal').style.display = 'flex'; });
socket.on('game_log', (data) => {
    const logBox = document.getElementById('game-log-box');
    logBox.innerHTML += `<div>${data.msg}</div>`;
    logBox.scrollTop = logBox.scrollHeight;
});

/* Interaction Emitters */
function joinGame() {
    const name = document.getElementById('username').value.trim();
    if (!name) { triggerMobileToast("Please enter a name!"); return; }
    socket.emit('join_game', { name: name });
    document.getElementById('setup-panel').style.display = 'none';
    soundEffect('play');
}

function startGame() { socket.emit('start_match'); }
/* Look for this line around line 216 and change 'def' to 'function' */
function playSelected() { 
    if (selectedCards.length === 0) return; 
    socket.emit('play_cards', { cards: selectedCards }); 
}
function selectAceSuit(suit) { socket.emit('declare_ace_suit', { suit: suit }); document.getElementById('ace-modal').style.display = 'none'; }
function drawOrResolve() { socket.emit('take_penalty_or_draw'); }
function cascade(suit) { socket.emit('queen_cascade', { suit: suit }); }
function fireNudge(targetPlayer, emojiChar) { socket.emit('send_nudge', { target: targetPlayer, emoji: emojiChar }); }

socket.on('error', (data) => { triggerMobileToast(data.msg); });
socket.on('game_over', (data) => { 
    document.getElementById('game-over-text').innerText = `${data.winner} cleared their hand and won!`;
    document.getElementById('game-over-modal').style.display = 'flex';
});
function closeGameOverModal() { document.getElementById('game-over-modal').style.display = 'none'; }

/* Audio AudioEngine */
function soundEffect(type) {
    try {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!AudioContext) return;
        const ctx = new AudioContext();
        const now = ctx.currentTime;

        if (type === 'shuffle') {
            for (let i = 0; i < 8; i++) {
                const osc = ctx.createOscillator(); const gain = ctx.createGain();
                osc.type = 'triangle'; osc.frequency.setValueAtTime(150 + (i * 40), now + (i * 0.04));
                gain.connect(ctx.destination); osc.connect(gain);
                gain.gain.setValueAtTime(0.08, now + (i * 0.04));
                gain.gain.linearRampToValueAtTime(0, now + (i * 0.04) + 0.03);
                osc.start(now + (i * 0.04)); osc.stop(now + (i * 0.04) + 0.03);
            }
        } else if (type === 'play') {
            const osc = ctx.createOscillator(); const gain = ctx.createGain();
            osc.connect(gain); gain.connect(ctx.destination);
            osc.type = 'triangle'; osc.frequency.setValueAtTime(440, now);
            osc.frequency.exponentialRampToValueAtTime(880, now + 0.1);
            gain.gain.setValueAtTime(0.1, now); gain.gain.linearRampToValueAtTime(0, now + 0.15);
            osc.start(now); osc.stop(now + 0.15);
        } else if (type === 'draw') {
            const osc = ctx.createOscillator(); const gain = ctx.createGain();
            osc.connect(gain); gain.connect(ctx.destination);
            osc.type = 'sine'; osc.frequency.setValueAtTime(600, now);
            osc.frequency.linearRampToValueAtTime(300, now + 0.12);
            gain.gain.setValueAtTime(0.15, now); gain.gain.linearRampToValueAtTime(0, now + 0.12);
            osc.start(now); osc.stop(now + 0.12);
        } else if (type === 'penalty') {
            const osc = ctx.createOscillator(); const gain = ctx.createGain();
            osc.connect(gain); gain.connect(ctx.destination);
            osc.type = 'sawtooth'; osc.frequency.setValueAtTime(180, now);
            osc.frequency.linearRampToValueAtTime(90, now + 0.3);
            gain.gain.setValueAtTime(0.2, now); gain.gain.linearRampToValueAtTime(0, now + 0.3);
            osc.start(now); osc.stop(now + 0.3);
        } else if (type === 'nudge_vibe') {
            const osc = ctx.createOscillator(); const gain = ctx.createGain();
            osc.connect(gain); gain.connect(ctx.destination);
            osc.type = 'sawtooth'; osc.frequency.setValueAtTime(110, now);
            gain.gain.setValueAtTime(0.3, now); gain.gain.linearRampToValueAtTime(0, now + 0.1);
            osc.start(now); osc.stop(now + 0.12);
            setTimeout(() => {
                const osc2 = ctx.createOscillator(); const gain2 = ctx.createGain();
                osc2.connect(gain2); gain2.connect(ctx.destination);
                osc2.type = 'sawtooth'; osc2.frequency.setValueAtTime(105, ctx.currentTime);
                gain2.gain.setValueAtTime(0.3, ctx.currentTime); gain2.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.1);
                osc2.start(); osc2.stop(ctx.currentTime + 0.12);
            }, 140);
        } else if (type === 'victory') {
            const osc = ctx.createOscillator(); const gain = ctx.createGain();
            osc.connect(gain); gain.connect(ctx.destination);
            osc.type = 'square'; osc.frequency.setValueAtTime(587.33, now);
            osc.frequency.setValueAtTime(880, now + 0.15); osc.frequency.setValueAtTime(1174.66, now + 0.3);
            gain.gain.setValueAtTime(0.15, now); gain.gain.linearRampToValueAtTime(0, now + 0.6);
            osc.start(now); osc.stop(now + 0.6);
        }
    } catch (e) {}
}