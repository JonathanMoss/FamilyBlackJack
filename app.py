"""Family Blackjack Engine Flask App.

A WebSocket-driven card game engine handling room loops, penalty handling,
and career stats persistence.
"""
# pylint: disable=too-many-public-methods,too-many-instance-attributes,too-few-public-methods
# pylint: disable=too-many-lines, invalid-name, too-many-locals, too-many-branches, too-many-statements
# pylint: disable=inconsistent-return-statements

import random
import time
# pylint: disable=import-error
from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.config['SECRET_KEY'] = 'blackjack_family_secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

BOT_NAME = "🤖 Computer"
BOT_ROSTER = [
    "🤖 HAL 9000", "🤖 The Architect", "🤖 KITT", "🤖 V'ger",
    "🤖 Ash", "🤖 R2-D2", "🤖 C3-PO"
]


# pylint: disable=too-many-instance-attributes
class FamilyBlackjackEngine:
    """Core state machine managing players, card decks, and gameplay rounds."""

    def __init__(self, turn_timeout=30.0):
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
        
        self.turn_timeout = turn_timeout
        self.host_name = None

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

        self.match_stats = {}
        self.current_turn_start_time = 0.0
        self.avatars = {}
        self.jokers_available = {}
        self.joker_cooldown = 0

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
        self.match_stats = {}
        self.current_turn_start_time = 0.0
        self.avatars = {}
        self.jokers_available = {}
        self.joker_cooldown = 0
        self.host_name = None
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
        self.match_stats = {}
        self.current_turn_start_time = 0.0
        self.jokers_available = {}
        self.joker_cooldown = 0
        self.host_name = None

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
        if name.startswith('🤖'):
            return
        if name not in self.league_wins:
            self.league_wins[name] = 0
        if name not in self.league_losses:
            self.league_losses[name] = 0

    def add_player(self, name):
        """Register a new player in the lobby and manage bot yield logic."""
        if name not in self.players:
            self.players.append(name)
            self.hands[name] = []
            if name not in self.avatars:
                self.avatars[name] = '🤖' if name.startswith('🤖') else '👤'

            # If the lobby is idle and we now have multiple humans, remove the bot
            if not self.is_started:
                human_players = [p for p in self.players if not p.startswith('🤖')]
                if len(human_players) >= 2 and BOT_NAME in self.players:
                    self.players.remove(BOT_NAME)
                    return True
        return False

    def clear_bots_if_humans(self):
        """Remove bot players from the lobby if any human players are present."""
        humans = [p for p in self.players if not p.startswith('🤖')]
        if humans:
            bots = [p for p in self.players if p.startswith('🤖')]
            for bot in bots:
                self.players.remove(bot)
                if bot in self.hands:
                    del self.hands[bot]
            if self.players:
                self.current_turn_index %= len(self.players)

    def start_game(self):
        """Boot up a brand new card round from the active lobby.

        Returns:
            bool: True if game initialization succeeds, False otherwise.
        """
        # Clean up computer player if we have enough human players
        human_players = [p for p in self.players if not p.startswith('🤖')]
        if len(human_players) >= 2 and BOT_NAME in self.players:
            self.players.remove(BOT_NAME)
            socketio.emit('game_log', {'msg': f"{BOT_NAME} has shutdown!"}, room='game_room')

        # Automatically add a computer player if someone starts alone
        if len(self.players) == 1:
            if BOT_NAME not in self.players:
                self.players.append(BOT_NAME)
                self.avatars[BOT_NAME] = '🤖'

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

        self.match_stats = {
            p: {
                'cards_played': 0,
                'turn_time_total': 0.0,
                'turn_count': 0,
                'nudges_sent': 0,
                'penalties_received': 0,
                'power_cards_played': 0
            } for p in self.players
        }
        self.current_turn_start_time = time.time()
        self.jokers_available = {p: True for p in self.players}
        self.joker_cooldown = 0

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
        if not self.players:
            return None
        return self.players[self.current_turn_index % len(self.players)]

    def _skip_spectators(self):
        """Helper to ensure current_turn_index points to an active player with cards."""
        if not self.players or not self.is_started:
            return
        self.current_turn_index %= len(self.players)
        attempts = 0
        while (not self.hands.get(self.players[self.current_turn_index]) and
               attempts < len(self.players)):
            # In BDD tests, if all active players hit 0 cards, prevent an infinite skip loop
            if attempts >= len(self.players):
                break
            self.current_turn_index = (self.current_turn_index + self.direction) % len(self.players)
            attempts += 1

    def advance_turn(self, steps=1):
        """Pass turn control down the user tracking registry, skipping spectators."""
        if not self.players:
            return

        current_p = self.get_current_player_name()
        if self.is_started and getattr(self, 'match_stats', None) and current_p in self.match_stats:
            elapsed = time.time() - self.current_turn_start_time
            self.match_stats[current_p]['turn_time_total'] += elapsed
            self.match_stats[current_p]['turn_count'] += 1

        for _ in range(steps):
            self.current_turn_index = (self.current_turn_index + self.direction) % len(self.players)
            self._skip_spectators()
            if getattr(self, 'joker_cooldown', 0) > 0:
                self.joker_cooldown -= 1

        self.current_turn_start_time = time.time()
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

        # Let the bot logic handle its own auto-draw with a natural delay
        if current_name and current_name.startswith('🤖'):
            return

        if not self.has_valid_penalty_counter(current_name):
            self.draw_card(current_name, self.accumulated_penalty, reason='penalty_auto')
            log_msg = (
                f"💥 {current_name} had no defence cards "
                f"and drew {self.accumulated_penalty} cards!"
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
                        "been flipped."
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

        if name in getattr(self, 'match_stats', {}):
            if reason and 'penalty' in reason:
                self.match_stats[name]['penalties_received'] += len(drawn)

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
        if not winner_name.startswith('🤖'):
            self.league_wins[winner_name] += 1

        for name in self.players:
            if name != winner_name:
                self.register_league_player(name)
                if not name.startswith('🤖'):
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
                    f"not found in your hand!"
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
                return False, "Your last card must be a 2!", 0
            if self.active_penalty_type == 'BJ' and not (last_is_bj or last_is_rj):
                return False, "Your last card must be a Jack!", 0

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
        fc_card = matched_cards[0]
        # Determine if we are in a "Queen Dump" state (either started by this play or the table)
        is_dump_active = fc_card['value'] == 'Queen' or is_table_queen
        dump_suit = fc_card['suit'] if fc_card['value'] == 'Queen' else active_suit

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
                    return False, "Chain invalid: Cards must match rank, suit, be an Ace, or follow a Queen", 0

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

        if name in getattr(self, 'match_stats', {}):
            self.match_stats[name]['cards_played'] += len(matched_cards)
            power_count = sum(
                1 for c in matched_cards if c['value'] in ['2', '8', 'Jack', 'Queen', 'Ace']
            )
            self.match_stats[name]['power_cards_played'] = (
                self.match_stats[name].get('power_cards_played', 0) + power_count
            )

        return True, "Success", eight_skips

    def calculate_awards(self):
        """Determine end-of-game fun awards based on match statistics."""
        awards = {}
        if not getattr(self, 'match_stats', None):
            return awards

        stats = self.match_stats
        active_players = [p for p in stats if stats[p]['turn_count'] > 0]
        if not active_players:
            return awards

        # 1. Least Cards Played
        least_cards = min(active_players, key=lambda p: stats[p]['cards_played'])
        awards['least_cards'] = {'name': least_cards, 'value': stats[least_cards]['cards_played']}

        # 2. Quickest Player
        def avg_time(p):
            return stats[p]['turn_time_total'] / stats[p]['turn_count']

        quickest = min(active_players, key=avg_time)
        awards['quickest'] = {'name': quickest, 'value': round(avg_time(quickest), 1)}

        # 3. Most Nudges
        most_nudges = max(active_players, key=lambda p: stats[p]['nudges_sent'])
        if stats[most_nudges]['nudges_sent'] > 0:
            awards['most_nudges'] = {
                'name': most_nudges, 'value': stats[most_nudges]['nudges_sent']
            }

        # 4. Most Penalized
        most_penalized = max(active_players, key=lambda p: stats[p]['penalties_received'])
        if stats[most_penalized]['penalties_received'] > 0:
            awards['most_penalties'] = {
                'name': most_penalized, 'value': stats[most_penalized]['penalties_received']
            }

        # 5. Most Power Cards
        most_power = max(active_players, key=lambda p: stats[p].get('power_cards_played', 0))
        if stats[most_power].get('power_cards_played', 0) > 0:
            awards['most_power'] = {
                'name': most_power, 'value': stats[most_power]['power_cards_played']
            }

        return awards

    def play_joker(self, name):
        """Play a Joker card to reverse direction."""
        if not self.is_started:
            return False, "Game not started."
        active_players = sum(1 for p in self.players if len(self.hands.get(p, [])) > 0)
        if active_players <= 2:
            return False, "Joker cannot be used in a 2-player game."
        if name != self.get_current_player_name():
            return False, "Not your turn."
        if not getattr(self, 'jokers_available', {}).get(name, False):
            return False, "You have already used your Joker."
        if getattr(self, 'joker_cooldown', 0) > 0:
            return False, f"Joker is on cooldown for {self.joker_cooldown} more turns."

        self.jokers_available[name] = False
        self.direction *= -1
        self.joker_cooldown = len(self.players)
        return True, "Joker played! Direction reversed."

    def enforce_turn_timer(self):
        """Check if the current turn has exceeded 30 seconds and enforce auto-draw if so."""
        if not self.is_started:
            return None
        current_player = self.get_current_player_name()
        if not current_player or current_player.startswith('🤖'):
            return None

        elapsed = time.time() - self.current_turn_start_time
        if elapsed >= self.turn_timeout:
            was_penalty = False
            penalty_amount = 1
            if self.accumulated_penalty > 0:
                penalty_amount = self.accumulated_penalty + 1
                self.draw_card(current_player, penalty_amount, reason='penalty_timeout')
                self.accumulated_penalty = 0
                self.active_penalty_type = None
                self.penalty_source = None
                was_penalty = True
            else:
                self.draw_card(current_player, 1, reason='timeout_draw')

            if self.discard_pile and self.discard_pile[-1]['value'] == 'Ace' and not self.declared_ace_suit:
                self.declared_ace_suit = self.discard_pile[-1]['suit']

            self.advance_turn()
            return {'player': current_player, 'was_penalty': was_penalty, 'amount': penalty_amount}
        return None

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
                {
                    'msg': f"👁️ {name} waiting to play, now observing..."
                }, room='game_room')
        elif bot_yielded:
            socketio.emit('game_log',
                {
                    'msg': f"{BOT_NAME} has shutdown!"
                }, room='game_room')

    game.sid_to_name[sid] = name
    game.name_to_sid[name] = sid

    join_room('game_room')
    broadcast_state()
    return None

timer_task_started = False

def turn_timer_loop():
    """Background task to enforce the 30-second turn limit."""
    while True:
        socketio.sleep(1)
        if game.is_started:
            result = game.enforce_turn_timer()
            if result:
                player_name = result['player']
                if result['was_penalty']:
                    log_msg = f"⏰ Timeout! {player_name} drew {result['amount']} cards."
                else:
                    log_msg = f"⏰ Timeout! {player_name} drew 1 card."
                socketio.emit('game_log', {'msg': log_msg}, room='game_room')

                target_sid = game.name_to_sid.get(player_name)
                if target_sid:
                    socketio.emit('play_sound', {'type': 'alert'}, to=target_sid)

                broadcast_state()
                check_for_bot_turn()

@socketio.on('connect')
def handle_connect():
    """Start the global turn timer loop when the first user connects."""
    # pylint: disable=global-statement
    global timer_task_started
    if not timer_task_started:
        socketio.start_background_task(turn_timer_loop)
        timer_task_started = True

def check_for_bot_turn():
    """Determine if the current turn belongs to the computer and trigger AI logic."""
    if not game.is_started:
        return
    current_player = game.get_current_player_name()
    if current_player and current_player.startswith('🤖'):
        socketio.start_background_task(run_bot_logic, current_player)


def run_bot_logic(expected_bot_name):
    """Background task simulating computer thinking and decision making."""
    if not game.is_started:
        return
    bot_name = game.get_current_player_name()
    if not bot_name or bot_name != expected_bot_name:
        return

    # 0. Joker Logic (30% chance to play if available and not on cooldown)
    active_players_count = sum(1 for p in game.players if len(game.hands.get(p, [])) > 0)
    if active_players_count > 2 and \
            getattr(game, 'jokers_available', {}).get(bot_name, False) and \
            getattr(game, 'joker_cooldown', 0) == 0:
        if random.random() < 0.3:
            success, _ = game.play_joker(bot_name)
            if success:
                log_msg = f"🃏🔄 {bot_name} played a Joker! Play direction is reversed!"
                socketio.emit('game_log', {'msg': log_msg}, room='game_room')
                socketio.emit(
                    'joker_played', {'player': bot_name, 'msg': log_msg}, room='game_room'
                )
                socketio.emit('play_sound', {'type': 'alert'}, room='game_room')
                broadcast_state()
                # Must sleep slightly to allow UI to react before the bot plays a card
                socketio.sleep(1.0)

    if not game.is_started or not game.discard_pile:
        return

    # 2. Decide on a move
    hand = game.hands.get(bot_name, [])
    possible_play = None
    top_card = game.discard_pile[-1]

    # Check for penalty counters specifically
    if game.accumulated_penalty > 0:
        if game.active_penalty_type == '2':
            matches = [c for c in hand if c['value'] == '2']
        else:
            matches = [c for c in hand if c['value'] == 'Jack']
        if matches:
            possible_play = matches
    else:
        # Regular turn logic
        active_suit = game.declared_ace_suit if (
            game.declared_ace_suit and top_card['value'] == 'Ace'
        ) else top_card['suit']
        active_val = top_card['value']

        valid_starters = [
            c for c in hand if c['value'] == 'Ace' or
            c['value'] == active_val or c['suit'] == active_suit
        ]
        if valid_starters:
            best_chain = []
            for starter in valid_starters:
                chain = [starter]
                for c in hand:
                    if c != starter and c['value'] == starter['value']:
                        chain.append(c)
                if len(chain) > len(best_chain):
                    best_chain = chain
            possible_play = best_chain

    if possible_play:
        success, _, skips = game.validate_and_play_move(bot_name, possible_play)
        if success:
            cards_desc = ", ".join([f"{c['value']} of {c['suit']}" for c in possible_play])
            socketio.emit(
                'game_log', {
                    'msg': f"📝 {bot_name} played : {cards_desc}"}, room='game_room'
            )

            if len(game.hands.get(bot_name, [])) == 0:
                if bot_name in getattr(game, 'match_stats', {}):
                    elapsed = time.time() - game.current_turn_start_time
                    game.match_stats[bot_name]['turn_time_total'] += elapsed
                    game.match_stats[bot_name]['turn_count'] += 1

                game.update_league_results(bot_name)
                game.is_started = False
                game.host_name = None

                awards = game.calculate_awards()
                game.clear_bots_if_humans()
                socketio.emit('game_over', {'winner': bot_name, 'awards': awards}, room='game_room')
                broadcast_state()
                return

            if len(game.hands.get(bot_name, [])) == 1:
                socketio.emit(
                    'game_log',
                    {
                        'msg': f"📢 🔥 {bot_name} is down to their LAST CARD!"
                    }, room='game_room')

            if possible_play[-1]['value'] == 'Ace':
                new_hand = game.hands.get(bot_name, [])
                if not new_hand:
                    chosen_suit = "Spades"
                else:
                    suits = [c['suit'] for c in new_hand]
                    chosen_suit = max(set(suits), key=suits.count)

                game.declared_ace_suit = chosen_suit
                socketio.emit(
                    'game_log',
                    {
                        'msg': f"🔮 {bot_name} set the active suit to: {chosen_suit}!"
                    }, room='game_room')

            # Broadcast immediately so everyone sees the card played before the 2s pause
            broadcast_state()
            # Artificial delay for natural feel after playing cards
            socketio.sleep(2.0)
            if not game.is_started:
                return

            game.advance_turn(steps=1 + skips)
        else:
            if game.get_current_player_name() == bot_name:
                game.draw_card(bot_name, 1, reason='draw_fallback')
                broadcast_state()
                socketio.sleep(2.0)
                if not game.is_started:
                    return
                game.advance_turn()
    else:
        # Must draw
        if game.get_current_player_name() == bot_name:
            if game.accumulated_penalty > 0:
                log_msg = f"💥 {bot_name} had no defence and drew {game.accumulated_penalty} cards!"
                if getattr(game, 'penalty_source', None):
                    log_msg += f" (caused by {game.penalty_source})"
                socketio.emit('game_log', {'msg': log_msg}, room='game_room')
                game.draw_card(bot_name, game.accumulated_penalty, reason='penalty_auto')
                game.accumulated_penalty = 0
                game.active_penalty_type = None
                game.penalty_source = None
            else:
                socketio.emit('game_log', {'msg': f"🎴 {bot_name} drew a card."}, room='game_room')
                game.draw_card(bot_name, 1, reason='draw')
            broadcast_state()
            socketio.sleep(2.0)
            if not game.is_started:
                return
            game.advance_turn()

    broadcast_state()
    check_for_bot_turn()


@socketio.on('add_bot')
def handle_add_bot():
    """Add an extra bot to the lobby."""
    sid = request.sid
    requester = game.sid_to_name.get(sid)
    if not requester:
        return emit('error', {'msg': 'You must be in the lobby to add a bot.'})

    current_bots = sum(1 for p in game.players if p.startswith('🤖'))
    if current_bots >= 3:
        return emit('error', {'msg': 'Maximum of 3 bots allowed.'})

    available_names = [n for n in BOT_ROSTER if n not in game.players]
    if not available_names:
        return emit('error', {'msg': 'No more bots available'})

    bot_name = random.choice(available_names)

    game.add_player(bot_name)
    socketio.emit(
        'game_log',
        {'msg': f"🤖 {requester} added {bot_name}."},
        room='game_room'
    )
    broadcast_state()


def _broadcast_match_start():
    """Helper to broadcast game start events and first card rules."""
    dealer_name = game.players[game.match_dealer_index]
    starter_name = game.get_current_player_name()

    socketio.emit(
        'game_log',
        {'msg': "🔀 Shuffling the deck..."},
        room='game_room'
    )
    log_msg = (
        f"🃏 Dealer for this hand is <b>{dealer_name}</b>. "
        f"Play starts with <b>{starter_name}</b>!"
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
            "declare the active suit."
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
            f"The first card is an 8! {skipped_name} misses a turn. "
            f"Action starts with {starter_name}!"
        )
        socketio.emit('game_log', {'msg': eight_msg}, room='game_room')

    broadcast_state()
    check_for_bot_turn()


@socketio.on('start_demo')
def handle_start_demo():
    """Launch a demo mode with 3 bots playing against each other."""
    sid = request.sid
    requester = game.sid_to_name.get(sid, "Someone")
    
    # Clear current players but keep connections (spectator mode)
    game.players = []
    game.host_name = None
    
    for bot in random.sample(BOT_ROSTER, 3):
        game.add_player(bot)
        
    socketio.emit(
        'game_log',
        {'msg': f"🎬 {requester} activated Demo Mode! 3 Bots are battling it out!"},
        room='game_room'
    )
    
    if game.start_game():
        _broadcast_match_start()
    else:
        emit('error', {'msg': 'Failed to start demo mode!'})


@socketio.on('stop_demo')
def handle_stop_demo():
    """Finish the demo mode and return human clients back to the lobby."""
    sid = request.sid
    requester = game.sid_to_name.get(sid, "Someone")

    socketio.emit(
        'game_log',
        {'msg': f"🛑 {requester} finished the Demo Mode. Returning to lobby..."},
        room='game_room'
    )

    # Stop the game loop flag
    game.is_started = False

    # Remove all bots
    bots = [p for p in game.players if p.startswith('🤖')]
    for bot in bots:
        game.players.remove(bot)
        if bot in game.hands:
            del game.hands[bot]

    # Restore human players based on active connections
    for human_name in game.sid_to_name.values():
        game.add_player(human_name)

    game.reset_match()

    socketio.emit(
        'room_reset',
        {'msg': 'Demo stopped, lobby restored.'},
        room='game_room'
    )
    broadcast_state()


@socketio.on('start_match')
def handle_start():
    """Transition state parameters to live round execution modes."""
    sid = request.sid
    requester = game.sid_to_name.get(sid)
    game.host_name = requester
    if game.start_game():
        _broadcast_match_start()
    else:
        game.host_name = None
        emit('error', {'msg': 'Need at least 2 players to start!'})


# pylint: disable=too-many-locals, too-many-branches, too-many-statements
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
            if name in getattr(game, 'match_stats', {}):
                elapsed = time.time() - game.current_turn_start_time
                game.match_stats[name]['turn_time_total'] += elapsed
                game.match_stats[name]['turn_count'] += 1

            game.update_league_results(name)

            game.is_started = False
            game.host_name = None
            game.accumulated_penalty = 0
            game.active_penalty_type = None
            game.declared_ace_suit = None
            game.penalty_source = None

            awards = game.calculate_awards()
            game.clear_bots_if_humans()
            socketio.emit(
                'game_over',
                {'winner': name, 'awards': awards},
                room='game_room'
            )
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
                    f"{skips} player(s) skipped by the 8 "
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
        {'msg': f"🔮 {name} set the game suit to: {chosen_suit}!"},
        room='game_room'
    )
    socketio.emit('play_sound', {'type': 'play'}, room='game_room')
    game.advance_turn()
    broadcast_state()
    check_for_bot_turn()


@socketio.on('play_joker')
def handle_play_joker():
    """Handle a user playing their Joker card to reverse direction."""
    sid = request.sid
    name = game.sid_to_name.get(sid)
    if not name:
        emit('error', {'msg': "Not authenticated."})
        return

    success, msg = game.play_joker(name)
    if success:
        log_msg = f"🃏🔄 {name} played a Joker! Play direction is reversed!"
        socketio.emit('game_log', {'msg': log_msg}, room='game_room')
        socketio.emit(
            'joker_played', {'player': name, 'msg': log_msg}, room='game_room'
        )
        socketio.emit('play_sound', {'type': 'alert'}, room='game_room')
        broadcast_state()
    else:
        emit('error', {'msg': msg})


@socketio.on('reset_match')
def handle_reset_match():
    """Reset only the active match while preserving lobby roster and career stats."""
    sid = request.sid
    requester = game.sid_to_name.get(sid)
    if not requester:
        emit('error', {'msg': 'You must be in the lobby to reset the match.'})
        return

    if not game.is_started:
        emit('error', {'msg': 'There is no active match to stop.'})
        return

    if requester != game.host_name:
        emit('error', {'msg': 'Only the match host can stop the game.'})
        return

    bots = [p for p in game.players if p.startswith('🤖')]
    for bot in bots:
        game.players.remove(bot)
        if bot in game.hands:
            del game.hands[bot]

    game.reset_match()
    socketio.emit(
        'game_log',
        {'msg': f"🛑 {requester} stopped the game. All bots have been removed."},
        room='game_room'
    )
    socketio.emit(
        'room_reset',
        {'msg': 'Match stopped and returned to lobby.'},
        room='game_room'
    )
    broadcast_state()


@socketio.on('change_avatar')
def handle_change_avatar(data):
    """Update the player's chosen avatar and broadcast the change."""
    sid = request.sid
    name = game.sid_to_name.get(sid)
    if name:
        game.avatars[name] = data.get('avatar', '👤')
        broadcast_state()


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

    if sender_name in getattr(game, 'match_stats', {}):
        game.match_stats[sender_name]['nudges_sent'] += 1

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
        'host_name': getattr(game, 'host_name', None),
        'top_card': top_card,
        'active_suit': active_suit,
        'current_player': current_player,
        'current_player_sid': current_sid,
        'penalty': game.accumulated_penalty,
        'penalty_type': game.active_penalty_type,
        'player_list': game.players,
        'avatars': getattr(game, 'avatars', {}),
        'jokers_available': getattr(game, 'jokers_available', {}),
        'joker_cooldown': getattr(game, 'joker_cooldown', 0),
        'direction': game.direction,
        'hand_sizes': {
            p: len(game.hands[p]) for p in game.players if p in game.hands
        },
        'league_table': scoreboards,
        'turn_start_time': game.current_turn_start_time,
        'server_time': time.time()
    }
    socketio.emit('state_update', state, room='game_room')

    # We broadcast hands to ALL connected clients so spectators accurately receive data
    for sid, name in game.sid_to_name.items():
        hand = game.hands.get(name, [])
        socketio.emit('your_hand', {'hand': hand}, to=sid)

        # Spectator View: If the game is running and they have 0 cards,
        # securely send them the hands of all active players!
        if game.is_started and len(hand) == 0:
            spectator_hands = {
                p_name: game.hands.get(p_name, [])
                for p_name in game.players
                if len(game.hands.get(p_name, [])) > 0
            }
            socketio.emit(
                'spectator_hands', {'hands': spectator_hands}, to=sid
            )


if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
