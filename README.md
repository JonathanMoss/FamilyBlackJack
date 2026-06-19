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

