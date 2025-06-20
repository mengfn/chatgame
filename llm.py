from openai import OpenAI
import os


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
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    completion = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[
            {"role":"system","content":"You are a strategic meeting assistant."},
            {"role":"user","content":prompt}
        ],
        temperature=0.7,
        max_tokens=512
    )
    return completion.choices[0].message.content
    
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


from random import choices as _choices

def sample_from_strategy(strategy, legal):
    actions, probs = zip(*strategy.items())
    return _choices(actions, probs)[0]