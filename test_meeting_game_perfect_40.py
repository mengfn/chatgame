
import re
from typing import List
from game import MeetingGamePerfect40, typedef, SLOTS
from mgp40_solver import MCTSSolver, chat_with_solver, is_agreement
import datetime


if __name__ == "__main__":
    def make_slots():
        days, d = [], datetime.date.today()
        while len(days) < 5:
            d += datetime.timedelta(days=1)
            if d.weekday() < 5:
                days.append(d)
        return [f"{day.strftime('%a %Y-%m-%d')} {h:02d}:00-{h+1:02d}:00"
                for day in days for h in range(9, 17)]

    slots = make_slots()
    # Example for 3 players
    players = [1,2,3]
    valuations = {
        p: {s: float((i + p) % 5 + 1) for i, s in enumerate(SLOTS)}
        for p in players
    }
    # availability: round-robin halves
    availability = {
        1: SLOTS[:20],
        2: SLOTS[10:30],
        3: SLOTS[15:]
    }
    game = MeetingGamePerfect40(players, slots, valuations, availability,
                       max_rounds=5, unanimous_bonus=100.0)
    solver = MCTSSolver(game, iterations=5000, c=1.4)
    best_path, payoff = solver.solve()
    solver_result = {}
    for p, slot in best_path:
        solver_result[p] = slot
        
    history: List[typedef] = []
    agreed = False
    for turn in range(game.max_proposals):
        player = players[turn % len(players)]
        reply = chat_with_solver(history, game, player, solver_result)
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
