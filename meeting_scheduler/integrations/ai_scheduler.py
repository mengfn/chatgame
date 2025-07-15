from .google_calendar_api import GoogleCalendarAPI
from .calendar_adapter import CalendarPreferenceAdapter
from .meeting_executor import MeetingExecutor

# Import your existing modules (no modifications needed!)
from ..game_core import MultiPlayerMeetingGame
from ..solvers import MultiPlayerCFRSolver
from ..experiments import run_three_player_strategy_comparison
from ..players import MultiPlayerLLMPlayer, MultiPlayerCFRPlayer, MultiPlayerCFRGuidedLLMPlayer
from ..config import get_meeting_scheduling_config

class AIScheduler:
    """Main interface for AI-powered meeting scheduling with Google Calendar"""
    
    def __init__(self, credentials_path='credentials.json', token_path='token.pickle'):
        print("🤖 Initializing AI Scheduler...")
        
        # Initialize Google Calendar API
        self.calendar = GoogleCalendarAPI(credentials_path, token_path)
        
        # Initialize adapters
        self.preference_adapter = CalendarPreferenceAdapter(self.calendar)
        self.meeting_executor = MeetingExecutor(self.calendar)
        
        print("✅ AI Scheduler ready!")
    
    def schedule_meeting_for_emails(self, participant_emails, meeting_title=None, 
                                  use_real_calendars=True, cfr_iterations=200):
        """
        Main entry point: Schedule a meeting for given email addresses
        
        Args:
            participant_emails: List of email addresses (max 3)
            meeting_title: Optional custom meeting title
            use_real_calendars: If True, use real calendar data; if False, use simulated data
            cfr_iterations: Number of CFR training iterations
        
        Returns:
            Dict with scheduling results and analysis
        """
        
        if len(participant_emails) > 3:
            participant_emails = participant_emails[:3]
            print(f"⚠️  Limited to 3 participants: {participant_emails}")
        
        print(f"\n🎯 Scheduling meeting for: {', '.join(participant_emails)}")
        
        try:
            # Step 1: Generate preferences
            if use_real_calendars:
                print("📅 Analyzing real calendar data...")
                preferences, valuations = self.preference_adapter.generate_real_preferences_from_calendars(
                    participant_emails
                )
            else:
                print("🎲 Using simulated preferences...")
                from ..preferences import generate_three_player_overlapping_preferences
                preferences, valuations = generate_three_player_overlapping_preferences(seed=42)
            
            # Step 2: Create game (using your existing code!)
            print("🎮 Creating meeting scheduling game...")
            game = MultiPlayerMeetingGame(preferences, valuations)
            
            # Validate game setup
            game.validate_game_setup()
            
            # Step 3: Train CFR solver (using your existing code!)
            print(f"🧠 Training CFR solver ({cfr_iterations} iterations)...")
            cfr_solver = MultiPlayerCFRSolver(game, num_players=3)
            cfr_solver.train(iterations=cfr_iterations, silent=True)
            
            # Step 4: Run strategy comparison (using your existing code!)
            print("⚔️  Comparing strategies...")
            strategy_results = run_three_player_strategy_comparison(game, cfr_solver, silent=True)
            
            # Step 5: Simulate negotiation with best strategy
            print("🤝 Simulating negotiation...")
            final_state = self._simulate_optimal_negotiation(game, cfr_solver)
            
            # Step 6: Execute real meeting creation
            if final_state._agreement_reached:
                print("✅ Agreement reached! Creating calendar event...")
                meeting_result = self.meeting_executor.execute_game_result(
                    final_state, participant_emails, meeting_title
                )
            else:
                print("❌ No agreement could be reached")
                meeting_result = {
                    'success': False,
                    'error': 'No agreement reached in game simulation'
                }
            
            # Return comprehensive results
            return {
                'meeting_result': meeting_result,
                'strategy_analysis': strategy_results,
                'preferences_used': preferences,
                'game_summary': {
                    'total_segments': sum(len(segs) for segs in preferences.values()),
                    'cfr_iterations': cfr_iterations,
                    'agreement_reached': final_state._agreement_reached if final_state else False,
                    'final_proposal': final_state._current_proposal if final_state else None
                }
            }
            
        except Exception as e:
            print(f"❌ Error during scheduling: {e}")
            return {
                'meeting_result': {'success': False, 'error': str(e)},
                'strategy_analysis': None,
                'preferences_used': None,
                'game_summary': None
            }
    
    def _simulate_optimal_negotiation(self, game, cfr_solver):
        """Simulate negotiation using the best strategy"""
        config = get_meeting_scheduling_config()
        
        # Use CFR-guided players for optimal performance
        players = [
            MultiPlayerCFRGuidedLLMPlayer(0, config["players"][0], cfr_solver),
            MultiPlayerCFRGuidedLLMPlayer(1, config["players"][1], cfr_solver),
            MultiPlayerCFRGuidedLLMPlayer(2, config["players"][2], cfr_solver)
        ]
        
        state = game.new_initial_state()
        step = 0
        max_steps = 20
        
        while not state.is_terminal() and step < max_steps:
            current_player = state.current_player()
            
            try:
                # For demo purposes, we'll use CFR players instead of LLM players
                # to avoid API calls. In production, you'd use the LLM players.
                cfr_player = MultiPlayerCFRPlayer(current_player, cfr_solver)
                action = cfr_player.select_action(state)
                
                if action is not None:
                    state.apply_action(action)
                else:
                    break
                    
            except Exception as e:
                print(f"Warning: Action selection failed at step {step}: {e}")
                break
            
            step += 1
        
        return state
    
    def analyze_availability(self, participant_emails, date_range=None):
        """Analyze participant availability without scheduling"""
        print(f"🔍 Analyzing availability for: {', '.join(participant_emails)}")
        
        preferences, valuations = self.preference_adapter.generate_real_preferences_from_calendars(
            participant_emails, date_range
        )
        
        from ..preferences import analyze_three_player_preferences
        analysis = analyze_three_player_preferences(preferences, valuations)
        
        return {
            'preferences': preferences,
            'analysis': analysis,
            'participants': participant_emails
        }
    
    def get_user_calendars(self):
        """Get list of user's calendars"""
        return self.calendar.get_calendar_list()