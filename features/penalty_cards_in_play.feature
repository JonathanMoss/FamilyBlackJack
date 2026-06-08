Feature: Penalty cards and cancel cards in active gameplay
  As a Family Blackjack player
  I want penalty cards (2, Jack) played during the game to apply their effects
  So that stacking and canceling penalties creates strategic depth

  Scenario: Playing a 2 card during the game applies a +2 penalty
    Given a game is in progress with Alice and Bob
    And Alice has no active penalty
    When Alice plays a "2 of Hearts" as the last card
    Then the active penalty type should be "2"
    And the accumulated penalty should be 2
    And Bob should be unable to play without a 2 counter

  Scenario: Playing a black Jack during the game applies a +5 BJ penalty
    Given a game is in progress with Alice and Bob
    And Alice has no active penalty
    When Alice plays a "Jack of Spades" as the last card
    Then the active penalty type should be "BJ"
    And the accumulated penalty should be 5
    And Bob should be unable to play without a Jack counter

  Scenario: Playing a red Jack cancels an existing BJ penalty
    Given a game is in progress with Alice and Bob
    And Alice has an active BJ penalty of 5 cards
    When Bob plays a "Jack of Hearts" as the last card
    Then the active penalty should be cleared
    And the accumulated penalty should be 0

  Scenario: Playing a 2 when a 2 penalty exists accumulates to +4
    Given a game is in progress with Alice and Bob
    And Alice has an active 2 penalty of 2 cards
    When Bob plays a "2 of Diamonds" as the last card
    Then the active penalty type should be "2"
    And the accumulated penalty should be 4

  Scenario: Playing a black Jack when a BJ penalty exists accumulates to +10
    Given a game is in progress with Alice and Bob
    And Alice has an active BJ penalty of 5 cards
    When Bob plays a "Jack of Clubs" as the last card
    Then the active penalty type should be "BJ"
    And the accumulated penalty should be 10

  Scenario: Player fails to play without a penalty counter
    Given a game is in progress with Alice and Bob
    And Alice has an active 2 penalty of 2 cards
    And Bob's hand does not contain a 2
    When Bob attempts to play a non-penalty card
    Then the play should be rejected with message about counter requirement
    And the accumulated penalty should remain 2

  Scenario: Playing a penalty card as the only card in the hand applies the penalty
    Given a game is in progress with Alice and Bob
    And Bob has only one card remaining: "2 of Hearts"
    And Alice has no active penalty
    When Bob plays their final card "2 of Hearts"
    Then Bob should have no cards left
    And the active penalty type should be "2"
    And the accumulated penalty should be 2
    And Alice should face the penalty
