import pyspiel

from .config import (
        get_meeting_scheduling_config, 
        get_action_space_size,
        encode_time_segment_action,
        decode_time_segment_action,
        TimeSegment,
        generate_all_possible_time_segments
    )


class MultiPlayerMeetingState(pyspiel.State):
    
    
    def __init__(self, game, preferences, valuations):
        super().__init__(game)
        self.preferences = preferences  # {player: [TimeSegment, ...]}
        self.valuations = valuations    # {player: {(day, start, end): value}}
        self.config = get_meeting_scheduling_config()
        
        # Game state variables
        self._current_player = 0
        self._is_terminal = False
        self._turn_count = 0
        self._history = []
        self._player_responses = {}  # {player_id: response} for current proposal
        self._agreement_reached = False
        self._phase = "propose"  # "propose", "respond"
        self._proposing_player = 0
        self._current_proposal = None  # (day, start_time, end_time, duration)
        
    def current_player(self):
        """Return the current player to act"""
        return self._current_player
    
    def legal_actions(self, player=None):
        """Return legal actions for the current state"""
        if self._is_terminal:
            return []
        
        if self._phase == "propose":
            # Only allow proposals that are in the current player's preferences
            current_player_name = self.config["players"][self._current_player]
            player_segments = self.preferences[current_player_name]
            
            legal_proposal_actions = []
            for segment in player_segments:
                try:
                    action = encode_time_segment_action(segment.day, segment.start_time, segment.end_time)
                    legal_proposal_actions.append(action)
                except:
                    continue  # Skip invalid segments
            
            return legal_proposal_actions
        else:  # respond phase
            # Return accept/reject actions
            all_segments = generate_all_possible_time_segments()
            num_days = len(self.config["days"])
            action_space_size = num_days * len(all_segments)
            return [action_space_size, action_space_size + 1]  # accept, reject
    
    def apply_action(self, action):
        """Apply an action to the game state"""
        player_name = self.config["players"][self._current_player]
        
        if self._phase == "propose":
            day, start_time, end_time, duration = decode_time_segment_action(action)
            
            # Verify this proposal is in the player's preferences
            current_player_segments = self.preferences[player_name]
            is_valid_proposal = False
            proposed_segment_value = 0
            
            for segment in current_player_segments:
                if (segment.day == day and 
                    segment.start_time == start_time and 
                    segment.end_time == end_time):
                    is_valid_proposal = True
                    proposed_segment_value = segment.value
                    break
            
            if not is_valid_proposal:
                # This should not happen if legal_actions is implemented correctly
                print(f"Warning: Invalid proposal {day} {start_time}-{end_time} by {player_name}")
                return
            
            self._current_proposal = (day, start_time, end_time, duration)
            self._proposing_player = self._current_player
            
            # Format duration string
            duration_hours = duration // 60
            duration_mins = duration % 60
            if duration_mins == 0:
                duration_str = f"{duration_hours}h"
            else:
                duration_str = f"{duration_hours}h{duration_mins}m"
            
            self._history.append(
                f"{player_name} proposes {day} {start_time}-{end_time} ({duration_str}, value={proposed_segment_value})"
            )
            
            # Switch to response phase
            self._phase = "respond"
            self._player_responses = {}
            self._current_player = (self._current_player + 1) % 3
            
        else:  # respond phase
            all_segments = generate_all_possible_time_segments()
            num_days = len(self.config["days"])
            action_space_size = num_days * len(all_segments)
            
            if action == action_space_size:  # accept
                self._player_responses[self._current_player] = "accept"
                self._history.append(f"{player_name} accepts")
            else:  # reject
                self._player_responses[self._current_player] = "reject" 
                self._history.append(f"{player_name} rejects")
            
            # Check if all non-proposing players have responded
            if len(self._player_responses) == 2:  # 2 other players
                self._evaluate_responses()
            else:
                # Move to next player to respond
                self._current_player = (self._current_player + 1) % 3
                # Skip the proposing player
                if self._current_player == self._proposing_player:
                    self._current_player = (self._current_player + 1) % 3
    
    def _evaluate_responses(self):
        """Evaluate all responses and determine next phase"""
        accepts = sum(1 for response in self._player_responses.values() if response == "accept")
        
        if accepts == 2:  # All other players accepted
            self._agreement_reached = True
            self._is_terminal = True
            day, start_time, end_time, duration = self._current_proposal
            self._history.append(f"Agreement reached: {day} {start_time}-{end_time}")
        else:
            # No agreement, continue to next round
            self._turn_count += 1
            
            if self._turn_count >= self.config["max_turns"]:
                self._is_terminal = True
                self._history.append("Maximum turns reached - no agreement")
            else:
                # Move to next proposer
                self._phase = "propose" 
                self._current_player = (self._proposing_player + 1) % 3
    
    def is_terminal(self):
        """Check if the game has ended"""
        return self._is_terminal
    
    def returns(self):
        """Return the utilities for all players"""
        if not self._is_terminal:
            return [0.0, 0.0, 0.0]
        
        if self._agreement_reached and self._current_proposal:
            day, start_time, end_time, duration = self._current_proposal
            returns = []
            
            for player in self.config["players"]:
                # Find the value for this player based on their preferred segments
                player_value = 0.0
                player_segments = self.preferences[player]
                
                for segment in player_segments:
                    # Check if the agreed meeting is exactly this segment
                    if (segment.day == day and 
                        segment.start_time == start_time and 
                        segment.end_time == end_time):
                        player_value = float(segment.value)
                        break
                    # Check if the agreed meeting is contained within this segment
                    elif (segment.day == day and 
                          segment.start_time <= start_time and 
                          segment.end_time >= end_time):
                        player_value = float(segment.value)
                        break
                    # Check for partial overlap (less ideal)
                    elif (segment.day == day and 
                          segment.start_time < end_time and 
                          segment.end_time > start_time):
                        # Partial overlap - use proportional value
                        overlap_duration = min(
                            self._time_to_minutes(segment.end_time),
                            self._time_to_minutes(end_time)
                        ) - max(
                            self._time_to_minutes(segment.start_time),
                            self._time_to_minutes(start_time)
                        )
                        segment_duration = (
                            self._time_to_minutes(segment.end_time) - 
                            self._time_to_minutes(segment.start_time)
                        )
                        if segment_duration > 0:
                            overlap_ratio = overlap_duration / segment_duration
                            player_value = float(segment.value * overlap_ratio)
                            break
                
                returns.append(player_value)
            
            return returns
        else:
            return [0.0, 0.0, 0.0]
    
    def _time_to_minutes(self, time_str):
        """Convert HH:MM to minutes since midnight"""
        hours, minutes = map(int, time_str.split(':'))
        return hours * 60 + minutes
    
    def _decode_proposal_action(self, action):
        """Decode proposal action for display purposes"""
        try:
            day, start_time, end_time, duration = decode_time_segment_action(action)
            return day, f"{start_time}-{end_time}"
        except:
            return "Unknown", "Unknown"
    
    def information_state_string(self, player):
        """Return information state string for a player"""
        player_name = self.config["players"][player]
        
        # Show player's preferred time segments (limited for readability)
        preferred_segments = []
        if player_name in self.preferences:
            for segment in self.preferences[player_name][:8]:  # Limit to 8 for readability
                preferred_segments.append(str(segment))
        
        state_info = {
            "player": player_name,
            "phase": self._phase,
            "turn": self._turn_count,
            "current_proposal": self._current_proposal,
            "preferred_segments": preferred_segments,
            "recent_history": self._history[-5:] if len(self._history) > 5 else self._history,
            "proposing_player": self._proposing_player if self._phase == "respond" else None,
            "player_responses": dict(self._player_responses) if self._phase == "respond" else None
        }
        
        return str(state_info)
    
    def observation_string(self, player):
        """Return observation string for a player"""
        return self.information_state_string(player)
    
    def clone(self):
        """Create a deep copy of the current state"""
        new_state = MultiPlayerMeetingState(self.get_game(), self.preferences, self.valuations)
        new_state._current_player = self._current_player
        new_state._is_terminal = self._is_terminal
        new_state._turn_count = self._turn_count
        new_state._history = list(self._history)
        new_state._player_responses = dict(self._player_responses)
        new_state._agreement_reached = self._agreement_reached
        new_state._phase = self._phase
        new_state._proposing_player = self._proposing_player
        new_state._current_proposal = self._current_proposal
        return new_state
    
    def get_game_history(self):
        """Get the complete game history"""
        return list(self._history)
    
    def get_proposal_details(self):
        """Get details about the current proposal"""
        if self._current_proposal:
            day, start_time, end_time, duration = self._current_proposal
            return {
                "day": day,
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "proposing_player": self.config["players"][self._proposing_player]
            }
        return None

class MultiPlayerMeetingGame(pyspiel.Game):
    """3-player meeting scheduling game with 24-hour time segment preferences"""
    
    def __init__(self, preferences, valuations):
        self.preferences = preferences
        self.valuations = valuations
        
        config = get_meeting_scheduling_config()
        action_space_size = get_action_space_size()
        
        game_type = pyspiel.GameType(
            short_name="24h_meeting_scheduling",
            long_name="Multi-Player 24-Hour Meeting Scheduling with Time Segment Preferences",
            dynamics=pyspiel.GameType.Dynamics.SEQUENTIAL,
            chance_mode=pyspiel.GameType.ChanceMode.DETERMINISTIC,
            information=pyspiel.GameType.Information.IMPERFECT_INFORMATION,
            utility=pyspiel.GameType.Utility.GENERAL_SUM,
            reward_model=pyspiel.GameType.RewardModel.TERMINAL,
            max_num_players=3,
            min_num_players=3,
            provides_information_state_string=True,
            provides_information_state_tensor=False,
            provides_observation_string=True,
            provides_observation_tensor=False,
            parameter_specification={},
            default_loadable=False,
            provides_factored_observation_string=False,
        )
        
        # Calculate max utility based on highest possible values
        max_segment_value = 10.0  # Maximum value a segment can have
        
        game_info = pyspiel.GameInfo(
            num_distinct_actions=action_space_size,
            max_chance_outcomes=0,
            num_players=3,
            min_utility=0.0,
            max_utility=max_segment_value,
            utility_sum=None,
            max_game_length=config["max_turns"] * 3 + 10  # Estimate max game length
        )
        
        super().__init__(game_type, game_info, {})
    
    def new_initial_state(self):
        """Create a new initial game state"""
        return MultiPlayerMeetingState(self, self.preferences, self.valuations)
    
    def get_preferences_summary(self):
        """Get a summary of player preferences"""
        summary = {}
        config = get_meeting_scheduling_config()
        
        for player in config["players"]:
            player_segments = self.preferences[player]
            summary[player] = {
                "num_segments": len(player_segments),
                "days_available": list(set(seg.day for seg in player_segments)),
                "time_ranges": [(seg.start_time, seg.end_time) for seg in player_segments],
                "avg_value": sum(seg.value for seg in player_segments) / len(player_segments) if player_segments else 0,
                "total_hours": sum(seg.duration_minutes for seg in player_segments) / 60
            }
        
        return summary
    
    def validate_game_setup(self):
        """Validate that the game is properly set up"""
        config = get_meeting_scheduling_config()
        
        # Check that all players have preferences
        for player in config["players"]:
            if player not in self.preferences:
                raise ValueError(f"Missing preferences for player {player}")
            if len(self.preferences[player]) == 0:
                raise ValueError(f"Player {player} has no time segment preferences")
        
        # Validate time segments
        for player, segments in self.preferences.items():
            for segment in segments:
                try:
                    from .config import validate_time_segment
                    validate_time_segment(segment.day, segment.start_time, segment.end_time)
                except Exception as e:
                    raise ValueError(f"Invalid segment for {player}: {segment} - {e}")
        
        return True

# Legacy compatibility
TimeSegmentMeetingState = MultiPlayerMeetingState
TimeSegmentMeetingGame = MultiPlayerMeetingGame