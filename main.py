# File: main.py
import asyncio
import logging
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path
import signal
from typing import Optional
import json
import os

import sentry_sdk
from openai import AsyncOpenAI
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src'))) # Added path to the src directory
from src.config import Config, load_config, ConfigError
from src.bot import Bot
from src.database_manager import DatabaseManager
from src.tts_manager import TTSManager
from src.chat_manager import ChatManager
from src.command_handler import CommandHandler
from src.littlenavmap_integration import LittleNavmapIntegration
from src.personality import PersonalityManager
# Add Aviation Weather Dependency
from src.aviation_weather_integration import AviationWeatherIntegration

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "filename": record.filename,
            "lineno": record.lineno,
            "funcName": record.funcName,
            "threadName": record.threadName,
            "process": record.process
            
        }
        if record.exc_info:
            log_data["exc_info"] = self.formatException(record.exc_info)
            
        return json.dumps(log_data)

class BotApplication:
    def __init__(self):
        self.logger = self.setup_logging()
        self.config: Optional[Config] = None
        self.bot: Optional[Bot] = None
        self.shutdown_event = asyncio.Event()
        
    def setup_logging(self) -> logging.Logger:
        """Setup logging configuration."""
        logger = logging.getLogger('BotApplication')
        logger.setLevel(logging.INFO)

        # Create logs directory if it doesn't exist
        Path("logs").mkdir(exist_ok=True)

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)

        # File handler
        file_handler = RotatingFileHandler(
            'logs/bot.log',
            maxBytes=10485760,  # 10MB
            backupCount=5
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = JsonFormatter()
        file_handler.setFormatter(file_formatter)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

        return logger

    async def initialize(self):
        """Initialize all bot components."""
        try:
            self.logger.info("Starting bot initialization...")
            
            # Load configuration
            try:
                self.config = load_config()
                self.logger.info("Configuration loaded successfully")
            except ConfigError as e:
                self.logger.error(f"Configuration Error: {e}")
                raise

            # Initialize Sentry
            if self.config.is_production and self.config.sentry_dsn:
                sentry_sdk.init(
                    dsn=self.config.sentry_dsn,
                    traces_sample_rate=1.0
                )
                self.logger.info("Sentry initialized")

            # Initialize OpenAI client
            try:
                openai_client = AsyncOpenAI(api_key=self.config.openai.API_KEY)
                self.logger.info("OpenAI client initialized")
            except Exception as e:
                self.logger.error(f"Error initializing OpenAI client: {e}")
                raise
                

            # Initialize database manager
            try:
                db_manager = DatabaseManager(self.config)
                await db_manager.connect()
                self.logger.info("Database connection established")
            except Exception as e:
                 self.logger.error(f"Error initializing database manager: {e}")
                 raise

            # Initialize TTS manager
            try:
                tts_manager = TTSManager(self.config)
                await tts_manager.start()
                self.logger.info("TTS manager initialized")
            except Exception as e:
                self.logger.error(f"Error initializing TTS manager: {e}")
                raise


            # Initialize LittleNavmap integration
            try:
                navmap = LittleNavmapIntegration(self.config)
                await navmap.start()
                self.logger.info("LittleNavmap integration initialized")
            except Exception as e:
                 self.logger.error(f"Error initializing LittleNavmap integration: {e}")
                 raise
            
            # Initialize Aviation Weather integration
            try:
                aviation_weather = AviationWeatherIntegration(self.config)
                await aviation_weather.start()
                self.logger.info("Aviation weather integration initialized")
            except Exception as e:
                self.logger.error(f"Error initializing Aviation weather integration: {e}")
                raise

            # Initialize personality manager
            try:
                personality = PersonalityManager()
                personality.load_state()
                self.logger.info("Personality manager initialized")
            except Exception as e:
                 self.logger.error(f"Error initializing Personality manager: {e}")
                 raise

            # Initialize bot instance
            try:
                self.bot = Bot(
                    openai_client=openai_client,
                    config=self.config,
                    db_manager=db_manager,
                    tts_manager=tts_manager,
                    littlenavmap=navmap,
                    personality=personality,
                    aviation_weather = aviation_weather # Added AviationWeatherIntegration
                )
            except Exception as e:
                  self.logger.error(f"Error initializing bot instance: {e}")
                  raise

            # Initialize chat manager
            try:
                 chat_manager = ChatManager(self.bot, self.config)
                 await chat_manager.start()
                 self.logger.info("Chat manager initialized")
            except Exception as e:
                 self.logger.error(f"Error initializing Chat manager: {e}")
                 raise


            # Initialize command handler
            try:
                command_handler = CommandHandler(self.bot)  # Only pass the bot instance
                command_handler.aviation_weather = aviation_weather  # Set the aviation weather integration
                self.logger.info("Command handler initialized")
            except Exception as e:
                 self.logger.error(f"Error initializing Command handler: {e}")
                 raise

            # Set up components in bot
            self.bot.chat_manager = chat_manager
            self.bot.command_handler = command_handler
            
            self.logger.info("Bot initialization completed successfully")

        except Exception as e:
            self.logger.error(f"Error during initialization: {e}", exc_info=True)
            raise

    async def shutdown(self):
        """Gracefully shutdown all components."""
        self.logger.info("Initiating shutdown sequence...")
        
        try:
            if self.bot:
                # Save personality state
                if hasattr(self.bot, 'personality'):
                    try:
                       self.bot.personality.save_state()
                       self.logger.info("Personality state saved")
                    except Exception as e:
                        self.logger.error(f"Error saving personality: {e}")

                # Close TTS manager
                if hasattr(self.bot, 'tts_manager'):
                    try:
                        await self.bot.tts_manager.close()
                        self.logger.info("TTS manager closed")
                    except Exception as e:
                        self.logger.error(f"Error closing TTS manager: {e}")

                # Close database connection
                if hasattr(self.bot, 'db_manager'):
                    try:
                       await self.bot.db_manager.close()
                       self.logger.info("Database connection closed")
                    except Exception as e:
                       self.logger.error(f"Error closing database manager: {e}")
                       
                # Close LittleNavmap integration
                if hasattr(self.bot, 'littlenavmap'):
                   try:
                        await self.bot.littlenavmap.stop()
                        self.logger.info("LittleNavmap integration stopped")
                   except Exception as e:
                       self.logger.error(f"Error stopping LNM integration: {e}")

                 # Close Aviation Weather Integration
                if hasattr(self.bot, 'aviation_weather'):
                  try:
                      await self.bot.aviation_weather.stop()
                      self.logger.info("Aviation Weather integration stopped")
                  except Exception as e:
                      self.logger.error(f"Error stopping Aviation Weather integration: {e}")


                # Close chat manager
                if hasattr(self.bot, 'chat_manager') and self.bot.chat_manager:
                    try:
                        await self.bot.chat_manager.close()
                        self.logger.info("Chat manager closed")
                    except Exception as e:
                        self.logger.error(f"Error closing chat manager: {e}")

                # Close bot
                try:
                   await self.bot.close()
                   self.logger.info("Bot closed")
                except Exception as e:
                     self.logger.error(f"Error closing bot: {e}")

            self.logger.info("Shutdown sequence completed")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
            raise
        finally:
            self.shutdown_event.set()

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(sig, frame):
            self.logger.info(f"Shutdown signal {sig} received")
            asyncio.create_task(self.shutdown())

        try:
            for sig in (signal.SIGTERM, signal.SIGINT):
                signal.signal(sig, signal_handler)
        except NotImplementedError:
            # Windows doesn't support SIGTERM
            pass

    async def run(self):
        """Main run method."""
        try:
            await self.initialize()
            self.setup_signal_handlers()
            
            self.logger.info("Starting bot...")
            if self.bot:
                await self.bot.start()
            
            # Keep running until shutdown event is set
            await self.shutdown_event.wait()
            
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}", exc_info=True)
            await self.shutdown()
        finally:
            self.logger.info("Bot application terminated")

def main():
    """Entry point for the application."""
    app = BotApplication()
    
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        print("\nShutdown initiated by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()