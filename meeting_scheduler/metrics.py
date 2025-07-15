import numpy as np

try:
    from .players import (
        MultiPlayerLLMPlayer, 
        MultiPlayerCFRGuidedLLMPlayer, 
        MultiPlayerCFRPlayer
    )
    from .solvers import ApproximateBestResponsePlayer
    from .config import get_meeting_scheduling_config
except ImportError:
    from players import (
        MultiPlayerLLMPlayer, 
        MultiPlayerCFRGuidedLLMPlayer, 
        MultiPlayerCFRPlayer
    )
    from solvers import ApproximateBestResponsePlayer
    from config import get_meeting_scheduling_config

def calculate_nash_conv(game, cfr_solver, num_samples=10, use_approximate=True, silent=False):
    """Calculate NashConv for 3-player game"""
    total_exploitability = 0
    
    if not silent:
        print("Computing Nash convergence...")
    
    for player in range(3):
        opponent_strategies = []
        for p in range(3):
            if p != player:
                opponent_strategies.append(cfr_solver)
            else:
                opponent_strategies.append(None)
        
        if use_approximate:
            best_response_player = ApproximateBestResponsePlayer(
                player, game, opponent_strategies, lookahead_depth=2
            )
        else:
            # For simplicity, fallback to approximate if exact is not available
            best_response_player = ApproximateBestResponsePlayer(
                player, game, opponent_strategies, lookahead_depth=3
            )
        
        best_response_values = []
        cfr_values = []
        
        for sample in range(num_samples):
            state = game.new_initial_state()
            
            br_value = simulate_game_with_best_response(state, player, best_response_player, cfr_solver)
            best_response_values.append(br_value)
            
            cfr_value = simulate_game_with_cfr(state, player, cfr_solver)
            cfr_values.append(cfr_value)
        
        player_exploitability = max(0, np.mean(best_response_values) - np.mean(cfr_values))
        total_exploitability += player_exploitability
    
    nash_conv = total_exploitability / 3
    return nash_conv

def simulate_game_with_best_response(initial_state, best_response_player_id, best_response_player, cfr_solver):
    """Simulate game with one best response player and two CFR players"""
    state = initial_state.clone()
    players = []
    
    for i in range(3):
        if i == best_response_player_id:
            players.append(best_response_player)
        else:
            players.append(MultiPlayerCFRPlayer(i, cfr_solver))
    
    step = 0
    max_steps = 20
    while not state.is_terminal() and step < max_steps:
        current_player = state.current_player()
        try:
            action = players[current_player].select_action(state)
            if action is not None:
                state.apply_action(action)
        except:
            break
        step += 1
    
    returns = state.returns()
    return returns[best_response_player_id]

def simulate_game_with_cfr(initial_state, target_player, cfr_solver):
    """Simulate game with all CFR players"""
    state = initial_state.clone()
    cfr_players = [MultiPlayerCFRPlayer(i, cfr_solver) for i in range(3)]
    
    step = 0
    max_steps = 20
    while not state.is_terminal() and step < max_steps:
        current_player = state.current_player()
        try:
            action = cfr_players[current_player].select_action(state)
            if action is not None:
                state.apply_action(action)
        except:
            break
        step += 1
    
    returns = state.returns()
    return returns[target_player]

def calculate_cfr_gain(game, cfr_solver, num_samples=10, silent=False):
    """Calculate CFR Gain comparing CFR-guided vs baseline LLM players"""
    config = get_meeting_scheduling_config()
    
    if not silent:
        print("Computing CFR gain...")
    
    # Baseline: three LLM players
    baseline_utilities = []
    for sample in range(num_samples):
        state = game.new_initial_state()
        players = [
            MultiPlayerLLMPlayer(0, config["players"][0]), 
            MultiPlayerLLMPlayer(1, config["players"][1]),
            MultiPlayerLLMPlayer(2, config["players"][2])
        ]
        
        step = 0
        while not state.is_terminal() and step < 20:
            current_player = state.current_player()
            try:
                action = players[current_player].select_action(state)
                if action is not None:
                    state.apply_action(action)
            except:
                break
            step += 1
        
        returns = state.returns()
        baseline_utilities.extend(returns)
    
    # CFR-guided: one CFR-guided player with two LLM players
    cfr_guided_utilities = []
    for sample in range(num_samples):
        state = game.new_initial_state()
        cfr_guided = MultiPlayerCFRGuidedLLMPlayer(0, config["players"][0], cfr_solver)
        baseline_players = [
            MultiPlayerLLMPlayer(1, config["players"][1]),
            MultiPlayerLLMPlayer(2, config["players"][2])
        ]
        players = [cfr_guided] + baseline_players
        
        step = 0
        while not state.is_terminal() and step < 20:
            current_player = state.current_player()
            try:
                action = players[current_player].select_action(state)
                if action is not None:
                    state.apply_action(action)
            except:
                break
            step += 1
        
        returns = state.returns()
        cfr_guided_utilities.append(returns[0])
    
    baseline_avg = np.mean(baseline_utilities)
    cfr_guided_avg = np.mean(cfr_guided_utilities)
    
    cfr_gain = cfr_guided_avg - baseline_avg
    return cfr_gain