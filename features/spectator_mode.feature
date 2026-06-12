Feature: Spectator Mode and Demo Games

  Scenario: Human players remain as spectators when a Demo Game starts
    Given a lobby has a human player "Dave"
    When a Demo Game is started
    Then "Dave" should still be in the lobby
    And "Dave" should have 0 cards
    And the lobby should contain 3 bots
    
  Scenario: Spectators do not receive a loss when a match ends
    Given a lobby has active players "Alice" and "Bob"
    And the game has started
    When "Charlie" joins as a spectator
    And the game calculates league results with winner "Alice"
    Then "Alice" should have 1 win
    And "Bob" should have 1 loss
    And "Charlie" should have 0 losses