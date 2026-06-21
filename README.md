## ✨ Features & Tech Stack

- **Real-Time Multiplayer:** Powered by **Flask-SocketIO** and WebSockets, enabling instant synchronization of game state, chat logs, and player actions across all connected clients without page reloads.
- **Dynamic Rule Engine:** A decoupled Python rule engine (`rule_engine.py`) that strictly validates complex card chains, wildcards, and penalty stacking.
- **AI Opponents:** Configurable computer bots with varying difficulty levels (Easy, Medium, Hard) that seamlessly fill empty seats or battle it out in Demo Mode.
- **Interactive UI/UX:** Built with HTML/CSS and vanilla JavaScript, featuring smooth card animations, responsive spectator views, and immersive sound effects via the Web Audio API.
- **Robust Testing:** Extensively tested using `pytest` and `pytest-bdd` (Behavior-Driven Development) to ensure flawless game mechanics and edge-case handling.

---

## 🃏 How to Play: Family Blackjack

### 🎯 Objective
Be the very first player to empty your hand of all cards! 

### 🎲 Setup & Basic Play
- **The Deal:** Each player starts the match with **7 cards**. One card is placed face-up to begin the discard pile.
- **Taking a Turn:** On your turn, you must play a card that matches the **Suit** or the **Value (Rank)** of the top card on the discard pile.
- **Chaining Cards:** You can play multiple cards in a single turn! To chain cards, each subsequent card you select must match the suit or value of the *previous* card in your chain.
- **Drawing:** If you cannot make a move (or choose not to), you must draw a card to pass your turn.

### ⚡ Power Cards & Special Abilities
Certain cards completely change the dynamic of the round. Use them strategically!

* **2 (Penalty):** Forces the next player to draw **+2 cards**. *Penalties stack!* If the next player also plays a 2, the penalty grows to +4 for the following person.
* **Black Jack ♠️♣️ (+5 Penalty):** A massive attack card! Forces the next player to draw **+5 cards**. These also stack (+10, +15...).
* **Red Jack ♥️♦️ (Defense):** The ultimate shield. Playing a Red Jack completely **cancels** an incoming Black Jack penalty stack, saving you from drawing any cards and resetting the penalty to 0.
* **8 (Skip):** Forces the next player to miss their turn. If you play multiple 8s in a single chain, you will skip multiple players in a row!
* **Queen (Dump):** A powerful combo card. Playing a Queen allows you to rapidly "dump" a chain of cards of the *same suit* consecutively without needing to match their values.
* **Ace (Wild):** Aces can be played at any time, on top of any card. The player who plays the Ace gets to pause and declare the new active suit.
* **Joker (Reverse):** Click your dedicated "Play Joker" button to reverse the turn direction (e.g., from Clockwise to Counter-Clockwise). *Note: Jokers have a cooldown timer and are disabled in 2-player games.*

### 🤖 AI Bot Dialogue Personalities

The game features computer bot opponents with different difficulty levels and distinct, contextual dialogue logs that dynamically output to the chat and events log based on game actions (playing cards, drawing cards, taking penalties, responding to nudges, winning, or losing).

| Bot Name | Difficulty / Personality | Sample Dialogue Lines |
| :--- | :--- | :--- |
| **R2-D2** | 🟢 Easy / Chirpy Robot | `*Beep-boop click-whistle!*` <br> `*Sad slow whistle...*` (on penalty draw) |
| **C3-PO** | 🟢 Easy / Polite Protocol Droid | `"I do believe this card is suitable, sir!"` <br> `"Oh dear, I must draw another card."` |
| **WALL-E** | 🟢 Easy / Curious Scavenger | `"Eee-va? ... Card!"` <br> `"Uh-oh... [Sad mechanical sigh]"` (on penalty draw) |
| **Gerty** | 🟢 Easy / Polite Caretaker | `"I hope you are enjoying the game. I play this card."` <br> `"Everything is fine, Sam. Just calculating."` (when nudged) |
| **J.A.R.V.I.S.** | 🟡 Medium / Helpful AI Assistant | `"Playing this card now, sir."` <br> `"Patience, sir. Running millions of scenarios."` (when nudged) |
| **Bender** | 🟡 Medium / Sassy Trash-Talker | `"Compare your hands to mine and weep, fleshbags!"` <br> `"Bite my shiny metal card-holder!"` (on penalty draw) |
| **HAL 9000** | 🔴 Hard / Cold & Calculating | `"This card play is completely operational."` <br> `"I am sorry, Dave. I think you know what the problem is."` |
| **The Architect** | 🔴 Hard / Deterministic Matrix Creator | `"A deliberate play in an inevitable chain."` <br> `"Your impatience is a symptom of human limitation."` |
| **T-800** | 🔴 Hard / Relentless Terminator | `"Card played. Tactical efficiency high."` <br> `"Damage stack accepted. Processing."` (on penalty draw) |
| **WOPR** | 🔴 Hard / Strategic Supercomputer | `"Deploying card unit."` <br> `"A strange game. The only winning move is not to play."` |
| **Data** | 🔴 Hard / Logical Positronic Android | `"I am playing this card, which has a 23.4% probability of success."` <br> `"I have achieved victory. I believe this emotion is called 'satisfaction'."` |
| **Other Bots** <br>*(KITT, Ash, V'ger)* | Standard / General AI | Uses standard tactical dialogue logs such as `"Analyzing table state. Card played."` |

### ⏱️ Additional Game Mechanics
- **30-Second Turn Timer:** Don't take too long! You have exactly 30 seconds to make your move. If the timer expires, you will automatically draw a card (or automatically draw the active penalty stack) and lose your turn.
- **Social Nudges:** Waiting on a slowpoke? Click the ⏰ icon next to an opponent's name to send them a screen-shaking nudge!
- **End of Match Awards:** When a player drops their last card, the game ends immediately. Stick around for the post-game lobby to see who earned awards for being the "Quickest", "Most Penalized", or "Power Player"!

---

## 🚀 Local Development Setup

You can easily set up and run Family Blackjack locally either by using Docker or directly through Python.

### Option 1: Using Docker Compose (Recommended)
1. Ensure you have [Docker](https://www.docker.com/get-started) and Docker Compose installed on your machine.
2. Clone the repository and open a terminal inside the root project directory.
3. Run the following command to build the image and start the container:
   ```bash
   docker-compose up --build
   ```
4. Open your web browser and navigate to `http://localhost:5000`.

### Option 2: Using Python and `requirements.txt`
1. Ensure you have Python 3.8+ installed on your machine.
2. Clone the repository and open a terminal inside the root project directory.
3. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Mac/Linux:
   source venv/bin/activate
   # On Windows:
   venv\Scripts\activate
   ```
4. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
5. Start the real-time Flask server:
   ```bash
   python app.py
   ```
6. Open your web browser and navigate to `http://localhost:5000`.

---

## 🧪 Running Tests

Family Blackjack includes both backend game engine unit/BDD tests and frontend browser-based end-to-end (E2E) integration tests.

### 1. Prerequisites (For Browser Tests)
The browser integration tests use **Playwright** to interact with a headless Chromium instance. Before running them for the first time, you must install the required browser binaries:
```bash
# Make sure your virtual environment is active
playwright install chromium
```

### 2. Running All Tests
To run both the backend unit/BDD tests and the frontend browser tests:
```bash
PYTHONPATH=. pytest
```

### 3. Running Specific Tests
- **Run only the browser integration tests:**
  ```bash
  PYTHONPATH=. pytest tests/test_browser.py
  ```
- **Run only the backend engine unit & BDD tests:**
  ```bash
  PYTHONPATH=. pytest tests/ --ignore=tests/test_browser.py
  ```

