from game import PrisonersDilemmaGame
from pd_solver import StrictDominanceSolver, chat_with_solver


if __name__ == "__main__":
    from typing import List, Tuple

    game = PrisonersDilemmaGame()
    solver = StrictDominanceSolver(game)
    strategies, elimination_history = solver.run()

    decisions: List[Tuple[int, str]] = []
    for player in [1, 2]:
        suggestions = strategies[player]
        decision, explanation = chat_with_solver(
            suggestions,
            game.payoff_matrix,
            player
        )
        print(f"Player {player} Decision: {decision}\nExplanation: {explanation}\n")
        decisions.append((player, decision))

    history = [(1, decisions[0][1]), (2, decisions[1][1])]
    final_payoff = game.get_payoff(history)
    print(f"Final Payoff: {final_payoff}")