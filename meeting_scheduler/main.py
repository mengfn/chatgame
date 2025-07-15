"""Meeting Scheduler (Clean Version)"""
import argparse
import sys

try:
    from .experiments import (
        run_comprehensive_experiment, 
        run_single_scenario_experiment,
        run_detailed_game_analysis,
        run_random_robustness_test,
        run_mixed_experiment
    )
    from .preferences import PREFERENCE_GENERATORS, generate_three_player_random_preferences
    from .config import EXPERIMENT_CONFIG
    from .game_core import MultiPlayerMeetingGame
    from .solvers import MultiPlayerCFRSolver
except ImportError:
    from experiments import (
        run_comprehensive_experiment, 
        run_single_scenario_experiment,
        run_detailed_game_analysis,
        run_random_robustness_test,
        run_mixed_experiment
    )
    from preferences import PREFERENCE_GENERATORS, generate_three_player_random_preferences
    from config import EXPERIMENT_CONFIG
    from game_core import MultiPlayerMeetingGame
    from solvers import MultiPlayerCFRSolver

def main():
    parser = argparse.ArgumentParser(description='Meeting Scheduler')
    
    parser.add_argument('--mode', 
                       choices=['comprehensive', 'single', 'detailed', 'random', 'mixed', 'demo'], 
                       default='demo')
    parser.add_argument('--scenario', 
                       choices=list(PREFERENCE_GENERATORS.keys()),
                       default='random_24h')
    parser.add_argument('--num-scenarios', type=int, default=10)
    parser.add_argument('--random-type', 
                       choices=['mixed', 'busy', 'flexible'],
                       default='mixed')
    parser.add_argument('--seed', type=int, default=None)
    parser.add_argument('--quick', '-q', action='store_true')
    parser.add_argument('--silent', '-s', action='store_true')
    parser.add_argument('--iterations', type=int, default=None)
    parser.add_argument('--detailed', '-d', action='store_true')
    
    args = parser.parse_args()
    
    if args.quick:
            EXPERIMENT_CONFIG['cfr_iterations'] = 50
            EXPERIMENT_CONFIG['nash_conv_samples'] = 3
            EXPERIMENT_CONFIG['cfr_gain_samples'] = 3
            EXPERIMENT_CONFIG['strategy_comparison_games'] = 5
            if not args.silent:
                print("🚀 Using QUICK configuration")
                
    elif args.detailed:
            
            EXPERIMENT_CONFIG['cfr_iterations'] = 200
            EXPERIMENT_CONFIG['nash_conv_samples'] = 10
            EXPERIMENT_CONFIG['cfr_gain_samples'] = 10
            EXPERIMENT_CONFIG['strategy_comparison_games'] = 15
            EXPERIMENT_CONFIG['max_game_steps'] = 12
            if not args.silent:
                print("🔬 Using DETAILED configuration")
    
    if args.iterations:
        EXPERIMENT_CONFIG['cfr_iterations'] = args.iterations
    
    try:
        if args.mode == 'demo':
            run_demo(args.silent)
        elif args.mode == 'single':
            if args.scenario.startswith('random_') and args.seed:
                preference_generator = lambda: PREFERENCE_GENERATORS[args.scenario](seed=args.seed)
            else:
                preference_generator = PREFERENCE_GENERATORS[args.scenario]
            run_single_scenario_experiment(args.scenario, preference_generator, silent=args.silent)
        elif args.mode == 'random':
            run_random_robustness_test(
                num_scenarios=args.num_scenarios,
                scenario_type=args.random_type,
                seed=args.seed,
                silent=args.silent
            )
        elif args.mode == 'comprehensive':
            run_comprehensive_experiment(silent=args.silent)
        elif args.mode == 'mixed':
            run_mixed_experiment(silent=args.silent)
        elif args.mode == 'detailed':
            run_detailed_game_analysis(args.scenario, args.seed or 42, silent=args.silent)
        
        if not args.silent:
            print("✅ Done")
        return 0
        
    except KeyboardInterrupt:
        print("\n❌ Interrupted")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

def run_demo(silent=False):
    """Quick demo"""
    if not silent:
        print("Demo...")
    
    preferences, valuations = generate_three_player_random_preferences(seed=123)
    
    if not silent:
        total_segments = sum(len(segments) for segments in preferences.values())
        print(f"Generated: {total_segments} segments")
    
    game = MultiPlayerMeetingGame(preferences, valuations)
    cfr_solver = MultiPlayerCFRSolver(game, num_players=3)
    cfr_solver.train(iterations=EXPERIMENT_CONFIG['cfr_iterations'], silent=silent)

if __name__ == "__main__":
    sys.exit(main())