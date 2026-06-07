import random
import os
from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'blackjack_family_secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

class FamilyBlackjackEngine:
    def __init__(self):
        self.players = []       
        self.player_names = {}  
        self.hands = {}         
        self.deck = []
        self.discard_pile = []
        self.current_turn_index = 0
        self.direction = 1      
        self.is_started = False
        
        # Penalty & Wildcard Tracking
        self.active_penalty_type = None  
        self.accumulated_penalty = 0     
        self.declared_ace_suit = None   
        
        # Career League Standings Data
        self.league_wins = {}   # Map of Name -> Wins
        self.league_losses = {} # Map of Name -> Losses

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
        self.hands = {pid: [] for pid in self.players}
        
        # Ensure everyone in this round is registered on the board
        for pid in self.players:
            self.register_league_player(self.player_names[pid])
        
        for _ in range(7):
            for pid in self.players:
                self.hands[pid].append(self.deck.pop())
                
        starter = self.deck.pop()
        self.discard_pile.append(starter)
        
        self.active_penalty_type = None
        self.accumulated_penalty = 0
        self.current_turn_index = 0
        self.declared_ace_suit = None
        self.is_started = True
        return True

    def get_current_player_sid(self):
        return self.players[self.current_turn_index] if self.players else None

    def advance_turn(self, steps=1):
        if not self.players:
            return
        self.current_turn_index = (self.current_turn_index + (steps * self.direction)) % len(self.players)
        self.check_and_enforce_autodraw()

    def has_valid_penalty_counter(self, player_sid):
        if self.accumulated_penalty == 0:
            return True
        hand = self.hands.get(player_sid, [])
        if self.active_penalty_type == '2':
            return any(c['value'] == '2' for c in hand)
        elif self.active_penalty_type == 'BJ':
            return any(c['value'] == 'Jack' for c in hand)
        return False

    def check_and_enforce_autodraw(self):
        if not self.is_started or self.accumulated_penalty == 0:
            return

        current_sid = self.get_current_player_sid()
        if not self.has_valid_penalty_counter(current_sid):
            self.draw_card(current_sid, self.accumulated_penalty)
            p_name = self.player_names.get(current_sid, "Unknown")
            socketio.emit('game_log', {'msg': f"💥 {p_name} had no counter cards and auto-drew {self.accumulated_penalty} cards!"}, room='game_room')
            socketio.emit('play_sound', {'type': 'penalty'}, to=current_sid)
            
            self.accumulated_penalty = 0
            self.active_penalty_type = None
            
            self.current_turn_index = (self.current_turn_index + self.direction) % len(self.players)
            self.check_and_enforce_autodraw()

    def draw_card(self, player_sid, count=1):
        drawn = []
        for _ in range(count):
            if not self.deck:
                if len(self.discard_pile) > 1:
                    top_card = self.discard_pile.pop()
                    self.deck = self.discard_pile.copy()
                    random.shuffle(self.deck)
                    self.discard_pile = [top_card]
                else:
                    break
            if self.deck:
                drawn.append(self.deck.pop())
        if player_sid in self.hands:
            self.hands[player_sid].extend(drawn)
        return drawn

    def update_league_results(self, winner_sid):
        winner_name = self.player_names.get(winner_sid)
        if not winner_name:
            return
            
        self.register_league_player(winner_name)
        self.league_wins[winner_name] += 1
        
        for pid in self.players:
            if pid != winner_sid:
                p_name = self.player_names[pid]
                self.register_league_player(p_name)
                self.league_losses[p_name] += 1

    def validate_and_play_move(self, player_sid, selected_cards):
        if player_sid != self.get_current_player_sid() or not selected_cards:
            return False, "Not your turn or no cards selected.", 0

        player_hand = self.hands[player_sid]
        for c in selected_cards:
            if c not in player_hand:
                return False, "Card not found in your hand.", 0

        top_card = self.discard_pile[-1]
        active_suit = self.declared_ace_suit if (self.declared_ace_suit and top_card['value'] == 'Ace') else top_card['suit']
        active_val = top_card['value']

        temp_penalty_type = self.active_penalty_type
        temp_accumulated = self.accumulated_penalty

        first_card = selected_cards[0]
        
        if temp_accumulated > 0:
            if temp_penalty_type == '2' and first_card['value'] != '2':
                return False, "Your starting defense card must be a 2!", 0
            if temp_penalty_type == 'BJ' and first_card['value'] != 'Jack':
                return False, "Your starting defense card must be a Jack!", 0
        else:
            if not (first_card['suit'] == active_suit or first_card['value'] == active_val or first_card['value'] == 'Ace'):
                return False, f"First card must match active suit ({active_suit}) or value ({active_val}).", 0

        eight_skips = 0

        for i, card in enumerate(selected_cards):
            is_bj = (card['value'] == 'Jack' and card['suit'] in ['Spades', 'Clubs'])
            is_rj = (card['value'] == 'Jack' and card['suit'] in ['Hearts', 'Diamonds'])
            is_two = (card['value'] == '2')

            if i > 0:
                prev_card = selected_cards[i-1]
                if not (card['suit'] == prev_card['suit'] or card['value'] == prev_card['value'] or card['value'] == 'Ace'):
                    return False, f"Broken chain at position {i+1}: {card['value']} of {card['suit']} doesn't match {prev_card['value']} of {prev_card['suit']}.", 0
                
                if temp_accumulated > 0:
                    if temp_penalty_type == '2' and not is_two:
                        return False, "You can only stack 2s while a penalty is active.", 0
                    if temp_penalty_type == 'BJ' and not (is_bj or is_rj):
                        return False, "You can only stack/counter Jacks while a penalty is active.", 0

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

        for c in selected_cards:
            player_hand.remove(c)
            self.discard_pile.append(c)

        return True, "Success", eight_skips

    def execute_queen_cascade(self, player_sid, suit_to_dump):
        if player_sid != self.get_current_player_sid():
            return False, "Not your turn."
        if self.discard_pile[-1]['value'] != 'Queen':
            return False, "Top card is not a Queen."
        
        player_hand = self.hands[player_sid]
        cards_to_dump = [c for c in player_hand if c['suit'] == suit_to_dump]
        
        for c in cards_to_dump:
            player_hand.remove(c)
            self.discard_pile.append(c)
        return True, f"Dumped {len(cards_to_dump)} cards."

game = FamilyBlackjackEngine()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/templates/<filename>')
def serve_static_js(filename):
    return send_from_directory(os.path.join(app.root_path, 'templates'), filename)

@socketio.on('join_game')
def handle_join(data):
    sid = request.sid
    name = data.get('name', '').strip()
    if not name:
        name = f"Player {len(game.players)+1}"
    if sid not in game.players and not game.is_started:
        game.players.append(sid)
        game.player_names[sid] = name
        game.register_league_player(name)
    join_room('game_room')
    broadcast_state()

@socketio.on('start_match')
def handle_start():
    if game.start_game():
        socketio.emit('game_log', {'msg': "🃏 A fresh match has begun! 7 cards dealt clockwise."}, room='game_room')
        socketio.emit('play_sound', {'type': 'start'}, room='game_room')
        broadcast_state()
    else:
        emit('error', {'msg': 'Need at least 2 players to start!'})

@socketio.on('play_cards')
def handle_play(data):
    sid = request.sid
    cards = data.get('cards', [])
    p_name = game.player_names.get(sid, "Unknown")
    
    success, msg, skips = game.validate_and_play_move(sid, cards)
    if success:
        cards_desc = ", ".join([f"{c['value']} of {c['suit']}" for c in cards])
        socketio.emit('game_log', {'msg': f"📝 {p_name} played a chain: {cards_desc}"}, room='game_room')
        
        # Check Winner State
        if len(game.hands.get(sid, [])) == 0:
            game.update_league_results(sid)
            socketio.emit('game_over', {'winner': p_name}, room='game_room')
            socketio.emit('play_sound', {'type': 'victory'}, room='game_room')
            game.is_started = False
            broadcast_state()
            return

        # Automatic Last Card Trigger Check
        if len(game.hands.get(sid, [])) == 1:
            socketio.emit('game_log', {'msg': f"📢 🔥 LAST CARD! {p_name} is down to their final card!"}, room='game_room')
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
    if sid != game.get_current_player_sid():
        return
    chosen_suit = data.get('suit')
    game.declared_ace_suit = chosen_suit
    p_name = game.player_names.get(sid, "Unknown")
    
    socketio.emit('game_log', {'msg': f"🔮 {p_name} set the active game suit to: {chosen_suit}!"}, room='game_room')
    socketio.emit('play_sound', {'type': 'play'}, room='game_room')
    game.advance_turn()
    broadcast_state()

@socketio.on('queen_cascade')
def handle_cascade(data):
    sid = request.sid
    suit = data.get('suit')
    p_name = game.player_names.get(sid, "Unknown")
    success, msg = game.execute_queen_cascade(sid, suit)
    if success:
        socketio.emit('game_log', {'msg': f"👑 {p_name} executed a Queen Cascade on {suit}!"}, room='game_room')
        socketio.emit('play_sound', {'type': 'play'}, room='game_room')
        
        if len(game.hands.get(sid, [])) == 0:
            game.update_league_results(sid)
            socketio.emit('game_over', {'winner': p_name}, room='game_room')
            socketio.emit('play_sound', {'type': 'victory'}, room='game_room')
            game.is_started = False
        else:
            if len(game.hands.get(sid, [])) == 1:
                socketio.emit('game_log', {'msg': f"📢 🔥 LAST CARD! {p_name} is down to their final card!"}, room='game_room')
            game.advance_turn()
        broadcast_state()
    else:
        emit('error', {'msg': msg})

@socketio.on('take_penalty_or_draw')
def handle_draw():
    sid = request.sid
    if sid != game.get_current_player_sid():
        emit('error', {'msg': "Not your turn."})
        return

    p_name = game.player_names.get(sid, "Unknown")
    socketio.emit('play_sound', {'type': 'draw'}, to=sid)
    if game.accumulated_penalty > 0:
        socketio.emit('game_log', {'msg': f"🏳️ {p_name} accepted the penalty and drew {game.accumulated_penalty} cards."}, room='game_room')
        game.draw_card(sid, game.accumulated_penalty)
        game.accumulated_penalty = 0
        game.active_penalty_type = None
    else:
        socketio.emit('game_log', {'msg': f"🎴 {p_name} drew a single card."}, room='game_room')
        game.draw_card(sid, 1)

    game.advance_turn()
    broadcast_state()

def broadcast_state():
    active_suit = game.declared_ace_suit
    if not active_suit and game.discard_pile:
        active_suit = game.discard_pile[-1]['suit']

    # Package league scores object list format
    scoreboards = []
    for name in game.league_wins.keys():
        scoreboards.append({
            'name': name,
            'wins': game.league_wins.get(name, 0),
            'losses': game.league_losses.get(name, 0)
        })
    scoreboards.sort(key=lambda x: x['wins'], reverse=True)

    state = {
        'is_started': game.is_started,
        'top_card': game.discard_pile[-1] if game.discard_pile else None,
        'active_suit': active_suit,
        'current_player': game.player_names.get(game.get_current_player_sid()) if game.is_started else None,
        'current_player_sid': game.get_current_player_sid() if game.is_started else None,
        'penalty': game.accumulated_penalty,
        'penalty_type': game.active_penalty_type,
        'player_list': [game.player_names[p] for p in game.players],
        'hand_sizes': {game.player_names[p]: len(game.hands[p]) for p in game.players if p in game.hands},
        'league_table': scoreboards
    }
    socketio.emit('state_update', state, room='game_room')
    for pid in game.players:
        hand = game.hands.get(pid, [])
        socketio.emit('your_hand', {'hand': hand}, to=pid)

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
