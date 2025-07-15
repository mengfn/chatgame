import random
import numpy as np


from .config import (
    get_meeting_scheduling_config,
    TimeSegment,
    time_to_minutes,
    minutes_to_time,
    validate_time_segment,
    get_time_period,
    WORK_TIME_PERIODS,
    get_action_space_size
)



def generate_ultra_simple_scenario():
    
    # 1小时和2小时的会议，只在2天，只有很少选择
    alice_segments = [
        TimeSegment("Monday", "10:00", "12:00", 8),     # 上午2小时
        TimeSegment("Tuesday", "10:00", "11:00", 7),    # 上午1小时
    ]
    
    bob_segments = [
        TimeSegment("Monday", "10:00", "12:00", 7),     # 与Alice完全重叠！
        TimeSegment("Tuesday", "12:00", "14:00", 8),    # 下午2小时
    ]
    
    charlie_segments = [
        TimeSegment("Monday", "10:00", "12:00", 9),     # 三人完全重叠！高价值
        TimeSegment("Tuesday", "14:00", "15:00", 6),    # 下午1小时
    ]
    
    preferences = {
        "Alice": alice_segments,
        "Bob": bob_segments,
        "Charlie": charlie_segments
    }
    
    # 创建价值字典
    valuations = {}
    for player, segments in preferences.items():
        player_valuations = {}
        for segment in segments:
            key = (segment.day, segment.start_time, segment.end_time)
            player_valuations[key] = segment.value
        valuations[player] = player_valuations
    
    return preferences, valuations



    
def generate_simple_time_segment(day, seed_offset=0, time_preferences=None):
    """Generate a simple time segment for working hours (10:00-17:00, 1小时间隔)"""
    config = get_meeting_scheduling_config()
    
    # 更新的时间偏好，支持1小时间隔和1-3小时会议
    if time_preferences is None:
        time_preferences = {
            "preferred_periods": ["morning", "afternoon"],
            "typical_durations": [1, 2, 3]  # 1到3小时
        }
    
    # 选择偏好时间段
    period = random.choice(time_preferences["preferred_periods"])
    period_start, period_end = WORK_TIME_PERIODS[period]
    
    # 选择会议时长
    duration_hours = random.choice(time_preferences["typical_durations"])
    
    # 生成所有可能的1小时间隔开始时间
    available_start_times = []
    
    # 从period_start到period_end，每1小时一个时间点
    work_end_hour = config["day_end_hour"]  # 17
    
    for hour in range(period_start, period_end):
        # 检查会议是否会超出工作时间
        if hour + duration_hours <= work_end_hour:
            start_time = f"{hour:02d}:00"
            available_start_times.append(start_time)
    
    # 如果当前时段没有合适时间，扩展到整个工作时间
    if not available_start_times:
        work_start_hour = config["day_start_hour"]  # 10
        for hour in range(work_start_hour, work_end_hour):
            if hour + duration_hours <= work_end_hour:
                start_time = f"{hour:02d}:00"
                available_start_times.append(start_time)
    
    # 最后的保障：如果还是没有，选择最短的会议
    if not available_start_times:
        duration_hours = 1  # 1小时会议
        work_start_hour = config["day_start_hour"]
        for hour in range(work_start_hour, work_end_hour):
            if hour + duration_hours <= work_end_hour:
                start_time = f"{hour:02d}:00"
                available_start_times.append(start_time)
    
    if available_start_times:
        start_time = random.choice(available_start_times)
        start_hour = int(start_time.split(':')[0])
        end_time = f"{start_hour + duration_hours:02d}:00"
    else:
        # 实在没有的话，默认一个简单的时间段
        start_time = "10:00"
        end_time = "11:00"
    
    # 生成价值 (更高的基础价值以增加重叠概率)
    base_value = 5  # 提高基础价值
    
    # 根据时间段调整价值
    if period in ["morning", "afternoon"]:
        base_value += random.randint(1, 3)
    else:
        base_value += random.randint(0, 2)
    
    # 添加随机性但保持较高价值
    value = max(3, min(10, base_value + random.randint(-1, 2)))
    
    return TimeSegment(day, start_time, end_time, value)



def generate_overlapping_preferences_for_player(player_name, common_segments, seed=None):
    """为单个玩家生成包含公共时间段的偏好 - 支持1小时间隔"""
    if seed is not None:
        random.seed(seed + hash(player_name) % 1000)
    
    config = get_meeting_scheduling_config()
    segments = []
    
    # 1. 每个玩家有70%概率包含每个公共时间段
    for common_segment in common_segments:
        if random.random() < 0.7:  # 70%概率包含公共时间段
            # 添加一些价值变化
            value = common_segment.value + random.randint(-1, 2)
            value = max(4, min(10, value))  # 保持合理范围
            
            segment = TimeSegment(
                common_segment.day, 
                common_segment.start_time, 
                common_segment.end_time, 
                value
            )
            segments.append(segment)
    
    # 2. 添加2-3个个人独特时间段
    personal_segments_count = random.randint(2, 3)
    attempts = 0
    
    while len(segments) < len(segments) + personal_segments_count and attempts < 15:
        attempts += 1
        day = random.choice(config["days"])
        
        # 更新个人偏好类型，适配1小时间隔
        player_types = {
            "Alice": {"preferred_periods": ["morning", "lunch"]},
            "Bob": {"preferred_periods": ["afternoon"]}, 
            "Charlie": {"preferred_periods": ["morning", "afternoon"]}
        }
        
        player_prefs = player_types.get(player_name, {"preferred_periods": ["morning", "afternoon"]})
        
        try:
            segment = generate_simple_time_segment(day, attempts, player_prefs)
            
            # 检查是否与现有时间段重叠
            overlap = False
            for existing in segments:
                if existing.day == segment.day and existing.overlaps_with(segment):
                    overlap = True
                    break
            
            if not overlap:
                segments.append(segment)
        except Exception as e:
            continue
    
    # 确保至少有3个时间段
    while len(segments) < 3:
        day = random.choice(config["days"])
        try:
            segment = TimeSegment(day, "10:00", "11:00", random.randint(5, 8))
            segments.append(segment)
        except:
            break
    
    return segments



def generate_three_player_overlapping_preferences(seed=None):
    """生成保证重叠的三人偏好 (1小时间隔, 10:00-17:00)"""
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
    
    config = get_meeting_scheduling_config()
    
    common_segments = [
        TimeSegment("Monday", "10:00", "12:00", 8),      # 2小时会议
        TimeSegment("Monday", "14:00", "15:00", 7),      # 1小时会议
        TimeSegment("Tuesday", "11:00", "12:00", 7),     # 1小时会议
        TimeSegment("Tuesday", "14:00", "15:00", 6),     # 1小时会议
        TimeSegment("Wednesday", "10:00", "13:00", 8),   # 3小时会议
        TimeSegment("Wednesday", "15:00", "16:00", 7),   # 1小时会议
        TimeSegment("Thursday", "11:00", "13:00", 8),    # 2小时会议
        TimeSegment("Thursday", "14:00", "15:00", 7),    # 1小时会议
        TimeSegment("Friday", "10:00", "11:00", 6),      # 1小时会议
        TimeSegment("Friday", "13:00", "16:00", 7),      # 3小时会议
    ]
    
    preferences = {}
    valuations = {}
    
    # 2. 为每个玩家生成偏好
    for i, player in enumerate(config["players"]):
        player_seed = seed + i * 100 if seed is not None else None
        segments = generate_overlapping_preferences_for_player(player, common_segments, player_seed)
        
        # 限制时间段数量
        if len(segments) > config["max_segments_per_player"]:
            # 优先保留高价值时间段
            segments.sort(key=lambda s: s.value, reverse=True)
            segments = segments[:config["max_segments_per_player"]]
        
        preferences[player] = segments
        
        # 创建价值字典
        player_valuations = {}
        for segment in segments:
            key = (segment.day, segment.start_time, segment.end_time)
            player_valuations[key] = segment.value
        
        valuations[player] = player_valuations
    
    return preferences, valuations

def generate_simple_demo_scenario():
    
    
    # Alice: 偏好上午
    alice_segments = [
        TimeSegment("Monday", "10:00", "12:00", 8),     
        TimeSegment("Monday", "14:00", "15:00", 6),      
        TimeSegment("Tuesday", "10:00", "12:00", 9),     
        TimeSegment("Wednesday", "11:00", "12:00", 7),  
        TimeSegment("Friday", "10:00", "11:00", 6),     
    ]

    bob_segments = [
        TimeSegment("Monday", "10:00", "12:00", 7),      
        TimeSegment("Monday", "15:00", "17:00", 8),      
        TimeSegment("Tuesday", "14:00", "16:00", 9),     
        TimeSegment("Wednesday", "11:00", "12:00", 8),   
        TimeSegment("Thursday", "15:00", "17:00", 7),    
    ]

    charlie_segments = [
        TimeSegment("Monday", "10:00", "11:00", 6),      
        TimeSegment("Tuesday", "10:00", "11:00", 7),     
        TimeSegment("Tuesday", "15:00", "16:00", 6),     
        TimeSegment("Wednesday", "11:00", "12:00", 9),   
        TimeSegment("Thursday", "13:00", "15:00", 5),    
        TimeSegment("Friday", "10:00", "11:00", 5),      
    ]
    
    preferences = {
        "Alice": alice_segments,
        "Bob": bob_segments,
        "Charlie": charlie_segments
    }
    
    # 创建价值字典
    valuations = {}
    for player, segments in preferences.items():
        player_valuations = {}
        for segment in segments:
            key = (segment.day, segment.start_time, segment.end_time)
            player_valuations[key] = segment.value
        valuations[player] = player_valuations
    
    return preferences, valuations

def analyze_three_player_preferences(preferences, valuations):
    """分析三人偏好的重叠情况"""
    config = get_meeting_scheduling_config()
    players = config["players"]
    
    possible_meetings = []
    
    # 获取每个玩家的时间段
    alice_segments = preferences[players[0]]
    bob_segments = preferences[players[1]]
    charlie_segments = preferences[players[2]]
    
    # 检查三人重叠
    for alice_seg in alice_segments:
        for bob_seg in bob_segments:
            for charlie_seg in charlie_segments:
                
                # 必须在同一天
                if alice_seg.day == bob_seg.day == charlie_seg.day:
                    
                    # 检查时间重叠
                    if (alice_seg.start_time == bob_seg.start_time == charlie_seg.start_time and
                        alice_seg.end_time == bob_seg.end_time == charlie_seg.end_time):
                        
                        # 完全匹配
                        total_value = alice_seg.value + bob_seg.value + charlie_seg.value
                        
                        meeting = {
                            "day": alice_seg.day,
                            "start_time": alice_seg.start_time,
                            "end_time": alice_seg.end_time,
                            "duration_minutes": alice_seg.duration_minutes,
                            "total_value": total_value,
                            "individual_values": [alice_seg.value, bob_seg.value, charlie_seg.value],
                            "type": "exact_match"
                        }
                        
                        possible_meetings.append(meeting)
    
    # 去重并排序
    unique_meetings = []
    for meeting in possible_meetings:
        is_duplicate = False
        for existing in unique_meetings:
            if (meeting["day"] == existing["day"] and
                meeting["start_time"] == existing["start_time"] and
                meeting["end_time"] == existing["end_time"]):
                is_duplicate = True
                if meeting["total_value"] > existing["total_value"]:
                    unique_meetings.remove(existing)
                    unique_meetings.append(meeting)
                break
        
        if not is_duplicate:
            unique_meetings.append(meeting)
    
    # 按总价值排序
    unique_meetings.sort(key=lambda x: x["total_value"], reverse=True)
    
    # 计算复杂度
    total_segments = sum(len(segments) for segments in preferences.values())
    
    if len(unique_meetings) == 0:
        complexity = "impossible"
    elif len(unique_meetings) <= 2:
        complexity = "simple"
    elif len(unique_meetings) <= 5:
        complexity = "medium"
    else:
        complexity = "complex"
    
    return {
        "complexity": complexity,
        "total_segments": total_segments,
        "potential_meetings": unique_meetings[:10],  # 前10个选项
        "total_options": len(unique_meetings),
        "players_segment_counts": {player: len(segments) for player, segments in preferences.items()},
        "action_space_size": get_action_space_size()
    }


# 场景生成器字典
PREFERENCE_GENERATORS = {
    "ultra_simple": generate_ultra_simple_scenario,
    "simple_demo": generate_simple_demo_scenario,
    "overlapping": generate_three_player_overlapping_preferences,
    "random_24h": generate_three_player_overlapping_preferences,
    "random_busy": lambda seed=None: generate_three_player_overlapping_preferences(seed),
    "random_flexible": lambda seed=None: generate_three_player_overlapping_preferences(seed),
    "specific_24h_conflicts": generate_simple_demo_scenario,
    "extreme_schedules": generate_simple_demo_scenario,
}

FIXED_PREFERENCE_GENERATORS = {
    "ultra_simple": generate_ultra_simple_scenario,
    "simple_demo": generate_simple_demo_scenario,
    "specific_24h_conflicts": generate_simple_demo_scenario,
    "extreme_schedules": generate_simple_demo_scenario,
}

RANDOM_PREFERENCE_GENERATORS = {
    "random_24h": generate_three_player_overlapping_preferences,
    "random_busy": lambda seed=None: generate_three_player_overlapping_preferences(seed),
    "random_flexible": lambda seed=None: generate_three_player_overlapping_preferences(seed),
    "overlapping": generate_three_player_overlapping_preferences,
}



def generate_preferences(preference_type="simple_demo", **kwargs):
    """使用指定类型生成偏好"""
    generator = PREFERENCE_GENERATORS.get(preference_type, generate_simple_demo_scenario)
    
    import inspect
    sig = inspect.signature(generator)
    if 'seed' in sig.parameters and 'seed' in kwargs:
        return generator(seed=kwargs['seed'])
    elif len(sig.parameters) > 0:
        valid_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return generator(**valid_kwargs)
    else:
        return generator()

def generate_random_batch(num_scenarios=5, scenario_type="overlapping", seed=None):
    """生成一批随机重叠场景"""
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
    
    scenarios = []
    
    for i in range(num_scenarios):
        scenario_seed = random.randint(0, 10000) if seed is None else seed + i
        
        prefs, vals = generate_three_player_overlapping_preferences(seed=scenario_seed)
        scenario_name = f"overlapping_{i}"
        
        # 分析场景
        analysis = analyze_three_player_preferences(prefs, vals)
        
        scenarios.append({
            "id": i,
            "name": scenario_name,
            "seed": scenario_seed,
            "preferences": prefs,
            "valuations": vals,
            "analysis": analysis,
            "type": scenario_type
        })
    
    return scenarios

generate_three_player_random_preferences = generate_three_player_overlapping_preferences
analyze_three_player_preferences_24h = analyze_three_player_preferences

def get_action_space_size():
    
    from .config import get_action_space_size
    return get_action_space_size()