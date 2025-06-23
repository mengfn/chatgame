from collections import defaultdict
from game import dates
from llm import ask_llm  # Assuming you have a module for LLM interactions


class CFRSolver:
    def __init__(self, game, iterations=5000):
        self.game = game
        self.iterations = iterations
        self.regret_sum = defaultdict(lambda: {d:0.0 for d in dates})
        self.strategy_sum = defaultdict(lambda: {d:0.0 for d in dates})

    def regret_matching(self, regrets, legal):
        pos = {a: max(regrets[a],0) for a in legal}
        total = sum(pos.values())
        if total>0:
            return {a:pos[a]/total for a in legal}
        return {a:1/len(legal) for a in legal}

    def cfr(self, history, p1, p2):
        if self.game.is_terminal(history):
            return self.game.get_payoff(history)
        player = 1 if len(history)%2==0 else 2
        I = (player, tuple(history))
        legal = self.game.legal_actions(player)
        strategy = self.regret_matching(self.regret_sum[I], legal)

        util = {}
        node_util = 0
        node_util_other = 0
        for a, prob in strategy.items():
            next_hist = history + [(player,a)]
            if player==1:
                u1,u2 = self.cfr(next_hist, p1*prob, p2)
            else:
                u1,u2 = self.cfr(next_hist, p1, p2*prob)
            util[a] = u1 if player==1 else u2
            node_util += prob * util[a]
            node_util_other += prob * (u2 if player==1 else u1)

        for a in legal:
            regret = util[a] - node_util
            opp_reach = p2 if player==1 else p1
            self.regret_sum[I][a] += opp_reach * regret
            self.strategy_sum[I][a] += (p1 if player==1 else p2) * strategy[a]

        return (node_util, node_util_other)

    def train(self):
        for _ in range(self.iterations):
            self.cfr([],1,1)

    def get_avg_strategy(self):
        avg = {}
        for I, strat_sum in self.strategy_sum.items():
            total = sum(strat_sum.values())
            if total>0:
                avg[I] = {a:strat_sum[a]/total for a in self.game.legal_actions(I[0])}
            else:
                legal = self.game.legal_actions(I[0])
                avg[I] = {a:1/len(legal) for a in legal}
        return avg
    
def build_prompt(times_available, day_vals, suggestion, sender="Bob", receiver="Suzy"):
    lines = []
    lines.append("Times Available:")
    lines += [f"{d}: {times_available[d]}" for d in times_available]
    lines.append("Day Valuations:")
    lines += [f"{d}: {day_vals[d]}" for d in day_vals]
    lines.append(f"Action: Propose {suggestion}")
    lines.append("############################")
    lines.append("Schedule Proposal Message:")
    lines.append(f"from: {sender}")
    lines.append(f"to: {receiver}")
    lines.append("############################")
    return "\n".join(lines)

def chat_with_solver(history, avg_strategy, game_state, player_id):
    # Prepare state for prompt
    ta = {d: (0 if any(h[1]==d for h in history) else 1) for d in game_state.dates}
    dv = game_state.valuations[player_id]
    info_set = (player_id, tuple(history))
    # Fallback to uniform if no precomputed strategy
    if info_set in avg_strategy:
        strategy = avg_strategy[info_set]
    else:
        legal = game_state.legal_actions(player_id)
        strategy = {a: 1/len(legal) for a in legal}
    suggestion = sample_from_strategy(strategy, game_state.legal_actions(player_id))
    # Dynamic sender/receiver swap
    if player_id == 1:
        sender, receiver = "Bob", "Suzy"
    else:
        sender, receiver = "Suzy", "Bob"
    prompt = build_prompt(ta, dv, suggestion, sender, receiver)
    content = ask_llm(prompt, system_prompt="You are a strategic meeting assistant.")
    return content
    
from random import choices as _choices

def sample_from_strategy(strategy, legal):
    actions, probs = zip(*strategy.items())
    return _choices(actions, probs)[0]