import random
import numpy as np

try:
    from .config import (
        client, 
        get_meeting_scheduling_config,
        decode_time_segment_action,
        encode_time_segment_action,
        generate_all_possible_time_segments,
        TimeSegment,
        time_to_minutes
    )
except ImportError:
    from config import (
        client, 
        get_meeting_scheduling_config,
        decode_time_segment_action,
        encode_time_segment_action,
        generate_all_possible_time_segments,
        TimeSegment,
        time_to_minutes
    )

class MultiPlayerLLMPlayer:
    """LLM Player for 3-player working hours meeting scheduling (9:00-17:00)"""
    
    def __init__(self, player_id, player_name):
        self.player_id = player_id
        self.player_name = player_name
    
    def select_action(self, state):
        """Select action using LLM reasoning"""
        legal_actions = state.legal_actions()
        if not legal_actions:
            return None
        
        prompt = self.build_prompt(state)
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are negotiating meeting times during working hours (10:00-17:00) with 2 other people. Be flexible and collaborative to reach agreements quickly."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=400
            )
            
            llm_response = response.choices[0].message.content.strip()
            return self.parse_response(llm_response, state)
            
        except Exception as e:
            return self.fallback_action(state)
    
    def build_prompt(self, state):
        """Build prompt for LLM based on current game state"""
        config = get_meeting_scheduling_config()
        player_segments = state.preferences[self.player_name]
        
        prompt = f"""You are {self.player_name} in a 3-person meeting scheduling negotiation.
Working hours: 10:00-17:00, Monday-Friday.

Your preferred meeting time segments:"""
        
        segments_by_day = {}
        for segment in player_segments:
            if segment.day not in segments_by_day:
                segments_by_day[segment.day] = []
            segments_by_day[segment.day].append(segment)
        
        for day, day_segments in sorted(segments_by_day.items()):
            prompt += f"\n  {day}:"
            for segment in sorted(day_segments, key=lambda s: s.start_time):
                prompt += f"\n    {segment.start_time}-{segment.end_time} (value: {segment.value}/10, {segment.format_duration()})"
        
        prompt += f"\n\nCurrent situation:\n- Phase: {state._phase}\n- Turn: {state._turn_count + 1}/{config['max_turns']}\n"
        
        if state._history:
            recent_history = state._history[-3:]
            prompt += f"- Recent moves:\n"
            for move in recent_history:
                prompt += f"  • {move}\n"
        
        if state._phase == "propose":
            prompt += f"""
You need to propose a meeting time from YOUR preferred segments above.
Consider:
- Your highest-value time segments
- What others might accept based on previous negotiations
- Be flexible - any reasonable overlap is good
- Time pressure: only {config['max_turns'] - state._turn_count} turns left!

Choose one of your preferred time segments and respond in the format:
'Day HH:MM-HH:MM' (e.g., 'Monday 09:15-11:00')

Your proposal must be exactly one of your preferred segments listed above."""
        else:
            day, start_time, end_time, duration = state._current_proposal
            proposer = config["players"][state._proposing_player]
            
            overlap_info = self._analyze_proposal_overlap(player_segments, day, start_time, end_time)
            
            duration_str = self._format_duration(duration)
            
            prompt += f"""
{proposer} proposed: {day} {start_time}-{end_time} ({duration_str})

Your analysis of this proposal:
{overlap_info['description']}

Consider:
- Your utility from this proposal: {overlap_info['value']:.1f}/10
- Time pressure: only {config['max_turns'] - state._turn_count} turns left!
- Getting ANY agreement is better than no agreement
- Be collaborative and flexible

Respond with 'accept' or 'reject'."""
        
        return prompt
    
    def _analyze_proposal_overlap(self, player_segments, day, start_time, end_time):
        """Analyze how a proposal overlaps with player's segments"""
        best_overlap = {"value": 0, "segment": None, "overlap_type": "none"}
        
        proposal_start = time_to_minutes(start_time)
        proposal_end = time_to_minutes(end_time)
        
        for segment in player_segments:
            if segment.day == day:
                seg_start = time_to_minutes(segment.start_time)
                seg_end = time_to_minutes(segment.end_time)
                
                if seg_start == proposal_start and seg_end == proposal_end:
                    return {
                        "value": segment.value,
                        "segment": segment,
                        "overlap_type": "exact",
                        "description": f"PERFECT MATCH with your {segment} - Maximum value!"
                    }
                
                elif seg_start <= proposal_start and seg_end >= proposal_end:
                    if segment.value > best_overlap["value"]:
                        best_overlap = {
                            "value": segment.value,
                            "segment": segment,
                            "overlap_type": "contained",
                            "description": f"FULLY COVERED by your {segment}"
                        }
                
                elif seg_start < proposal_end and seg_end > proposal_start:
                    overlap_start = max(seg_start, proposal_start)
                    overlap_end = min(seg_end, proposal_end)
                    overlap_duration = overlap_end - overlap_start
                    proposal_duration = proposal_end - proposal_start
                    
                    if overlap_duration > 0:
                        overlap_ratio = overlap_duration / proposal_duration
                        partial_value = segment.value * overlap_ratio
                        
                        if partial_value > best_overlap["value"]:
                            best_overlap = {
                                "value": partial_value,
                                "segment": segment,
                                "overlap_type": "partial",
                                "description": f"PARTIALLY OVERLAPS with your {segment} ({overlap_ratio:.1%} coverage)"
                            }
        
        if best_overlap["overlap_type"] == "none":
            return {
                "value": 0,
                "segment": None,
                "overlap_type": "none",
                "description": "NO OVERLAP with any of your preferred time segments"
            }
        
        return best_overlap
    
    def _format_duration(self, duration_minutes):
        """Format duration in minutes to readable string"""
        hours = duration_minutes // 60
        minutes = duration_minutes % 60
        
        if minutes == 0:
            return f"{hours}h"
        else:
            return f"{hours}h{minutes}m"
    
    def parse_response(self, response, state):
        """Parse LLM response into valid action"""
        config = get_meeting_scheduling_config()
        response = response.lower().strip()
        
        if state._phase == "propose":
            player_segments = state.preferences[self.player_name]
            
            for segment in player_segments:
                day_match = segment.day.lower() in response
                time_match = (segment.start_time in response and segment.end_time in response)
                
                if day_match and time_match:
                    try:
                        action = encode_time_segment_action(segment.day, segment.start_time, segment.end_time)
                        return action
                    except:
                        continue
            
            import re
            for day in config["days"]:
                if day.lower() in response:
                    time_pattern = r'(\d{1,2}):(\d{2})-(\d{1,2}):(\d{2})'
                    match = re.search(time_pattern, response)
                    
                    if match:
                        start_hour, start_min, end_hour, end_min = map(int, match.groups())
                        start_time = f"{start_hour:02d}:{start_min:02d}"
                        end_time = f"{end_hour:02d}:{end_min:02d}"
                        
                        for segment in player_segments:
                            if (segment.day == day and 
                                segment.start_time == start_time and 
                                segment.end_time == end_time):
                                try:
                                    return encode_time_segment_action(day, start_time, end_time)
                                except:
                                    continue
            
            return self.fallback_action(state)
        else:
            all_segments = generate_all_possible_time_segments()
            num_days = len(config["days"])
            action_space_size = num_days * len(all_segments)
            
            if "accept" in response:
                return action_space_size
            else:
                return action_space_size + 1
    
    def fallback_action(self, state):
        """Intelligent fallback when parsing fails"""
        config = get_meeting_scheduling_config()
        legal_actions = state.legal_actions()
        
        if state._phase == "propose":
            player_segments = state.preferences[self.player_name]
            
            # 优先选择高价值的时间段
            sorted_segments = sorted(player_segments, key=lambda s: s.value, reverse=True)
            
            for segment in sorted_segments:
                try:
                    action = encode_time_segment_action(segment.day, segment.start_time, segment.end_time)
                    if action in legal_actions:
                        return action
                except:
                    continue
            
            return random.choice(legal_actions) if legal_actions else None
        else:
            if state._current_proposal:
                day, start_time, end_time, duration = state._current_proposal
                player_segments = state.preferences[self.player_name]
                
                overlap_info = self._analyze_proposal_overlap(player_segments, day, start_time, end_time)
                
                all_segments = generate_all_possible_time_segments()
                num_days = len(config["days"])
                action_space_size = num_days * len(all_segments)
                
                
                base_threshold = 0.8  
                turn_ratio = state._turn_count / config["max_turns"]
                
                # 随着时间推移，阈值进一步降低
                dynamic_threshold = base_threshold * (1 - turn_ratio * 0.8)  # 最后阶段阈值可降到0.16
                
                # 如果游戏快结束了，接受任何有微小价值的提议
                if state._turn_count >= config["max_turns"] * 0.7:
                    dynamic_threshold = 0.3
                if state._turn_count >= config["max_turns"] * 0.9:
                    dynamic_threshold = 0.1  # 最后阶段几乎接受任何提议
                
                if overlap_info["value"] >= dynamic_threshold:
                    return action_space_size  # accept
                else:
                    return action_space_size + 1  # reject
            
            return random.choice(legal_actions)

class MultiPlayerCFRGuidedLLMPlayer:
    """CFR-guided LLM Player for working hours scheduling with lower thresholds"""
    
    def __init__(self, player_id, player_name, cfr_solver):
        self.player_id = player_id
        self.player_name = player_name
        self.cfr_solver = cfr_solver
    
    def select_action(self, state):
        """Select action using CFR guidance + LLM reasoning with lower thresholds"""
        legal_actions = state.legal_actions()
        if not legal_actions:
            return None
        
        cfr_strategy = self.cfr_solver.get_average_strategy(state, self.player_id)
        prompt = self.build_cfr_guided_prompt(state, cfr_strategy)
        
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a strategic meeting scheduler using game theory insights. Be collaborative and flexible to reach agreements within working hours (10:00-17:00)."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=300
            )
            
            llm_response = response.choices[0].message.content.strip()
            return self.parse_response(llm_response, state)
            
        except Exception as e:
            if cfr_strategy:
                actions = list(cfr_strategy.keys())
                probs = list(cfr_strategy.values())
                return np.random.choice(actions, p=probs)
            return random.choice(legal_actions)
    
    def build_cfr_guided_prompt(self, state, cfr_strategy):
        """Build prompt with CFR strategic guidance"""
        config = get_meeting_scheduling_config()
        player_segments = state.preferences[self.player_name]
        
        prompt = f"""You are {self.player_name} with advanced game theory analysis.

Your preferred time segments (working hours 10:00-17:00):"""
        
        segments_by_day = {}
        for segment in player_segments:
            if segment.day not in segments_by_day:
                segments_by_day[segment.day] = []
            segments_by_day[segment.day].append(segment)
        
        for day, day_segments in sorted(segments_by_day.items()):
            prompt += f"\n  {day}:"
            for segment in sorted(day_segments, key=lambda s: s.start_time):
                prompt += f"\n    {segment}"
        
        prompt += f"\n\nGame theory analysis recommends:"
        
        if state._phase == "propose":
            prompt += "\n\nTop strategic time segment recommendations:"
            
            sorted_strategy = sorted(cfr_strategy.items(), key=lambda x: x[1], reverse=True)
            
            count = 0
            for action, prob in sorted_strategy:
                if prob > 0.01 and count < 3:  
                    try:
                        day, start_time, end_time, duration = decode_time_segment_action(action)
                        
                        matching_segment = None
                        for segment in player_segments:
                            if (segment.day == day and 
                                segment.start_time == start_time and 
                                segment.end_time == end_time):
                                matching_segment = segment
                                break
                        
                        if matching_segment:
                            prompt += f"\n  {day} {start_time}-{end_time}: {prob:.1%} (value: {matching_segment.value})"
                            count += 1
                    except:
                        continue
            
            prompt += f"\n\nChoose the most strategically optimal segment. Be collaborative!"
            
        else:
            all_segments = generate_all_possible_time_segments()
            num_days = len(config["days"])
            action_space_size = num_days * len(all_segments)
            
            accept_prob = cfr_strategy.get(action_space_size, 0)
            reject_prob = cfr_strategy.get(action_space_size + 1, 0)
            
            day, start_time, end_time, duration = state._current_proposal
            
            llm_player = MultiPlayerLLMPlayer(self.player_id, self.player_name)
            overlap_info = llm_player._analyze_proposal_overlap(player_segments, day, start_time, end_time)
            
            prompt += f"\n\nProposal: {day} {start_time}-{end_time}"
            prompt += f"\nYour utility: {overlap_info['value']:.1f}/10"
            prompt += f"\nTurn {state._turn_count + 1}/{config['max_turns']} - Time pressure!"
            
            prompt += f"\n\nStrategic recommendation:"
            prompt += f"\n  Accept: {accept_prob:.1%}"
            prompt += f"\n  Reject: {reject_prob:.1%}"
            
            if accept_prob > reject_prob:
                prompt += f"\n\nCFR analysis suggests ACCEPTING is strategically optimal."
            else:
                prompt += f"\n\nCFR analysis suggests REJECTING, but consider time pressure!"
            
            prompt += f"\n\nRespond with 'accept' or 'reject'."
        
        return prompt
    
    def parse_response(self, response, state):
        """Parse response with fallback to CFR strategy"""
        llm_player = MultiPlayerLLMPlayer(self.player_id, self.player_name)
        return llm_player.parse_response(response, state)

class MultiPlayerCFRPlayer:
    """Pure CFR Player for working hours scheduling"""
    
    def __init__(self, player_id, solver):
        self.player_id = player_id
        self.solver = solver
    
    def select_action(self, state):
        """Select action based on CFR average strategy"""
        if state.is_terminal():
            return None
        
        strategy = self.solver.get_average_strategy(state, self.player_id)
        if not strategy:
            legal_actions = state.legal_actions()
            return random.choice(legal_actions) if legal_actions else None
        
        actions = list(strategy.keys())
        probs = list(strategy.values())
        
        return np.random.choice(actions, p=probs)

# Legacy compatibility aliases
LLMPlayer = MultiPlayerLLMPlayer
CFRGuidedLLMPlayer = MultiPlayerCFRGuidedLLMPlayer
CFRPlayer = MultiPlayerCFRPlayer