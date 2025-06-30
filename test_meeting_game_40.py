
import re
from typing import List
from game import MeetingGame40, typedef, SLOTS
from mg40_solver import MCCFRSolver, chat_with_solver, is_agreement


if __name__ == "__main__":
    # Example for 3 players
    players = [1,2,3]
    valuations = {
        p: {s: float((i + p) % 5 + 1) for i, s in enumerate(SLOTS)}
        for p in players
    }
    # availability: round-robin halves
    availability = {
        1: SLOTS[:15],
        2: SLOTS[10:30],
        3: SLOTS[25:]
    }
    game = MeetingGame40(players, valuations, availability, 5)

    solver = MCCFRSolver(game, iterations=2)
    solver.train()
    avg_strategy = solver.get_avg_strategy()

    history: List[typedef] = []
    agreed = False
    for turn in range(game.max_proposals):
        player = players[turn % len(players)]
        reply = chat_with_solver(history, avg_strategy, game, player)
        print(f"Player {player} -> {reply}\n")
        m = re.search(r"^Proposed-Date:\s*(.+)$", reply, re.MULTILINE)
        if not m:
            raise ValueError(f"Cannot parse proposal from:\n{reply}")
        proposed = m.group(1).strip()
        if proposed not in SLOTS:
            raise ValueError(f"Invalid slot: {proposed}")
        history.append((player, proposed))
        # check unanimous last cycle
        if game.is_terminal(history) and is_agreement(history, players):
            print(f"Agreement reached on {proposed}")
            agreed = True
            break
    print("Final history:", history)
    if not agreed:
        print("No agreement reached.")
