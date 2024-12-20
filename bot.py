# File: bot.py
import logging
from typing import Optional
import asyncio
import signal
from datetime import datetime
import random
import math

from twitchio.ext import commands
from openai import AsyncOpenAI
from config import Config
from database_manager import DatabaseManager
from tts_manager import TTSManager
from chat_manager import ChatManager
from command_handler import CommandHandler
from littlenavmap_integration import LittleNavmapIntegration
from personality import PersonalityManager

class Bot(commands.Bot):
    def __init__(
        self,
        openai_client: AsyncOpenAI,
        config: Config,
        db_manager: DatabaseManager,
        tts_manager: TTSManager,
        littlenavmap: LittleNavmapIntegration,
        personality: PersonalityManager
    ):
        # Initialize parent class with required parameters
        super().__init__(
            token=config.twitch.OAUTH_TOKEN,
            prefix=config.twitch.PREFIX,
            initial_channels=[config.twitch.CHANNEL.lower()]  # Make sure channel is lowercase
        )
        
        self.logger = logging.getLogger('Bot')
        self.config = config
        self.openai_client = openai_client
        self.db_manager = db_manager
        self.tts_manager = tts_manager
        self.littlenavmap = littlenavmap
        self.personality = personality
        
        # These will be set by main.py after initialization
        self.chat_manager: Optional[ChatManager] = None
        self.command_handler: Optional[CommandHandler] = None
        
        self.bot_ready = asyncio.Event()
        self._last_flight_update = None
        self._shutdown_event = asyncio.Event()
        self.start_time = datetime.now()

    async def event_ready(self):
        """Called once when the bot goes online."""
        self.logger.info(f"Bot is ready | {self.nick}")
        self.bot_ready.set()
        
        # Start periodic tasks
        self.loop.create_task(self.periodic_flight_info_update())
        if self.config.voice.ENABLED:
            self.loop.create_task(self.process_voice_commands())
        self.loop.create_task(self.periodic_location_facts())
        
        # Send startup message
        startup_message = self.personality.format_response(
            "AI Overlord systems online. Commencing channel supervision.",
            {}
        )
        
        # Get the channel from config
        channel_name = self.config.twitch.CHANNEL.lower()
        if channel := self.get_channel(channel_name):
            await channel.send(startup_message)
            await self.tts_manager.speak(startup_message)
        else:
            self.logger.error(f"Could not find channel: {channel_name}")

        self.logger.info(f"Bot joined channel: {channel_name}")

    async def event_message(self, message):
        """Called for every message received."""
        # Ignore messages from the bot itself
        if message.echo:
            return

        try:
            await self.chat_manager.handle_message(message)
        except Exception as e:
            self.logger.error(f"Error handling message: {e}", exc_info=True)

    async def event_command_error(self, ctx, error):
        """Called when a command encounters an error."""
        error_message = self.personality.get_error_response(
            "command_error",
            {"user": ctx.author.name}
        )
        await ctx.send(error_message)
        self.logger.error(f"Command error: {error}", exc_info=True)

    async def generate_chatgpt_response(self, message: str) -> str:
        """Generate a response using ChatGPT."""
        try:
            conversation_history = await self.db_manager.get_conversation_history()
            
            messages = [{"role": "system", "content": self.config.bot_personality}]
            for entry in conversation_history:
                messages.append({"role": "user", "content": entry['user']})
                messages.append({"role": "assistant", "content": entry['bot']})
            messages.append({"role": "user", "content": message})

            start_time = datetime.now()
            response = await self.openai_client.chat.completions.create(
                model=self.config.openai.MODEL,
                messages=messages,
                max_tokens=self.config.openai.MAX_TOKENS,
                temperature=self.config.openai.TEMPERATURE
            )
            
            bot_response = response.choices[0].message.content.strip()
            
            # Save conversation with timing metadata
            await self.db_manager.save_conversation(
                message, 
                bot_response,
                metadata={
                    'response_time': (datetime.now() - start_time).total_seconds(),
                    'model': self.config.openai.MODEL
                }
            )
            
            # Format response with personality
            return self.personality.format_response(bot_response, {})
            
        except Exception as e:
            self.logger.error(f"Error generating ChatGPT response: {e}", exc_info=True)
            return "Error processing request. Maintenance protocols engaged. Comply."

    
    async def periodic_flight_info_update(self):
        """Periodically update flight information."""
        last_altitude = None
        last_position = None
        sim_initialized = False
        
        while not self._shutdown_event.is_set():
            try:
                sim_info = await self.littlenavmap.get_sim_info()
                if sim_info and sim_info.get('active'):
                    # Check if simulator is properly initialized
                    if not sim_initialized and sim_info.get('simconnect_status') == "No Error":
                        sim_initialized = True
                        self.logger.info("Flight simulator connection established")
                        
                    # Get current values
                    current_altitude = sim_info.get('indicated_altitude', 0)
                    ground_altitude = sim_info.get('ground_altitude', 0)
                    altitude_agl = sim_info.get('altitude_above_ground', 0)
                    current_position = sim_info.get('position', {})
                    
                    # Adjust for ground level
                    adjusted_altitude = max(0, current_altitude + abs(min(0, current_altitude)))
                    
                    # Convert units
                    altitude_ft = round(adjusted_altitude)
                    ground_speed_kts = round(sim_info.get('ground_speed', 0) * 1.943844)  # m/s to knots
                    heading = round(sim_info.get('heading', 0), 1)
                    wind_speed_kts = round(sim_info.get('wind_speed', 0) * 1.943844)  # m/s to knots
                    wind_direction = round(sim_info.get('wind_direction', 0), 1)
                    vertical_speed_fpm = round(sim_info.get('vertical_speed', 0) * 196.85)  # m/s to ft/min
                    
                    # Only process if we have valid altitude
                    if altitude_ft >= 0:
                        # Log significant altitude changes
                        if last_altitude is None or abs(altitude_ft - last_altitude) > 1000:
                            self.logger.info(f"Significant altitude change: {altitude_ft} feet (AGL: {round(altitude_agl)} ft)")
                            last_altitude = altitude_ft
                            
                            # Only announce if we're airborne
                            if altitude_agl > 50:  # More than 50 feet AGL
                                message = self.personality.format_response(
                                    f"Altitude milestone: {altitude_ft:,.0f} feet above sea level, "
                                    f"{round(altitude_agl):,.0f} feet above ground.",
                                    {}
                                )
                                await self.tts_manager.speak(message, priority=2)
                        
                        # Log significant position changes
                        if last_position is None or (
                            abs(current_position.get('lat', 0) - last_position.get('lat', 0)) > 0.1 or
                            abs(current_position.get('lon', 0) - last_position.get('lon', 0)) > 0.1
                        ):
                            self.logger.info(
                                f"Significant position change: "
                                f"Lat {current_position.get('lat')}, Lon {current_position.get('lon')}"
                            )
                            last_position = current_position.copy()
                        
                        # Save flight data to database
                        await self.db_manager.save_flight_data(
                            {
                                'altitude': altitude_ft,
                                'altitude_agl': round(altitude_agl),
                                'ground_altitude': round(ground_altitude),
                                'latitude': current_position.get('lat', 0),
                                'longitude': current_position.get('lon', 0),
                                'heading': heading,
                                'ground_speed': ground_speed_kts,
                                'wind_speed': wind_speed_kts,
                                'wind_direction': wind_direction,
                                'on_ground': altitude_agl < 1,
                                'vertical_speed': vertical_speed_fpm,
                                'true_airspeed': round(sim_info.get('true_airspeed', 0) * 1.943844),  # m/s to knots
                                'indicated_speed': round(sim_info.get('indicated_speed', 0) * 1.943844)  # m/s to knots
                            }
                        )
                        
                        self._last_flight_update = datetime.now()
                    else:
                        self.logger.debug(f"Invalid altitude reading: {current_altitude}")
                else:
                    if sim_initialized:
                        self.logger.info("Lost connection to flight simulator")
                        sim_initialized = False
                    else:
                        self.logger.debug("Waiting for flight simulator connection...")
                        
            except Exception as e:
                self.logger.error(f"Error during flight info update: {e}")
            
            await asyncio.sleep(60)  # Update every minute
            
    async def process_voice_commands(self):
        """Process voice commands."""
        while not self._shutdown_event.is_set():
            try:
                # Placeholder for voice command processing
                # This would involve using a voice recognition library
                # and then parsing the recognized text for commands
                # For now, just log the command
                # Example:
                # recognized_text = await self.voice_recognizer.recognize()
                # if recognized_text:
                #     self.logger.info(f"Voice command recognized: {recognized_text}")
                #     await self.chat_manager.handle_voice_command(recognized_text)
                await asyncio.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Error processing voice commands: {e}")
                await asyncio.sleep(1)

    async def handle_alert(self, alert_name: str, channel: str):
        """Handle alert triggers."""
        alert = self.personality.get_alert(alert_name)
        if alert:
            response = self.personality.format_response(alert, {})
            if channel_obj := self.get_channel(channel):
                await channel_obj.send(response)
                await self.tts_manager.speak(response)

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler():
            self.logger.info("Shutdown signal received")
            self._shutdown_event.set()

        try:
            for sig in (signal.SIGTERM, signal.SIGINT):
                self.loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Windows doesn't support SIGTERM
            pass

    async def close(self):
        """Close the bot and cleanup resources."""
        self.logger.info("Closing bot...")
        
        # Set shutdown event
        self._shutdown_event.set()
        
        # Save personality state
        self.personality.save_state()
        
        # Close all managers
        await self.tts_manager.close()
        await self.db_manager.close()
        await self.littlenavmap.stop()
        if self.chat_manager:
            await self.chat_manager.close()
        
        # Close parent
        await super().close()
        
        self.logger.info("Bot shutdown complete")

    async def __aenter__(self):
        self.setup_signal_handlers()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def periodic_location_facts(self):
        """Periodically announce interesting facts about the current location."""
        while not self._shutdown_event.is_set():
            try:
                sim_info = await self.littlenavmap.get_sim_info()
                if sim_info and sim_info.get('active'):
                    latitude = sim_info.get('position', {}).get('lat')
                    longitude = sim_info.get('position', {}).get('lon')
                    
                    if latitude is not None and longitude is not None:
                        self.logger.debug(f"Location data: Latitude={latitude}, Longitude={longitude}")
                        fact = await self.generate_location_fact(latitude, longitude)
                        if fact:
                            await self.chat_manager.send_message(
                                self.config.twitch.CHANNEL.lower(),
                                fact,
                                tts=True
                            )
                
                # Random interval between 5 and 15 minutes
                interval = random.randint(300, 900)
                await asyncio.sleep(interval)
            except Exception as e:
                self.logger.error(f"Error during periodic location fact update: {e}")
                await asyncio.sleep(60)

    async def generate_location_fact(self, latitude: float, longitude: float) -> Optional[str]:
        """Generate a fact about the current location using GPT-4."""
        try:
            miles = 10
            kilometers = self.miles_to_kilometers(miles)
            prompt = (
                f"Generate an interesting fact about a landmark or point of interest within {kilometers:.0f} kilometers (approximately {miles} miles) of latitude {latitude} and longitude {longitude}. "
                "Keep it concise and engaging for a Twitch chat."
            )
            
            response = await self.openai_client.chat.completions.create(
                model=self.config.openai.MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.config.openai.MAX_TOKENS,
                temperature=self.config.openai.TEMPERATURE
            )
            
            fact = response.choices[0].message.content.strip()
            return self.personality.format_response(fact, {})
        except Exception as e:
            self.logger.error(f"Error generating location fact: {e}", exc_info=True)
            return None

    def miles_to_kilometers(self, miles: float) -> float:
        """Convert miles to kilometers."""
        return miles * 1.60934