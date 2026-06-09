Feature: First-card startup behavior
  As a Family Blackjack player
  I want the game to treat the initial discard card like a normal play card
  So that an Ace starter asks for suit choice and a 2 or black Jack starter applies a penalty

  Scenario: Ace starter prompts the first player for suit declaration
    Given a lobby has players "Alice" and "Bob"
    And the first discard card is "Ace of Spades"
    When the game starts
    Then the first player should be prompted to declare the active suit
    And the game should not have an active penalty

  Scenario: Two starter applies the +2 penalty to the first player
    Given a lobby has players "Alice" and "Bob"
    And the first discard card is "2 of Diamonds"
    When the game starts
    Then the first player should face a 2-card penalty
    And the penalty type should be "2"

  Scenario: Black Jack starter applies the +5 BJ penalty to the first player
    Given a lobby has players "Alice" and "Bob"
    And the first discard card is "Jack of Spades"
    When the game starts
    Then the first player should face a 5-card BJ penalty
    And the penalty type should be "BJ"

  Scenario: Red Jack starter does not apply a BJ penalty
    Given a lobby has players "Alice" and "Bob"
    And the first discard card is "Jack of Hearts"
    When the game starts
    Then the game should not have an active penalty

  Scenario: An 8 card as the starter card applies the miss-turn penalty to the first player
    Given a lobby has players "Alice" and "Bob"
    And the first discard card is "8 of Spades"
    When the game starts
    Then the first player "Bob" should be skipped
    And "Alice" should be the current player
  
