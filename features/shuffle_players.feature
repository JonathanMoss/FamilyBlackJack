Feature: Shuffle Players in Lobby

  Scenario: A player shuffles the lobby successfully
    Given a lobby has players "Alice", "Bob", and "Charlie"
    When "Alice" requests to shuffle the players
    Then the player order should be randomized
    And a game log message should announce the shuffle

  Scenario: A player cannot shuffle an active game
    Given a lobby has players "Alice", "Bob", and "Charlie"
    And the game has started
    When "Alice" requests to shuffle the players
    Then the shuffle should be rejected with an error message