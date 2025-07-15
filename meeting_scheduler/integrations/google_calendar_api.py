import os
import pickle
from datetime import datetime, timedelta
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

class GoogleCalendarAPI:
    """Google Calendar API wrapper for meeting scheduling"""
    
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    
    def __init__(self, credentials_path='credentials.json', token_path='token.pickle'):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate with Google Calendar API"""
        creds = None
        
        # Load existing token
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)
        
        # If there are no (valid) credentials available, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)
        
        self.service = build('calendar', 'v3', credentials=creds)
        print("✅ Google Calendar API authenticated successfully")
    
    def get_free_busy(self, email, start_time, end_time):
        """Get free/busy information for a user"""
        try:
            body = {
                "timeMin": start_time.isoformat() + 'Z',
                "timeMax": end_time.isoformat() + 'Z',
                "items": [{"id": email}],
                "timeZone": "UTC"
            }
            
            result = self.service.freebusy().query(body=body).execute()
            busy_times = result.get('calendars', {}).get(email, {}).get('busy', [])
            
            return self._calculate_free_slots(start_time, end_time, busy_times)
            
        except HttpError as error:
            print(f"❌ Error getting free/busy for {email}: {error}")
            return []
    
    def _calculate_free_slots(self, start_time, end_time, busy_times):
        """Calculate free time slots from busy periods"""
        free_slots = []
        current_time = start_time
        
        # Sort busy times by start time
        busy_periods = []
        for busy in busy_times:
            busy_start = datetime.fromisoformat(busy['start'].replace('Z', '+00:00'))
            busy_end = datetime.fromisoformat(busy['end'].replace('Z', '+00:00'))
            busy_periods.append((busy_start, busy_end))
        
        busy_periods.sort(key=lambda x: x[0])
        
        # Find gaps between busy periods
        for busy_start, busy_end in busy_periods:
            if current_time < busy_start:
                # Free slot before this busy period
                free_slots.append({
                    'start': current_time,
                    'end': busy_start
                })
            current_time = max(current_time, busy_end)
        
        # Final free slot after last busy period
        if current_time < end_time:
            free_slots.append({
                'start': current_time,
                'end': end_time
            })
        
        return free_slots
    
    def create_meeting(self, meeting_details):
        """Create a calendar event"""
        try:
            event = self.service.events().insert(
                calendarId='primary',
                body=meeting_details,
                sendUpdates='all'  # Send invitations to attendees
            ).execute()
            
            print(f"✅ Meeting created: {event.get('htmlLink')}")
            return event
            
        except HttpError as error:
            print(f"❌ Error creating meeting: {error}")
            return None
    
    def get_calendar_list(self):
        """Get list of user's calendars"""
        try:
            calendar_list = self.service.calendarList().list().execute()
            return calendar_list.get('items', [])
        except HttpError as error:
            print(f"❌ Error getting calendar list: {error}")
            return []
    
    def delete_meeting(self, event_id, calendar_id='primary'):
        """Delete a calendar event"""
        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id,
                sendUpdates='all'
            ).execute()
            print(f"✅ Meeting {event_id} deleted successfully")
            return True
        except HttpError as error:
            print(f"❌ Error deleting meeting: {error}")
            return False