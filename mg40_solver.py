from typing import List, Tuple, Dict
from collections import defaultdict
from random import choices as _choices
from llm import ask_llm


# Define the meeting game for N players
typedef = Tuple[int, str]

# Sample-based MC-CFR solver for N-player
def product(iterable):
    p = 1.0
    for x in iterable:
        p *= x
    return p

def is_agreement(history, players):
    if len(history) < len(players):
        return False
    last_cycle = history[-len(players):]
    slots = [d for (_, d) in last_cycle]
    return len(set(slots)) == 1

class MCCFRSolver:
    def __init__(self, game, iterations: int = 2000):
        self.game = game
        self.iterations = iterations
        # regret_sum and strategy_sum per player info-set
        self.regret_sum = {p: defaultdict(lambda: {d: 0.0 for d in game.dates})
                           for p in game.players}
        self.strategy_sum = {p: defaultdict(lambda: {d: 0.0 for d in game.dates})
                             for p in game.players}

    def regret_matching(self, regrets: Dict[str, float], legal: List[str]) -> Dict[str, float]:
        pos = {a: max(regrets[a], 0.0) for a in legal}
        total = sum(pos.values())
        if total > 0:
            return {a: pos[a]/total for a in legal}
        return {a: 1.0/len(legal) for a in legal}

    def mc_cfr(self,
               history: List[typedef],
               p_reach: Dict[int, float],
               sampling_player: int) -> Tuple[float, ...]:
        # Terminal check
        if self.game.is_terminal(history):
            return self.game.get_payoff(history)

        # Determine current player by round-robin
        current = self.game.players[len(history) % len(self.game.players)]
        legal = self.game.legal_actions(current)
        info_set = (current, tuple(history))
        strategy = self.regret_matching(self.regret_sum[current][info_set], legal)

        # Sampling node vs. others
        if current == sampling_player:
            # Full expand for sampling player
            util = {}
            node_util = {p: 0.0 for p in self.game.players}
            for a in legal:
                next_hist = history + [(current, a)]
                # update reach probabilities
                p_next = p_reach.copy()
                p_next[current] *= strategy[a]
                payoffs = self.mc_cfr(next_hist, p_next, sampling_player)
                util[a] = payoffs[current - 1]
                for p_idx, payoff in zip(self.game.players, payoffs):
                    node_util[p_idx] += strategy[a] * payoff
            # Regret and strategy sum updates for sampling player
            opp_reach = product([p_reach[p] for p in self.game.players if p != current])
            for a in legal:
                r = util[a] - node_util[current]
                self.regret_sum[current][info_set][a] += opp_reach * r
                self.strategy_sum[current][info_set][a] += p_reach[current] * strategy[a]
            # return expected payoffs
            return tuple(node_util[p] for p in self.game.players)
        else:
            # Sample an action for non-sampling players
            probs = [strategy[a] for a in legal]
            a = _choices(legal, probs)[0]
            next_hist = history + [(current, a)]
            p_reach_next = p_reach.copy()
            p_reach_next[current] *= strategy[a]
            return self.mc_cfr(next_hist, p_reach_next, sampling_player)

    def train(self):
        # initialize reach proba
        for i in range(self.iterations):
            sp = self.game.players[i % len(self.game.players)]
            # fresh reach probabilities
            p0 = {p: 1.0 for p in self.game.players}
            self.mc_cfr([], p0, sp)

    def get_avg_strategy(self) -> Dict[int, Dict[Tuple, Dict[str, float]]]:
        avg = {p: {} for p in self.game.players}
        for p in self.game.players:
            for I, strat_sum in self.strategy_sum[p].items():
                legal = self.game.legal_actions(p)
                total = sum(strat_sum[a] for a in legal)
                if total > 0:
                    avg[p][I] = {a: strat_sum[a]/total for a in legal}
                else:
                    avg[p][I] = {a: 1.0/len(legal) for a in legal}
        return avg

# Helpers for sampling and uniform fallback
def uniform_strategy(legal: List[str]) -> Dict[str, float]:
    return {a: 1.0/len(legal) for a in legal}

def sample_from_strategy(strategy: Dict[str, float]) -> str:
    actions, probs = zip(*strategy.items())
    return _choices(actions, probs)[0]

def build_prompt(
    history: List[typedef],
    times_avail: Dict[str, int],
    valuations: Dict[str, float],
    suggestion: str,
    player: int
) -> str:
    lines = ["History:"]
    for p, d in history:
        lines.append(f"  Player {p} proposed {d}")
    lines.append("\nYour availability:")
    for slot, avail in times_avail.items():
        lines.append(f"  {slot}: {'Yes' if avail else 'No'}")
    lines.append("\nYour valuations:")
    for slot, val in valuations.items():
        lines.append(f"  {slot}: {val}")
    lines.append(f"\nSolver guidance: propose {suggestion}")
    lines.append("\nIMPORTANT: Reply with exactly one line in the form:")
    lines.append("  Proposed-Date: <slot>")
    lines.append("and nothing else on that line.")
    return "\n".join(lines)

def chat_with_solver(
    history: List[typedef],
    avg_strategy: Dict[int, Dict[Tuple, Dict[str, float]]],
    game,
    player_id: int
) -> str:
    # prepare state
    times_avail = {s: int(all(h[1] != s for h in history)) for s in game.dates}
    valuations = game.valuations[player_id]
    I = (player_id, tuple(history))
    strat = avg_strategy[player_id].get(I, uniform_strategy(game.legal_actions(player_id)))
    suggestion = sample_from_strategy(strat)
    prompt = build_prompt(history, times_avail, valuations, suggestion, player_id)
    content = ask_llm(prompt, system_prompt="You are a strategic meeting assistant.")
    return content
