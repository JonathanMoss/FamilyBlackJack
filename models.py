"""Pydantic schemas and types for the Family Blackjack application."""

from typing import Dict, List, Literal, Optional
from pydantic import BaseModel, Field

# Type aliases for strict validation
Suit = Literal['Hearts', 'Diamonds', 'Clubs', 'Spades']
Value = Literal[
    '2', '3', '4', '5', '6', '7', '8', '9', '10',
    'Jack', 'Queen', 'King', 'Ace'
]
PenaltyType = Literal['2', 'BJ']


class Card(BaseModel):
    """Represents a single playing card."""
    suit: Suit
    value: Value


class FamilyBlackjackState(BaseModel):
    """Pydantic model representing the state of the Family Blackjack Engine."""

    # Roster & Session Management
    players: List[str] = Field(
        default_factory=list, description="Ordered list of Unique Usernames"
    )
    sid_to_name: Dict[str, str] = Field(
        default_factory=dict,
        description="Maps active connection request.sid -> Name"
    )
    name_to_sid: Dict[str, str] = Field(
        default_factory=dict,
        description="Maps Username -> active connection sid"
    )

    # Gameplay Mechanics
    hands: Dict[str, List[Card]] = Field(
        default_factory=dict, description="Maps Username -> Card Array"
    )
    deck: List[Card] = Field(default_factory=list)
    discard_pile: List[Card] = Field(default_factory=list)
    current_turn_index: int = Field(default=0)
    direction: int = Field(default=1)
    is_started: bool = Field(default=False)
    match_dealer_index: int = Field(
        default=-1, description="Increments to 0 on match setup"
    )

    # Penalty & Wildcard Tracking
    active_penalty_type: Optional[PenaltyType] = Field(default=None)
    accumulated_penalty: int = Field(default=0)
    declared_ace_suit: Optional[Suit] = Field(default=None)
    penalty_source: Optional[str] = Field(
        default=None,
        description="Player who caused the accumulated penalty"
    )

    # Career League Standings Data
    league_wins: Dict[str, int] = Field(default_factory=dict)
    league_losses: Dict[str, int] = Field(default_factory=dict)
