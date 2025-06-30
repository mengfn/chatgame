from typing import List, Tuple, Dict
import datetime


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


# Generate 5 workdays × 8 hourly slots (09:00–17:00)
def next_workdays(start_date: datetime.date, n: int) -> List[datetime.date]:
    days = []
    d = start_date
    while len(days) < n:
        d += datetime.timedelta(days=1)
        if d.weekday() < 5:
            days.append(d)
    return days

def make_time_slots(start_date: datetime.date) -> List[str]:
    workdays = next_workdays(start_date, 5)
    hours = [f"{h:02d}:00-{h+1:02d}:00" for h in range(9, 17)]
    return [f"{d.strftime('%a %Y-%m-%d')} {slot}" for d in workdays for slot in hours]

SLOTS = make_time_slots(datetime.date.today())  # 40 slots
typedef = Tuple[int, str]
class MeetingGame40:
    def __init__(self,
                 players: List[int],
                 valuations: Dict[int, Dict[str, float]],
                 availability: Dict[int, List[str]],
                 max_rounds: int = 3):
        self.players = players
        self.dates = SLOTS
        self.valuations = valuations
        self.availability = availability
        self.max_rounds = max_rounds
        self.max_proposals = max_rounds * len(players)

    def is_terminal(self, history: List[typedef]) -> bool:
        if len(history) >= len(self.players):
            last_cycle = history[-len(self.players):]
            # unanimous slot and one proposal per player
            slots = [d for (_, d) in last_cycle]
            ppl   = [p for (p, _) in last_cycle]
            if len(set(ppl)) == len(self.players) and len(set(slots)) == 1:
                return True
        return len(history) >= self.max_proposals

    def get_payoff(self, history: List[typedef]) -> Tuple[float, ...]:
        if self.is_terminal(history):
            slot = history[-1][1]
            return tuple(self.valuations[p][slot] for p in self.players)
        return tuple(0.0 for _ in self.players)

    def legal_actions(self, player: int) -> List[str]:
        return self.availability[player]