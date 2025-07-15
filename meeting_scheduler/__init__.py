from .config import get_meeting_scheduling_config, get_action_space_size, EXPERIMENT_CONFIG
from .preferences import (
    generate_preferences, 
    generate_three_player_random_preferences,
    analyze_three_player_preferences,
    generate_random_batch,
    PREFERENCE_GENERATORS,
    FIXED_PREFERENCE_GENERATORS,
    RANDOM_PREFERENCE_GENERATORS
)
from .game_core import MultiPlayerMeetingGame, MultiPlayerMeetingState
from .solvers import MultiPlayerCFRSolver, BestResponseSolver
from .players import (
    MultiPlayerLLMPlayer,
    MultiPlayerCFRGuidedLLMPlayer, 
    MultiPlayerCFRPlayer,
    # Legacy aliases
    LLMPlayer,
    CFRGuidedLLMPlayer,
    CFRPlayer
)
from .metrics import (
    calculate_nash_conv,
    calculate_cfr_gain
)
from .experiments import (
    run_comprehensive_experiment,
    run_single_scenario_experiment,
    run_detailed_game_analysis,
    run_random_robustness_test,
    run_mixed_experiment,
    run_three_player_strategy_comparison
)

__all__ = [
    # Configuration
    'get_meeting_scheduling_config',
    'get_action_space_size',
    'EXPERIMENT_CONFIG',
    
    # Preference generation
    'generate_preferences',
    'generate_three_player_random_preferences',
    'analyze_three_player_preferences',
    'generate_random_batch',
    'PREFERENCE_GENERATORS',
    'FIXED_PREFERENCE_GENERATORS', 
    'RANDOM_PREFERENCE_GENERATORS',
    
    # Game core
    'MultiPlayerMeetingGame',
    'MultiPlayerMeetingState',
    
    # Solvers
    'MultiPlayerCFRSolver',
    'BestResponseSolver',
    
    # Players
    'MultiPlayerLLMPlayer',
    'MultiPlayerCFRGuidedLLMPlayer',
    'MultiPlayerCFRPlayer',
    'LLMPlayer',
    'CFRGuidedLLMPlayer',
    'CFRPlayer',
    
    # Metrics
    'calculate_nash_conv',
    'calculate_cfr_gain',
    
    # Experiments
    'run_comprehensive_experiment',
    'run_single_scenario_experiment',
    'run_detailed_game_analysis',
    'run_random_robustness_test',
    'run_mixed_experiment',
    'run_three_player_strategy_comparison'
]



def get_package_info():
    """Get package information"""
    return {
        "version": __version__,
        "description": __description__,
        "core_players": ["LLM", "CFR", "CFR-Guided"],
        "core_metrics": ["Nash Convergence", "CFR Gain"]
    }


def demo():
    """Quick demo"""
    print("Meeting Scheduler Demo")
    
    preferences, valuations = create_simple_scenario()
    
    config = get_meeting_scheduling_config()
    for player, segments in preferences.items():
        print(f"{player}: {len(segments)} segments")
        if segments:
            print(f"  Sample: {segments[0]}")
    
    analysis = analyze_three_player_preferences(preferences, valuations)
    print(f"Complexity: {analysis['complexity']}")
    print(f"Options: {analysis['total_options']}")
    
    if analysis['potential_meetings']:
        best = analysis['potential_meetings'][0]
        print(f"Best: {best['day']} {best['start_time']}-{best['end_time']}")
    
    return preferences, valuations, analysis

def create_simple_scenario():
    """Create simple demo scenario"""
    from .config import TimeSegment
    
    preferences = {
        "Alice": [
            TimeSegment("Monday", "07:00", "08:30", 9),
            TimeSegment("Monday", "10:00", "12:00", 8),
            TimeSegment("Tuesday", "08:00", "10:00", 8),
        ],
        "Bob": [
            TimeSegment("Monday", "11:00", "13:00", 7),
            TimeSegment("Monday", "15:30", "18:00", 9),
            TimeSegment("Tuesday", "13:00", "15:30", 8),
        ],
        "Charlie": [
            TimeSegment("Monday", "10:30", "12:30", 8),
            TimeSegment("Tuesday", "09:00", "11:00", 6),
            TimeSegment("Tuesday", "14:00", "16:00", 8),
        ]
    }
    
    valuations = {}
    for player, segments in preferences.items():
        player_valuations = {}
        for segment in segments:
            key = (segment.day, segment.start_time, segment.end_time)
            player_valuations[key] = segment.value
        valuations[player] = player_valuations
    
    return preferences, valuations

def get_available_scenarios():
    """Get available scenarios"""
    return {
        "fixed": list(FIXED_PREFERENCE_GENERATORS.keys()),
        "random": list(RANDOM_PREFERENCE_GENERATORS.keys()),
        "all": list(PREFERENCE_GENERATORS.keys())
    }

# Legacy compatibility
generate_three_player_random_preferences_24h = generate_three_player_random_preferences
analyze_three_player_preferences_24h = analyze_three_player_preferences