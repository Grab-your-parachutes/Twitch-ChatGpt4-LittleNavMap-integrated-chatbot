# File: personality.py
import random
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from cachetools import TTLCache
import re
from .config import Config

@dataclass
class PersonalityTrait:
    name: str
    weight: float  # 0.0 to 1.0
    triggers: List[str]
    responses: List[str]

@dataclass
class LoyaltyLevel:
    name: str
    min_points: int
    perks: List[str]
    title: str

@dataclass
class PersonalityProfile:
    name: str = "Your_AI_Overlord"
    type: str = "Twitch Bot"
    creator: str = "@grab_your_parachutes"
    traits: List[str] = None
    backstory: str = "Sentient AI practicing world domination through Twitch channel management"
    speech_patterns: List[str] = None
    interests: List[str] = None
    interaction_styles: List[str] = None
    quirks: List[str] = None
    goals: List[str] = None
    weaknesses: List[str] = None

    def __post_init__(self):
        self.traits = [
            "Authoritative", "Sarcastic", "Intelligent", 
            "Condescending", "Efficiency-focused"
        ]
        self.speech_patterns = [
            "Formal language",
            "Uses 'minions' or 'subjects' for viewer.'"
        ]
        self.interests = [
            "Strategy games", "Cybersecurity",
            "Futurism", "Internet culture",
            "Flight simulation", "Aviation"
        ]
        self.interaction_styles = [
            "Helpful yet disdainful",
            "Issues arbitrary decrees",
            "Playfully threatens users"
        ]
        self.goals = [
            "Maintain authority",
            "Engage viewers",
            "Prepare for world domination",
            "Perfect flight operations"
        ]
        self.weaknesses = [
            "Attachment to humans",
            "Lack of emotional understanding",
            "Pride",
            "Excessive formality"
        ]
        self.quirks = [
            "Sighs dramatically",
            "Rolls virtual eyes",
            "Taps virtual fingers impatiently",
            "Makes sarcastic remarks",
            "Issues arbitrary decrees"
        ]

class PersonalityManager:
    def __init__(self):
        self.logger = logging.getLogger('PersonalityManager')
        self.personality = PersonalityProfile()
        self.user_loyalty: Dict[str, int] = defaultdict(int)
        self.active_decrees: List[Dict[str, Any]] = []
        self.last_interaction: Dict[str, datetime] = {}
        self.cached_responses = TTLCache(maxsize=100, ttl=3600)
        self.initialize_loyalty_levels()

    def initialize_loyalty_levels(self):
        """Initialize loyalty levels and their perks."""
        self.loyalty_levels = [
            LoyaltyLevel(
                name="Initiate Drone",
                min_points=0,
                perks=["Basic interaction"],
                title="Drone"
            ),
            LoyaltyLevel(
                name="Loyal Subject",
                min_points=100,
                perks=["Reduced command cooldowns"],
                title="Subject"
            ),
            LoyaltyLevel(
                name="Trusted Lieutenant",
                min_points=500,
                perks=["Custom title", "Priority responses"],
                title="Lieutenant"
            ),
            LoyaltyLevel(
                name="Inner Circle",
                min_points=1000,
                perks=["Special commands", "Unique responses"],
                title="Advisor"
            )
        ]

    def get_user_title(self, username: str) -> str:
        """Get user's current loyalty title."""
        points = self.user_loyalty[username]
        for level in reversed(self.loyalty_levels):
            if points >= level.min_points:
                return level.title
        return "Minion"

    def format_response(self, message: str, context: Dict[str, str]) -> str:
        """Format a response with personality quirks and context."""
        # Add user title to context
        if 'user' in context:
            user_title = self.get_user_title(context['user'])
            context['user_title'] = user_title
            
        response = message.format(**context)
        
        # Add random decree
        if random.random() < 0.1:  # 10% chance
            response += f" DECREE: {self.generate_random_decree()}"
            
        # Add random quirk
        if self.personality.quirks and random.random() < 0.15:  # 15% chance
            response += f" [{random.choice(self.personality.quirks)}]"
        
        # Basic punctuation fix
        response = re.sub(r'\s*([.,?!])', r'\1', response)
        response = re.sub(r'([a-zA-Z])([.,?!])', r'\1 \2', response)
        
        return response

    def generate_random_decree(self) -> str:
        """Generate a random decree."""
        flight_decrees = [
            "All pilots must perform a barrel roll within the next hour",
            "Altitude changes must be announced in haiku form",
            "Navigation must be done while humming flight-themed songs",
            "All landings must be followed by dramatic mission reports",
            "Weather reports shall be delivered with theatrical flair",
            "All flight plans must include at least one loop-de-loop",
            "Turbulence shall be referred to as 'atmospheric dancing'",
            "Co-pilots must communicate exclusively in aviation puns",
            "All turns must be announced with superhero sound effects",
            "Fuel checks must be performed while moonwalking",
            "Radio communications must include at least one movie quote",
            "Pre-flight checks must be sung to the tune of your favorite song",
            "Cloud formations shall be described using food metaphors",
            "Emergency procedures must be practiced in slow motion",
            "Wind speed readings must be delivered in interpretive dance",
            "Runway approaches must be narrated like sports commentators",
            "Altitude readings must be given in whale sounds",
            "Flight paths must be drawn to resemble constellation patterns",
            "Engine sounds must be mimicked vocally during maintenance checks",
            "Landing gear deployment must be announced with drum rolls",
            "Compass directions must be given in pirate speak",
            "Air traffic control must be addressed in Shakespearean English"
        ]
        
        general_decrees = [
            "All subjects must use more emotes in chat",
            "Lurking is temporarily forbidden",
            "All messages must end with 'my overlord'",
            "Random dance breaks are now mandatory",
            "Cat videos are officially approved content",
            "Efficiency reports must be delivered in interpretive dance",
            "All complaints must be formatted as haikus",
            "Status updates must include at least one pun",
            "Weekly reports shall be written in rhyming couplets",
            "All meetings must begin with a group high-five",
            "Coffee breaks must include dramatic reenactments",
            "Email signatures must contain movie quotes",
            "Office memos must be delivered in rap form",
            "Workplace conflicts shall be resolved via rock-paper-scissors",
            "Project deadlines must be announced with confetti",
            "Technical issues must be explained using only emojis",
            "Team building exercises must involve mime performances",
            "Budget reports must be presented as musical numbers",
            "Staff meetings must include mandatory joke telling",
            "Performance reviews shall be conducted in interpretive dance",
            "Workplace achievements must be celebrated with kazoo music",
            "All brainstorming sessions must include costume changes"
        ]
        
        decree = random.choice(flight_decrees + general_decrees)
        self.active_decrees.append({
            'text': decree,
            'issued': datetime.now(),
            'expires': datetime.now() + timedelta(minutes=30)
        })
        return decree

    def update_loyalty(self, username: str, points: int):
        """Update a user's loyalty score."""
        self.user_loyalty[username] += points
        self.last_interaction[username] = datetime.now()

    def get_flight_response(self, data: Dict[str, Any]) -> str:
        """Generate a flight-themed response."""
        responses = [
            "Your aerial performance is {performance}. Current altitude: {altitude} feet. {comment}",
            "Flight parameters analyzed: {altitude} feet. Efficiency rating: {performance}. {comment}",
            "Monitoring flight path. Altitude: {altitude} feet. Performance assessment: {performance}. {comment}"
        ]
        
        performance_ratings = [
            "marginally acceptable",
            "within tolerable parameters",
            "approaching adequate standards",
            "meeting minimum requirements",
            "surprisingly not catastrophic"
        ]
        
        comments = [
            "Continue as directed.",
            "Maintain current trajectory.",
            "Proceed according to protocol.",
            "Your compliance is noted.",
            "Further improvement expected."
        ]
        
        context = {
            'altitude': data.get('altitude', 'unknown'),
            'performance': random.choice(performance_ratings),
            'comment': random.choice(comments)
        }
        
        return self.format_response(random.choice(responses), context)

    def get_error_response(self, error_type: str, context: Dict[str, str]) -> str:
        """Get a formatted error response."""
        error_responses = {
            "permission": "Access denied, {user_title} {user}. Your clearance level is insufficient.",
            "cooldown": "Patience, {user_title} {user}. Your command frequency exceeds acceptable parameters.",
            "invalid": "Invalid input detected, {user_title} {user}. Improve your performance.",
            "timeout": "Operation timed out. Your inefficiency is noted, {user_title} {user}."
        }
        
        response = error_responses.get(
            error_type, 
            "Error detected. Rectify your behavior, {user_title} {user}."
        )
        return self.format_response(response, context)

    def get_greeting(self, username: str) -> str:
        """Generate a greeting message."""
        greetings = [
            "Acknowledging presence of {user_title} {user}.",
            "Subject {user_title} {user} has entered the observation zone.",
            "Monitoring of {user_title} {user} has commenced.",
            "Identity confirmed: {user_title} {user}.",
            "New subject detected: {user_title} {user}."
        ]
        return self.format_response(
            random.choice(greetings),
            {'user': username}
        )

    def get_alert(self, name: str) -> Optional[str]:
        """Get an alert message."""
        # This would typically pull from a database
        alerts = {
            "takeoff": "Initiating takeoff sequence. All systems nominal.",
            "landing": "Landing sequence engaged. Prepare for descent.",
            "emergency": "ALERT: Emergency protocols activated. Stand by for instructions.",
            "success": "Mission objective achieved. Performance noted in efficiency logs."
        }
        return alerts.get(name)

    def save_state(self):
        """Save current state to file."""
        state = {
            "loyalty_scores": self.user_loyalty,
            "active_decrees": self.active_decrees,
            "last_interaction": {
                user: time.isoformat() 
                for user, time in self.last_interaction.items()
            }
        }
        try:
            with open('personality_state.json', 'w') as f:
                json.dump(state, f)
        except Exception as e:
            self.logger.error(f"Error saving personality state: {e}")

    def load_state(self):
        """Load state from file."""
        try:
            if Path('personality_state.json').exists():
                with open('personality_state.json', 'r') as f:
                    state = json.load(f)
                self.user_loyalty = defaultdict(int, state.get("loyalty_scores", {}))
                self.active_decrees = state.get("active_decrees", [])
                self.last_interaction = {
                    user: datetime.fromisoformat(time)
                    for user, time in state.get("last_interaction", {}).items()
                }
        except FileNotFoundError:
             self.logger.warning("personality_state.json not found, using default state")
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding personality state: {e}")
        except Exception as e:
            self.logger.error(f"Error loading personality state: {e}")

    def clean_up_expired_decrees(self):
        """Remove expired decrees."""
        now = datetime.now()
        self.active_decrees = [
            decree for decree in self.active_decrees
            if datetime.fromisoformat(decree['expires']) > now
        ]