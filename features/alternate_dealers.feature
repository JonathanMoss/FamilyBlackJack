Feature: Each game rotates dealer and first player
  As a Family Blackjack player
  I want the game to rotate dealer and first players
  So that each player takes a turn being dealer and first player

Scenario: Game 1 selects the next player after the Dealer as starting player
  Given a lobby has 2 players "Alice" and "Bob"
  When the game starts
  Then Alice is selected as Dealer
  And Bob is selected as first player

Scenario: Game 2 rotates dealer to the other player
  Given a lobby has 2 players "Alice" and "Bob"
  When the game starts
  And the next game starts
  Then Bob is selected as Dealer after the second game
  And Alice is selected as first player after the second game

Scenario: Game 1 selects the next player after the Dealer in a 3-player lobby
  Given a lobby has 3 players "Alice", "Bob", and "Charlie"
  When the game starts
  Then Alice is selected as Dealer
  And Bob is selected as first player

Scenario: Game 2 rotates dealer to the next player in a 3-player lobby
  Given a lobby has 3 players "Alice", "Bob", and "Charlie"
  When the game starts
  And the next game starts
  Then Bob is selected as Dealer after the second game
  And Charlie is selected as first player after the second game

Scenario: Game 3 cycles dealer back to first player in a 2-player lobby
  Given a lobby has 2 players "Alice" and "Bob"
  When the game starts
  And the next game starts
  And the third game starts
  Then Alice is selected as Dealer after the third game
  And Bob is selected as first player after the third game

Scenario: Game 3 cycles dealer back to first player in a 3-player lobby
  Given a lobby has 3 players "Alice", "Bob", and "Charlie"
  When the game starts
  And the next game starts
  And the third game starts
  Then Charlie is selected as Dealer after the third game
  And Alice is selected as first player after the third game
