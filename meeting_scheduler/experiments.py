import numpy as np
from .preferences import (
    PREFERENCE_GENERATORS, 
    FIXED_PREFERENCE_GENERATORS,
    RANDOM_PREFERENCE_GENERATORS,
    analyze_three_player_preferences, 
    generate_random_batch
)
from .game_core import MultiPlayerMeetingGame
from .solvers import MultiPlayerCFRSolver
from .players import (
    MultiPlayerLLMPlayer, 
    MultiPlayerCFRGuidedLLMPlayer, 
    MultiPlayerCFRPlayer
)
from .metrics import (
    calculate_nash_conv, 
    calculate_cfr_gain
)
from .config import get_meeting_scheduling_config, EXPERIMENT_CONFIG

def run_single_scenario_experiment(scenario_name, preference_generator, silent=False):
    """Run experiment on a single scenario"""
    
    if not silent:
        print(f"Scenario: {scenario_name}")
    
    preferences, valuations = preference_generator()
    analysis = analyze_three_player_preferences(preferences, valuations)
    
    if not silent:
        print(f"Complexity: {analysis['complexity']}, Options: {analysis['total_options']}")
    
    if analysis['total_options'] == 0:
        if not silent:
            print("❌ No meetings")
        return {
            "scenario": scenario_name,
            "analysis": analysis,
            "error": "No meetings"
        }
    
    game = MultiPlayerMeetingGame(preferences, valuations)
    cfr_solver = MultiPlayerCFRSolver(game, num_players=3)
    cfr_solver.train(iterations=EXPERIMENT_CONFIG['cfr_iterations'], silent=silent)
    
    nash_conv = cfr_gain = None
    try:
        nash_conv = calculate_nash_conv(game, cfr_solver, 
                                      num_samples=EXPERIMENT_CONFIG['nash_conv_samples'],
                                      use_approximate=True)
        cfr_gain = calculate_cfr_gain(game, cfr_solver, 
                                    num_samples=EXPERIMENT_CONFIG['cfr_gain_samples'])
        if not silent:
            print(f"Nash: {nash_conv:.4f}, CFR Gain: {cfr_gain:.4f}")
    except Exception as e:
        if not silent:
            print(f"Metrics failed: {e}")
    
    strategy_results = run_three_player_strategy_comparison(game, cfr_solver, silent=silent)
    
    return {
        "scenario": scenario_name,
        "analysis": analysis,
        "nash_conv": nash_conv,
        "cfr_gain": cfr_gain,
        "strategy_results": strategy_results
    }

def run_three_player_strategy_comparison(game, cfr_solver, silent=False):
    """Compare three core strategy types"""
    config = get_meeting_scheduling_config()
    
    strategies = {
        "LLM": lambda: [
            MultiPlayerLLMPlayer(0, config["players"][0]), 
            MultiPlayerLLMPlayer(1, config["players"][1]),
            MultiPlayerLLMPlayer(2, config["players"][2])
        ],
        "CFR": lambda: [
            MultiPlayerCFRPlayer(0, cfr_solver),
            MultiPlayerCFRPlayer(1, cfr_solver),
            MultiPlayerCFRPlayer(2, cfr_solver)
        ],
        "CFR-Guided": lambda: [
            MultiPlayerCFRGuidedLLMPlayer(0, config["players"][0], cfr_solver),
            MultiPlayerCFRGuidedLLMPlayer(1, config["players"][1], cfr_solver),
            MultiPlayerCFRGuidedLLMPlayer(2, config["players"][2], cfr_solver)
        ]
    }
    
    results = {}
    
    for strategy_name, strategy_factory in strategies.items():
        total_returns = [0, 0, 0]
        agreement_count = 0
        total_games = EXPERIMENT_CONFIG['strategy_comparison_games']
        
        for _ in range(total_games):
            state = game.new_initial_state()
            players = strategy_factory()
            
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
            for i in range(3):
                total_returns[i] += returns[i]
            
            if state._agreement_reached:
                agreement_count += 1
        
        avg_returns = [r/total_games for r in total_returns]
        agreement_rate = agreement_count / total_games
        total_utility = sum(avg_returns)
        
        results[strategy_name] = {
            "avg_returns": avg_returns,
            "agreement_rate": agreement_rate,
            "total_utility": total_utility
        }
        
        if not silent:
            print(f"{strategy_name}: {total_utility:.1f}, {agreement_rate:.1%}")
    
    return results

def run_comprehensive_experiment(silent=False):
    """Run comprehensive experiment across all fixed scenarios"""
    if not silent:
        print("Running comprehensive experiment...")
    
    all_results = []
    
    for scenario_name, preference_generator in FIXED_PREFERENCE_GENERATORS.items():
        try:
            result = run_single_scenario_experiment(scenario_name, preference_generator, silent=True)
            all_results.append(result)
        except Exception as e:
            if not silent:
                print(f"Error in {scenario_name}: {e}")
            continue
    
    random_scenarios = generate_random_batch(num_scenarios=3, scenario_type="mixed", seed=42)
    
    for scenario in random_scenarios:
        if scenario['analysis']['total_options'] == 0:
            continue
            
        def temp_generator():
            return scenario['preferences'], scenario['valuations']
        
        try:
            result = run_single_scenario_experiment(scenario['name'], temp_generator, silent=True)
            all_results.append(result)
        except:
            continue
    
    if not silent:
        generate_report(all_results)
    
    return all_results

def run_random_robustness_test(num_scenarios=10, scenario_type="mixed", seed=None, silent=False):
    
    if not silent:
        print(f"🧪 Testing {num_scenarios} scenarios...")
    
    scenarios = generate_random_batch(
        num_scenarios=num_scenarios, 
        scenario_type=scenario_type, 
        seed=seed
    )
    
    all_results = []
    successful_scenarios = 0
    
    for i, scenario in enumerate(scenarios):
        if not silent:
            print(f"\n{'='*60}")
            print(f"🎯 Scenario {i+1}/{num_scenarios}: {scenario['name']}")
            if scenario.get('seed'):
                print(f"   Seed: {scenario['seed']}")
            print(f"{'='*60}")
            
            # 显示每个玩家的详细偏好
            preferences = scenario['preferences']
            config = get_meeting_scheduling_config()
            
            print(f"👥 Player Preferences:")
            for player in config["players"]:
                segments = preferences[player]
                print(f"\n  🧑‍💼 {player} ({len(segments)} time segments):")
                
                # 按天分组显示
                segments_by_day = {}
                for segment in segments:
                    if segment.day not in segments_by_day:
                        segments_by_day[segment.day] = []
                    segments_by_day[segment.day].append(segment)
                
                for day in config["days"]:
                    if day in segments_by_day:
                        day_segments = sorted(segments_by_day[day], key=lambda s: s.start_time)
                        print(f"     📅 {day}:")
                        for j, segment in enumerate(day_segments):
                            duration_str = segment.format_duration()
                            print(f"        {j+1}. {segment.start_time}-{segment.end_time} "
                                  f"({duration_str}) -> Value: {segment.value}/10")
            
            # 显示场景分析
            analysis = scenario['analysis']
            print(f"\n📊 Scenario Analysis:")
            print(f"   Complexity: {analysis['complexity']}")
            print(f"   Total segments: {analysis['total_segments']}")
            print(f"   Possible meetings: {analysis['total_options']}")
            
            # 显示可能的会议
            if analysis.get('potential_meetings') and len(analysis['potential_meetings']) > 0:
                print(f"\n🤝 Possible Meeting Times (Top 5):")
                for j, meeting in enumerate(analysis['potential_meetings'][:5]):
                    print(f"   {j+1}. {meeting['day']} {meeting['start_time']}-{meeting['end_time']} "
                          f"(Total Value: {meeting['total_value']:.1f})")
                    print(f"      Individual Values: Alice={meeting['individual_values'][0]:.1f}, "
                          f"Bob={meeting['individual_values'][1]:.1f}, "
                          f"Charlie={meeting['individual_values'][2]:.1f}")
            else:
                print(f"\n❌ No feasible meeting times - Skipping scenario")
        
        if scenario['analysis']['total_options'] == 0:
            continue
        
        try:
            def temp_generator():
                return scenario['preferences'], scenario['valuations']
            
            if not silent:
                print(f"\n🚀 Running CFR training and strategy comparison...")
            
            result = run_single_scenario_experiment(scenario['name'], temp_generator, silent=True)
            all_results.append(result)
            successful_scenarios += 1
            
            if not silent:
                # 显示实验结果摘要
                print(f"\n📈 Experiment Results:")
                if result.get('nash_conv') is not None:
                    print(f"   Nash Convergence: {result['nash_conv']:.6f}")
                if result.get('cfr_gain') is not None:
                    print(f"   CFR Gain: {result['cfr_gain']:.6f}")
                
                # 显示策略对比结果
                if result.get('strategy_results'):
                    print(f"   Strategy Comparison:")
                    for strategy, metrics in result['strategy_results'].items():
                        print(f"     {strategy}: Utility={metrics['total_utility']:.1f}, "
                              f"Agreement={metrics['agreement_rate']:.1%}")
            
        except Exception as e:
            if not silent:
                print(f"❌ Scenario {i+1} failed: {e}")
            continue
        
        if not silent and (i + 1) % max(1, num_scenarios // 4) == 0:
            print(f"\n📊 Progress: {i + 1}/{num_scenarios} completed")
    
    if not silent:
        print(f"\n{'='*60}")
        print(f"🏁 Random Scenario Test Completed")
        print(f"{'='*60}")
        print(f"Successfully completed: {successful_scenarios}/{num_scenarios} scenarios")
        
        if all_results:
            nash_convs = [r.get('nash_conv') for r in all_results if r.get('nash_conv')]
            cfr_gains = [r.get('cfr_gain') for r in all_results if r.get('cfr_gain')]
            
            if nash_convs:
                print(f"\n🎯 Nash Convergence Statistics:")
                print(f"   Average: {np.mean(nash_convs):.6f} ± {np.std(nash_convs):.6f}")
                print(f"   Range: [{np.min(nash_convs):.6f}, {np.max(nash_convs):.6f}]")
                good_convergence = len([nc for nc in nash_convs if nc < 0.01])
                print(f"   Well-converged (<0.01): {good_convergence}/{len(nash_convs)} ({good_convergence/len(nash_convs):.1%})")
            
            if cfr_gains:
                print(f"\n📈 CFR Gain Statistics:")
                print(f"   Average: {np.mean(cfr_gains):.6f} ± {np.std(cfr_gains):.6f}")
                print(f"   Range: [{np.min(cfr_gains):.6f}, {np.max(cfr_gains):.6f}]")
                positive_gains = len([cg for cg in cfr_gains if cg > 0.1])
                print(f"   CFR Beneficial (>0.1): {positive_gains}/{len(cfr_gains)} ({positive_gains/len(cfr_gains):.1%})")
    
    return all_results


def run_mixed_experiment(silent=False):
    """Run mixed experiment with both fixed and random scenarios"""
    if not silent:
        print("Running mixed experiment...")
    
    all_results = []
    
    for scenario_name, preference_generator in FIXED_PREFERENCE_GENERATORS.items():
        try:
            result = run_single_scenario_experiment(scenario_name, preference_generator, silent=True)
            result['experiment_type'] = 'fixed'
            all_results.append(result)
        except:
            continue
    
    random_scenarios = generate_random_batch(num_scenarios=5, scenario_type="mixed", seed=42)
    
    for scenario in random_scenarios:
        if scenario['analysis']['total_options'] == 0:
            continue
            
        def temp_generator():
            return scenario['preferences'], scenario['valuations']
        
        try:
            result = run_single_scenario_experiment(scenario['name'], temp_generator, silent=True)
            result['experiment_type'] = 'random'
            all_results.append(result)
        except:
            continue
    
    if not silent:
        generate_report(all_results)
    
    return all_results

def run_detailed_game_analysis(scenario_name="random_24h", seed=42, silent=False):
    """Run detailed analysis of a specific scenario"""
    if not silent:
        print(f"Detailed analysis: {scenario_name}")
    
    if scenario_name in RANDOM_PREFERENCE_GENERATORS:
        preference_generator = lambda: RANDOM_PREFERENCE_GENERATORS[scenario_name](seed=seed)
    else:
        preference_generator = PREFERENCE_GENERATORS[scenario_name]
    
    preferences, valuations = preference_generator()
    analysis = analyze_three_player_preferences(preferences, valuations)
    
    if not silent:
        print(f"Complexity: {analysis['complexity']}")
        print(f"Options: {analysis['total_options']}")
    
    if analysis['total_options'] > 0:
        game = MultiPlayerMeetingGame(preferences, valuations)
        cfr_solver = MultiPlayerCFRSolver(game, num_players=3)
        cfr_solver.train(iterations=200, silent=silent)
        
        detailed_analysis = {}
        try:
            nash_conv = calculate_nash_conv(game, cfr_solver, num_samples=5, use_approximate=True)
            cfr_gain = calculate_cfr_gain(game, cfr_solver, num_samples=5)
            detailed_analysis = {"nash_conv": nash_conv, "cfr_gain": cfr_gain}
            
            if not silent:
                print(f"Nash: {nash_conv:.4f}, CFR Gain: {cfr_gain:.4f}")
        except Exception as e:
            if not silent:
                print(f"Metrics failed: {e}")
        
        return preferences, valuations, analysis, detailed_analysis
    
    return preferences, valuations, analysis

def generate_report(all_results):
    """Generate analysis report"""
    if not all_results:
        print("No results to analyze.")
        return
    
    valid_results = [r for r in all_results if r.get('analysis', {}).get('total_options', 0) > 0]
    
    print(f"\n📊 RESULTS SUMMARY")
    print(f"Valid scenarios: {len(valid_results)}/{len(all_results)}")
    
    if not valid_results:
        return
    
    nash_convs = [r.get('nash_conv') for r in valid_results if r.get('nash_conv') is not None]
    if nash_convs:
        print(f"\n🎯 Nash Convergence:")
        print(f"  Average: {np.mean(nash_convs):.4f}")
        print(f"  Range: [{np.min(nash_convs):.4f}, {np.max(nash_convs):.4f}]")
        good_convergence = len([nc for nc in nash_convs if nc < 0.01])
        print(f"  Well-converged: {good_convergence}/{len(nash_convs)} ({good_convergence/len(nash_convs):.1%})")
    
    cfr_gains = [r.get('cfr_gain') for r in valid_results if r.get('cfr_gain') is not None]
    if cfr_gains:
        print(f"\n📈 CFR Gain:")
        print(f"  Average: {np.mean(cfr_gains):.4f}")
        print(f"  Range: [{np.min(cfr_gains):.4f}, {np.max(cfr_gains):.4f}]")
        positive_gains = len([cg for cg in cfr_gains if cg > 0.1])
        print(f"  CFR beneficial: {positive_gains}/{len(cfr_gains)} ({positive_gains/len(cfr_gains):.1%})")
    
    strategy_performance = {}
    for result in valid_results:
        for strategy_name, metrics in result.get("strategy_results", {}).items():
            if strategy_name not in strategy_performance:
                strategy_performance[strategy_name] = {
                    'utilities': [],
                    'agreement_rates': []
                }
            strategy_performance[strategy_name]['utilities'].append(metrics.get("total_utility", 0))
            strategy_performance[strategy_name]['agreement_rates'].append(metrics.get("agreement_rate", 0))
    
    if strategy_performance:
        print(f"\n🏆 Strategy Performance:")
        for strategy, data in strategy_performance.items():
            avg_utility = np.mean(data['utilities'])
            avg_agreement = np.mean(data['agreement_rates'])
            print(f"  {strategy}: {avg_utility:.2f}, {avg_agreement:.1%}")