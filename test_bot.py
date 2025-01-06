# File: test_bot.py (continued)
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta
import json
from collections import deque

from bot import Bot
from config import Config, TwitchConfig, DatabaseConfig, OpenAIConfig, VoiceConfig, StreamerBotConfig, LittleNavMapConfig
from database_manager import DatabaseManager, CollectionNames
from tts_manager import TTSManager, TTSStatus, TTSMessage
from chat_manager import ChatManager, ChatMetrics, UserState
from command_handler import CommandHandler, CommandUsage, CommandPermission
from littlenavmap_integration import LittleNavmapIntegration
from personality import PersonalityManager, PersonalityProfile, LoyaltyLevel

# Mock Config
@pytest.fixture
def mock_config():
    return Config(
        twitch=TwitchConfig(
            OAUTH_TOKEN="oauth:mock_token",
            CHANNEL="mock_channel",
            BOT_NAME="mock_bot",
            BROADCASTER_ID="12345",
            PREFIX="!"
        ),
        database=DatabaseConfig(
            URI="mongodb://localhost:27017/",
            DB_NAME="mock_db"
        ),
        openai=OpenAIConfig(
            API_KEY="mock_api_key"
        ),
        voice=VoiceConfig(),
        streamerbot=StreamerBotConfig(
            WS_URI="ws://localhost:7580"
        ),
        littlenavmap=LittleNavMapConfig(),
        bot_trigger_words=["bot", "assistant"],
        bot_personality="Mock AI Overlord",
        verbose=True
    )

# Mock DatabaseManager
@pytest.fixture
def mock_db_manager():
    mock = AsyncMock(spec=DatabaseManager)
    mock.collections = {
        CollectionNames.CONVERSATIONS: AsyncMock(),
        CollectionNames.USERS: AsyncMock(),
        CollectionNames.COMMANDS: AsyncMock(),
        CollectionNames.METRICS: AsyncMock(),
        CollectionNames.BACKUPS: AsyncMock(),
        CollectionNames.FLIGHT_DATA: AsyncMock(),
        CollectionNames.ALERTS: AsyncMock()
    }
    return mock

# Mock TTSManager
@pytest.fixture
def mock_tts_manager():
    mock = AsyncMock(spec=TTSManager)
    mock.status = TTSStatus.CONNECTED
    mock.available_voices = {"default": AsyncMock()}
    mock.message_queue = AsyncMock()
    mock.message_history = deque(maxlen=100)
    return mock

# Mock LittleNavmapIntegration
@pytest.fixture
def mock_littlenavmap():
    mock = AsyncMock(spec=LittleNavmapIntegration)
    return mock

# Mock PersonalityManager
@pytest.fixture
def mock_personality_manager():
    mock = MagicMock(spec=PersonalityManager)
    mock.personality = PersonalityProfile()
    mock.loyalty_levels = [
        LoyaltyLevel(
            name="Initiate Drone",
            min_points=0,
            perks=["Basic interaction"],
            title="Drone"
        )
    ]
    mock.user_loyalty = {}
    mock.active_decrees = []
    mock.last_interaction = {}
    return mock

# Mock OpenAI Client
@pytest.fixture
def mock_openai_client():
    mock = AsyncMock()
    mock.chat.completions.create = AsyncMock(return_value=AsyncMock(choices=[AsyncMock(message=AsyncMock(content="Mock response"))]))
    return mock

# Mock Twitch Message
@pytest.fixture
def mock_message():
    mock = AsyncMock()
    mock.content = "!test command"
    mock.author.name = "test_user"
    mock.author.is_mod = False
    mock.author.is_subscriber = False
    mock.channel.name = "mock_channel"
    return mock

# Bot Tests
@pytest.mark.asyncio
async def test_bot_initialization(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    assert bot.config == mock_config
    assert bot.db_manager == mock_db_manager
    assert bot.tts_manager == mock_tts_manager
    assert bot.littlenavmap == mock_littlenavmap
    assert bot.personality == mock_personality_manager
    assert bot.openai_client == mock_openai_client
    assert bot.bot_ready.is_set() is False

@pytest.mark.asyncio
async def test_bot_event_ready(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    bot.get_channel = AsyncMock(return_value=AsyncMock())
    await bot.event_ready()
    assert bot.bot_ready.is_set() is True
    bot.get_channel.assert_called_once()
    mock_tts_manager.speak.assert_called_once()

@pytest.mark.asyncio
async def test_bot_event_message(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    bot.chat_manager = AsyncMock()
    mock_message = AsyncMock()
    mock_message.echo = False
    await bot.event_message(mock_message)
    bot.chat_manager.handle_message.assert_called_once_with(mock_message)

@pytest.mark.asyncio
async def test_bot_event_command_error(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    mock_ctx = AsyncMock()
    mock_ctx.author.name = "test_user"
    mock_error = Exception("Test error")
    mock_personality_manager.get_error_response = MagicMock(return_value="Error message")
    await bot.event_command_error(mock_ctx, mock_error)
    mock_ctx.send.assert_called_once_with("Error message")

@pytest.mark.asyncio
async def test_bot_generate_chatgpt_response(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    response = await bot.generate_chatgpt_response("Test message")
    assert response == "Mock response"
    mock_openai_client.chat.completions.create.assert_called_once()
    mock_db_manager.save_conversation.assert_called_once()

@pytest.mark.asyncio
async def test_bot_periodic_flight_info_update(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    mock_littlenavmap.get_sim_info = AsyncMock(return_value={"active": True, "indicated_altitude": 1000, "ground_altitude": 0, "altitude_above_ground": 100, "position": {"lat": 0, "lon": 0}, "ground_speed": 100, "heading": 0, "wind_speed": 10, "wind_direction": 0, "vertical_speed": 10, "true_airspeed": 100, "indicated_speed": 100, "simconnect_status": "No Error"})
    mock_personality_manager.format_response = MagicMock(return_value="Mock response")
    await bot.periodic_flight_info_update()
    mock_db_manager.save_flight_data.assert_called_once()
    mock_tts_manager.speak.assert_called_once()

@pytest.mark.asyncio
async def test_bot_process_voice_commands(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    # This test is a placeholder as the voice command processing is not implemented
    await bot.process_voice_commands()
    # Add assertions if voice command processing is implemented

@pytest.mark.asyncio
async def test_bot_handle_alert(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    mock_personality_manager.get_alert = MagicMock(return_value="Test alert")
    bot.get_channel = AsyncMock(return_value=AsyncMock())
    await bot.handle_alert("test_alert", "mock_channel")
    mock_personality_manager.get_alert.assert_called_once_with("test_alert")
    bot.get_channel.assert_called_once_with("mock_channel")
    mock_tts_manager.speak.assert_called_once()

@pytest.mark.asyncio
async def test_bot_close(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    bot.chat_manager = AsyncMock()
    await bot.close()
    mock_tts_manager.close.assert_called_once()
    mock_db_manager.close.assert_called_once()
    mock_littlenavmap.stop.assert_called_once()
    bot.chat_manager.close.assert_called_once()

@pytest.mark.asyncio
async def test_bot_periodic_location_facts(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    mock_littlenavmap.get_sim_info = AsyncMock(return_value={"active": True, "position": {"lat": 0, "lon": 0}})
    mock_openai_client.chat.completions.create = AsyncMock(return_value=AsyncMock(choices=[AsyncMock(message=AsyncMock(content="Mock location fact"))]))
    bot.chat_manager = AsyncMock()
    await bot.periodic_location_facts()
    mock_openai_client.chat.completions.create.assert_called_once()
    bot.chat_manager.send_message.assert_called_once()

# ChatManager Tests
@pytest.mark.asyncio
async def test_chat_manager_initialization(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    assert chat_manager.bot == bot
    assert chat_manager.config == mock_config
    assert isinstance(chat_manager.metrics, ChatMetrics)
    assert chat_manager.message_queue.empty() is True
    assert chat_manager.spam_protection == {}
    assert chat_manager.blocked_phrases == set()
    assert chat_manager.user_states == {}
    assert chat_manager.message_cache.currsize == 0

@pytest.mark.asyncio
async def test_chat_manager_start(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    await chat_manager.start()
    assert chat_manager._processor_task is not None
    assert chat_manager._metrics_task is not None

@pytest.mark.asyncio
async def test_chat_manager_handle_message(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.content = "test message"
    mock_message.author.name = "test_user"
    await chat_manager.handle_message(mock_message)
    assert chat_manager.metrics.total_messages == 1
    assert "test_user" in chat_manager.metrics.users_active
    assert chat_manager.metrics.message_frequency["test_user"] == 1
    assert not chat_manager.message_queue.empty()

@pytest.mark.asyncio
async def test_chat_manager_is_bot_mention(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    assert await chat_manager.is_bot_mention("hello bot") is True
    assert await chat_manager.is_bot_mention("hello assistant") is True
    assert await chat_manager.is_bot_mention("hello @mock_bot") is True
    assert await chat_manager.is_bot_mention("hello") is False

@pytest.mark.asyncio
async def test_chat_manager_handle_bot_mention(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.content = "hello bot"
    mock_message.author.name = "test_user"
    chat_manager.send_message = AsyncMock()
    await chat_manager.handle_bot_mention(mock_message)
    chat_manager.send_message.assert_called_once()
    assert chat_manager.metrics.bot_mentions == 0

@pytest.mark.asyncio
async def test_chat_manager_handle_command(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    bot.command_handler = AsyncMock()
    mock_message = AsyncMock()
    mock_message.content = "!test command"
    await chat_manager.handle_command(mock_message)
    bot.command_handler.handle_command.assert_called_once_with(mock_message)

@pytest.mark.asyncio
async def test_chat_manager_handle_streamer_message(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.content = "test message"
    mock_message.author.name = mock_config.twitch.CHANNEL.lower()
    await chat_manager.handle_streamer_message(mock_message)
    assert mock_message.content in chat_manager.message_cache.values()

@pytest.mark.asyncio
async def test_chat_manager_handle_regular_chat_message(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.content = "test message"
    mock_message.author.name = "test_user"
    await chat_manager.handle_regular_chat_message(mock_message)
    assert mock_message.content in chat_manager.message_cache.values()

@pytest.mark.asyncio
async def test_chat_manager_should_filter_message(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.content = "test message"
    mock_message.author.name = "test_user"
    chat_manager.is_spam = AsyncMock(return_value=False)
    chat_manager.contains_blocked_content = AsyncMock(return_value=False)
    chat_manager.is_on_cooldown = AsyncMock(return_value=False)
    chat_manager.is_repeated_message = AsyncMock(return_value=False)
    assert await chat_manager.should_filter_message(mock_message) is False
    chat_manager.is_spam = AsyncMock(return_value=True)
    assert await chat_manager.should_filter_message(mock_message) is True
    chat_manager.is_spam = AsyncMock(return_value=False)
    chat_manager.contains_blocked_content = AsyncMock(return_value=True)
    assert await chat_manager.should_filter_message(mock_message) is True
    chat_manager.contains_blocked_content = AsyncMock(return_value=False)
    chat_manager.is_on_cooldown = AsyncMock(return_value=True)
    assert await chat_manager.should_filter_message(mock_message) is True
    chat_manager.is_on_cooldown = AsyncMock(return_value=False)
    chat_manager.is_repeated_message = AsyncMock(return_value=True)
    assert await chat_manager.should_filter_message(mock_message) is True

@pytest.mark.asyncio
async def test_chat_manager_is_spam(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.author.name = "test_user"
    for _ in range(5):
        await chat_manager.is_spam(mock_message)
    assert await chat_manager.is_spam(mock_message) is True
    
@pytest.mark.asyncio
async def test_chat_manager_handle_spam(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.author.name = "test_user"
    chat_manager.send_message = AsyncMock()
    await chat_manager.handle_spam(mock_message)
    chat_manager.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_chat_manager_contains_blocked_content(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    chat_manager.blocked_phrases = {"blocked"}
    mock_message = AsyncMock()
    mock_message.content = "this is blocked"
    assert await chat_manager.contains_blocked_content(mock_message) is True
    mock_message.content = "this is not blocked"
    assert await chat_manager.contains_blocked_content(mock_message) is False

@pytest.mark.asyncio
async def test_chat_manager_handle_blocked_content(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.author.name = "test_user"
    chat_manager.send_message = AsyncMock()
    await chat_manager.handle_blocked_content(mock_message)
    chat_manager.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_chat_manager_is_on_cooldown(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.author.name = "test_user"
    mock_message.author.is_mod = False
    assert await chat_manager.is_on_cooldown(mock_message) is False
    chat_manager.user_states["test_user"] = UserState(username="test_user", last_command=datetime.now())
    assert await chat_manager.is_on_cooldown(mock_message) is True
    chat_manager.user_states["test_user"].last_command = datetime.now() - timedelta(seconds=5)
    assert await chat_manager.is_on_cooldown(mock_message) is False
    mock_message.author.is_mod = True
    assert await chat_manager.is_on_cooldown(mock_message) is False

@pytest.mark.asyncio
async def test_chat_manager_is_repeated_message(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.content = "test message"
    mock_message.author.name = "test_user"
    assert await chat_manager.is_repeated_message(mock_message) is False
    chat_manager.user_states["test_user"] = UserState(username="test_user", last_message_content="test message")
    assert await chat_manager.is_repeated_message(mock_message) is True
    mock_message.content = "new message"
    assert await chat_manager.is_repeated_message(mock_message) is False

@pytest.mark.asyncio
async def test_chat_manager_handle_repeated_message(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.author.name = "test_user"
    chat_manager.send_message = AsyncMock()
    await chat_manager.handle_repeated_message(mock_message)
    chat_manager.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_chat_manager_update_user_state(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.author.name = "test_user"
    mock_message.author.is_subscriber = True
    mock_message.content = "!test command"
    await chat_manager.update_user_state(mock_message)
    assert "test_user" in chat_manager.user_states
    assert chat_manager.user_states["test_user"].is_subscriber is True
    assert chat_manager.user_states["test_user"].last_command is not None
    mock_message.content = "test message"
    await chat_manager.update_user_state(mock_message)
    assert chat_manager.user_states["test_user"].last_command is not None

@pytest.mark.asyncio
async def test_chat_manager_update_message_metrics(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.author.name = "test_user"
    chat_manager.update_message_metrics(mock_message)
    assert chat_manager.metrics.total_messages == 1
    assert "test_user" in chat_manager.metrics.users_active
    assert chat_manager.metrics.message_frequency["test_user"] == 1

@pytest.mark.asyncio
async def test_chat_manager_send_message(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    bot.get_channel = AsyncMock(return_value=AsyncMock())
    await chat_manager.send_message("mock_channel", "test message")
    bot.get_channel.assert_called_once_with("mock_channel")
    
@pytest.mark.asyncio
async def test_chat_manager_send_error_message(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    chat_manager.send_message = AsyncMock()
    await chat_manager.send_error_message("mock_channel")
    chat_manager.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_chat_manager_send_greeting(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    chat_manager.send_message = AsyncMock()
    mock_personality_manager.get_greeting = MagicMock(return_value="Mock greeting")
    await chat_manager.send_greeting("test_user", "mock_channel")
    chat_manager.send_message.assert_called_once()

@pytest.mark.asyncio
async def test_chat_manager_process_message_queue(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    mock_message = AsyncMock()
    chat_manager._process_message = AsyncMock()
    await chat_manager.message_queue.put(mock_message)
    await chat_manager._process_message_queue()
    chat_manager._process_message.assert_called_once_with(mock_message)

@pytest.mark.asyncio
async def test_chat_manager_update_metrics(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    chat_manager.user_states["test_user"] = UserState(username="test_user", last_message=datetime.now())
    await chat_manager._update_metrics()
    assert len(chat_manager.metrics.users_active) == 1

@pytest.mark.asyncio
async def test_chat_manager_close(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    chat_manager = ChatManager(bot, mock_config)
    await chat_manager.start()
    await chat_manager.close()
    assert chat_manager._processor_task.cancelled()
    assert chat_manager._metrics_task.cancelled()
    
@pytest.mark.asyncio
async def test_command_handler_initialization(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    assert command_handler.bot == bot
    assert command_handler.config == mock_config
    assert command_handler.command_usage == {}
    assert command_handler.custom_commands == {}
    assert command_handler.command_aliases == {}

@pytest.mark.asyncio
async def test_command_handler_handle_command(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.content = "!status"
    command_handler.flight_status_command = AsyncMock()
    await command_handler.handle_command(mock_message)
    command_handler.flight_status_command.assert_called_once()

@pytest.mark.asyncio
async def test_command_handler_flight_status_command(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    mock_message = AsyncMock()
    mock_littlenavmap.get_sim_info = AsyncMock(return_value={"active": True})
    await command_handler.flight_status_command(mock_message)
    mock_littlenavmap.get_sim_info.assert_called_once()
    mock_tts_manager.speak.assert_called_once()

@pytest.mark.asyncio
async def test_command_handler_brief_status_command(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    mock_message = AsyncMock()
    mock_littlenavmap.get_sim_info = AsyncMock(return_value={"active": True})
    await command_handler.brief_status_command(mock_message)
    mock_littlenavmap.get_sim_info.assert_called_once()
    mock_tts_manager.speak.assert_called_once()

@pytest.mark.asyncio
async def test_command_handler_weather_command(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    mock_message = AsyncMock()
    mock_littlenavmap.get_sim_info = AsyncMock(return_value={"active": True})
    await command_handler.weather_command(mock_message)
    mock_littlenavmap.get_sim_info.assert_called_once()
    mock_tts_manager.speak.assert_called_once()

@pytest.mark.asyncio
async def test_command_handler_timeout_user(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.author.is_mod = True
    mock_message.content = "!timeout test_user 10"
    await command_handler.timeout_user(mock_message, "test_user", "10")
    mock_message.channel.send.assert_called()

@pytest.mark.asyncio
async def test_command_handler_clear_chat(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.author.is_mod = True
    await command_handler.clear_chat(mock_message)
    mock_message.channel.send.assert_called()

@pytest.mark.asyncio
async def test_command_handler_get_stats(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    mock_message = AsyncMock()
    mock_littlenavmap.get_sim_info = AsyncMock(return_value={"active": True})
    await command_handler.get_stats(mock_message)
    mock_message.channel.send.assert_called()
    mock_tts_manager.speak.assert_called()

@pytest.mark.asyncio
async def test_command_handler_set_title(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.author.is_mod = True
    await command_handler.set_title(mock_message, "new title")
    mock_message.channel.send.assert_called()

@pytest.mark.asyncio
async def test_command_handler_set_game(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.author.is_mod = True
    await command_handler.set_game(mock_message, "new game")
    mock_message.channel.send.assert_called()

@pytest.mark.asyncio
async def test_command_handler_handle_tts(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    mock_message = AsyncMock()
    await command_handler.handle_tts(mock_message, "voice", "test_voice")
    mock_tts_manager.update_settings.assert_called()

@pytest.mark.asyncio
async def test_command_handler_airport_info(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    mock_message = AsyncMock()
    mock_littlenavmap.get_airport_info = AsyncMock(return_value={"ident": "test"})
    await command_handler.airport_info(mock_message, "test")
    mock_littlenavmap.get_airport_info.assert_called()
    mock_tts_manager.speak.assert_called()

@pytest.mark.asyncio
async def test_command_handler_add_alert(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.author.is_mod = True
    await command_handler.add_alert(mock_message, "test_alert", "test message")
    mock_db_manager.save_alert.assert_called()

@pytest.mark.asyncio
async def test_command_handler_trigger_alert(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    mock_message = AsyncMock()
    mock_db_manager.get_alert = AsyncMock(return_value={"message": "test alert"})
    await command_handler.trigger_alert(mock_message, "test_alert")
    mock_db_manager.get_alert.assert_called()
    mock_tts_manager.speak.assert_called()

@pytest.mark.asyncio
async def test_command_handler_say(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    mock_message = AsyncMock()
    await command_handler.say(mock_message, "test message")
    mock_message.channel.send.assert_called()
    mock_tts_manager.speak.assert_called()

@pytest.mark.asyncio
async def test_command_handler_add_custom_command(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.author.is_mod = True
    await command_handler.add_custom_command(mock_message, "test_command", "test response")
    assert "test_command" in command_handler.custom_commands

@pytest.mark.asyncio
async def test_command_handler_delete_custom_command(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.author.is_mod = True
    command_handler.custom_commands["test_command"] = "test response"
    await command_handler.delete_custom_command(mock_message, "test_command")
    assert "test_command" not in command_handler.custom_commands

@pytest.mark.asyncio
async def test_command_handler_edit_custom_command(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.author.is_mod = True
    command_handler.custom_commands["test_command"] = "test response"
    await command_handler.edit_custom_command(mock_message, "test_command", "new response")
    assert command_handler.custom_commands["test_command"] == "new response"

@pytest.mark.asyncio
async def test_command_handler_handle_custom_command(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    mock_message = AsyncMock()
    command_handler.custom_commands["test_command"] = "test response"
    await command_handler.handle_custom_command(mock_message, "test_command")
    mock_message.channel.send.assert_called()

@pytest.mark.asyncio
async def test_command_handler_process_command_variables(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.author.name = "test_user"
    mock_message.channel.name = "mock_channel"
    bot.get_uptime = MagicMock(return_value="1d 1h 1m 1s")
    bot.get_game = MagicMock(return_value="test_game")
    bot.get_title = MagicMock(return_value="test_title")
    text = command_handler.process_command_variables("{user} {channel} {uptime} {game} {title}", mock_message)
    assert text == "test_user mock_channel 1d 1h 1m 1s test_game test_title"

@pytest.mark.asyncio
async def test_command_handler_add_command_alias(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    mock_message = AsyncMock()
    mock_message.author.is_mod = True
    command_handler.commands["status"] = AsyncMock()
    await command_handler.add_command_alias(mock_message, "alias_status", "status")
    assert "alias_status" in command_handler.command_aliases

@pytest.mark.asyncio
async def test_command_handler_help(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    mock_message = AsyncMock()
    await command_handler.help(mock_message)
    mock_message.channel.send.assert_called()
    
    mock_message.channel.send.reset_mock()
    await command_handler.help(mock_message, "status")
    mock_message.channel.send.assert_called()

@pytest.mark.asyncio
async def test_command_handler_get_command_stats(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    command_handler.command_usage["status"] = CommandUsage(use_count=1)
    stats = command_handler.get_command_stats()
    assert "status" in stats
    assert stats["status"]["uses"] == 1

@pytest.mark.asyncio
async def test_command_handler_get_uptime(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    uptime = command_handler.get_uptime()
    assert isinstance(uptime, str)

@pytest.mark.asyncio
async def test_command_handler_load_save_command_data(mock_config, mock_db_manager, mock_tts_manager, mock_littlenavmap, mock_personality_manager, mock_openai_client):
    bot = Bot(
        openai_client=mock_openai_client,
        config=mock_config,
        db_manager=mock_db_manager,
        tts_manager=mock_tts_manager,
        littlenavmap=mock_littlenavmap,
        personality=mock_personality_manager
    )
    command_handler = CommandHandler(bot, mock_config)
    command_handler.custom_commands["test_command"] = "test response"
    command_handler.command_aliases["alias_command"] = "test_command"
    command_handler.save_command_data()
    command_handler.custom_commands = {}
    command_handler.command_aliases = {}
    command_handler.load_command_data()
    assert "test_command" in command_handler.custom_commands
    assert "alias_command" in command_handler.command_aliases

# DatabaseManager Tests
@pytest.mark.asyncio
async def test_database_manager_connect(mock_config):
    db_manager = DatabaseManager(mock_config)
    await db_manager.connect()
    assert db_manager.client is not None
    assert db_manager.db is not None
    assert db_manager._connected.is_set() is True

@pytest.mark.asyncio
async def test_database_manager_save_conversation(mock_config, mock_db_manager):
    db_manager = DatabaseManager(mock_config)
    db_manager._connected.set()
    mock_db_manager.collections[CollectionNames.CONVERSATIONS].insert_one = AsyncMock(return_value=AsyncMock(inserted_id="test_id"))
    result = await db_manager.save_conversation("test_user", "test_bot")
    assert result == "test_id"

@pytest.mark.asyncio
async def test_database_manager_get_conversation_history(mock_config, mock_db_manager):
    db_manager = DatabaseManager(mock_config)
    db_manager._connected.set()
    mock_db_manager.collections[CollectionNames.CONVERSATIONS].find = AsyncMock(return_value=AsyncMock(to_list=AsyncMock(return_value=[{"user": "test_user", "bot": "test_bot"}])))
    history = await db_manager.get_conversation_history()
    assert len(history) == 1
    assert history[0]["user"] == "test_user"

@pytest.mark.asyncio
async def test_database_manager_save_flight_data(mock_config, mock_db_manager):
    db_manager = DatabaseManager(mock_config)
    db_manager._connected.set()
    mock_db_manager.collections[CollectionNames.FLIGHT_DATA].insert_one = AsyncMock(return_value=AsyncMock(inserted_id="test_id"))
    result = await db_manager.save_flight_data({"altitude": 1000})
    assert result == "test_id"

@pytest.mark.asyncio
async def test_database_manager_save_alert(mock_config, mock_db_manager):
    db_manager = DatabaseManager(mock_config)
    db_manager._connected.set()
    mock_db_manager.collections[CollectionNames.ALERTS].update_one = AsyncMock()
    await db_manager.save_alert("test_alert", "test message")
    mock_db_manager.collections[CollectionNames.ALERTS].update_one.assert_called()

@pytest.mark.asyncio
async def test_database_manager_get_alert(mock_config, mock_db_manager):
    db_manager = DatabaseManager(mock_config)
    db_manager._connected.set()
    mock_db_manager.collections[CollectionNames.ALERTS].find_one = AsyncMock(return_value={"name": "test_alert", "message": "test message"})
    alert = await db_manager.get_alert("test_alert")
    assert alert["name"] == "test_alert"

@pytest.mark.asyncio
async def test_database_manager_delete_alert(mock_config, mock_db_manager):
    db_manager = DatabaseManager(mock_config)
    db_manager._connected.set()
    mock_db_manager.collections[CollectionNames.ALERTS].delete_one = AsyncMock(return_value=AsyncMock(deleted_count=1))
    result = await db_manager.delete_alert("test_alert")
    assert result is True

@pytest.mark.asyncio
async def test_database_manager_periodic_backup(mock_config, mock_db_manager):
    db_manager = DatabaseManager(mock_config)
    db_manager._connected.set()
    db_manager._create_backup = AsyncMock()
    await db_manager._periodic_backup()
    db_manager._create_backup.assert_called()

@pytest.mark.asyncio
async def test_database_manager_create_backup(mock_config, mock_db_manager):
    db_manager = DatabaseManager(mock_config)
    db_manager._connected.set()
    mock_db_manager.collections[CollectionNames.BACKUPS].insert_one = AsyncMock()
    for name, collection in mock_db_manager.collections.items():
        if name != CollectionNames.BACKUPS:
            collection.find = AsyncMock(return_value=AsyncMock(to_list=AsyncMock(return_value=[])))
    await db_manager._create_backup()
    mock_db_manager.collections[CollectionNames.BACKUPS].insert_one.assert_called()

@pytest.mark.asyncio
async def test_database_manager_periodic_metrics_update(mock_config, mock_db_manager):
    db_manager = DatabaseManager(mock_config)
    db_manager._connected.set()
    db_manager._update_metrics = AsyncMock()
    await db_manager._periodic_metrics_update()
    db_manager._update_metrics.assert_called()

@pytest.mark.asyncio
async def test_database_manager_update_metrics(mock_config, mock_db_manager):
    db_manager = DatabaseManager(mock_config)
    db_manager._connected.set()
    mock_db_manager.collections[CollectionNames.CONVERSATIONS].count_documents = AsyncMock(return_value=1)
    mock_db_manager.collections[CollectionNames.CONVERSATIONS].distinct = AsyncMock(return_value=["test_user"])
    mock_db_manager.collections[CollectionNames.CONVERSATIONS].aggregate = AsyncMock(return_value=AsyncMock(to_list=AsyncMock(return_value=[{"avg_time": 1.0}])))
    mock_db_manager.db.command = AsyncMock(return_value={"storageSize": 1000})
    mock_db_manager.collections[CollectionNames.USERS].count_documents = AsyncMock(return_value=1)
    mock_db_manager.collections[CollectionNames.FLIGHT_DATA].count_documents = AsyncMock(return_value=1)
    await db_manager._update_metrics()

@pytest.mark.asyncio
async def test_littlenavmap_integration_start(mock_config):
    navmap = LittleNavmapIntegration(mock_config)
    navmap.get_sim_info = AsyncMock(return_value={"active": True})
    await navmap.start()
    navmap.get_sim_info.assert_called_once()

@pytest.mark.asyncio
async def test_littlenavmap_integration_stop(mock_config):
    navmap = LittleNavmapIntegration(mock_config)
    await navmap.stop()
    # No specific assertions, just check that it runs without errors

@pytest.mark.asyncio
async def test_littlenavmap_integration_get_sim_info(mock_config):
    navmap = LittleNavmapIntegration(mock_config)
    navmap._get_data = AsyncMock(return_value={"active": True})
    sim_info = await navmap.get_sim_info()
    assert sim_info["active"] is True

@pytest.mark.asyncio
async def test_littlenavmap_integration_get_airport_info(mock_config):
    navmap = LittleNavmapIntegration(mock_config)
    navmap._get_data = AsyncMock(return_value={"ident": "test"})
    airport_info = await navmap.get_airport_info("test")
    assert airport_info["ident"] == "test"

@pytest.mark.asyncio
async def test_littlenavmap_integration_get_current_flight_data(mock_config):
    navmap = LittleNavmapIntegration(mock_config)
    navmap.get_sim_info = AsyncMock(return_value={"indicated_altitude": 1000, "ground_speed": 100, "heading": 0, "position": {"lat": 0, "lon": 0}, "wind_direction": 0, "wind_speed": 10, "on_ground": False})
    flight_data = await navmap.get_current_flight_data()
    assert flight_data["aircraft"]["altitude"] == 1000

@pytest.mark.asyncio
async def test_littlenavmap_integration_get_data(mock_config):
    navmap = LittleNavmapIntegration(mock_config)
    navmap.base_url = "http://test"
    navmap.logger.debug = MagicMock()
    navmap.logger.info = MagicMock()
    navmap.logger.error = MagicMock()
    
    # Mock a successful response
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.text = AsyncMock(return_value='{"test": "data"}')
    mock_response.json = AsyncMock(return_value={"test": "data"})
    
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=mock_response)
    
    with MagicMock(return_value=mock_session) as mock_client_session:
        data = await navmap._get_data("/test")
        assert data == {"test": "data"}
        mock_client_session.assert_called_once()
        mock_session.get.assert_called_once()
        mock_response.json.assert_called_once()
        
    # Mock a failed response
    mock_response.status = 404
    mock_response.text = AsyncMock(return_value='{"error": "not found"}')
    mock_session.get = AsyncMock(return_value=mock_response)
    
    with MagicMock(return_value=mock_session) as mock_client_session:
        data = await navmap._get_data("/test")
        assert data is None
        mock_client_session.assert_called_once()
        mock_session.get.assert_called_once()
        mock_response.text.assert_called_once()

@pytest.mark.asyncio
async def test_littlenavmap_integration_format_flight_data(mock_config):
    navmap = LittleNavmapIntegration(mock_config)
    data = {"indicated_altitude": 1000, "altitude_above_ground": 100, "ground_speed": 100, "heading": 0, "position": {"lat": 0, "lon": 0}, "wind_direction": 0, "wind_speed": 10, "vertical_speed": 10, "true_airspeed": 100}
    formatted_data = navmap.format_flight_data(data)
    assert isinstance(formatted_data, str)

@pytest.mark.asyncio
async def test_littlenavmap_integration_get_flight_phase(mock_config):
    navmap = LittleNavmapIntegration(mock_config)
    data = {"altitude_above_ground": 0, "ground_speed": 0, "vertical_speed": 0}
    assert navmap.get_flight_phase(data) == "Parked"
    data = {"altitude_above_ground": 0, "ground_speed": 10, "vertical_speed": 0}
    assert navmap.get_flight_phase(data) == "Taxiing"
    data = {"altitude_above_ground": 10, "ground_speed": 10, "vertical_speed": 100}
    assert navmap.get_flight_phase(data) == "Taking Off"
    data = {"altitude_above_ground": 10, "ground_speed": 10, "vertical_speed": -100}
    assert navmap.get_flight_phase(data) == "Landing"
    data = {"altitude_above_ground": 10, "ground_speed": 10, "vertical_speed": 0}
    assert navmap.get_flight_phase(data) == "Ground Roll"
    data = {"altitude_above_ground": 100, "ground_speed": 100, "vertical_speed": 600}
    assert navmap.get_flight_phase(data) == "Climbing"
    data = {"altitude_above_ground": 100, "ground_speed": 100, "vertical_speed": -600}
    assert navmap.get_flight_phase(data) == "Descending"
    data = {"altitude_above_ground": 100, "ground_speed": 100, "vertical_speed": 0}
    assert navmap.get_flight_phase(data) == "Cruise"
    assert navmap.get_flight_phase(None) == "Unknown"

@pytest.mark.asyncio
async def test_littlenavmap_integration_format_weather_data(mock_config):
    navmap = LittleNavmapIntegration(mock_config)
    data = {"wind_speed": 10, "wind_direction": 0, "sea_level_pressure": 1013.25}
    formatted_data = navmap.format_weather_data(data)
    assert isinstance(formatted_data, str)

@pytest.mark.asyncio
async def test_littlenavmap_integration_format_brief_status(mock_config):
    navmap = LittleNavmapIntegration(mock_config)
    data = {"indicated_altitude": 1000, "ground_speed": 100, "altitude_above_ground": 100, "vertical_speed": 100}
    formatted_data = navmap.format_brief_status(data)
    assert isinstance(formatted_data, str)

@pytest.mark.asyncio
async def test_littlenavmap_integration_format_airport_data(mock_config):
    navmap = LittleNavmapIntegration(mock_config)
    data = {"ident": "test", "name": "test airport", "elevation": 100}
    formatted_data = navmap.format_airport_data(data)
    assert isinstance(formatted_data, str) 
    
@pytest.mark.asyncio
async def test_personality_manager_initialization():
    personality_manager = PersonalityManager()
    assert isinstance(personality_manager.personality, PersonalityProfile)
    assert personality_manager.user_loyalty == {}
    assert personality_manager.active_decrees == []
    assert personality_manager.last_interaction == {}
    assert personality_manager.cached_responses.currsize == 0

@pytest.mark.asyncio
async def test_personality_manager_get_user_title(mock_personality_manager):
    mock_personality_manager.user_loyalty["test_user"] = 100
    title = mock_personality_manager.get_user_title("test_user")
    assert title == "Subject"
    mock_personality_manager.user_loyalty["test_user"] = 0
    title = mock_personality_manager.get_user_title("test_user")
    assert title == "Minion"

@pytest.mark.asyncio
async def test_personality_manager_format_response(mock_personality_manager):
    mock_personality_manager.generate_random_decree = MagicMock(return_value="Test decree")
    response = mock_personality_manager.format_response("Hello {user}", {"user": "test_user"})
    assert "Hello test_user" in response

@pytest.mark.asyncio
async def test_personality_manager_generate_random_decree(mock_personality_manager):
    decree = mock_personality_manager.generate_random_decree()
    assert isinstance(decree, str)
    assert len(mock_personality_manager.active_decrees) == 1

@pytest.mark.asyncio
async def test_personality_manager_update_loyalty(mock_personality_manager):
    mock_personality_manager.update_loyalty("test_user", 100)
    assert mock_personality_manager.user_loyalty["test_user"] == 100
    assert "test_user" in mock_personality_manager.last_interaction

@pytest.mark.asyncio
async def test_personality_manager_get_flight_response(mock_personality_manager):
    response = mock_personality_manager.get_flight_response({"altitude": 1000})
    assert isinstance(response, str)

@pytest.mark.asyncio
async def test_personality_manager_get_error_response(mock_personality_manager):
    response = mock_personality_manager.get_error_response("permission", {"user": "test_user"})
    assert isinstance(response, str)

@pytest.mark.asyncio
async def test_personality_manager_get_greeting(mock_personality_manager):
    response = mock_personality_manager.get_greeting("test_user")
    assert isinstance(response, str)

@pytest.mark.asyncio
async def test_personality_manager_get_alert(mock_personality_manager):
    mock_personality_manager.alerts = {"test_alert": "test message"}
    alert = mock_personality_manager.get_alert("test_alert")
    assert alert == "test message"

@pytest.mark.asyncio
async def test_personality_manager_save_load_state(mock_personality_manager):
    mock_personality_manager.user_loyalty["test_user"] = 100
    mock_personality_manager.active_decrees = [{"text": "test decree", "expires": datetime.now() + timedelta(minutes=30)}]
    mock_personality_manager.last_interaction["test_user"] = datetime.now()
    mock_personality_manager.save_state()
    mock_personality_manager.user_loyalty = {}
    mock_personality_manager.active_decrees = []
    mock_personality_manager.last_interaction = {}
    mock_personality_manager.load_state()
    assert mock_personality_manager.user_loyalty["test_user"] == 100
    assert len(mock_personality_manager.active_decrees) == 1
    assert "test_user" in mock_personality_manager.last_interaction

@pytest.mark.asyncio
async def test_personality_manager_clean_up_expired_decrees(mock_personality_manager):
    mock_personality_manager.active_decrees = [{"text": "test decree", "expires": datetime.now() - timedelta(minutes=30)}]
    mock_personality_manager.clean_up_expired_decrees()
    assert len(mock_personality_manager.active_decrees) == 0