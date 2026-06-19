Feature: Advanced Gameplay Mechanics
  As a Family Blackjack player
  I want to utilize complex card chains and power card sequences
  So that I can strategically clear my hand and skip opponents

  Scenario: Queen allows a manual suit chain followed by rank matching
    Given a game is in progress with Alice and Bob
    And it is "Alice"'s turn
    And the top card is "10 of Hearts"
    And Alice has "Queen of Hearts", "5 of Hearts", and "5 of Spades" in hand
    When Alice plays the chain: "Queen of Hearts", "5 of Hearts", "5 of Spades"
    Then Alice should have 0 cards left
    And "Bob" should be the current player

  Scenario: Stacking multiple cards of the same suit on an existing Table Queen
    Given a game is in progress with Alice and Bob
    And the top card is "Queen of Diamonds"
    And it is "Alice"'s turn
    And Alice has "5 of Diamonds", "6 of Diamonds", and "Jack of Diamonds" in hand
    When Alice plays the chain: "5 of Diamonds", "6 of Diamonds"
    Then Alice should have 1 cards left
    And the turn should return to Bob

  Scenario: Playing multiple 8s skips multiple players
    Given a lobby has 3 players "Alice", "Bob", and "Charlie"
    And a game is in progress
    And it is "Alice"'s turn
    And the top card is "8 of Spades"
    And Alice has "8 of Hearts" and "8 of Diamonds" in hand
    When Alice plays the chain: "8 of Hearts", "8 of Diamonds"
    Then "Alice" should be the current player

  Scenario: Automatic draw occurs when no counter is available
    Given a game is in progress with Alice and Bob
    And Alice just played a "2 of Hearts"
    And Bob has no "2" in hand
    When the turn advances to Bob
    Then Bob should automatically draw 2 cards
    And the turn should return to Alice

  Scenario: Playing an Ace during the game forces the next player to follow the declared suit
    Given a game is in progress with Alice and Bob
    And it is "Alice"'s turn
    And Alice plays an "Ace of Spades" and declares "Diamonds"
    And Bob has "5 of Spades" and "5 of Diamonds" in hand
    When Bob attempts to play "5 of Spades"
    Then the play should be rejected with message "First card must be a (Diamonds)"

  Scenario: Starting a match with one player adds a computer opponent
    Given a lobby has only one player "Alice"
    When the game starts
    Then "Alice" should have 7 cards
    And "Computer" should have 7 cards

  Scenario: Computer player leaves when a second human joins an idle lobby
    Given a lobby has only one player "Alice"
    And "Computer" is in the lobby
    When "Bob" joins the lobby
    Then "Computer" should not be in the lobby
    And the lobby should have 2 players

  Scenario: Computer player yields when a match starts with enough humans
    Given a lobby has 3 players "Alice", "Computer", and "Bob"
    When the game starts
    Then "Computer" should not be in the lobby
    And the lobby should have 2 players

  Scenario: Calculating end of game fun awards
    Given a game is in progress with Alice and Bob
    And Alice has played 2 cards
    And Bob has played 10 cards
    And Alice has received 5 penalty cards
    And Bob has sent 3 nudges
    And Alice has played 5 power cards
    When the game calculates awards
    Then "Alice" should receive the minimalist award
    And "Alice" should receive the most penalized award
    And "Bob" should receive the most nudges award
    And "Alice" should receive the power player award

  Scenario: Playing a Joker reverses direction and applies a cooldown
    Given a game is in progress with Alice, Bob, and Charlie
    And the top card is "4 of Hearts"
    And Alice has "5 of Hearts" and "King of Spades" in hand
    And it is "Alice"'s turn
    When Alice plays her Joker
    Then the play direction should be reversed
    And the Joker cooldown should be 3
    And "Alice" should not have a Joker available
    When Alice plays the chain: "5 of Hearts"
    Then the Joker cooldown should be 2
    And "Charlie" should be the current player
    When Charlie attempts to play his Joker
    Then the play should be rejected with message "Joker is on cooldown"

  Scenario: Computer player plays a chain of cards of the same rank
    Given a game is in progress with Alice and Computer
    And the top card is "10 of Hearts"
    And "Computer" has "5 of Hearts", "5 of Spades", "5 of Diamonds", and "King of Spades" in hand
    And it is "Computer"'s turn
    When the computer takes its turn
    Then "Computer" should have 1 cards left
    And the turn should return to Alice

  Scenario: Computer player plays a chain of penalty cards
    Given a game is in progress with Alice and Computer
    And Alice just played a "2 of Clubs"
    And Alice has "2 of Diamonds" in hand
    And "Computer" has "2 of Spades", "2 of Hearts", and "5 of Diamonds" in hand
    And it is "Computer"'s turn
    When the computer takes its turn
    Then "Computer" should have 1 cards left
    And the accumulated penalty should be 6

  Scenario: Turn timer expires and forces an auto-draw
    Given a game is in progress with Alice and Bob
    And it is "Alice"'s turn
    When 30 seconds pass
    Then Alice should automatically draw 1 cards
    And the turn should return to Bob

  Scenario: Turn timer expires while a penalty is active
    Given a game is in progress with Alice and Bob
    And Alice just played a "2 of Hearts"
    And it is "Bob"'s turn
    When 30 seconds pass
    Then Bob should automatically draw 3 cards
    And the turn should return to Alice

  Scenario: Turn timer expires while a Black Jack penalty is active and player holds a Red Jack
    Given a game is in progress with Alice and Bob
    And Alice just played a "Jack of Spades"
    And Bob has "Jack of Hearts" in hand
    And it is "Bob"'s turn
    When 30 seconds pass
    Then Bob should automatically draw 6 cards
    And the turn should return to Alice

  Scenario: Playing a Joker is not allowed in a 2-player game
    Given a game is in progress with Alice and Bob
    And it is "Alice"'s turn
    When Alice attempts to play her Joker
    Then the play should be rejected with message "Joker cannot be used in a 2-player game"

  Scenario: Turn timer expires while waiting for Ace suit declaration
    Given a game is in progress with Alice and Bob
    And the top card is "Ace of Diamonds"
    And it is "Alice"'s turn
    When 30 seconds pass
    Then Alice should automatically draw 1 cards
    And the declared suit should default to "Diamonds"
    And the turn should return to Bob

  Scenario: A player manually draws a card instead of playing
    Given a game is in progress with Alice and Bob
    And it is "Alice"'s turn
    When "Alice" chooses to draw
    Then Alice should automatically draw 1 cards
    And the turn should return to Bob

  Scenario: A player manually accepts an accumulated penalty stack
    Given a game is in progress with Alice and Bob
    And Alice just played a "Jack of Spades"
    And it is "Bob"'s turn
    When "Bob" chooses to take the penalty
    Then Bob should automatically draw 5 cards
    And the accumulated penalty should be 0
    And the turn should return to Alice

  Scenario: The draw pile is empty and reshuffles upon drawing
    Given a game is in progress with Alice and Bob
    And the deck is empty
    And the discard pile has "2 of Hearts", "3 of Clubs", and "Ace of Spades"
    And it is "Alice"'s turn
    When "Alice" chooses to draw
    Then Alice should automatically draw 1 cards
    And the deck should contain 1 cards
    And the top card should be "Ace of Spades"
    And the turn should return to Bob

  Scenario: A player disconnects before the game starts
    Given a lobby has 3 players "Alice", "Bob", and "Charlie"
    When "Bob" disconnects from the lobby
    Then the lobby should have 2 players
    And "Bob" should not be in the lobby

  Scenario: A player disconnects mid-game
    Given a game is in progress with Alice and Bob
    When "Alice" disconnects from the lobby
    Then "Alice" should still be in the lobby
    And the lobby should have 2 players

  Scenario: The lobby resets when the last human player disconnects
    Given a lobby has only one player "Alice"
    And "Computer" is in the lobby
    When "Alice" disconnects from the lobby
    Then the lobby should automatically reset
    And the lobby should have 0 players

  Scenario: A player sends a nudge to another player
    Given a game is in progress with Alice and Bob
    When "Alice" sends a nudge to "Bob"
    Then "Alice" should have sent 1 nudges
    And "Bob" should receive a nudge notification