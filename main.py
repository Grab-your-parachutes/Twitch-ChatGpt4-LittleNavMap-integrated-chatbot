# File: main.py
import asyncio
import logging
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path
import signal
from typing import Optional

import sentry_sdk
from openai import AsyncOpenAI
from config import Config, load_config
from bot import Bot
from database_manager import DatabaseManager
from tts_manager import TTSManager
from chat_manager import ChatManager
from command_handler import CommandHandler
from littlenavmap_integration import LittleNavmapIntegration
from personality import PersonalityManager

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
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)

        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

        return logger

    async def initialize(self):
        """Initialize all bot components."""
        try:
            self.logger.info("Starting bot initialization...")
            
            # Load configuration
            self.config = load_config()
            self.logger.info("Configuration loaded successfully")

            # Initialize Sentry
            if self.config.is_production and self.config.sentry_dsn:
                sentry_sdk.init(
                    dsn=self.config.sentry_dsn,
                    traces_sample_rate=1.0
                )
                self.logger.info("Sentry initialized")

            # Initialize OpenAI client
            openai_client = AsyncOpenAI(api_key=self.config.openai.API_KEY)
            self.logger.info("OpenAI client initialized")

            # Initialize database manager
            db_manager = DatabaseManager(self.config)
            await db_manager.connect()
            self.logger.info("Database connection established")

            # Initialize TTS manager
            tts_manager = TTSManager(self.config)
            await tts_manager.start()
            self.logger.info("TTS manager initialized")

            # Initialize LittleNavmap integration
            navmap = LittleNavmapIntegration(self.config)
            await navmap.start()
            self.logger.info("LittleNavmap integration initialized")

            # Initialize personality manager
            personality = PersonalityManager()
            personality.load_state()
            self.logger.info("Personality manager initialized")

            # Initialize bot instance
            self.bot = Bot(
                openai_client=openai_client,
                config=self.config,
                db_manager=db_manager,
                tts_manager=tts_manager,
                littlenavmap=navmap,
                personality=personality
            )

            # Initialize chat manager
            chat_manager = ChatManager(self.bot, self.config)
            await chat_manager.start()
            self.logger.info("Chat manager initialized")

            # Initialize command handler
            command_handler = CommandHandler(self.bot, self.config)
            self.logger.info("Command handler initialized")

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
                    self.bot.personality.save_state()
                    self.logger.info("Personality state saved")

                # Close TTS manager
                if hasattr(self.bot, 'tts_manager'):
                    await self.bot.tts_manager.close()
                    self.logger.info("TTS manager closed")

                # Close database connection
                if hasattr(self.bot, 'db_manager'):
                    await self.bot.db_manager.close()
                    self.logger.info("Database connection closed")

                # Close LittleNavmap integration
                if hasattr(self.bot, 'littlenavmap'):
                    await self.bot.littlenavmap.stop()
                    self.logger.info("LittleNavmap integration stopped")

                # Close chat manager
                if hasattr(self.bot, 'chat_manager') and self.bot.chat_manager:
                    await self.bot.chat_manager.close()
                    self.logger.info("Chat manager closed")

                # Close bot
                await self.bot.close()
                self.logger.info("Bot closed")

            self.logger.info("Shutdown sequence completed")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
            raise
        finally:
            self.shutdown_event.set()

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler():
            self.logger.info("Shutdown signal received")
            asyncio.create_task(self.shutdown())

        try:
            for sig in (signal.SIGTERM, signal.SIGINT):
                asyncio.get_event_loop().add_signal_handler(
                    sig,
                    signal_handler
                )
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