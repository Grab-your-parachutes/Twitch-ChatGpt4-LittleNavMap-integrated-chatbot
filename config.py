# File: config.py
import os
from dotenv import load_dotenv
from dataclasses import dataclass, field
from typing import Optional, Dict, List
import logging
import json
import yaml
from pathlib import Path
from pydantic import BaseModel, validator

logger = logging.getLogger(__name__)

class ConfigError(Exception):
    """Custom exception for configuration errors."""
    pass

class DatabaseConfig(BaseModel):
    URI: str
    DB_NAME: str
    COLLECTION_PREFIX: str = "bot_"
    MAX_POOL_SIZE: int = 10
    TIMEOUT_MS: int = 5000

    @validator('URI')
    def validate_uri(cls, v):
        if not v.startswith(('mongodb://', 'mongodb+srv://')):
            raise ValueError("Database URI must start with 'mongodb://' or 'mongodb+srv://'")
        return v

class TwitchConfig(BaseModel):
    OAUTH_TOKEN: str
    CHANNEL: str
    BOT_NAME: str
    BROADCASTER_ID: str
    PREFIX: str = "!"
    RATE_LIMIT: int = 20
    MESSAGE_LIMIT: int = 500

    @validator('OAUTH_TOKEN')
    def validate_oauth(cls, v):
        if not v.startswith('oauth:'):
            raise ValueError("Twitch OAuth token must start with 'oauth:'")
        return v

class OpenAIConfig(BaseModel):
    API_KEY: str
    MODEL: str = "gpt-4"
    MAX_TOKENS: int = 150
    TEMPERATURE: float = 0.7

class VoiceConfig(BaseModel):
    ENABLED: bool = True
    PREFIX: str = "Hey Overlord"
    COMMAND_TIMEOUT: float = 5.0
    PHRASE_LIMIT: float = 10.0
    LANGUAGE: str = "en-US"
    CONFIDENCE_THRESHOLD: float = 0.7

class StreamerBotConfig(BaseModel):
    WS_URI: str
    RECONNECT_ATTEMPTS: int = 5
    HEARTBEAT_INTERVAL: int = 20

    @validator('WS_URI')
    def validate_ws_uri(cls, v):
        if not v.startswith('ws://'):
            raise ValueError("WebSocket URI must start with 'ws://'")
        return v

class LittleNavMapConfig(BaseModel):
    BASE_URL: str = "http://localhost:8965"
    UPDATE_INTERVAL: float = 1.0
    CACHE_TTL: int = 30

@dataclass
class Config:
    twitch: TwitchConfig
    database: DatabaseConfig
    openai: OpenAIConfig
    voice: VoiceConfig
    streamerbot: StreamerBotConfig
    littlenavmap: LittleNavMapConfig
    bot_trigger_words: List[str] = field(default_factory=lambda: ["bot", "assistant"])
    bot_personality: str = "You are an AI Overlord managing a flight simulation Twitch channel."
    verbose: bool = False
    environment: str = field(default_factory=lambda: os.getenv('ENV', 'development'))
    command_cooldowns: Dict[str, int] = field(default_factory=dict)
    custom_commands_enabled: bool = True
    log_level: str = "INFO"
    sentry_dsn: Optional[str] = None

    def __post_init__(self):
        self.validate()
        self.setup_derived_values()

    def validate(self):
        """Validate configuration values."""
        if self.environment not in ['development', 'production', 'testing']:
            raise ConfigError("Invalid environment specified")

    def setup_derived_values(self):
        """Set up any derived configuration values."""
        self.is_production = self.environment == 'production'
        self.is_development = self.environment == 'development'
        self.is_testing = self.environment == 'testing'

    @classmethod
    def load_from_env(cls) -> 'Config':
        """Load configuration from environment variables."""
        load_dotenv()
        
        try:
            twitch_config = TwitchConfig(
                OAUTH_TOKEN=os.getenv('TWITCH_OAUTH_TOKEN'),
                CHANNEL=os.getenv('TWITCH_CHANNEL'),
                BOT_NAME=os.getenv('BOT_NAME'),
                BROADCASTER_ID=os.getenv('BROADCASTER_ID'),
                PREFIX=os.getenv('BOT_PREFIX', '!')
            )

            database_config = DatabaseConfig(
                URI=os.getenv('MONGO_URI'),
                DB_NAME=os.getenv('MONGO_DB_NAME')
            )

            openai_config = OpenAIConfig(
                API_KEY=os.getenv('CHATGPT_API_KEY'),
                MODEL=os.getenv('OPENAI_MODEL', 'gpt-4')
            )

            voice_config = VoiceConfig(
                ENABLED=os.getenv('VOICE_ENABLED', 'True').lower() == 'true',
                PREFIX=os.getenv('VOICE_PREFIX', 'Hey Overlord'),
                COMMAND_TIMEOUT=float(os.getenv('VOICE_COMMAND_TIMEOUT', '5')),
                PHRASE_LIMIT=float(os.getenv('VOICE_COMMAND_PHRASE_LIMIT', '10')),
                LANGUAGE=os.getenv('VOICE_COMMAND_LANGUAGE', 'en-US')
            )

            streamerbot_config = StreamerBotConfig(
                WS_URI=os.getenv('STREAMERBOT_WS_URI')
            )

            littlenavmap_config = LittleNavMapConfig(
                BASE_URL=os.getenv('LITTLENAVMAP_URL', 'http://localhost:8965')
            )

            return cls(
                twitch=twitch_config,
                database=database_config,
                openai=openai_config,
                voice=voice_config,
                streamerbot=streamerbot_config,
                littlenavmap=littlenavmap_config,
                bot_trigger_words=os.getenv('BOT_TRIGGER_WORDS', 'bot,assistant').split(','),
                bot_personality=os.getenv('BOT_PERSONALITY', 'You are an AI Overlord managing a flight simulation Twitch channel.'),
                verbose=os.getenv('VERBOSE', 'False').lower() == 'true',
                sentry_dsn=os.getenv('SENTRY_DSN')
            )

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise ConfigError(f"Configuration loading failed: {e}")

    @classmethod
    def load_from_file(cls, file_path: str) -> 'Config':
        """Load configuration from a YAML file."""
        try:
            with open(file_path, 'r') as f:
                config_data = yaml.safe_load(f)
            
            twitch_config = TwitchConfig(**config_data.get('twitch', {}))
            database_config = DatabaseConfig(**config_data.get('database', {}))
            openai_config = OpenAIConfig(**config_data.get('openai', {}))
            voice_config = VoiceConfig(**config_data.get('voice', {}))
            streamerbot_config = StreamerBotConfig(**config_data.get('streamerbot', {}))
            littlenavmap_config = LittleNavMapConfig(**config_data.get('littlenavmap', {}))
            
            return cls(
                twitch=twitch_config,
                database=database_config,
                openai=openai_config,
                voice=voice_config,
                streamerbot=streamerbot_config,
                littlenavmap=littlenavmap_config,
                bot_trigger_words=config_data.get('bot_trigger_words', ["bot", "assistant"]),
                bot_personality=config_data.get('bot_personality', 'You are an AI Overlord managing a flight simulation Twitch channel.'),
                verbose=config_data.get('verbose', False),
                sentry_dsn=config_data.get('sentry_dsn')
            )
        except Exception as e:
            logger.error(f"Failed to load configuration from file: {e}")
            raise ConfigError(f"Configuration file loading failed: {e}")

def load_config() -> Config:
    """Load configuration from environment or file."""
    try:
        if config_file := os.getenv('CONFIG_FILE'):
            if Path(config_file).exists():
                return Config.load_from_file(config_file)
            else:
                logger.warning(f"Config file not found at {config_file}, falling back to environment variables.")
                return Config.load_from_env()
        return Config.load_from_env()
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise