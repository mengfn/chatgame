import os
from datetime import datetime, timedelta
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_meeting_scheduling_config():
    
    return {
        "players": ["Alice", "Bob", "Charlie"],
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],  
        "time_interval_minutes": 60,           # 改为60分钟间隔 (1小时)
        "min_meeting_duration": 60,            # 最小会议60分钟 (1小时)
        "max_meeting_duration": 180,           # 最大会议180分钟 (3小时)
        "day_start_hour": 10,                  # 10点开始
        "day_end_hour": 17,                    # 17点结束
        "max_turns": 4,                        # 4轮协商
        "max_segments_per_player": 4,          # 每人最多4个时间段
    }

def time_to_minutes(time_str):
    """Convert HH:MM to minutes since midnight"""
    hours, minutes = map(int, time_str.split(':'))
    return hours * 60 + minutes

def minutes_to_time(minutes):
    """Convert minutes since midnight to HH:MM"""
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours:02d}:{mins:02d}"

def generate_all_possible_time_slots():
    """生成工作时间内的所有时间槽"""
    slots = []
    config = get_meeting_scheduling_config()
    
    # 只在工作时间内生成时间槽
    start_minutes = config["day_start_hour"] * 60  # 10:00 = 600分钟
    end_minutes = config["day_end_hour"] * 60      # 17:00 = 1020分钟
    
    for minutes in range(start_minutes, end_minutes, config["time_interval_minutes"]):
        slots.append(minutes_to_time(minutes))
    
    return slots

def generate_all_possible_time_segments():
    """生成工作时间内的所有可能时间段"""
    segments = []
    config = get_meeting_scheduling_config()
    
    start_minutes = config["day_start_hour"] * 60  # 10:00 = 600分钟
    end_minutes = config["day_end_hour"] * 60      # 17:00 = 1020分钟
    
    # 会议时长选项：1小时、2小时、3小时
    durations_hours = [1, 2, 3]
    
    # 生成所有可能的开始时间（按1小时间隔）
    for start_mins in range(start_minutes, end_minutes, 60):  # 60分钟间隔
        start_time = minutes_to_time(start_mins)
        
        # 生成所有可能的会议时长
        for duration_hours in durations_hours:
            duration_minutes = duration_hours * 60
            end_mins = start_mins + duration_minutes
            
            # 确保会议不会超出工作时间
            if end_mins <= end_minutes:
                end_time = minutes_to_time(end_mins)
                segments.append((start_time, end_time, duration_minutes))
    
    return segments

def do_segments_overlap(seg1_start, seg1_end, seg2_start, seg2_end):
    """Check if two time segments overlap"""
    start1_mins = time_to_minutes(seg1_start)
    end1_mins = time_to_minutes(seg1_end)
    start2_mins = time_to_minutes(seg2_start)
    end2_mins = time_to_minutes(seg2_end)
    
    return not (end1_mins <= start2_mins or end2_mins <= start1_mins)

def calculate_overlap_duration(seg1_start, seg1_end, seg2_start, seg2_end):
    """Calculate overlap duration in minutes between two segments"""
    start1_mins = time_to_minutes(seg1_start)
    end1_mins = time_to_minutes(seg1_end)
    start2_mins = time_to_minutes(seg2_start)
    end2_mins = time_to_minutes(seg2_end)
    
    overlap_start = max(start1_mins, start2_mins)
    overlap_end = min(end1_mins, end2_mins)
    
    return max(0, overlap_end - overlap_start)

def segments_are_identical(seg1_start, seg1_end, seg2_start, seg2_end):
    """Check if two segments are exactly the same"""
    return seg1_start == seg2_start and seg1_end == seg2_end

def encode_time_segment_action(day, start_time, end_time):
    """Encode a time segment proposal into action index"""
    config = get_meeting_scheduling_config()
    all_segments = generate_all_possible_time_segments()
    
    day_idx = config["days"].index(day)
    
    segment_idx = None
    
    for i, (seg_start, seg_end, seg_duration) in enumerate(all_segments):
        if seg_start == start_time and seg_end == end_time:
            segment_idx = i
            break
    
    if segment_idx is None:
        raise ValueError(f"Invalid time segment: {start_time}-{end_time}")
    
    return day_idx * len(all_segments) + segment_idx

def decode_time_segment_action(action):
    """Decode action index into (day, start_time, end_time, duration)"""
    config = get_meeting_scheduling_config()
    all_segments = generate_all_possible_time_segments()
    
    day_idx = action // len(all_segments)
    segment_idx = action % len(all_segments)
    
    day = config["days"][day_idx]
    start_time, end_time, duration = all_segments[segment_idx]
    
    return day, start_time, end_time, duration

def get_action_space_size():
    """获取动作空间大小"""
    config = get_meeting_scheduling_config()
    all_segments = generate_all_possible_time_segments()
    
    num_proposal_actions = len(config["days"]) * len(all_segments)
    
    # 调试信息
    print(f"工作时间段数量: {len(all_segments)}")
    print(f"总提议动作数: {num_proposal_actions}")
    print(f"总动作空间大小: {num_proposal_actions + 2}")
    
    return num_proposal_actions + 2

class TimeSegment:
    """Represents a time segment with day, start, end, and value"""
    
    def __init__(self, day, start_time, end_time, value):
        self.day = day
        self.start_time = start_time
        self.end_time = end_time
        self.value = value
        self.duration_minutes = time_to_minutes(end_time) - time_to_minutes(start_time)
    
    def __str__(self):
        duration_str = self.format_duration()
        return f"{self.day} {self.start_time}-{self.end_time} ({duration_str}, v={self.value})"
    
    def __repr__(self):
        return self.__str__()
    
    def format_duration(self):
        """Format duration as string"""
        hours = self.duration_minutes // 60
        minutes = self.duration_minutes % 60
        if minutes == 0:
            return f"{hours}h"
        else:
            return f"{hours}h{minutes}m"
    
    def overlaps_with(self, other_segment):
        """Check if this segment overlaps with another segment"""
        if self.day != other_segment.day:
            return False
        return do_segments_overlap(self.start_time, self.end_time, 
                                 other_segment.start_time, other_segment.end_time)
    
    def is_identical_to(self, other_segment):
        """Check if this segment is identical to another"""
        return (self.day == other_segment.day and 
                segments_are_identical(self.start_time, self.end_time,
                                     other_segment.start_time, other_segment.end_time))
    
    def calculate_overlap_with(self, other_segment):
        """Calculate overlap duration with another segment"""
        if self.day != other_segment.day:
            return 0
        return calculate_overlap_duration(self.start_time, self.end_time,
                                        other_segment.start_time, other_segment.end_time)

def validate_time_segment(day, start_time, end_time):
    """Validate that a time segment is valid within working hours"""
    config = get_meeting_scheduling_config()
    
    if day not in config["days"]:
        raise ValueError(f"Invalid day: {day}")
    
    try:
        start_mins = time_to_minutes(start_time)
        end_mins = time_to_minutes(end_time)
    except:
        raise ValueError(f"Invalid time format: {start_time}-{end_time}")
    
    duration = end_mins - start_mins
    
    # 检查会议时长是否在允许范围内（60-180分钟）
    if duration < config["min_meeting_duration"] or duration > config["max_meeting_duration"]:
        raise ValueError(f"Invalid duration: {duration} minutes. Must be between {config['min_meeting_duration']} and {config['max_meeting_duration']}")
    
   
    if duration % 60 != 0:
        raise ValueError(f"Duration must be multiple of 60 minutes, got {duration}")
    
    # 检查开始时间是否对齐到1小时间隔
    if start_mins % config["time_interval_minutes"] != 0:
        raise ValueError(f"Start time not aligned to {config['time_interval_minutes']}-minute intervals")
    
    # 检查是否在工作时间内
    work_start = config["day_start_hour"] * 60
    work_end = config["day_end_hour"] * 60
    
    if start_mins < work_start:
        raise ValueError(f"Meeting starts before work hours ({config['day_start_hour']}:00)")
    if end_mins > work_end:
        raise ValueError(f"Meeting ends after work hours ({config['day_end_hour']}:00)")
    
    return True

def get_time_period(time_str):
    """Get time period classification for working hours analysis"""
    hour = int(time_str.split(':')[0])
    
    if 10 <= hour < 12:
        return "morning"
    elif 12 <= hour < 14:
        return "lunch"
    elif 14 <= hour < 17:
        return "afternoon"
    else:
        return "outside_hours"

def generate_time_grid():
    """Generate a grid showing all possible time slots within working hours"""
    config = get_meeting_scheduling_config()
    time_slots = generate_all_possible_time_slots()
    
    grid = {}
    for day in config["days"]:
        grid[day] = {}
        for slot in time_slots:
            grid[day][slot] = {
                "available": True,
                "period": get_time_period(slot),
                "hour": int(slot.split(':')[0]),
                "minute": int(slot.split(':')[1])
            }
    
    return grid


EXPERIMENT_CONFIG = {
    # CFR训练配置
    "cfr_iterations": 100,          
    "cfr_timeout": 30,               
    
    # 评估指标配置  
    "nash_conv_samples": 5,          
    "cfr_gain_samples": 5,           
    
    # 策略对比配置
    "strategy_comparison_games": 8,  
    "max_game_steps": 8,             
    
    # 随机实验配置
    "random_scenarios_default": 15, 
    "convergence_threshold": 0.005,  
    
    # 性能优化配置
    "enable_early_stopping": True,   
    "max_cfr_depth": 30,             
    "action_sampling_threshold": 15, 
}


QUICK_EXPERIMENT_CONFIG = {
    "cfr_iterations": 50,            # 快速模式：50次迭代
    "nash_conv_samples": 3,          
    "cfr_gain_samples": 3,
    "strategy_comparison_games": 5,
    "max_game_steps": 6,
    "cfr_timeout": 15,               # 15秒超时
}

# 深度分析配置
DETAILED_EXPERIMENT_CONFIG = {
    "cfr_iterations": 200,           # 详细模式：200次迭代
    "nash_conv_samples": 10,
    "cfr_gain_samples": 10, 
    "strategy_comparison_games": 15,
    "max_game_steps": 12,
    "cfr_timeout": 60,               # 60秒超时
}

WORK_TIME_PERIODS = {
    "morning": (10, 12),     
    "lunch": (12, 14),       
    "afternoon": (14, 17)    
}



def get_experiment_config(mode="normal"):
    if mode == "quick":
        return QUICK_EXPERIMENT_CONFIG
    elif mode == "detailed":
        return DETAILED_EXPERIMENT_CONFIG
    else:
        return EXPERIMENT_CONFIG