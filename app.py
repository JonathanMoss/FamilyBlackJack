"""Family Blackjack Engine Flask App.

A WebSocket-driven card game engine handling room loops, penalty handling,
and career stats persistence.
"""

import random
# pylint: disable=import-error
from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'blackjack_family_secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

BOT_NAME = "🤖 Computer"


# pylint: disable=too-many-instance-attributes
class FamilyBlackjackEngine:
    """Core state machine managing players, card decks, and gameplay rounds."""

    def __init__(self):
        """Initialize defaults for a fresh blackjack lobby."""
        self.players = []          # Ordered list of Unique Usernames
        self.sid_to_name = {}      # Maps active connection request.sid -> Name
        self.name_to_sid = {}      # Maps Username -> active connection sid
        self.hands = {}            # Maps Username -> Card Array
        self.deck = []
        self.discard_pile = []
        self.current_turn_index = 0
        self.direction = 1
        self.is_started = False

        # Rotational Dealer Tracking Variable
        self.match_dealer_index = -1  # Increments to 0 on match setup

        # Penalty & Wildcard Tracking
        self.active_penalty_type = None
        self.accumulated_penalty = 0
        self.declared_ace_suit = None

        # Career League Standings Data
        self.league_wins = {}
        self.league_losses = {}
        # Track which player caused the current accumulated penalty (if any)
        self.penalty_source = None

    def reset_lobby(self):
        """Reset the match room engine back to baseline factory defaults."""
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
        self.penalty_source = None
        # Note: We intentionally DO NOT clear league_wins or league_losses
        # so career family stats persist across separate game room lobbies!

    def reset_match(self):
        """Reset only the active match state but keep lobby players and career stats.

        This preserves `players`, `league_wins`, and `league_losses` so the
        room roster and career table remain intact while clearing the current
        match (hands, deck, discard pile, penalties, and started flag).
        """
        self.deck = []
        self.discard_pile = []
        self.hands = {name: [] for name in self.players}
        self.current_turn_index = 0
        self.direction = 1
        self.is_started = False
        self.active_penalty_type = None
        self.accumulated_penalty = 0
        self.declared_ace_suit = None
        self.penalty_source = None

    def build_deck(self):  # pylint: disable=no-self-use
        """Construct a fresh 52-card deck array and shuffle it.

        Returns:
            list: A list of card dictionaries containing 'suit' and 'value'.
        """
        suits = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
        values = [
            '2', '3', '4', '5', '6', '7', '8', '9', '10',
            'Jack', 'Queen', 'King', 'Ace'
        ]
        deck = [
            {'suit': suit, 'value': value}
            for suit in suits for value in values
        ]
        random.shuffle(deck)
        return deck

    def register_league_player(self, name):
        """Initialize tracking keys for league players if not already present.

        Args:
            name (str): The unique profile username.
        """
        if name not in self.league_wins:
            self.league_wins[name] = 0
        if name not in self.league_losses:
            self.league_losses[name] = 0

    def add_player(self, name):
        """Register a new player in the lobby and manage bot yield logic."""
        if name not in self.players:
            self.players.append(name)
            self.hands[name] = []

            # If the lobby is idle and we now have multiple humans, remove the bot
            if not self.is_started:
                human_players = [p for p in self.players if p != BOT_NAME]
                if len(human_players) >= 2 and BOT_NAME in self.players:
                    self.players.remove(BOT_NAME)
                    return True
        return False

    def start_game(self):
        """Boot up a brand new card round from the active lobby.

        Returns:
            bool: True if game initialization succeeds, False otherwise.
        """
        # Clean up computer player if we have enough human players
        human_players = [p for p in self.players if p != BOT_NAME]
        if len(human_players) >= 2 and BOT_NAME in self.players:
            self.players.remove(BOT_NAME)
            socketio.emit('game_log', {'msg': f"{BOT_NAME} has left the table to make room for humans."}, room='game_room')

        # Automatically add a computer player if someone starts alone
        if len(self.players) == 1:
            if BOT_NAME not in self.players:
                self.players.append(BOT_NAME)

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
        self.penalty_source = None

        # --- ROTATION LOGIC ---
        # Update dealer and starting turn BEFORE checking for specialty starter cards
        self.match_dealer_index = (self.match_dealer_index + 1) % len(self.players)
        self.current_turn_index = (self.match_dealer_index + 1) % len(self.players)

        self.is_started = True
        self._skip_spectators()

        if starter['value'] == '2':
            self.active_penalty_type = '2'
            self.accumulated_penalty = 2
        elif starter['value'] == 'Jack' and starter['suit'] in ['Clubs', 'Spades']:
            self.active_penalty_type = 'BJ'
            self.accumulated_penalty = 5
        elif starter['value'] == '8':
            # Skip the first active player
            self.advance_turn(steps=1)
            return True

        self.check_and_enforce_autodraw()
        return True

    def get_current_player_name(self):
        """Identify the active user who owns the current game choice authority.

        Returns:
            str or None: Username of active player or None.
        """
        return self.players[self.current_turn_index] if self.players else None

    def _skip_spectators(self):
        """Helper to ensure current_turn_index points to an active player with cards."""
        if not self.players or not self.is_started:
            return
        attempts = 0
        while (not self.hands.get(self.players[self.current_turn_index]) and 
               attempts < len(self.players)):
            self.current_turn_index = (self.current_turn_index + self.direction) % len(self.players)
            attempts += 1

    def advance_turn(self, steps=1):
        """Pass turn control down the user tracking registry, skipping spectators."""
        if not self.players:
            return
        for _ in range(steps):
            self.current_turn_index = (self.current_turn_index + self.direction) % len(self.players)
            self._skip_spectators()
        self.check_and_enforce_autodraw()

    def has_valid_penalty_counter(self, name):
        """Assess if the player's profile has counter cards for active penalties.

        Args:
            name (str): Target player name.

        Returns:
            bool: True if counter is valid or no penalty exists, False otherwise.
        """
        if self.accumulated_penalty == 0:
            return True
        hand = self.hands.get(name, [])
        if self.active_penalty_type == '2':
            return any(card['value'] == '2' for card in hand)
        if self.active_penalty_type == 'BJ':
            return any(card['value'] == 'Jack' for card in hand)
        return False

    def check_and_enforce_autodraw(self):
        """Evaluate penalty counters; trigger card drawings for undefended states."""
        if not self.is_started or self.accumulated_penalty == 0:
            return

        current_name = self.get_current_player_name()
        if not self.has_valid_penalty_counter(current_name):
            self.draw_card(current_name, self.accumulated_penalty, reason='penalty_auto')
            log_msg = (
                f"💥 {current_name} had no defence cards "
                f"and auto-drew {self.accumulated_penalty} cards!"
            )
            if getattr(self, 'penalty_source', None):
                log_msg += f" (caused by {self.penalty_source})"
            socketio.emit(
                'game_log', {'msg': log_msg}, room='game_room'
            )

            target_sid = self.name_to_sid.get(current_name)
            if target_sid:
                socketio.emit('play_sound', {'type': 'penalty'}, to=target_sid)

            self.accumulated_penalty = 0
            self.active_penalty_type = None
            self.penalty_source = None

            self.advance_turn(steps=1)

    def draw_card(self, name, count=1, reason=None):
        """Move card units safely from the deck entity to a player's hand array.

        Args:
            name (str): Target username recipient.
            count (int): Amount of cards to pop.

        Returns:
            list: Parsed collection of pop values captured.
        """
        drawn = []
        for _ in range(count):
            if not self.deck:
                if len(self.discard_pile) > 1:
                    top_card = self.discard_pile.pop()
                    self.deck = self.discard_pile.copy()
                    self.discard_pile = [top_card]
                    msg_txt = (
                        "🔄 The draw pile ran out! The discard pile has "
                        "been flipped over into the deck (Order Maintained)."
                    )
                    socketio.emit(
                        'game_log', {'msg': msg_txt}, room='game_room'
                    )
                else:
                    break
            if self.deck:
                drawn.append(self.deck.pop())
        if name in self.hands:
            self.hands[name].extend(drawn)
        # Notify the receiving player's client about the drawn cards
        if drawn:
            target_sid = self.name_to_sid.get(name)
            payload = {'count': len(drawn), 'cards': drawn, 'reason': reason}
            # include penalty source if applicable
            if reason and 'penalty' in (reason or ''):
                payload['source'] = getattr(self, 'penalty_source', None)
            if target_sid:
                socketio.emit('received_cards', payload, to=target_sid)
        return drawn

    def update_league_results(self, winner_name):
        """Append win statistics to the winner and increment losses for the rest.

        Args:
            winner_name (str): Target identity of the round victor.
        """
        self.register_league_player(winner_name)
        self.league_wins[winner_name] += 1

        for name in self.players:
            if name != winner_name:
                self.register_league_player(name)
                self.league_losses[name] += 1

    def _calculate_penalty_update(self, card, current_type, current_accumulated, player_name):
        """Helper to determine the new penalty state after playing a card.

        Returns:
            tuple: (new_penalty_type, new_accumulated_penalty, new_penalty_source)
        """
        new_type = current_type
        new_accumulated = current_accumulated
        new_source = self.penalty_source

        if card['value'] == '2':
            new_accumulated = new_accumulated + 2 if current_type == '2' else 2
            new_type = '2'
            new_source = player_name
        elif card['value'] == 'Jack' and card['suit'] in ['Spades', 'Clubs']:
            new_accumulated = new_accumulated + 5 if current_type == 'BJ' else 5
            new_type = 'BJ'
            new_source = player_name
        elif (
            card['value'] == 'Jack' and
            card['suit'] in ['Hearts', 'Diamonds'] and
            current_type == 'BJ'
        ):
            new_type = None
            new_accumulated = 0
            new_source = None

        return new_type, new_accumulated, new_source

    # pylint: disable=too-many-locals,too-many-return-statements,too-many-branches,too-many-statements
    def validate_and_play_move(self, name, selected_cards):
        """Process legal game plays against rules and active penalties.

        Args:
            name (str): Player validation context.
            selected_cards (list): Payload listing cards to discard.

        Returns:
            tuple: (bool: success status, str: outcome logs, int: skip metrics)
        """
        if name != self.get_current_player_name() or not selected_cards:
            return False, "Not your turn or no cards selected.", 0

        player_hand = self.hands[name]

        matched_cards = []
        for sel_card in selected_cards:
            found = next(
                (card for card in player_hand if
                 card['value'] == sel_card['value'] and
                 card['suit'] == sel_card['suit'] and
                 card not in matched_cards),
                None
            )
            if not found:
                err_msg = (
                    f"Card ({sel_card['value']} of {sel_card['suit']}) "
                    f"not found in your hand."
                )
                return False, err_msg, 0
            matched_cards.append(found)

        top_card = self.discard_pile[-1]
        is_ace_active = self.declared_ace_suit and top_card['value'] == 'Ace'
        is_table_queen = top_card['value'] == 'Queen'
        active_suit = self.declared_ace_suit if is_ace_active else top_card['suit']
        active_val = top_card['value']

        # Pre-calculate intended penalty enforcement.
        last_card = matched_cards[-1]
        last_is_bj = (last_card['value'] == 'Jack' and last_card['suit'] in ['Spades', 'Clubs'])
        last_is_rj = (last_card['value'] == 'Jack' and last_card['suit'] in ['Hearts', 'Diamonds'])
        last_is_two = (last_card['value'] == '2')

        if self.accumulated_penalty > 0:
            if self.active_penalty_type == '2' and not last_is_two:
                return False, "Your last card must be a 2 to counter the penalty!", 0
            if self.active_penalty_type == 'BJ' and not (last_is_bj or last_is_rj):
                return False, "Your final card must be a Jack to counter the penalty!", 0

        temp_penalty_type = self.active_penalty_type
        temp_accumulated = self.accumulated_penalty
        first_card = matched_cards[0]

        is_valid_match = (
            first_card['suit'] == active_suit or
            first_card['value'] == active_val or
            first_card['value'] == 'Ace'
        )
        if not is_valid_match:
            err_msg = (
                f"First card must be a ({active_suit}) "
                f"or value ({active_val})."
            )
            return False, err_msg, 0

        eight_skips = 0
        first_chain_card = matched_cards[0]
        # Determine if we are in a "Queen Dump" state (either started by this play or the table)
        is_dump_active = first_chain_card['value'] == 'Queen' or is_table_queen
        dump_suit = first_chain_card['suit'] if first_chain_card['value'] == 'Queen' else active_suit

        for card_idx, card in enumerate(matched_cards):
            if card_idx > 0:
                prev_card = matched_cards[card_idx - 1]
                
                # A card is valid in a chain if:
                # 1. It matches the rank of the previous card
                # 2. It matches the suit of the previous card
                # 3. It is an Ace (wildcard)
                # 4. It matches the suit of the Queen dump
                is_same_rank = card['value'] == prev_card['value']
                is_same_suit = card['suit'] == prev_card['suit']
                is_ace = card['value'] == 'Ace'
                is_suit_chain = is_dump_active and card['suit'] == dump_suit

                is_chain_valid = is_same_rank or is_same_suit or is_ace or is_suit_chain
                if not is_chain_valid:
                    return False, "Chain invalid: subsequent cards must match rank, suit, be an Ace, or follow a Queen dump.", 0

            if card['value'] == '8':
                eight_skips += 1

            # Accumulate penalties for every card in the chain using the helper
            (temp_penalty_type,
             temp_accumulated,
             self.penalty_source) = self._calculate_penalty_update(
                 card, temp_penalty_type, temp_accumulated, name
             )

        self.active_penalty_type = temp_penalty_type
        self.accumulated_penalty = temp_accumulated
        self.declared_ace_suit = None

        for card in matched_cards:
            player_hand.remove(card)
            self.discard_pile.append(card)

        return True, "Success", eight_skips

    def execute_queen_cascade(self, name, suit_to_dump):
        """Discard all cards matching a target suit following a Queen play.

        Args:
            name (str): Player username validation identifier.
            suit_to_dump (str): Target card suit to purge.

        Returns:
        tuple: (bool success status, str outcome message, int skips)
        """
        if name != self.get_current_player_name():
            return False, "Not your turn.", 0
        if not self.discard_pile or self.discard_pile[-1]['value'] != 'Queen':
            return False, "Top card is not a Queen.", 0

        player_hand = self.hands[name]
        cards_to_dump = [
            card for card in player_hand if card['suit'] == suit_to_dump
        ]

        if not cards_to_dump:
            return True, "No cards of that suit to dump.", 0

        skips = 0
        for card in cards_to_dump:
            player_hand.remove(card)
            self.discard_pile.append(card)

            # Update penalty state for every card dumped
            (self.active_penalty_type,
             self.accumulated_penalty,
             self.penalty_source) = self._calculate_penalty_update(
                 card, self.active_penalty_type, self.accumulated_penalty, name
             )
            if card['value'] == '8':
                skips += 1
        return True, f"Dumped {len(cards_to_dump)} cards.", skips


# Global instances tracking core system state mechanics
game = FamilyBlackjackEngine()


@app.route('/')
def index():
    """Render application baseline index template layout.

    Returns:
        str: HTML compilation result payload.
    """
    return render_template('index.html')


@app.route('/logout')
def logout():
    """Clear session cookie and redirect to index."""
    session.clear()
    return redirect(url_for('index'))


@socketio.on('join_game')
def handle_join(data):
    """Handle connection routing for entry registration tasks."""
    sid = request.sid
    name = data.get('name', '').strip()
    if not name:
        return emit('error', {'msg': 'Name cannot be blank.'})

    session['username'] = name

    if name not in game.players:
        was_started = game.is_started
        bot_yielded = game.add_player(name)
        if was_started:
            socketio.emit('game_log', 
                         {'msg': f"👁️ {name} joined as an observer and will play in the next match."}, room='game_room')
        elif bot_yielded:
            socketio.emit('game_log', {'msg': f"{BOT_NAME} has left the table to make room for humans."}, room='game_room')

    game.sid_to_name[sid] = name
    game.name_to_sid[name] = sid

    join_room('game_room')
    broadcast_state()
    return None


def check_for_bot_turn():
    """Determine if the current turn belongs to the computer and trigger AI logic."""
    if not game.is_started:
        return
    current_player = game.get_current_player_name()
    if current_player == BOT_NAME:
        socketio.start_background_task(run_bot_logic)


def run_bot_logic():
    """Background task simulating computer thinking and decision making."""
    socketio.sleep(1.5)  # Artificial delay for natural feel

    if not game.is_started or game.get_current_player_name() != BOT_NAME:
        return

    # 1. Handle Ace Suit Declaration if the bot just played an Ace but hasn't declared
    top_card = game.discard_pile[-1]
    if top_card['value'] == 'Ace' and not game.declared_ace_suit:
        hand = game.hands.get(BOT_NAME, [])
        if not hand:
            chosen_suit = "Spades"
        else:
            suits = [c['suit'] for c in hand]
            chosen_suit = max(set(suits), key=suits.count)
        
        game.declared_ace_suit = chosen_suit
        socketio.emit('game_log', {'msg': f"🔮 {BOT_NAME} set the active game suit to: {chosen_suit}!"}, room='game_room')
        game.advance_turn()
        broadcast_state()
        check_for_bot_turn()
        return

    # 2. Decide on a move
    hand = game.hands.get(BOT_NAME, [])
    possible_play = None
    
    # Check for penalty counters specifically
    if game.accumulated_penalty > 0:
        if game.active_penalty_type == '2':
            matches = [c for c in hand if c['value'] == '2']
        else:
            matches = [c for c in hand if c['value'] == 'Jack']
        if matches:
            possible_play = [matches[0]]
    else:
        # Regular turn logic
        active_suit = game.declared_ace_suit if (game.declared_ace_suit and top_card['value'] == 'Ace') else top_card['suit']
        active_val = top_card['value']
        for c in hand:
            if c['value'] == 'Ace' or c['value'] == active_val or c['suit'] == active_suit:
                possible_play = [c]
                break

    if possible_play:
        success, msg, skips = game.validate_and_play_move(BOT_NAME, possible_play)
        if success:
            socketio.emit('game_log', {'msg': f"📝 {BOT_NAME} played: {possible_play[0]['value']} of {possible_play[0]['suit']}"}, room='game_room')
            
            if len(game.hands.get(BOT_NAME, [])) == 0:
                game.update_league_results(BOT_NAME)
                game.is_started = False
                socketio.emit('game_over', {'winner': BOT_NAME}, room='game_room')
                broadcast_state()
                return

            if len(game.hands.get(BOT_NAME, [])) == 1:
                socketio.emit('game_log', {'msg': f"📢 🔥 LAST CARD! {BOT_NAME} is down to their final card!"}, room='game_room')

            game.advance_turn(steps=1 + skips)
    else:
        # Must draw
        if game.accumulated_penalty > 0:
            socketio.emit('game_log', {'msg': f"🏳️ {BOT_NAME} accepted the penalty and drew {game.accumulated_penalty} cards."}, room='game_room')
            game.draw_card(BOT_NAME, game.accumulated_penalty, reason='penalty_manual')
            game.accumulated_penalty = 0
            game.active_penalty_type = None
        else:
            socketio.emit('game_log', {'msg': f"🎴 {BOT_NAME} drew a card."}, room='game_room')
            game.draw_card(BOT_NAME, 1, reason='draw')
        game.advance_turn()

    broadcast_state()
    check_for_bot_turn()


@socketio.on('start_match')
def handle_start():
    """Transition state parameters to live round execution modes."""
    if game.start_game():
        dealer_name = game.players[game.match_dealer_index]
        starter_name = game.get_current_player_name()

        socketio.emit(
            'game_log',
            {'msg': "🔀 Shuffling the deck... Creating a fresh setup!"},
            room='game_room'
        )
        log_msg = (
            f"🃏 Dealer for this hand: <b>{dealer_name}</b>. "
            f"Action starts with <b>{starter_name}</b>!"
        )
        socketio.emit(
            'game_log',
            {'msg': log_msg},
            room='game_room'
        )
        socketio.emit('play_sound', {'type': 'shuffle'}, room='game_room')

        first_card = game.discard_pile[-1]
        if first_card['value'] == 'Ace':
            starter_sid = game.name_to_sid.get(starter_name)
            if starter_sid:
                socketio.emit('prompt_ace_suit', {}, to=starter_sid)
            ace_msg = (
                f"🔮 The first card is an Ace! {starter_name} "
                "must declare the active suit."
            )
            socketio.emit(
                'game_log',
                {'msg': ace_msg},
                room='game_room'
            )
        elif game.active_penalty_type == '2':
            two_msg = f"⚠️ The first card is a 2! {starter_name} must counter it or draw +2 cards."
            socketio.emit(
                'game_log',
                {'msg': two_msg},
                room='game_room'
            )
        elif game.active_penalty_type == 'BJ':
            bj_msg = f"⚠️ Black Jack! {starter_name} must counter or draw +5."
            socketio.emit(
                'game_log',
                {'msg': bj_msg},
                room='game_room'
            )
        elif first_card['value'] == '8':
            skipped_name = game.players[(game.match_dealer_index + 1) % len(game.players)]
            eight_msg = (
                f"🛑 The first card is an 8! {skipped_name} misses a turn. "
                f"Action starts with {starter_name}!"
            )
            socketio.emit('game_log', {'msg': eight_msg}, room='game_room')

        broadcast_state()
        check_for_bot_turn()
    else:
        emit('error', {'msg': 'Need at least 2 players to start!'})


@socketio.on('play_cards')
def handle_play(data):
    """Process incoming discard execution actions."""
    sid = request.sid
    name = game.sid_to_name.get(sid)
    if not name or name != game.get_current_player_name():
        return emit('error', {'msg': "It is not your turn!"})

    cards = data.get('cards', [])
    success, msg, skips = game.validate_and_play_move(name, cards)
    if success:
        cards_desc = ", ".join(
            [f"{card['value']} of {card['suit']}" for card in cards]
        )
        socketio.emit(
            'game_log',
            {'msg': f"📝 {name} played a chain: {cards_desc}"},
            room='game_room'
        )

        # 🏁 CRITICAL FIX: VICTORY POSITION CLEANUP
        if len(game.hands.get(name, [])) == 0:
            game.update_league_results(name)

            game.is_started = False
            game.accumulated_penalty = 0
            game.active_penalty_type = None
            game.declared_ace_suit = None
            game.penalty_source = None

            socketio.emit('game_over', {'winner': name}, room='game_room')
            socketio.emit('play_sound', {'type': 'victory'}, room='game_room')
            broadcast_state()
            return None

        if len(game.hands.get(name, [])) == 1:
            last_card_msg = (
                f"📢 🔥 LAST CARD! {name} is down to their final card!"
            )
            socketio.emit(
                'game_log', {'msg': last_card_msg}, room='game_room'
            )
            socketio.emit('play_sound', {'type': 'penalty'}, room='game_room')

        socketio.emit('play_sound', {'type': 'play'}, room='game_room')

        if cards[-1]['value'] == 'Ace':
            emit('prompt_ace_suit', {}, to=sid)
            broadcast_state()
        else:
            turn_steps = 1
            if skips > 0:
                turn_steps += skips
                skip_msg = (
                    f"skip 🛑 {skips} player(s) skipped by the 8 "
                    f"power card sequence!"
                )
                socketio.emit(
                    'game_log', {'msg': skip_msg}, room='game_room'
                )

            is_penalty_chain = cards[-1]['value'] in ['2', 'Jack']
            if game.accumulated_penalty == 0 or is_penalty_chain:
                game.advance_turn(steps=turn_steps)
            broadcast_state()
            check_for_bot_turn()
    else:
        emit('error', {'msg': msg})
    return None


@socketio.on('declare_ace_suit')
def handle_ace_suit(data):
    """Assign wildcard suit constraints following Ace plays."""
    sid = request.sid
    name = game.sid_to_name.get(sid)
    if not name or name != game.get_current_player_name():
        return
    chosen_suit = data.get('suit')
    game.declared_ace_suit = chosen_suit

    socketio.emit(
        'game_log',
        {'msg': f"🔮 {name} set the active game suit to: {chosen_suit}!"},
        room='game_room'
    )
    socketio.emit('play_sound', {'type': 'play'}, room='game_room')
    game.advance_turn()
    broadcast_state()
    check_for_bot_turn()


@socketio.on('reset_match')
def handle_reset_match():
    """Reset only the active match while preserving lobby roster and career stats."""
    sid = request.sid
    requester = game.sid_to_name.get(sid)
    if not requester:
        emit('error', {'msg': 'You must be in the lobby to reset the match.'})
        return

    game.reset_match()
    socketio.emit('game_log', {'msg': f"🧹 {requester} reset the current match."}, room='game_room')
    socketio.emit('room_reset', {'msg': 'Match has been reset by a player.'}, room='game_room')
    broadcast_state()


@socketio.on('queen_cascade')
def handle_cascade(data):
    """Execute sequence cleanouts on active Queen states."""
    sid = request.sid
    name = game.sid_to_name.get(sid)
    if not name or name != game.get_current_player_name():
        return
    suit = data.get('suit')
    success, msg, skips = game.execute_queen_cascade(name, suit)
    if success:
        log_msg = f"👑 {name} executed a Queen Cascade on {suit}!"
        socketio.emit(
            'game_log', {'msg': log_msg}, room='game_room'
        )
        socketio.emit('play_sound', {'type': 'play'}, room='game_room')

        if len(game.hands.get(name, [])) == 0:
            game.update_league_results(name)
            game.is_started = False
            game.accumulated_penalty = 0
            game.active_penalty_type = None
            game.declared_ace_suit = None
            game.penalty_source = None

            socketio.emit('game_over', {'winner': name}, room='game_room')
            socketio.emit('play_sound', {'type': 'victory'}, room='game_room')
        else:
            if len(game.hands.get(name, [])) == 1:
                last_card_msg = (
                    f"📢 🔥 LAST CARD! {name} is down to their final card!"
                )
                socketio.emit(
                    'game_log', {'msg': last_card_msg}, room='game_room'
                )

            turn_steps = 1 + skips
            if skips > 0:
                skip_msg = f"skip 🛑 {skips} player(s) skipped by cascaded 8s!"
                socketio.emit('game_log', {'msg': skip_msg}, room='game_room')

            game.advance_turn(steps=turn_steps)
        broadcast_state()
        check_for_bot_turn()
    else:
        emit('error', {'msg': msg})


@socketio.on('take_penalty_or_draw')
def handle_draw():
    """Draw a card manually or accept the accumulated stack penalty."""
    sid = request.sid
    name = game.sid_to_name.get(sid)
    if not name or name != game.get_current_player_name():
        emit('error', {'msg': "Not your turn."})
        return

    socketio.emit('play_sound', {'type': 'draw'}, to=sid)
    if game.accumulated_penalty > 0:
        log_msg = (
            f"🏳️ {name} accepted the penalty and "
            f"drew {game.accumulated_penalty} cards."
        )
        if getattr(game, 'penalty_source', None):
            log_msg += f" (caused by {game.penalty_source})"
        socketio.emit(
            'game_log', {'msg': log_msg}, room='game_room'
        )
        game.draw_card(name, game.accumulated_penalty, reason='penalty_manual')
        game.accumulated_penalty = 0
        game.active_penalty_type = None
        game.penalty_source = None
    else:
        socketio.emit(
            'game_log',
            {'msg': f"🎴 {name} drew a single card."},
            room='game_room'
        )
        game.draw_card(name, 1, reason='draw')

    game.advance_turn()
    broadcast_state()
    check_for_bot_turn()


@socketio.on('send_nudge')
def handle_nudge(data):
    """Pass connection message nudge payloads to specific players."""
    sid = request.sid
    sender_name = game.sid_to_name.get(sid, "Someone")
    target_name = data.get('target')
    emoji = data.get('emoji', '👋')
    if target_name not in game.players:
        return
    log_msg = f"💥 {sender_name} sent a nudge to {target_name}: {emoji}"
    socketio.emit(
        'game_log', {'msg': log_msg}, room='game_room'
    )
    target_sid = game.name_to_sid.get(target_name)
    if target_sid:
        socketio.emit(
            'receive_nudge',
            {'sender': sender_name, 'emoji': emoji},
            to=target_sid
        )


@socketio.on('disconnect')
def handle_disconnect():
    """Disconnect cleanup routing when a user connection falls offline."""
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
                socketio.emit(
                    'game_log',
                    {'msg': f"❌ {name} left the lobby."},
                    room='game_room'
                )
            else:
                socketio.emit(
                    'game_log',
                    {'msg': f"🔌 {name} disconnected (Went Offline)."},
                    room='game_room'
                )

        if len(game.sid_to_name) == 0:
            print("🚨 LOBBY EMPTY DETECTED: Automated room reset executed.")
            game.reset_lobby()
            socketio.emit(
                'game_log',
                {'msg': "🧹 Room automatically reset because all players left."},
                room='game_room'
            )

        broadcast_state()


def broadcast_state():
    """Transmit a synchronized payload package containing global configurations."""
    active_suit = game.declared_ace_suit
    if not active_suit and game.discard_pile:
        active_suit = game.discard_pile[-1]['suit']

    # Determine the top card to display. If the lobby is idle (no game started and no pile),
    # we show a decorative Ace of Spades placeholder.
    if not game.discard_pile and not game.is_started:
        top_card = {'suit': 'Spades', 'value': 'Ace'}
        active_suit = 'Spades'
    else:
        top_card = game.discard_pile[-1] if game.discard_pile else None

    scoreboards = []
    for u_name in game.league_wins:
        scoreboards.append({
            'name': u_name,
            'wins': game.league_wins.get(u_name, 0),
            'losses': game.league_losses.get(u_name, 0)
        })
    scoreboards.sort(key=lambda x: x['wins'], reverse=True)

    current_player = game.get_current_player_name()
    current_sid = (
        game.name_to_sid.get(current_player) if current_player else None
    )

    state = {
        'is_started': game.is_started,
        'top_card': top_card,
        'active_suit': active_suit,
        'current_player': current_player,
        'current_player_sid': current_sid,
        'penalty': game.accumulated_penalty,
        'penalty_type': game.active_penalty_type,
        'player_list': game.players,
        'hand_sizes': {
            p: len(game.hands[p]) for p in game.players if p in game.hands
        },
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
