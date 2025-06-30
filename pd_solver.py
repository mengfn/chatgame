from game import PrisonersDilemmaGame
from typing import List, Dict, Tuple
from llm import ask_llm  # Assuming you have an LLM interface

class StrictDominanceSolver:
    """
    Solver that iteratively eliminates strictly dominated strategies
    for a two-player one-shot game.
    """
    def __init__(self, game: PrisonersDilemmaGame, players: List[int] = None):
        self.game = game
        # Default players are 1 and 2
        self.players: List[int] = players or [1, 2]
        # Initialize remaining strategies
        self.strategies: Dict[int, List[str]] = {
            p: game.legal_actions(p) for p in self.players
        }
        # Record of eliminated strategies
        self.elimination_history: List[Tuple[int, str]] = []

    def run(self) -> Tuple[Dict[int, List[str]], List[Tuple[int, str]]]:
        """
        Perform iterative elimination of strictly dominated strategies.
        Returns remaining strategies and elimination sequence.
        """
        changed = True
        while changed:
            changed = False
            for p in self.players:
                dominated = self._find_dominated_for_player(p)
                for strategy in dominated:
                    self.strategies[p].remove(strategy)
                    self.elimination_history.append((p, strategy))
                    changed = True
        return self.strategies, self.elimination_history

    def _find_dominated_for_player(self, player: int) -> List[str]:
        opponents = [pl for pl in self.players if pl != player]
        if len(opponents) != 1:
            raise ValueError("Solver supports exactly 2 players.")
        opponent = opponents[0]
        own_strategies = self.strategies[player]
        opponent_strategies = self.strategies[opponent]
        dominated: List[str] = []
        for s in own_strategies:
            for t in own_strategies:
                if t == s:
                    continue
                if self._strictly_dominates(player, t, s, opponent_strategies):
                    dominated.append(s)
                    break
        return dominated

    def _strictly_dominates(
        self,
        player: int,
        strategy_t: str,
        strategy_s: str,
        opponent_strategies: List[str]
    ) -> bool:
        for opp_action in opponent_strategies:
            if player == 1:
                history_s = [(1, strategy_s), (2, opp_action)]
                history_t = [(1, strategy_t), (2, opp_action)]
                payoff_s = self.game.get_payoff(history_s)[0]
                payoff_t = self.game.get_payoff(history_t)[0]
            else:
                history_s = [(1, opp_action), (2, strategy_s)]
                history_t = [(1, opp_action), (2, strategy_t)]
                payoff_s = self.game.get_payoff(history_s)[1]
                payoff_t = self.game.get_payoff(history_t)[1]
            if payoff_t <= payoff_s:
                return False
        return True

# ===== LLM Integration =====

def chat_with_solver(
    suggestions: List[str],
    payoff_matrix: Dict[Tuple[str, str], Tuple[int, int]],
    player_id: int
) -> Tuple[str, str]:
    # Construct prompt with explicit format requirement
    prompt = build_prompt(suggestions, payoff_matrix, player_id)
    response = ask_llm(prompt)
    decision = parse_decision(response)
    return decision, response


def build_prompt(
    suggestions: List[str],
    payoff_matrix: Dict[Tuple[str, str], Tuple[int, int]],
    player_id: int
) -> str:
    # Extract player's payoffs
    player_payoffs = {actions: payoffs[player_id - 1]
                      for actions, payoffs in payoff_matrix.items()}
    # Instruct LLM to reply with 'Decision: C' or 'Decision: D' on the first line
    return (
        f"Player {player_id} available strategies: {suggestions}\n"
        f"Corresponding payoffs: {player_payoffs}\n"
        "Please respond EXACTLY with 'Decision: C' or 'Decision: D' on the first line,"  \
        " followed by a brief explanation."
    )


def parse_decision(text: str) -> str:
    # Expect first line to be 'Decision: X'
    first_line = text.splitlines()[0].strip()
    if first_line.lower().startswith('decision:'):
        parts = first_line.split(':', 1)
        if len(parts) > 1:
            decision = parts[1].strip().upper()
            if decision in ['C', 'D']:
                return decision
    raise ValueError(
        "Unable to parse decision. Ensure the first line is 'Decision: C' or 'Decision: D'."
    )
