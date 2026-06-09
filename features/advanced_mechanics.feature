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

  Scenario: Executing a Queen Cascade with a penalty card
    Given a game is in progress with Alice, Bob, and Charlie
    And it is "Alice"'s turn
    And the top card is "Queen of Diamonds"
    And Alice has "2 of Hearts" and "8 of Hearts" in hand
    And Bob has "King of Spades" in hand
    And Charlie has "2 of Clubs" in hand
    When Alice executes a Queen Cascade on "Hearts"
    Then the accumulated penalty should be 2
    And "Alice" should have 0 cards left
    And "Charlie" should be the current player

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
    And "🤖 Computer" should have 7 cards