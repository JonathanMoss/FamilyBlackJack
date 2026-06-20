"""Core game logic and state machine for Family Blackjack."""
# pylint: disable=too-many-public-methods,too-many-instance-attributes,too-few-public-methods
# pylint: disable=too-many-lines, invalid-name, too-many-locals, too-many-branches, too-many-statements
# pylint: disable=inconsistent-return-statements

import json
import os
import random
import re
import sys
import time

import rule_engine

BOT_NAME = "Computer"
BOT_ROSTER = [
    "HAL 9000", "The Architect", "KITT", "V'ger",
    "Ash", "R2-D2", "C3-PO"
]

STATS_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stats.json')




class FamilyBlackjackEngine:
    """Core state machine managing players, card decks, and gameplay rounds."""

    def __init__(self, turn_timeout=30.0):
        """Initialize defaults for a fresh blackjack lobby."""
        self.players = []          # Ordered list of Unique Usernames
        self.bots = set()          # Set of bot player names
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

        self.socketio = None
        self.cached_league_html = None
        self.timer_session_id = 0
        self.stats_file_path = None if ('pytest' in sys.modules or 'unittest' in sys.modules) else STATS_FILE_PATH
        self._load_stats()

    def _save_stats(self):
        """Save league standings to a JSON file."""
        if not self.stats_file_path:
            return
        try:
            data = {
                'wins': self.league_wins,
                'losses': self.league_losses
            }
            with open(self.stats_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Failed to save stats to {self.stats_file_path}: {e}")

    def _load_stats(self):
        """Load league standings from a JSON file."""
        if not self.stats_file_path:
            return
        if os.path.exists(self.stats_file_path):
            try:
                with open(self.stats_file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.league_wins = data.get('wins', {})
                self.league_losses = data.get('losses', {})
            except Exception as e:
                print(f"Failed to load stats from {self.stats_file_path}: {e}")

    def set_socketio(self, socketio_instance):
        """Inject a SocketIO instance for decoupled event emitting."""
        self.socketio = socketio_instance

    def emit(self, event, data, **kwargs):
        """Safely emit real-time events if a SocketIO instance is bound."""
        if self.socketio:
            self.socketio.emit(event, data, **kwargs)

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
        self.cached_league_html = None
        # Note: We intentionally DO NOT clear league_wins or league_losses
        # so career family stats persist across separate game room lobbies!

    def clear_penalty(self):
        """Reset active penalty accumulation states."""
        self.accumulated_penalty = 0
        self.active_penalty_type = None
        self.penalty_source = None

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
        self.clear_penalty()
        self.declared_ace_suit = None
        self.match_stats = {}
        self.current_turn_start_time = 0.0
        self.jokers_available = {}
        self.joker_cooldown = 0
        self.host_name = None
        self.cached_league_html = None

    def build_deck(self):
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
        if self.is_bot(name):
            return
        updated = False
        if name not in self.league_wins:
            self.league_wins[name] = 0
            updated = True
        if name not in self.league_losses:
            self.league_losses[name] = 0
            updated = True
        if updated:
            self._save_stats()

    def is_bot(self, name):
        """Check if a player name belongs to an AI bot."""
        if not name:
            return False
        if name in self.bots:
            return True
        # Backward compatibility for existing tests and rosters (avoiding substring matching 'Bot' in name)
        if (name == BOT_NAME or 
                name in BOT_ROSTER or 
                name.startswith('🤖') or 
                re.match(r'^Bot \d+$', name)):
            return True
        return False

    def add_player(self, name):
        """Register a new player in the lobby and manage bot yield logic."""
        if name not in self.players:
            if (name == BOT_NAME or 
                    name in BOT_ROSTER or 
                    name.startswith('🤖') or 
                    re.match(r'^Bot \d+$', name)):
                self.bots.add(name)
            self.players.append(name)
            self.hands[name] = []
            if name not in self.avatars:
                self.avatars[name] = '🤖' if self.is_bot(name) else '👤'

            # If the lobby is idle and we now have multiple humans, remove the bot
            if not self.is_started:
                human_players = [p for p in self.players if not self.is_bot(p)]
                if len(human_players) >= 2 and BOT_NAME in self.players:
                    self.players.remove(BOT_NAME)
                    return True
        return False

    def clear_bots_if_humans(self):
        """Remove bot players from the lobby if any human players are present."""
        humans = [p for p in self.players if not self.is_bot(p)]
        if humans:
            bots = [p for p in self.players if self.is_bot(p)]
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
        human_players = [p for p in self.players if not self.is_bot(p)]
        if len(human_players) >= 2 and BOT_NAME in self.players:
            self.players.remove(BOT_NAME)
            self.emit('game_log', {'msg': f"{BOT_NAME} has shutdown!"}, room='game_room')

        # Automatically add a computer player if someone starts alone
        if len(self.players) == 1:
            if BOT_NAME not in self.players:
                self.bots.add(BOT_NAME)
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

        self.clear_penalty()
        self.declared_ace_suit = None

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
        self.timer_session_id += 1
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
        if (self.is_started and getattr(self, 'match_stats', None) and
                current_p in self.match_stats):
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
        hand = self.hands.get(name, [])
        return rule_engine.has_valid_penalty_counter(
            hand, self.active_penalty_type, self.accumulated_penalty
        )

    def check_and_enforce_autodraw(self):
        """Evaluate penalty counters; trigger card drawings for undefended states."""
        if not self.is_started or self.accumulated_penalty == 0:
            return

        current_name = self.get_current_player_name()

        # Let the bot logic handle its own auto-draw with a natural delay
        if current_name and self.is_bot(current_name):
            return

        if not self.has_valid_penalty_counter(current_name):
            self.draw_card(current_name, self.accumulated_penalty, reason='penalty_auto')
            log_msg = (
                f"💥 {current_name} had no defence cards "
                f"and drew {self.accumulated_penalty} cards!"
            )
            if getattr(self, 'penalty_source', None):
                log_msg += f" (caused by {self.penalty_source})"
            self.emit(
                'game_log', {'msg': log_msg}, room='game_room'
            )

            target_sid = self.name_to_sid.get(current_name)
            if target_sid:
                self.emit('play_sound', {'type': 'penalty'}, to=target_sid)

            self.clear_penalty()

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
                    self.emit(
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
                self.emit('received_cards', payload, to=target_sid)
        return drawn

    def update_league_results(self, winner_name):
        """Append win statistics to the winner and increment losses for the rest.

        Args:
            winner_name (str): Target identity of the round victor.
        """
        self.register_league_player(winner_name)
        if not self.is_bot(winner_name):
            self.league_wins[winner_name] += 1

        for name in self.players:
            if name != winner_name:
                if self.match_stats and name not in self.match_stats:
                    continue
                self.register_league_player(name)
                if not self.is_bot(name):
                    self.league_losses[name] += 1

        self._save_stats()

    # pylint: disable=too-many-return-statements
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
        active_suit = self.declared_ace_suit if is_ace_active else top_card['suit']

        validation_result = rule_engine.validate_move(
            matched_cards=matched_cards,
            top_card=top_card,
            active_suit=active_suit,
            active_penalty_type=self.active_penalty_type,
            accumulated_penalty=self.accumulated_penalty,
            penalty_source=self.penalty_source,
            player_name=name
        )

        if not validation_result['success']:
            return False, validation_result['msg'], 0

        self.active_penalty_type = validation_result['new_penalty_type']
        self.accumulated_penalty = validation_result['new_accumulated_penalty']
        self.penalty_source = validation_result['new_penalty_source']
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

        return True, validation_result['msg'], validation_result['eight_skips']

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
        if not current_player or self.is_bot(current_player):
            return None

        elapsed = time.time() - self.current_turn_start_time
        if elapsed >= self.turn_timeout:
            was_penalty = False
            penalty_amount = 1
            if self.accumulated_penalty > 0:
                penalty_amount = self.accumulated_penalty + 1
                self.draw_card(current_player, penalty_amount, reason='penalty_timeout')
                self.clear_penalty()
                was_penalty = True
            else:
                self.draw_card(current_player, 1, reason='timeout_draw')

            if (self.discard_pile and self.discard_pile[-1]['value'] == 'Ace'
                    and not self.declared_ace_suit):
                self.declared_ace_suit = self.discard_pile[-1]['suit']

            self.advance_turn()
            return {'player': current_player, 'was_penalty': was_penalty, 'amount': penalty_amount}
        return None
