import numpy as np
from collections import defaultdict
import time
import signal

class MultiPlayerCFRSolver:
    """CFR Solver that supports multiple players (specifically 3 players) for 24-hour scheduling"""
    
    def __init__(self, game, num_players=3):
        self.game = game
        self.num_players = num_players
        self.regrets = defaultdict(lambda: defaultdict(float))
        self.strategy_sum = defaultdict(lambda: defaultdict(float))
        self.t = 0
        self.convergence_history = []
    
    def get_strategy(self, state, player):
        """Get current strategy for a player at given state"""
        info_state = state.information_state_string(player)
        legal_actions = state.legal_actions()
        
        if not legal_actions:
            return {}
        
        regret_sum = np.array([max(0, self.regrets[info_state][a]) for a in legal_actions])
        
        if regret_sum.sum() > 0:
            strategy = regret_sum / regret_sum.sum()
        else:
            strategy = np.ones(len(legal_actions)) / len(legal_actions)
        
        # Update strategy sum for average strategy calculation
        for i, action in enumerate(legal_actions):
            self.strategy_sum[info_state][action] += strategy[i]
        
        return {legal_actions[i]: strategy[i] for i in range(len(legal_actions))}
    
    def get_average_strategy(self, state, player):
        """Get average strategy for a player at given state"""
        info_state = state.information_state_string(player)
        legal_actions = state.legal_actions()
        
        if not legal_actions:
            return {}
        
        strategy_sum = np.array([self.strategy_sum[info_state][a] for a in legal_actions])
        
        if strategy_sum.sum() > 0:
            avg_strategy = strategy_sum / strategy_sum.sum()
        else:
            avg_strategy = np.ones(len(legal_actions)) / len(legal_actions)
        
        return {legal_actions[i]: avg_strategy[i] for i in range(len(legal_actions))}
    
    def cfr(self, state, reach_probs, max_depth=50):
        """CFR algorithm with depth limit to prevent infinite recursion"""
        if max_depth <= 0:
            # 达到最大深度，返回启发式评估
            if state.is_terminal():
                return state.returns()
            else:
                return [0.0] * self.num_players
        
        if state.is_terminal():
            return state.returns()
        
        current_player = state.current_player()
        info_state = state.information_state_string(current_player)
        legal_actions = state.legal_actions()
        
        if not legal_actions:
            return [0.0] * self.num_players
        
        # 限制动作数量，避免状态空间爆炸
        if len(legal_actions) > 20:
            # 随机采样部分动作
            import random
            legal_actions = random.sample(legal_actions, 20)
        
        strategy = self.get_strategy(state, current_player)
        action_utilities = {}
        
        # Calculate utility for each action
        for action in legal_actions:
            new_state = state.clone()
            try:
                new_state.apply_action(action)
                
                # Update reach probabilities
                new_reach_probs = reach_probs.copy()
                new_reach_probs[current_player] *= strategy.get(action, 0.0)
                
                action_utilities[action] = self.cfr(new_state, new_reach_probs, max_depth - 1)
            except Exception as e:
                # 动作执行失败，跳过
                action_utilities[action] = [0.0] * self.num_players
        
        # Calculate expected utility
        utility = [0.0] * self.num_players
        for action in legal_actions:
            action_prob = strategy.get(action, 0.0)
            if action in action_utilities:
                for player in range(self.num_players):
                    utility[player] += action_prob * action_utilities[action][player]
        
        # Update regrets for current player
        for action in legal_actions:
            if action in action_utilities:
                regret = action_utilities[action][current_player] - utility[current_player]
                
                # Compute counterfactual reach probability
                cfr_reach = 1.0
                for player in range(self.num_players):
                    if player != current_player:
                        cfr_reach *= reach_probs[player]
                
                self.regrets[info_state][action] += cfr_reach * regret
        
        return utility
        

    def train(self, iterations=1000, print_interval=100, silent=False, timeout=60):
        """Train the CFR solver with timeout protection"""
        if not silent:
            print(f"Training CFR ({iterations} iterations, timeout={timeout}s)")
        
        start_time = time.time()
        
        # 设置超时处理
        def timeout_handler(signum, frame):
            raise TimeoutError(f"CFR training timeout after {timeout} seconds")
        
        if timeout > 0:
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout)
        
        try:
            for iteration in range(iterations):
                iteration_start = time.time()
                
                if not silent and iteration % max(1, print_interval // 10) == 0:
                    elapsed = time.time() - start_time
                    print(f"  Iteration {iteration}/{iterations} (elapsed: {elapsed:.1f}s)")
                
                self.t += 1
                state = self.game.new_initial_state()
                initial_reach_probs = [1.0] * self.num_players
                
                try:
                    self.cfr(state, initial_reach_probs)
                except Exception as e:
                    if not silent:
                        print(f"  Warning: CFR iteration {iteration} failed: {e}")
                    continue
                
               
                iteration_time = time.time() - iteration_start
                if iteration_time > 5:  # 单次迭代超过5秒就警告
                    if not silent:
                        print(f"  Warning: Slow iteration {iteration}, took {iteration_time:.2f}s")
                
                # 每10次迭代检查一次收敛
                if iteration > 0 and iteration % 10 == 0:
                    avg_regret = self._calculate_average_regret()
                    self.convergence_history.append(avg_regret)
                    if not silent:
                        print(f"  Regret at iteration {iteration}: {avg_regret:.6f}")
                    
                   
                    if avg_regret < 0.001:
                        if not silent:
                            print(f"  Early convergence at iteration {iteration}")
                        break
            
            final_regret = self._calculate_average_regret()
            if not silent:
                total_time = time.time() - start_time
                print(f"Training completed! Regret: {final_regret:.6f}, Time: {total_time:.2f}s")
            
        except TimeoutError as e:
            if not silent:
                print(f"Training timeout: {e}")
        except KeyboardInterrupt:
            if not silent:
                print("Training interrupted by user")
        finally:
            if timeout > 0:
                signal.alarm(0)  # 取消超时
        
        return self.convergence_history


    def _calculate_average_regret(self):
        """Calculate average regret across all information states"""
        total_regret = 0
        count = 0
        
        for info_state, action_regrets in self.regrets.items():
            for action, regret in action_regrets.items():
                total_regret += max(0, regret)
                count += 1
        
        return total_regret / count if count > 0 else 0
    
    def get_strategy_profile(self, state):
        """Get strategy profile for all players at given state"""
        strategies = {}
        for player in range(self.num_players):
            strategies[player] = self.get_average_strategy(state, player)
        return strategies
    
    def analyze_convergence(self):
        """Analyze convergence properties"""
        if len(self.convergence_history) < 2:
            return {"status": "insufficient_data"}
        
        recent_regrets = self.convergence_history[-10:]
        if len(recent_regrets) < 5:
            return {"status": "insufficient_data"}
        
        trend = np.polyfit(range(len(recent_regrets)), recent_regrets, 1)[0]
        
        return {
            "status": "converged" if trend < 0 and recent_regrets[-1] < 0.01 else "converging",
            "final_regret": recent_regrets[-1],
            "trend": trend,
            "iterations": len(self.convergence_history)
        }

class BestResponseSolver:
    """Best response solver for multi-player 24-hour scheduling games"""
    
    def __init__(self, game, opponent_strategies):
        self.game = game
        self.opponent_strategies = opponent_strategies
        self.memo = {}
        self.computation_stats = {"states_evaluated": 0, "cache_hits": 0}
    
    def solve(self, state, player):
        """Find best response for a player given opponent strategies"""
        state_key = (state.information_state_string(player), player)
        
        if state_key in self.memo:
            self.computation_stats["cache_hits"] += 1
            return self.memo[state_key]
        
        self.computation_stats["states_evaluated"] += 1
        
        if state.is_terminal():
            returns = state.returns()
            result = returns[player]
            self.memo[state_key] = result
            return result
        
        if state.current_player() != player:
            # Other player's turn - use their strategy
            opponent = state.current_player()
            opponent_strategy = self.get_opponent_strategy(state, opponent)
            expected_value = 0.0
            
            for action, prob in opponent_strategy.items():
                if prob > 0:
                    new_state = state.clone()
                    new_state.apply_action(action)
                    expected_value += prob * self.solve(new_state, player)
            
            self.memo[state_key] = expected_value
            return expected_value
        else:
            # Current player's turn - find best action
            legal_actions = state.legal_actions()
            best_value = float('-inf')
            
            for action in legal_actions:
                new_state = state.clone()
                new_state.apply_action(action)
                value = self.solve(new_state, player)
                best_value = max(best_value, value)
            
            self.memo[state_key] = best_value
            return best_value
    
    def get_opponent_strategy(self, state, opponent):
        """Get strategy for an opponent player"""
        if opponent < len(self.opponent_strategies) and self.opponent_strategies[opponent] is not None:
            strategy_source = self.opponent_strategies[opponent]
            if hasattr(strategy_source, 'get_average_strategy'):
                return strategy_source.get_average_strategy(state, opponent)
        
        # Fallback to uniform random
        legal_actions = state.legal_actions()
        uniform_prob = 1.0 / len(legal_actions) if legal_actions else 0.0
        return {action: uniform_prob for action in legal_actions}
    
    def get_computation_stats(self):
        """Get statistics about the computation"""
        total_evaluations = self.computation_stats["states_evaluated"]
        cache_hits = self.computation_stats["cache_hits"]
        cache_hit_rate = cache_hits / (total_evaluations + cache_hits) if (total_evaluations + cache_hits) > 0 else 0
        
        return {
            "states_evaluated": total_evaluations,
            "cache_hits": cache_hits,
            "cache_hit_rate": cache_hit_rate,
            "memo_size": len(self.memo)
        }

class ExactBestResponsePlayer:
    """Player that computes exact best response against given strategies for 24-hour scheduling"""
    
    def __init__(self, player_id, game, opponent_strategies):
        self.player_id = player_id
        self.game = game
        self.opponent_strategies = opponent_strategies
        self.best_response_solver = BestResponseSolver(game, opponent_strategies)
        self.policy = {}
        self.computation_complete = False
    
    def compute_best_response_policy(self):
        """Pre-compute best response policy for all reachable states"""
        print(f"Computing best response policy for player {self.player_id}...")
        
        visited_states = set()
        states_to_visit = [self.game.new_initial_state()]
        states_processed = 0
        
        while states_to_visit:
            state = states_to_visit.pop(0)
            states_processed += 1
            
            if states_processed % 1000 == 0:
                print(f"  Processed {states_processed} states, {len(states_to_visit)} remaining")
            
            if state.is_terminal():
                continue
            
            info_state = state.information_state_string(self.player_id)
            
            if info_state in visited_states:
                continue
            
            visited_states.add(info_state)
            
            if state.current_player() == self.player_id:
                legal_actions = state.legal_actions()
                action_values = {}
                
                for action in legal_actions:
                    new_state = state.clone()
                    new_state.apply_action(action)
                    value = self.best_response_solver.solve(new_state, self.player_id)
                    action_values[action] = value
                
                if action_values:
                    best_action = max(action_values, key=action_values.get)
                    self.policy[info_state] = best_action
            
            # Add successor states
            for action in state.legal_actions():
                new_state = state.clone()
                new_state.apply_action(action)
                states_to_visit.append(new_state)
        
        self.computation_complete = True
        stats = self.best_response_solver.get_computation_stats()
        print(f"Best response computation complete:")
        print(f"  Policy entries: {len(self.policy)}")
        print(f"  States evaluated: {stats['states_evaluated']}")
        print(f"  Cache hit rate: {stats['cache_hit_rate']:.2%}")
    
    def select_action(self, state):
        """Select best response action for current state"""
        if state.current_player() != self.player_id:
            return None
        
        info_state = state.information_state_string(self.player_id)
        
        if info_state in self.policy:
            return self.policy[info_state]
        else:
            # Compute best action on the fly if not in pre-computed policy
            legal_actions = state.legal_actions()
            if not legal_actions:
                return None
                
            best_action = None
            best_value = float('-inf')
            
            for action in legal_actions:
                new_state = state.clone()
                new_state.apply_action(action)
                value = self.best_response_solver.solve(new_state, self.player_id)
                
                if value > best_value:
                    best_value = value
                    best_action = action
            
            return best_action
    
    def get_policy_summary(self):
        """Get summary of the computed policy"""
        if not self.computation_complete:
            return {"status": "computation_not_complete"}
        
        action_counts = {}
        for action in self.policy.values():
            action_counts[action] = action_counts.get(action, 0) + 1
        
        return {
            "status": "complete",
            "policy_size": len(self.policy),
            "action_distribution": action_counts,
            "computation_stats": self.best_response_solver.get_computation_stats()
        }

class ApproximateBestResponsePlayer:
    """Approximate best response player using limited lookahead for large state spaces"""
    
    def __init__(self, player_id, game, opponent_strategies, lookahead_depth=3):
        self.player_id = player_id
        self.game = game
        self.opponent_strategies = opponent_strategies
        self.lookahead_depth = lookahead_depth
        self.evaluations_performed = 0
    
    def select_action(self, state):
        """Select approximately best action using limited lookahead"""
        if state.current_player() != self.player_id:
            return None
        
        legal_actions = state.legal_actions()
        if not legal_actions:
            return None
        
        best_action = None
        best_value = float('-inf')
        
        for action in legal_actions:
            new_state = state.clone()
            new_state.apply_action(action)
            value = self._evaluate_state(new_state, self.lookahead_depth)
            
            if value > best_value:
                best_value = value
                best_action = action
        
        return best_action
    
    def _evaluate_state(self, state, depth):
        """Evaluate state using limited lookahead"""
        self.evaluations_performed += 1
        
        if state.is_terminal() or depth == 0:
            if state.is_terminal():
                returns = state.returns()
                return returns[self.player_id]
            else:
                # Use heuristic evaluation for non-terminal states at depth limit
                return self._heuristic_evaluation(state)
        
        current_player = state.current_player()
        
        if current_player == self.player_id:
            # Max node - choose best action for this player
            legal_actions = state.legal_actions()
            best_value = float('-inf')
            
            for action in legal_actions:
                new_state = state.clone()
                new_state.apply_action(action)
                value = self._evaluate_state(new_state, depth - 1)
                best_value = max(best_value, value)
            
            return best_value
        else:
            # Opponent node - use their strategy
            opponent_strategy = self._get_opponent_strategy(state, current_player)
            expected_value = 0.0
            
            for action, prob in opponent_strategy.items():
                if prob > 0:
                    new_state = state.clone()
                    new_state.apply_action(action)
                    value = self._evaluate_state(new_state, depth - 1)
                    expected_value += prob * value
            
            return expected_value
    
    def _heuristic_evaluation(self, state):
        """Heuristic evaluation for non-terminal states"""
        # Simple heuristic: estimate utility based on current proposal overlap
        if hasattr(state, '_current_proposal') and state._current_proposal:
            day, start_time, end_time, duration = state._current_proposal
            player_name = self.game.config["players"][self.player_id]
            player_segments = state.preferences[player_name]
            
            # Calculate overlap value
            from .players import MultiPlayerLLMPlayer
            llm_player = MultiPlayerLLMPlayer(self.player_id, player_name)
            overlap_info = llm_player._analyze_proposal_overlap(player_segments, day, start_time, end_time)
            
            return overlap_info["value"]
        
        return 0.0  # Neutral evaluation
    
    def _get_opponent_strategy(self, state, opponent):
        """Get strategy for an opponent player"""
        if opponent < len(self.opponent_strategies) and self.opponent_strategies[opponent] is not None:
            strategy_source = self.opponent_strategies[opponent]
            if hasattr(strategy_source, 'get_average_strategy'):
                return strategy_source.get_average_strategy(state, opponent)
        
        # Fallback to uniform random
        legal_actions = state.legal_actions()
        uniform_prob = 1.0 / len(legal_actions) if legal_actions else 0.0
        return {action: uniform_prob for action in legal_actions}
    
    def get_stats(self):
        """Get performance statistics"""
        return {
            "evaluations_performed": self.evaluations_performed,
            "lookahead_depth": self.lookahead_depth
        }

class MonteCarloTreeSearchPlayer:
    """MCTS player for 24-hour meeting scheduling"""
    
    def __init__(self, player_id, game, simulations=1000, exploration_constant=1.4):
        self.player_id = player_id
        self.game = game
        self.simulations = simulations
        self.exploration_constant = exploration_constant
        self.node_stats = {}  # {state_key: {"visits": int, "value": float, "children": dict}}
    
    def select_action(self, state):
        """Select action using MCTS"""
        if state.current_player() != self.player_id:
            return None
        
        legal_actions = state.legal_actions()
        if not legal_actions:
            return None
        
        if len(legal_actions) == 1:
            return legal_actions[0]
        
        root_key = self._get_state_key(state)
        
        # Run MCTS simulations
        for _ in range(self.simulations):
            self._simulate(state.clone())
        
        # Select best action based on visit count
        if root_key in self.node_stats:
            children = self.node_stats[root_key].get("children", {})
            best_action = None
            best_visits = -1
            
            for action in legal_actions:
                action_key = str(action)
                if action_key in children:
                    visits = children[action_key]["visits"]
                    if visits > best_visits:
                        best_visits = visits
                        best_action = action
            
            if best_action is not None:
                return best_action
        
        # Fallback to random selection
        return np.random.choice(legal_actions)
    
    def _simulate(self, state):
        """Run one MCTS simulation"""
        path = []
        
        # Selection and expansion
        while not state.is_terminal():
            state_key = self._get_state_key(state)
            path.append((state_key, state.current_player()))
            
            if state_key not in self.node_stats:
                # Initialize new node
                self.node_stats[state_key] = {"visits": 0, "value": 0.0, "children": {}}
                break
            
            # Select action
            if state.current_player() == self.player_id:
                action = self._select_action_ucb(state)
            else:
                # Random action for opponents in simulation
                legal_actions = state.legal_actions()
                action = np.random.choice(legal_actions) if legal_actions else None
            
            if action is None:
                break
            
            state.apply_action(action)
        
        # Simulation (random rollout)
        while not state.is_terminal():
            legal_actions = state.legal_actions()
            if not legal_actions:
                break
            action = np.random.choice(legal_actions)
            state.apply_action(action)
        
        # Backpropagation
        returns = state.returns()
        value = returns[self.player_id] if len(returns) > self.player_id else 0
        
        for state_key, player in reversed(path):
            if state_key in self.node_stats:
                self.node_stats[state_key]["visits"] += 1
                self.node_stats[state_key]["value"] += (value - self.node_stats[state_key]["value"]) / self.node_stats[state_key]["visits"]
    
    def _select_action_ucb(self, state):
        
        state_key = self._get_state_key(state)
        legal_actions = state.legal_actions()
        
        if state_key not in self.node_stats:
            return np.random.choice(legal_actions)
        
        node = self.node_stats[state_key]
        best_action = None
        best_ucb = float('-inf')
        
        for action in legal_actions:
            action_key = str(action)
            
            if action_key not in node["children"]:
                # Unvisited action gets high priority
                return action
            
            child = node["children"][action_key]
            if child["visits"] == 0:
                ucb_value = float('inf')
            else:
                exploitation = child["value"]
                exploration = self.exploration_constant * np.sqrt(np.log(node["visits"]) / child["visits"])
                ucb_value = exploitation + exploration
            
            if ucb_value > best_ucb:
                best_ucb = ucb_value
                best_action = action
        
        return best_action
    
    def _get_state_key(self, state):
        """Generate a key for state identification"""
        return hash(state.information_state_string(self.player_id))

# Legacy aliases for compatibility
CFRSolver = MultiPlayerCFRSolver