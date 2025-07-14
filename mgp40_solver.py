from typing import List, Tuple, Dict
from collections import defaultdict
from random import choices as _choices
from llm import ask_llm
import random, math


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

# --- MCTS Solver for 完全信息博弈 ---
class MCTSNode:
    def __init__(self, history: List[typedef], parent=None):
        self.history = history
        self.parent = parent
        self.children: Dict[str, MCTSNode] = {}
        self.visits = 0
        self.total_value: Dict[int, float] = {}

class MCTSSolver:
    def __init__(self, game, iterations: int = 5000, c: float = 1.4):
        self.game = game
        self.iterations = iterations
        self.c = c

    def tree_policy(self, node: MCTSNode) -> MCTSNode:
        # 向下展开或选择直到终端
        while not self.game.is_terminal(node.history):
            current = self.game.players[len(node.history) % len(self.game.players)]
            legal = self.game.legal_actions(current)
            # 如果还有动作未扩展，先扩展一个
            if len(node.children) < len(legal):
                return self.expand(node, current, legal)
            # 否则按 UCT 选择子节点
            node = self.best_uct_child(node, current)
        return node

    def expand(self, node: MCTSNode, player: int, legal: List[str]) -> MCTSNode:
        for a in legal:
            if a not in node.children:
                new_hist = node.history + [(player, a)]
                child = MCTSNode(new_hist, parent=node)
                child.total_value = {p: 0.0 for p in self.game.players}
                node.children[a] = child
                return child
        raise RuntimeError("No untried actions to expand")

    def best_uct_child(self, node: MCTSNode, player: int) -> MCTSNode:
        best_score = -float('inf')
        best_child = None
        for a, child in node.children.items():
            Q = child.total_value[player] / (child.visits or 1)
            U = self.c * math.sqrt((2 * math.log(node.visits)) / (child.visits or 1))
            score = Q + U
            if score > best_score:
                best_score = score
                best_child = child
        return best_child

    def simulate(self, history: List[typedef]) -> Tuple[float, ...]:
        h = history[:]
        while not self.game.is_terminal(h):
            current = self.game.players[len(h) % len(self.game.players)]
            a = random.choice(self.game.legal_actions(current))
            h.append((current, a))
        return self.game.get_payoff(h)

    def backpropagate(self, node: MCTSNode, payoff: Tuple[float, ...]):
        while node is not None:
            node.visits += 1
            for i, p in enumerate(self.game.players):
                node.total_value[p] += payoff[i]
            node = node.parent

    def solve(self) -> Tuple[List[typedef], Tuple[float, ...]]:
        root = MCTSNode(history=[])
        root.total_value = {p: 0.0 for p in self.game.players}

        for _ in range(self.iterations):
            leaf = self.tree_policy(root)
            payoff = self.simulate(leaf.history)
            self.backpropagate(leaf, payoff)

        # 从根节点沿访问次数最多的路径输出结果
        path: List[typedef] = []
        node = root
        while node.children:
            node = max(node.children.values(), key=lambda c: c.visits)
            path.append(node.history[-1])
        final_payoff = self.game.get_payoff(path)
        return path, final_payoff


# Helpers for sampling and uniform fallback
def uniform_strategy(legal: List[str]) -> Dict[str, float]:
    return {a: 1.0/len(legal) for a in legal}

def sample_from_strategy(strategy: Dict[str, float]) -> str:
    actions, probs = zip(*strategy.items())
    return _choices(actions, probs)[0]

def build_prompt(
    history: List[typedef],
    all_avail: Dict[int, List[str]],
    all_vals: Dict[int, Dict[str, float]],
    suggestion: str,
    player: int
) -> str:
    """
    Construct a prompt for the LLM including:
      - the proposal history,
      - public availability for each player,
      - public valuations for each player,
      - optional solver guidance, and
      - strict reply format instructions.
    """
    lines = ["History:"]
    for p, d in history:
        lines.append(f"  Player {p} proposed {d}")
    
    # Public availability for all players
    lines.append("\nPublic availability:")
    for p, avail_list in all_avail.items():
        slots = ', '.join(avail_list)
        lines.append(f"  Player {p}: {slots}")

    # Public valuations for all players
    lines.append("\nPublic valuations:")
    for p, vals in all_vals.items():
        # Show only the top 3 highest-valued slots for brevity
        items = sorted(vals.items(), key=lambda x: -x[1])
        top_n = 3
        if top_n is not None:
            items = items[:top_n]
        formatted = ', '.join(f"{slot}({value})" for slot, value in items)
        lines.append(f"  Player {p}: {formatted}")
    
    # If the solver has a suggestion, include it
    if suggestion:
        lines.append(f"\nSolver guidance: propose {suggestion}")
    
    # Instruct the model to respond in the exact required format
    lines.append("\nIMPORTANT: Reply with exactly one line in the form:")
    lines.append("  Proposed-Date: <slot>")
    lines.append("and nothing else on that line.")
    return "\n".join(lines)

def chat_with_solver(
    history: List[typedef],
    game,
    player_id: int,
    solver = None,
) -> str:
    # prepare state
    if solver != None:
        suggestion = solver[player_id]
    else:
        suggestion = ""
    prompt = build_prompt(
        history,
        all_avail=game.availability,
        all_vals=game.valuations,
        suggestion=suggestion,
        player=player_id
    )
    content = ask_llm(prompt, system_prompt="You are a strategic meeting assistant.")
    return content