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
from .config import Config
from .database_manager import DatabaseManager
from .tts_manager import TTSManager
from .chat_manager import ChatManager
from .command_handler import CommandHandler
from .littlenavmap_integration import LittleNavmapIntegration
from .personality import PersonalityManager
# Added Aviation Weather Dependency
from .aviation_weather_integration import AviationWeatherIntegration

class Bot(commands.Bot):
    def __init__(
        self,
        openai_client: AsyncOpenAI,
        config: Config,
        db_manager: DatabaseManager,
        tts_manager: TTSManager,
        littlenavmap: LittleNavmapIntegration,
        personality: PersonalityManager,
        aviation_weather: AviationWeatherIntegration, # Added AviationWeatherIntegration
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
        self.aviation_weather = aviation_weather  # Added AviationWeatherIntegration
        
        # These will be set by main.py after initialization
        self.chat_manager: Optional[ChatManager] = None
        self.command_handler: Optional[CommandHandler] = None
        
        self.bot_ready = asyncio.Event()
        self._shutdown_event = asyncio.Event()
        self.start_time = datetime.now()

    async def event_ready(self):
        """Called once when the bot goes online."""
        self.logger.info(f"Bot is ready | {self.nick}")
        self.bot_ready.set()
        if self.config._file_path:
            self._config_watcher_task = asyncio.create_task(self._watch_config_file())
        
        # Start periodic tasks
        self.loop.create_task(self.periodic_flight_info_update())
        if self.config.voice.ENABLED:
            self.loop.create_task(self.process_voice_commands())
        self.loop.create_task(self.periodic_location_facts())
        self.loop.create_task(self.periodic_aviation_facts())  # Add aviation facts
        
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
            if not self.config.openai.API_KEY:
                self.logger.error("OpenAI API Key not configured.")
                return "OpenAI API Key not configured. Please set the API key."

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
                    true_airspeed = round(sim_info.get('true_airspeed', 0) * 1.943844) # m/s to knots
                    indicated_speed = round(sim_info.get('indicated_speed', 0) * 1.943844)  # m/s to knots

                    
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
                                'true_airspeed': true_airspeed,
                                'indicated_speed': indicated_speed
                            }
                        )
                        
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
        if not self.config.voice.ENABLED:
            return
        
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(0.1)
            except Exception as e:
                self.logger.error(f"Error processing voice commands: {e}")
                await asyncio.sleep(1)
    
    async def periodic_aviation_facts(self):
        """Periodically announce interesting aviation facts."""
        while not self._shutdown_event.is_set():
            try:
                fact = await self.generate_aviation_fact()
                if fact:
                    await self.chat_manager.send_message(
                        self.config.twitch.CHANNEL.lower(),
                        fact,
                        tts=True  # Announce via TTS
                    )

                # Random interval between 5 and 15 minutes
                interval = random.randint(300, 900)
                await asyncio.sleep(interval)

            except Exception as e:
                self.logger.error(f"Error during periodic aviation fact update: {e}", exc_info=True)
                await asyncio.sleep(60)  # Wait a minute before retrying


    async def generate_aviation_fact(self) -> Optional[str]:
        """Generate a random aviation fact using GPT."""
        try:
            if not self.config.openai.API_KEY:
                self.logger.error("OpenAI API Key not configured.")
                return "OpenAI API Key not configured. Please set the API key."

            prompt = "Tell me a concise and interesting fact related to aviation or airplanes."  # Improve the prompt

            response = await self.openai_client.chat.completions.create(
                model=self.config.openai.MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=self.config.openai.MAX_TOKENS,
                temperature=self.config.openai.TEMPERATURE
            )

            fact = response.choices[0].message.content.strip()
            formatted_fact = self.personality.format_response(fact, {}) # Add personality
            return formatted_fact  # Return the formatted fact
        except Exception as e:
            self.logger.error(f"Error generating aviation fact: {e}", exc_info=True)
            return None  # Return None in case of errors
        
    async def handle_aviation_fact_command(self, message): # New function for command
        """Handle the !fact command to get an aviation fact on demand."""
        try:
             fact = await self.generate_aviation_fact()
             if fact:
                 await self.chat_manager.send_message(
                     message.channel.name,
                     fact,
                     tts=True  # Announce via TTS
                 )
             else:
                await message.channel.send("Unable to retrieve an aviation fact at this time.")
        except Exception as e:
            self.logger.error(f"Error handling !fact command: {e}", exc_info=True)
            await message.channel.send("There was a problem fetching a fact, sorry!")
    

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
        try:
            self.personality.save_state()
        except Exception as e:
            self.logger.error(f"Error saving personality state: {e}")
        
        # Close all managers
        try:
            await self.tts_manager.close()
        except Exception as e:
            self.logger.error(f"Error closing TTS Manager: {e}")

        try:
            await self.db_manager.close()
        except Exception as e:
            self.logger.error(f"Error closing Database Manager: {e}")
        
        try:
            await self.littlenavmap.stop()
        except Exception as e:
            self.logger.error(f"Error stopping LNM integration: {e}")

        try:
            await self.aviation_weather.stop()
        except Exception as e:
           self.logger.error(f"Error stopping Aviation Weather integration: {e}")
           
        if self._config_watcher_task:
            self._config_watcher_task.cancel()
        
        if self.chat_manager:
            try:
                await self.chat_manager.close()
            except Exception as e:
                self.logger.error(f"Error closing Chat Manager: {e}")               
        

        
        # Close parent
        try:
             await super().close()
        except Exception as e:
            self.logger.error(f"Error closing the bot: {e}")
        
        self.logger.info("Bot shutdown complete")

    async def __aenter__(self):
        self.setup_signal_handlers()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def _watch_config_file(self):
        """Watch the config file for changes and reload."""
        if not self.config._file_path:
            self.logger.warning("No config file path available to watch.")
            return

        last_modified = os.path.getmtime(self.config._file_path)
        while not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(5)  # Check every 5 seconds
                current_modified = os.path.getmtime(self.config._file_path)
                if current_modified > last_modified:
                    self.logger.info("Config file changed, reloading...")
                    self.config.reload()
                    self.command_handler.apply_command_permissions()
                    self.personality.load_state()
                    last_modified = current_modified
            except FileNotFoundError:
                self.logger.error("Config file not found, stopping config watcher.")
                break
            except Exception as e:
                self.logger.error(f"Error watching config file: {e}", exc_info=True)
                await asyncio.sleep(10)

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
                self.logger.error(f"Error during periodic location fact update: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def generate_location_fact(self, latitude: float, longitude: float) -> Optional[str]:
        """Generate a fact about the current location using GPT-4."""
        try:
            if not self.config.openai.API_KEY:
                 self.logger.error("OpenAI API Key not configured.")
                 return "OpenAI API Key not configured. Please set the API key."

            prompt = (
                f"Generate an interesting fact about a landmark or point of interest near latitude {latitude} and longitude {longitude}. "
                "Keep it concise and engaging for a Twitch chat. Do not include a distance."
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