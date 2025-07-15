from datetime import datetime, timedelta

class MeetingExecutor:
    """Execute meeting scheduling results by creating real calendar events"""
    
    def __init__(self, calendar_api, timezone='UTC'):
        self.calendar = calendar_api
        self.timezone = timezone
    
    def execute_game_result(self, game_state, participant_emails, meeting_title=None):
        """Convert game result to real calendar meeting"""
        
        if not game_state._agreement_reached or not game_state._current_proposal:
            print("❌ No agreement reached - cannot create meeting")
            return None
        
        day, start_time, end_time, duration = game_state._current_proposal
        
        print(f"✅ Agreement reached: {day} {start_time}-{end_time}")
        print(f"👥 Creating meeting for: {', '.join(participant_emails)}")
        
        # Convert to calendar event format
        meeting_details = self._create_event_details(
            day, start_time, end_time, participant_emails, meeting_title
        )
        
        # Create the actual calendar event
        calendar_event = self.calendar.create_meeting(meeting_details)
        
        if calendar_event:
            return {
                'success': True,
                'event_id': calendar_event.get('id'),
                'event_link': calendar_event.get('htmlLink'),
                'meeting_time': f"{day} {start_time}-{end_time}",
                'duration_minutes': duration,
                'attendees': participant_emails,
                'calendar_event': calendar_event
            }
        else:
            return {
                'success': False,
                'error': 'Failed to create calendar event'
            }
    
    def _create_event_details(self, day, start_time, end_time, participant_emails, meeting_title):
        """Create Google Calendar event details"""
        
        # Convert day name to actual date
        meeting_date = self._get_next_date_for_day(day)
        
        # Create datetime strings
        start_datetime = f"{meeting_date}T{start_time}:00"
        end_datetime = f"{meeting_date}T{end_time}:00"
        
        if meeting_title is None:
            meeting_title = "AI Scheduled Meeting"
        
        event_details = {
            'summary': meeting_title,
            'description': 'Meeting scheduled using AI game theory optimization',
            'start': {
                'dateTime': start_datetime,
                'timeZone': self.timezone,
            },
            'end': {
                'dateTime': end_datetime,
                'timeZone': self.timezone,
            },
            'attendees': [
                {'email': email, 'responseStatus': 'needsAction'} 
                for email in participant_emails
            ],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},  # 1 day before
                    {'method': 'popup', 'minutes': 15},       # 15 min before
                ],
            },
            'conferenceData': {
                'createRequest': {
                    'requestId': f"ai-meeting-{datetime.now().strftime('%Y%m%d%H%M%S')}",
                    'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                }
            },
            'guestsCanInviteOthers': False,
            'guestsCanModify': False,
        }
        
        return event_details
    
    def _get_next_date_for_day(self, day_name):
        """Get the next occurrence of a day name (e.g., 'Monday')"""
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        
        if day_name not in days:
            raise ValueError(f"Invalid day name: {day_name}")
        
        today = datetime.now().date()
        target_weekday = days.index(day_name)
        
        # Calculate days until target day
        days_ahead = target_weekday - today.weekday()
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        
        target_date = today + timedelta(days=days_ahead)
        return target_date.isoformat()
    
    def cancel_meeting(self, event_id):
        """Cancel a created meeting"""
        return self.calendar.delete_meeting(event_id)