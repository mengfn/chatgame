import random
from datetime import datetime, timedelta
from ..config import TimeSegment, get_meeting_scheduling_config, time_to_minutes, minutes_to_time

class CalendarPreferenceAdapter:
    """Adapter to convert real calendar data to meeting scheduler preferences"""
    
    def __init__(self, calendar_api):
        self.calendar = calendar_api
        self.config = get_meeting_scheduling_config()
    
    def generate_real_preferences_from_calendars(self, participant_emails, date_range=None):
        """Generate preferences from real calendar data"""
        
        if date_range is None:
            date_range = self._get_next_week_range()
        
        start_time, end_time = date_range
        
        print(f"📅 Analyzing calendars from {start_time.date()} to {end_time.date()}")
        
        # Get free slots for each participant
        free_slots_by_email = {}
        for email in participant_emails[:3]:  # Limit to 3 participants
            print(f"  🔍 Checking availability for {email}")
            free_slots = self.calendar.get_free_busy(email, start_time, end_time)
            free_slots_by_email[email] = free_slots
        
        # Convert to meeting scheduler format
        preferences = {}
        valuations = {}
        
        player_names = self.config["players"]
        
        for i, email in enumerate(participant_emails[:3]):
            player = player_names[i]
            print(f"  👤 Processing {player} ({email})")
            
            # Convert free slots to TimeSegment objects
            segments = self._convert_free_slots_to_segments(
                free_slots_by_email[email], 
                player
            )
            
            preferences[player] = segments
            
            # Generate valuations dictionary
            player_valuations = {}
            for segment in segments:
                key = (segment.day, segment.start_time, segment.end_time)
                player_valuations[key] = segment.value
            valuations[player] = player_valuations
            
            print(f"    ✅ Generated {len(segments)} preference segments")
        
        print(f"🎯 Calendar analysis complete!")
        return preferences, valuations
    
    def _get_next_week_range(self):
        """Get date range for next week"""
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Find next Monday
        days_ahead = 0 - today.weekday()  # Monday is 0
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        
        start_date = today + timedelta(days=days_ahead)
        end_date = start_date + timedelta(days=5)  # Monday to Friday
        
        return start_date, end_date
    
    def _convert_free_slots_to_segments(self, free_slots, player_name):
        """Convert calendar free slots to TimeSegment objects"""
        segments = []
        
        for slot in free_slots:
            # Convert datetime to our format
            start_dt = slot['start']
            end_dt = slot['end']
            
            # Only consider working hours slots
            for day_dt in self._get_work_days_in_range(start_dt, end_dt):
                day_segments = self._extract_work_day_segments(
                    day_dt, start_dt, end_dt, player_name
                )
                segments.extend(day_segments)
        
        # Remove duplicates and limit segments
        unique_segments = self._deduplicate_segments(segments)
        
        # Limit to max segments per player
        if len(unique_segments) > self.config["max_segments_per_player"]:
            # Sort by value and take top segments
            unique_segments.sort(key=lambda s: s.value, reverse=True)
            unique_segments = unique_segments[:self.config["max_segments_per_player"]]
        
        return unique_segments
    
    def _get_work_days_in_range(self, start_dt, end_dt):
        """Get work days within the datetime range"""
        work_days = []
        current = start_dt.date()
        end_date = end_dt.date()
        
        while current <= end_date:
            if current.strftime('%A') in self.config["days"]:
                work_days.append(current)
            current += timedelta(days=1)
        
        return work_days
    
    def _extract_work_day_segments(self, day_date, slot_start, slot_end, player_name):
        """Extract work hour segments from a day"""
        segments = []
        day_name = day_date.strftime('%A')
        
        # Work hours boundaries
        work_start_minutes = self.config["day_start_hour"] * 60  # 10:00
        work_end_minutes = self.config["day_end_hour"] * 60      # 17:00
        
        # Slot boundaries for this day
        day_start = datetime.combine(day_date, datetime.min.time())
        day_end = day_start + timedelta(days=1)
        
        slot_day_start = max(slot_start, day_start)
        slot_day_end = min(slot_end, day_end)
        
        if slot_day_start >= slot_day_end:
            return segments
        
        # Convert to minutes since midnight
        slot_start_minutes = slot_day_start.hour * 60 + slot_day_start.minute
        slot_end_minutes = slot_day_end.hour * 60 + slot_day_end.minute
        
        # Clip to work hours
        available_start = max(slot_start_minutes, work_start_minutes)
        available_end = min(slot_end_minutes, work_end_minutes)
        
        if available_start >= available_end:
            return segments
        
        # Generate meeting segments within available time
        for duration in [60, 90, 120, 150, 180]:  # 1-3 hours
            segment_start_minutes = available_start
            
            # Align to 30-minute intervals
            segment_start_minutes = ((segment_start_minutes + 29) // 30) * 30
            
            while segment_start_minutes + duration <= available_end:
                segment_end_minutes = segment_start_minutes + duration
                
                # Convert back to time strings
                start_time = minutes_to_time(segment_start_minutes)
                end_time = minutes_to_time(segment_end_minutes)
                
                # Generate preference value
                value = self._estimate_preference_value(
                    day_name, start_time, end_time, player_name
                )
                
                segment = TimeSegment(day_name, start_time, end_time, value)
                segments.append(segment)
                
                # Move to next possible start time (30 min later)
                segment_start_minutes += 30
        
        return segments
    
    def _estimate_preference_value(self, day, start_time, end_time, player_name):
        """Estimate preference value based on time patterns"""
        base_value = 5  # Neutral preference
        
        hour = int(start_time.split(':')[0])
        
        # Time-based preferences (simulated patterns)
        if player_name == "Alice":
            # Morning person
            if 10 <= hour < 12:
                base_value += 3
            elif 14 <= hour < 16:
                base_value += 1
        elif player_name == "Bob":
            # Afternoon person  
            if 14 <= hour < 17:
                base_value += 3
            elif 10 <= hour < 12:
                base_value += 1
        elif player_name == "Charlie":
            # Flexible
            if 11 <= hour < 15:
                base_value += 2
        
        # Day-based preferences
        if day in ["Tuesday", "Wednesday", "Thursday"]:
            base_value += 1  # Mid-week preference
        
        # Add some randomness
        base_value += random.randint(-1, 2)
        
        # Ensure value is in valid range
        return max(3, min(10, base_value))
    
    def _deduplicate_segments(self, segments):
        """Remove duplicate segments"""
        seen = set()
        unique_segments = []
        
        for segment in segments:
            key = (segment.day, segment.start_time, segment.end_time)
            if key not in seen:
                seen.add(key)
                unique_segments.append(segment)
        
        return unique_segments