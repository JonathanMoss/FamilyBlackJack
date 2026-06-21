Feature: Bot Dialogue Personalities
  As a player
  I want AI bots to emit contextual dialogues
  So that the game feels interactive and lively

  Scenario: A bot plays a card and logs a play dialogue
    Given a lobby has players "Alice" and "Bender"
    And "Bender" is registered as a bot
    And the game has started
    And it is "Bender"'s turn
    When the bot "Bender" plays a valid card
    Then the game log should contain a dialogue message from "Bender"

  Scenario: A player nudges a bot and the bot responds
    Given a lobby has players "Alice" and "HAL 9000"
    And "HAL 9000" is registered as a bot
    And the game has started
    When "Alice" nudges "HAL 9000"
    Then the game log should contain a nudge dialogue message from "HAL 9000"
