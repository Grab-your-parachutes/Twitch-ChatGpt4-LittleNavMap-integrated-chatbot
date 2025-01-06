# config.py
import os
from dotenv import load_dotenv
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Union
import logging
import json
import yaml
from pathlib import Path
from pydantic import BaseModel, validator, ValidationError
import asyncio

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
     IGNORE_LIST: List[str] = field(default_factory=list)

     @validator('OAUTH_TOKEN')
     def validate_oauth(cls, v):
         if not v.startswith('oauth:'):
             raise ValueError("Twitch OAuth token must start with 'oauth:'")
         return v

class OpenAIConfig(BaseModel):
    API_KEY: str
    MODEL: str = "gpt-4o-mini" # Changed to gpt-4o-mini
    MAX_TOKENS: int = 150
    TEMPERATURE: float = 0.7

class VoiceConfig(BaseModel):
    ENABLED: bool = True
    PREFIX: str = "Hey Overlord"
    COMMAND_TIMEOUT: float = 5.0
    PHRASE_LIMIT: float = 10.0
    LANGUAGE: str = "en-US"
    CONFIDENCE_THRESHOLD: float = 0.7

    @validator('COMMAND_TIMEOUT')
    def validate_command_timeout(cls, v):
        if v <= 0:
            raise ValueError("Command timeout must be a positive number.")
        return v

    @validator('PHRASE_LIMIT')
    def validate_phrase_limit(cls, v):
        if v <= 0:
            raise ValueError("Phrase limit must be a positive number.")
        return v

class StreamerBotConfig(BaseModel):
    WS_URI: str
    RECONNECT_ATTEMPTS: int = 5
    HEARTBEAT_INTERVAL: int = 20

    @validator('WS_URI')
    def validate_ws_uri(cls, v):
        if not v.startswith('ws://'):
            raise ValueError("WebSocket URI must start with 'ws://'")
        return v

    @validator('RECONNECT_ATTEMPTS')
    def validate_reconnect_attempts(cls, v):
        if v <= 0:
            raise ValueError("Reconnect attempts must be a positive number.")
        return v

    @validator('HEARTBEAT_INTERVAL')
    def validate_heartbeat_interval(cls, v):
        if v <= 0:
            raise ValueError("Heartbeat interval must be a positive number.")
        return v

class LittleNavMapConfig(BaseModel):
    BASE_URL: str = "http://localhost:8965"
    UPDATE_INTERVAL: float = 1.0
    CACHE_TTL: int = 30

    @validator('UPDATE_INTERVAL')
    def validate_update_interval(cls, v):
        if v <= 0:
            raise ValueError("Update interval must be a positive number.")
        return v

    @validator('CACHE_TTL')
    def validate_cache_ttl(cls, v):
        if v <= 0:
            raise ValueError("Cache TTL must be a positive number.")
        return v

class AviationWeatherConfig(BaseModel):
    BASE_URL: str = "https://api.checkwx.com/metar"
    TIMEOUT_MS: int = 5000


@dataclass
class Config:
    twitch: TwitchConfig
    database: DatabaseConfig
    openai: OpenAIConfig
    voice: VoiceConfig
    streamerbot: StreamerBotConfig
    littlenavmap: LittleNavMapConfig
    aviationweather: AviationWeatherConfig
    bot_trigger_words: List[str] = field(default_factory=lambda: ["bot", "assistant"])
    bot_personality: str = "You are an AI Overlord managing a flight simulation Twitch channel."
    verbose: bool = False
    environment: str = field(default_factory=lambda: os.getenv('ENV', 'development'))
    command_cooldowns: Dict[str, int] = field(default_factory=dict)
    custom_commands_enabled: bool = True
    log_level: str = "INFO"
    sentry_dsn: Optional[str] = None
    checkwx_api_key: Optional[str] = None
    openweathermap_api_key: Optional[str] = None
    command_permissions: Dict[str, Dict[str, Union[bool, List[str]]]] = field(default_factory=dict)
    _file_path: Optional[str] = None
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger(__name__))

    def __post_init__(self):
        self.validate()
        self.setup_derived_values()
        self.load_command_permissions()
        if self._file_path:
            self.logger.info(f"Configuration loaded from file: {self._file_path}")

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
                MODEL=os.getenv('OPENAI_MODEL', 'gpt-4o-mini') # Changed to gpt-4o-mini
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
            aviationweather_config = AviationWeatherConfig(
                
            )
            
            openweathermap_api_key = os.getenv('OPENWEATHERMAP_API_KEY')
            checkwx_api_key = os.getenv('CHECKWX_API_KEY')
            
            config_file = os.getenv('CONFIG_FILE')

            return cls(
                twitch=twitch_config,
                database=database_config,
                openai=openai_config,
                voice=voice_config,
                streamerbot=streamerbot_config,
                littlenavmap=littlenavmap_config,
                aviationweather = aviationweather_config,
                bot_trigger_words=os.getenv('BOT_TRIGGER_WORDS', 'bot,assistant').split(','),
                bot_personality=os.getenv('BOT_PERSONALITY', 'You are an AI Overlord managing a flight simulation Twitch channel.'),
                verbose=os.getenv('VERBOSE', 'False').lower() == 'true',
                sentry_dsn=os.getenv('SENTRY_DSN'),
                checkwx_api_key=checkwx_api_key,
                openweathermap_api_key = openweathermap_api_key,
                _file_path = config_file,
                command_permissions = {},
                logger = logging.getLogger(__name__)
            )

        except ValidationError as e:
             logger.error(f"Pydantic validation error: {e}")
             raise ConfigError(f"Configuration validation failed: {e}")
        except ValueError as e:
            logger.error(f"Value error during config loading: {e}")
            raise ConfigError(f"Configuration loading failed: {e}")
        except TypeError as e:
            logger.error(f"Type error during config loading: {e}")
            raise ConfigError(f"Configuration loading failed: {e}")
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
            aviationweather_config = AviationWeatherConfig(**config_data.get('aviationweather', {}))
            
            openweathermap_api_key = config_data.get('openweathermap_api_key')
            checkwx_api_key = config_data.get('checkwx_api_key')

            return cls(
                twitch=twitch_config,
                database=database_config,
                openai=openai_config,
                voice=voice_config,
                streamerbot=streamerbot_config,
                littlenavmap=littlenavmap_config,
                aviationweather = aviationweather_config,
                bot_trigger_words=config_data.get('bot_trigger_words', ["bot", "assistant"]),
                bot_personality=config_data.get('bot_personality', 'You are an AI Overlord managing a flight simulation Twitch channel.'),
                verbose=config_data.get('verbose', False),
                sentry_dsn=os.getenv('SENTRY_DSN'),
                checkwx_api_key = checkwx_api_key,
                openweathermap_api_key = openweathermap_api_key,
                command_permissions = config_data.get('command_permissions', {}),
                _file_path = file_path,
                logger = logging.getLogger(__name__)
            )
        except FileNotFoundError as e:
            logger.error(f"Config file not found at {file_path}: {e}")
            raise ConfigError(f"Config file not found: {file_path}") from e
        except yaml.YAMLError as e:
            logger.error(f"YAML parsing error: {e}")
            raise ConfigError(f"YAML parsing failed: {e}") from e
        except ValidationError as e:
            logger.error(f"Pydantic validation error: {e}")
            raise ConfigError(f"Configuration validation failed: {e}") from e
        except ValueError as e:
            logger.error(f"Value error during config loading: {e}")
            raise ConfigError(f"Configuration loading failed: {e}") from e
        except TypeError as e:
            logger.error(f"Type error during config loading: {e}")
            raise ConfigError(f"Configuration loading failed: {e}") from e
        except Exception as e:
            logger.error(f"Failed to load configuration from file: {e}")
            raise ConfigError(f"Configuration file loading failed: {e}") from e

    def reload(self):
        """Reload configuration from file."""
        if self._file_path:
            new_config = Config.load_from_file(self._file_path)
            self.__dict__.update(new_config.__dict__)
            self.logger.info(f"Configuration reloaded from: {self._file_path}")
        else:
            self.logger.warning("No config file path available to reload from.")

    def load_command_permissions(self):
        """Load command permissions from the configuration."""
        if self.command_permissions:
            self.logger.info("Loading command permissions from configuration...")
            for command_name, permissions in self.command_permissions.items():
                 self.command_cooldowns[command_name] = permissions.get("cooldown", 0)

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
    except ConfigError as e:
        logger.error(f"Failed to load configuration: {e}")
        raise