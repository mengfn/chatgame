from game import MeetingGame
from mg_solver import CFRSolver, chat_with_solver

# 1. Initialize game
valuations = {1:{"Mon":5,"Tue":0,"Wed":3}, 2:{"Mon":0,"Tue":4,"Wed":2}}
availability = {1:["Mon","Wed"], 2:["Tue","Wed"]}
game = MeetingGame(valuations, availability)

# 2. Train solver offline
solver = CFRSolver(game, iterations=5000)
solver.train()
avg_strat = solver.get_avg_strategy()

# 3. Run interactive session
history = []
agreed = False 
for turn in range(game.max_proposals):
    player = 1 if turn%2==0 else 2
    reply = chat_with_solver(history, avg_strat, game, player)
    print(f"Player {player} -> {reply}\n")
    # Parse proposed date from LLM reply and append to history
    proposed_date = None
    # simple keyword matching among game dates
    for date in game.dates:
        if date.lower() in reply.lower():
            proposed_date = date
            break
    if proposed_date:
        history.append((player, proposed_date))
         # explicit agreement check: last two proposals match and by different players
        if len(history) >= 2:
            last_player, last_date = history[-1]
            prev_player, prev_date = history[-2]
            if last_date == prev_date and last_player != prev_player:
                print(f"Agreement reached on {last_date}")
                agreed = True
                break
    else:
        # fallback: no valid date found
        raise ValueError(f"Unable to parse a valid date from LLM reply: '{reply}'")

# 4. Final outcome
print(history)
if not agreed:
    print("No agreement reached after max proposals.")
