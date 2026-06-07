import random
import os
from flask import Flask, render_template, request, session
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'blackjack_family_secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

class FamilyBlackjackEngine:
    def __init__(self):
        self.players = []          # Ordered list of Unique Usernames
        self.sid_to_name = {}      # Maps active connection request.sid -> Username
        self.name_to_sid = {}      # Maps Username -> active connection request.sid
        self.hands = {}            # Maps Username -> Card Array
        self.deck = []
        self.discard_pile = []
        self.current_turn_index = 0
        self.direction = 1      
        self.is_started = False
        
        # Rotational Dealer Tracking Variable
        self.match_dealer_index = -1  # Increments to 0 on the very first match setup
        
        # Penalty & Wildcard Tracking
        self.active_penalty_type = None  
        self.accumulated_penalty = 0     
        self.declared_ace_suit = None   
        
        # Career League Standings Data
        self.league_wins = {}   
        self.league_losses = {} 

    def reset_lobby(self):
        """Resets the entire match room engine back to baseline factory defaults."""
        self.players = []
        self.sid_to_name = {}
        self.name_to_sid = {}
        self.hands = {}
        self.deck = []
        self.discard_pile = []
        self.current_turn_index = 0
        self.direction = 1      
        self.is_started = False
        self.match_dealer_index = -1
        self.active_penalty_type = None  
        self.accumulated_penalty = 0     
        self.declared_ace_suit = None   
        # Note: We intentionally DO NOT clear self.league_wins or self.league_losses 
        # so career family stats persist across separate game room lobbies!

    def build_deck(self):
        suits = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
        values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'Jack', 'Queen', 'King', 'Ace']
        deck = [{'suit': s, 'value': v} for s in suits for v in values]
        random.shuffle(deck)
        return deck

    def register_league_player(self, name):
        if name not in self.league_wins:
            self.league_wins[name] = 0
        if name not in self.league_losses:
            self.league_losses[name] = 0

    def start_game(self):
        if len(self.players) < 2:
            return False
        self.deck = self.build_deck()
        self.discard_pile = []
        self.hands = {name: [] for name in self.players}
        
        for name in self.players:
            self.register_league_player(name)
        
        # Deal cards out clockwise
        for _ in range(7):
            for name in self.players:
                self.hands[name].append(self.deck.pop())
                
        starter = self.deck.pop()
        self.discard_pile.append(starter)
        
        self.active_penalty_type = None
        self.accumulated_penalty = 0
        self.declared_ace_suit = None
        self.is_started = True

        # --- ROTATION LOGIC ---
        self.match_dealer_index = (self.match_dealer_index + 1) % len(self.players)
        self.current_turn_index = (self.match_dealer_index + 1) % len(self.players)
        return True

    def get_current_player_name(self):
        return self.players[self.current_turn_index] if self.players else None

    def advance_turn(self, steps=1):
        if not self.players:
            return
        self.current_turn_index = (self.current_turn_index + (steps * self.direction)) % len(self.players)
        self.check_and_enforce_autodraw()

    def has_valid_penalty_counter(self, name):
        if self.accumulated_penalty == 0:
            return True
        hand = self.hands.get(name, [])
        if self.active_penalty_type == '2':
            return any(c['value'] == '2' for c in hand)
        elif self.active_penalty_type == 'BJ':
            return any(c['value'] == 'Jack' for c in hand)
        return False

    def check_and_enforce_autodraw(self):
        if not self.is_started or self.accumulated_penalty == 0:
            return

        current_name = self.get_current_player_name()
        if not self.has_valid_penalty_counter(current_name):
            self.draw_card(current_name, self.accumulated_penalty)
            socketio.emit('game_log', {'msg': f"💥 {current_name} had no counter cards and auto-drew {self.accumulated_penalty} cards!"}, room='game_room')
            
            target_sid = self.name_to_sid.get(current_name)
            if target_sid:
                socketio.emit('play_sound', {'type': 'penalty'}, to=target_sid)
            
            self.accumulated_penalty = 0
            self.active_penalty_type = None
            
            self.current_turn_index = (self.current_turn_index + self.direction) % len(self.players)
            self.check_and_enforce_autodraw()

    def draw_card(self, name, count=1):
        drawn = []
        for _ in range(count):
            if not self.deck:
                if len(self.discard_pile) > 1:
                    top_card = self.discard_pile.pop()
                    self.deck = self.discard_pile.copy()
                    self.discard_pile = [top_card]
                    socketio.emit('game_log', {'msg': "🔄 The draw pile ran out! The discard pile has been flipped over into the deck (Order Maintained)."}, room='game_room')
                else:
                    break
            if self.deck:
                drawn.append(self.deck.pop())
        if name in self.hands:
            self.hands[name].extend(drawn)
        return drawn

    def update_league_results(self, winner_name):
        self.register_league_player(winner_name)
        self.league_wins[winner_name] += 1
        
        for name in self.players:
            if name != winner_name:
                self.register_league_player(name)
                self.league_losses[name] += 1

    def validate_and_play_move(self, name, selected_cards):
        if name != self.get_current_player_name() or not selected_cards:
            return False, "Not your turn or no cards selected.", 0

        player_hand = self.hands[name]
        
        matched_cards = []
        for sc in selected_cards:
            found = next((c for c in player_hand if c['value'] == sc['value'] and c['suit'] == sc['suit'] and c not in matched_cards), None)
            if not found:
                return False, f"Card ({sc['value']} of {sc['suit']}) not found in your hand.", 0
            matched_cards.append(found)

        top_card = self.discard_pile[-1]
        active_suit = self.declared_ace_suit if (self.declared_ace_suit and top_card['value'] == 'Ace') else top_card['suit']
        active_val = top_card['value']

        temp_penalty_type = self.active_penalty_type
        temp_accumulated = self.accumulated_penalty
        first_card = matched_cards[0]
        
        if temp_accumulated > 0:
            if temp_penalty_type == '2' and first_card['value'] != '2':
                return False, "Your starting defense card must be a 2!", 0
            if temp_penalty_type == 'BJ' and first_card['value'] != 'Jack':
                return False, "Your starting defense card must be a Jack!", 0
        else:
            if not (first_card['suit'] == active_suit or first_card['value'] == active_val or first_card['value'] == 'Ace'):
                return False, f"First card must match active suit ({active_suit}) or value ({active_val}).", 0

        eight_skips = 0
        for i, card in enumerate(matched_cards):
            is_bj = (card['value'] == 'Jack' and card['suit'] in ['Spades', 'Clubs'])
            is_rj = (card['value'] == 'Jack' and card['suit'] in ['Hearts', 'Diamonds'])
            is_two = (card['value'] == '2')

            if i > 0:
                prev_card = matched_cards[i-1]
                if not (card['suit'] == prev_card['suit'] or card['value'] == prev_card['value'] or card['value'] == 'Ace'):
                    return False, f"Chain broken at position {i+1}.", 0
                if temp_accumulated > 0:
                    if temp_penalty_type == '2' and not is_two:
                        return False, "You can only stack 2s while a penalty is active.", 0
                    if temp_penalty_type == 'BJ' and not (is_bj or is_rj):
                        return False, "You can only stack Jacks while a penalty is active.", 0

            if card['value'] == '8':
                eight_skips += 1
            if is_two:
                temp_penalty_type = '2'
                temp_accumulated += 2
            elif is_bj:
                temp_penalty_type = 'BJ'
                temp_accumulated += 5
            elif is_rj and temp_penalty_type == 'BJ':
                temp_penalty_type = None
                temp_accumulated = 0

        self.active_penalty_type = temp_penalty_type
        self.accumulated_penalty = temp_accumulated
        self.declared_ace_suit = None

        for c in matched_cards:
            player_hand.remove(c)
            self.discard_pile.append(c)

        return True, "Success", eight_skips

    def execute_queen_cascade(self, name, suit_to_dump):
        if name != self.get_current_player_name():
            return False, "Not your turn."
        if self.discard_pile[-1]['value'] != 'Queen':
            return False, "Top card is not a Queen."
        
        player_hand = self.hands[name]
        cards_to_dump = [c for c in player_hand if c['suit'] == suit_to_dump]
        
        for c in cards_to_dump:
            player_hand.remove(c)
            self.discard_pile.append(c)
        return True, f"Dumped {len(cards_to_dump)} cards."

game = FamilyBlackjackEngine()

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('join_game')
def handle_join(data):
    sid = request.sid
    name = data.get('name', '').strip()
    if not name:
        return emit('error', {'msg': 'Name cannot be blank.'})
        
    session['username'] = name
    
    if name not in game.players:
        if game.is_started:
            return emit('error', {'msg': 'Match already running!'})
        game.players.append(name)
    
    game.sid_to_name[sid] = name
    game.name_to_sid[name] = sid
    
    join_room('game_room')
    broadcast_state()

@socketio.on('start_match')
def handle_start():
    if game.start_game():
        dealer_name = game.players[game.match_dealer_index]
        starter_name = game.get_current_player_name()
        
        socketio.emit('game_log', {'msg': "🔀 Shuffling the deck... Creating a fresh setup!"}, room='game_room')
        socketio.emit('game_log', {'msg': f"🃏 Dealer for this hand: <b>{dealer_name}</b>. Action starts with <b>{starter_name}</b>!"}, room='game_room')
        socketio.emit('play_sound', {'type': 'shuffle'}, room='game_room')
        broadcast_state()
    else:
        emit('error', {'msg': 'Need at least 2 players to start!'})

@socketio.on('play_cards')
def handle_play(data):
    sid = request.sid
    name = game.sid_to_name.get(sid)
    if not name or name != game.get_current_player_name():
        return emit('error', {'msg': "It is not your turn!"})
        
    cards = data.get('cards', [])
    success, msg, skips = game.validate_and_play_move(name, cards)
    if success:
        cards_desc = ", ".join([f"{c['value']} of {c['suit']}" for c in cards])
        socketio.emit('game_log', {'msg': f"📝 {name} played a chain: {cards_desc}"}, room='game_room')
        
        # 🏁 CRITICAL FIX: VICTORY POSITION CLEANUP
        if len(game.hands.get(name, [])) == 0:
            game.update_league_results(name)
            
            # Immediately neutralize matching metrics to break any lingering background autodraw cycles
            game.is_started = False
            game.accumulated_penalty = 0
            game.active_penalty_type = None
            game.declared_ace_suit = None
            
            socketio.emit('game_over', {'winner': name}, room='game_room')
            socketio.emit('play_sound', {'type': 'victory'}, room='game_room')
            broadcast_state()
            return

        if len(game.hands.get(name, [])) == 1:
            socketio.emit('game_log', {'msg': f"📢 🔥 LAST CARD! {name} is down to their final card!"}, room='game_room')
            socketio.emit('play_sound', {'type': 'penalty'}, room='game_room')

        socketio.emit('play_sound', {'type': 'play'}, room='game_room')

        if cards[-1]['value'] == 'Ace':
            emit('prompt_ace_suit', {}, to=sid)
            broadcast_state()
        else:
            turn_steps = 1
            if skips > 0:
                turn_steps += skips
                socketio.emit('game_log', {'msg': f"skip 🛑 {skips} player(s) skipped by the 8 power card sequence!"}, room='game_room')
            
            if game.accumulated_penalty == 0 or cards[-1]['value'] in ['2', 'Jack']:
                game.advance_turn(steps=turn_steps)
            broadcast_state()
    else:
        emit('error', {'msg': msg})

@socketio.on('declare_ace_suit')
def handle_ace_suit(data):
    sid = request.sid
    name = game.sid_to_name.get(sid)
    if not name or name != game.get_current_player_name():
        return
    chosen_suit = data.get('suit')
    game.declared_ace_suit = chosen_suit
    
    socketio.emit('game_log', {'msg': f"🔮 {name} set the active game suit to: {chosen_suit}!"}, room='game_room')
    socketio.emit('play_sound', {'type': 'play'}, room='game_room')
    game.advance_turn()
    broadcast_state()

@socketio.on('queen_cascade')
def handle_cascade(data):
    sid = request.sid
    name = game.sid_to_name.get(sid)
    if not name or name != game.get_current_player_name():
        return
    suit = data.get('suit')
    success, msg = game.execute_queen_cascade(name, suit)
    if success:
        socketio.emit('game_log', {'msg': f"👑 {name} executed a Queen Cascade on {suit}!"}, room='game_room')
        socketio.emit('play_sound', {'type': 'play'}, room='game_room')
        
        if len(game.hands.get(name, [])) == 0:
            game.update_league_results(name)
            game.is_started = False
            game.accumulated_penalty = 0
            game.active_penalty_type = None
            game.declared_ace_suit = None
            
            socketio.emit('game_over', {'winner': name}, room='game_room')
            socketio.emit('play_sound', {'type': 'victory'}, room='game_room')
        else:
            if len(game.hands.get(name, [])) == 1:
                socketio.emit('game_log', {'msg': f"📢 🔥 LAST CARD! {name} is down to their final card!"}, room='game_room')
            game.advance_turn()
        broadcast_state()
    else:
        emit('error', {'msg': msg})

@socketio.on('take_penalty_or_draw')
def handle_draw():
    sid = request.sid
    name = game.sid_to_name.get(sid)
    if not name or name != game.get_current_player_name():
        emit('error', {'msg': "Not your turn."})
        return

    socketio.emit('play_sound', {'type': 'draw'}, to=sid)
    if game.accumulated_penalty > 0:
        socketio.emit('game_log', {'msg': f"🏳️ {name} accepted the penalty and drew {game.accumulated_penalty} cards."}, room='game_room')
        game.draw_card(name, game.accumulated_penalty)
        game.accumulated_penalty = 0
        game.active_penalty_type = None
    else:
        socketio.emit('game_log', {'msg': f"🎴 {name} drew a single card."}, room='game_room')
        game.draw_card(name, 1)

    game.advance_turn()
    broadcast_state()

@socketio.on('send_nudge')
def handle_nudge(data):
    sid = request.sid
    sender_name = game.sid_to_name.get(sid, "Someone")
    target_name = data.get('target')
    emoji = data.get('emoji', '👋')
    if target_name not in game.players:
        return
    socketio.emit('game_log', {'msg': f"💥 {sender_name} sent a nudge to {target_name}: {emoji}"}, room='game_room')
    target_sid = game.name_to_sid.get(target_name)
    if target_sid:
        socketio.emit('receive_nudge', {'sender': sender_name, 'emoji': emoji}, to=target_sid)

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    name = game.sid_to_name.get(sid)
    
    if name:
        if name in game.name_to_sid:
            del game.name_to_sid[name]
        if sid in game.sid_to_name:
            del game.sid_to_name[sid]
            
        if name in game.players:
            if not game.is_started:
                game.players.remove(name)
                if name in game.hands:
                    del game.hands[name]
                socketio.emit('game_log', {'msg': f"❌ {name} left the lobby."}, room='game_room')
            else:
                socketio.emit('game_log', {'msg': f"🔌 {name} disconnected (Went Offline)."}, room='game_room')

        if len(game.sid_to_name) == 0:
            print("🚨 LOBBY EMPTY DETECTED: Automated room reset executed.")
            game.reset_lobby()
            socketio.emit('game_log', {'msg': "🧹 Room automatically reset because all players left."}, room='game_room')
        
        broadcast_state()

def broadcast_state():
    active_suit = game.declared_ace_suit
    if not active_suit and game.discard_pile:
        active_suit = game.discard_pile[-1]['suit']

    scoreboards = []
    for u_name in game.league_wins.keys():
        scoreboards.append({
            'name': u_name,
            'wins': game.league_wins.get(u_name, 0),
            'losses': game.league_losses.get(u_name, 0)
        })
    scoreboards.sort(key=lambda x: x['wins'], reverse=True)

    current_player = game.get_current_player_name()
    current_sid = game.name_to_sid.get(current_player) if current_player else None

    state = {
        'is_started': game.is_started,
        'top_card': game.discard_pile[-1] if game.discard_pile else None,
        'active_suit': active_suit,
        'current_player': current_player,
        'current_player_sid': current_sid,
        'penalty': game.accumulated_penalty,
        'penalty_type': game.active_penalty_type,
        'player_list': game.players,
        'hand_sizes': {p: len(game.hands[p]) for p in game.players if p in game.hands},
        'league_table': scoreboards
    }
    socketio.emit('state_update', state, room='game_room')
    
    for name in game.players:
        target_sid = game.name_to_sid.get(name)
        if target_sid:
            hand = game.hands.get(name, [])
            socketio.emit('your_hand', {'hand': hand}, to=target_sid)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)