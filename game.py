from typing import List, Tuple, Dict

dates = ["Mon", "Tue", "Wed"]

class MeetingGame:
    def __init__(self, valuations, availability, max_rounds=3):
        self.dates = dates
        self.valuations = valuations            # dict: player -> {date: value}
        self.availability = availability        # dict: player -> [date,...]
        self.max_rounds = max_rounds
        self.max_proposals = max_rounds * 2

    def is_terminal(self, history):
        # terminal if agreement or rounds exhausted
        if len(history) >= 2 and history[-1][1] == history[-2][1]:
            return True
        if len(history) >= self.max_proposals:
            return True
        return False

    def get_payoff(self, history):
        # returns (u1,u2)
        if len(history) >= 2 and history[-1] == history[-2]:
            date = history[-1][1]
            return self.valuations[1][date], self.valuations[2][date]
        return 0, 0

    def legal_actions(self, player):
        return self.availability[player]
    

class PrisonersDilemmaGame:
    """
    One-shot Prisoner's Dilemma game with imperfect information:
    players choose simultaneously without observing the other's action.
    Actions: 'C' (cooperate) or 'D' (defect).
    """
    def __init__(self, payoff_matrix: Dict[Tuple[str, str], Tuple[int, int]] = None):
        self.actions: List[str] = ['C', 'D']
        # Default payoff matrix: (player1_payoff, player2_payoff)
        self.payoff_matrix = payoff_matrix or {
            ('C', 'C'): (3, 3),
            ('C', 'D'): (0, 5),
            ('D', 'C'): (5, 0),
            ('D', 'D'): (1, 1),
        }

    def legal_actions(self, player: int) -> List[str]:
        """Return the list of available actions for a player."""
        return self.actions.copy()

    def is_terminal(self, history: List[Tuple[int, str]]) -> bool:
        """Check if the game has reached its terminal state (two plays)."""
        return len(history) >= 2

    def get_payoff(self, history: List[Tuple[int, str]]) -> Tuple[int, int]:
        """Return the payoffs for both players given the history of actions."""
        if len(history) != 2:
            raise ValueError("History must contain exactly two actions.")
        _, action1 = history[0]
        _, action2 = history[1]
        return self.payoff_matrix[(action1, action2)]

    def get_info_set(self, player: int) -> Tuple[int]:
        """
        Return the information set identifier for a player.
        In a one-shot simultaneous game, the info set is just the player ID.
        """
        return (player,)
