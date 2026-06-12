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

from game_engine import FamilyBlackjackEngine, BOT_NAME, BOT_ROSTER

app = Flask(__name__)
app.config['SECRET_KEY'] = 'blackjack_family_secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global instances tracking core system state mechanics
game = FamilyBlackjackEngine()
game.set_socketio(socketio)

# Fallback for test environments using outdated FlaskStubs
if not hasattr(app, 'app_context'):
    class DummyAppContext:
        def __enter__(self): return self
        def __exit__(self, exc_type, exc_val, exc_tb): pass
    app.app_context = lambda: DummyAppContext()


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


@app.route('/snippets/modals')
def modals_snippet():
    """Serve HTML snippet for static modals."""
    avatars = [
        '👤', '😎', '🤠', '👽', '👾', '🐱', '🐶', '🦊', '🐻', '🐼',
        '🐨', '🐯', '🦁', '🐮', '🐷', '🐸', '🐵', '🦇', '🦉', '🦄'
    ]
    return render_template('snippets/modals.html', avatars=avatars)


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

            socketio.emit('play_sound', {'type': 'play'}, room='game_room')

            if len(game.hands.get(bot_name, [])) == 0:
                if bot_name in getattr(game, 'match_stats', {}):
                    elapsed = time.time() - game.current_turn_start_time
                    game.match_stats[bot_name]['turn_time_total'] += elapsed
                    game.match_stats[bot_name]['turn_count'] += 1

                game.update_league_results(bot_name)
                game.is_started = False
                game.host_name = None

                awards = game.calculate_awards()
                is_demo = all(p.startswith('🤖') for p in game.players)
                try:
                    with app.app_context():
                        html_content = render_template('snippets/game_over.html', winner=bot_name, awards=awards, is_demo=is_demo)
                except Exception:
                    html_content = f"<h2>Winner: {bot_name}!</h2><p>Game Over!</p>"

                game.clear_bots_if_humans()
                socketio.emit(
                    'game_over', {'html': html_content, 'is_demo': is_demo, 'winner': bot_name}, room='game_room'
                )
                socketio.emit('play_sound', {'type': 'victory'}, room='game_room')
                broadcast_state()
                return

            if len(game.hands.get(bot_name, [])) == 1:
                socketio.emit(
                    'game_log',
                    {
                        'msg': f"📢 🔥 {bot_name} is down to their LAST CARD!"
                    }, room='game_room')
                socketio.emit('play_sound', {'type': 'penalty'}, room='game_room')

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
                socketio.emit('play_sound', {'type': 'draw'}, room='game_room')
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
                socketio.emit('play_sound', {'type': 'penalty'}, room='game_room')
                game.draw_card(bot_name, game.accumulated_penalty, reason='penalty_auto')
                game.accumulated_penalty = 0
                game.active_penalty_type = None
                game.penalty_source = None
            else:
                socketio.emit('game_log', {'msg': f"🎴 {bot_name} drew a card."}, room='game_room')
                socketio.emit('play_sound', {'type': 'draw'}, room='game_room')
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


@socketio.on('shuffle_players')
def handle_shuffle_players():
    """Randomize the order of players in the lobby."""
    sid = request.sid
    requester = game.sid_to_name.get(sid)
    if not requester:
        return emit('error', {'msg': 'You must be in the lobby to shuffle players.'})

    if game.is_started:
        return emit('error', {'msg': 'Cannot shuffle players while a match is in progress.'})

    if len(game.players) > 1:
        random.shuffle(game.players)
        socketio.emit(
            'game_log',
            {'msg': f"🔀 {requester} shuffled the player order!"},
            room='game_room'
        )
        broadcast_state()


@socketio.on('remove_bot')
def handle_remove_bot(data):
    """Remove a specific bot from the lobby."""
    sid = request.sid
    requester = game.sid_to_name.get(sid)
    if not requester:
        return emit('error', {'msg': 'You must be in the lobby to remove a bot.'})

    if game.is_started:
        return emit('error', {'msg': 'Cannot remove bots while a match is in progress.'})

    bot_name = data.get('name')
    if bot_name and bot_name in game.players and bot_name.startswith('🤖'):
        game.players.remove(bot_name)
        if bot_name in game.hands:
            del game.hands[bot_name]
        socketio.emit(
            'game_log',
            {'msg': f"🤖 {requester} removed {bot_name}."},
            room='game_room'
        )
        broadcast_state()


def _broadcast_match_start():
    """Helper to broadcast game start events and first card rules."""
    dealer_name = game.players[game.match_dealer_index]
    intended_starter_name = game.players[(game.match_dealer_index + 1) % len(game.players)]

    socketio.emit(
        'game_log',
        {'msg': "🔀 Shuffling the deck..."},
        room='game_room'
    )
    log_msg = (
        f"🃏 Dealer for this hand is <b>{dealer_name}</b>. "
        f"Play starts with <b>{intended_starter_name}</b>!"
    )
    socketio.emit(
        'game_log',
        {'msg': log_msg},
        room='game_room'
    )
    socketio.emit('play_sound', {'type': 'shuffle'}, room='game_room')

    first_card = game.discard_pile[-1]
    if first_card['value'] == 'Ace':
        starter_sid = game.name_to_sid.get(intended_starter_name)
        if starter_sid:
            socketio.emit('prompt_ace_suit', {}, to=starter_sid)
        ace_msg = (
            f"🔮 The first card is an Ace! {intended_starter_name} "
            "declare the active suit."
        )
        socketio.emit(
            'game_log',
            {'msg': ace_msg},
            room='game_room'
        )
    elif game.active_penalty_type == '2':
        two_msg = f"⚠️ The first card is a 2! {intended_starter_name} must counter it or draw +2 cards."
        socketio.emit(
            'game_log',
            {'msg': two_msg},
            room='game_room'
        )
    elif game.active_penalty_type == 'BJ':
        bj_msg = f"⚠️ Black Jack! {intended_starter_name} must counter or draw +5."
        socketio.emit(
            'game_log',
            {'msg': bj_msg},
            room='game_room'
        )
    elif first_card['value'] == '8':
        skipped_name = game.players[(game.match_dealer_index + 1) % len(game.players)]
        actual_starter = game.get_current_player_name()
        eight_msg = (
            f"The first card is an 8! {skipped_name} misses a turn. "
            f"Action starts with {actual_starter}!"
        )
        socketio.emit('game_log', {'msg': eight_msg}, room='game_room')

    broadcast_state()

    # Enforce any immediate auto-draws from penalty start cards so the logs appear chronologically
    prev_penalty = game.accumulated_penalty
    game.check_and_enforce_autodraw()
    if prev_penalty > 0 and game.accumulated_penalty == 0:
        broadcast_state()

    check_for_bot_turn()


@socketio.on('start_demo')
def handle_start_demo():
    """Launch a demo mode with 3 bots playing against each other."""
    sid = request.sid
    requester = game.sid_to_name.get(sid, "Someone")

    # Store currently connected humans
    connected_humans = list(game.sid_to_name.values())

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
        for human in connected_humans:
            game.add_player(human)
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
            is_demo = all(p.startswith('🤖') for p in game.players)
            try:
                with app.app_context():
                    html_content = render_template('snippets/game_over.html', winner=name, awards=awards, is_demo=is_demo)
            except Exception:
                html_content = f"<h2>Winner: {name}!</h2><p>Game Over!</p>"

            game.clear_bots_if_humans()
            socketio.emit(
                'game_over', {'html': html_content, 'is_demo': is_demo, 'winner': name},
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

    try:
        with app.app_context():
            league_html = render_template('snippets/league_table.html', league_table=scoreboards)
    except Exception:
        league_html = "<tr><td colspan='3'>Scoreboard offline.</td></tr>"

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
        'server_time': time.time(),
        'league_html': league_html
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
