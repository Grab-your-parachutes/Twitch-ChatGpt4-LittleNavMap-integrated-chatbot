# File: chat_manager.py
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict
from twitchio.message import Message
from config import Config
from cachetools import TTLCache

@dataclass
class ChatMetrics:
    total_messages: int = 0
    commands_processed: int = 0
    bot_mentions: int = 0
    errors: int = 0
    last_message_time: Optional[datetime] = None
    users_active: set = None
    message_frequency: Dict[str, int] = None

    def __post_init__(self):
        if self.users_active is None:
            self.users_active = set()
        if self.message_frequency is None:
            self.message_frequency = defaultdict(int)

@dataclass
class UserState:
    username: str
    loyalty_points: int = 0
    last_message: Optional[datetime] = None
    warning_count: int = 0
    is_subscriber: bool = False
    first_seen: datetime = None
    last_command: Optional[datetime] = None
    last_message_content: Optional[str] = None
    has_been_greeted: bool = False

class MessageRateLimiter:
    def __init__(self, messages_per_second: float):
        self.rate = messages_per_second
        self.last_check = datetime.now()
        self.tokens = 1.0
        self.max_tokens = 1.0

    async def acquire(self):
        now = datetime.now()
        time_passed = (now - self.last_check).total_seconds()
        self.last_check = now

        self.tokens = min(self.max_tokens, self.tokens + time_passed * self.rate)
        if self.tokens < 1.0:
            await asyncio.sleep((1.0 - self.tokens) / self.rate)
            self.tokens = 1.0
        self.tokens -= 1.0

class ChatManager:
    def __init__(self, bot, config: Config):
        self.bot = bot
        self.config = config
        self.logger = logging.getLogger('ChatManager')
        self.metrics = ChatMetrics()
        self.rate_limiter = MessageRateLimiter(messages_per_second=1.0)
        self.message_queue = asyncio.Queue()
        self.spam_protection = defaultdict(list)
        self.blocked_phrases = set()
        self.user_states: Dict[str, UserState] = {}
        self.message_cache = TTLCache(maxsize=1000, ttl=300)  # 5-minute cache
        self._processor_task: Optional[asyncio.Task] = None
        self._metrics_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the chat manager and its background tasks."""
        self._processor_task = asyncio.create_task(self._process_message_queue())
        self._metrics_task = asyncio.create_task(self._update_metrics())
        self.logger.info("Chat manager started")

    async def handle_message(self, message: Message):
        """Main message handler."""
        try:
            if await self.should_filter_message(message):
                return

            self.update_message_metrics(message)
            await self.update_user_state(message)
            await self.message_queue.put(message)

        except Exception as e:
            self.metrics.errors += 1
            self.logger.error(f"Error handling message: {e}", exc_info=True)

    async def _process_message(self, message: Message):
        """Process a single message."""
        try:
            content = message.content.lower()

            if await self.is_bot_mention(content):
                await self.handle_bot_mention(message)
                self.metrics.bot_mentions += 1
            elif content.startswith(self.config.twitch.PREFIX):
                await self.handle_command(message)
                self.metrics.commands_processed += 1
            elif message.author.name.lower() == self.config.twitch.CHANNEL.lower():
                await self.handle_streamer_message(message)
            else:
                await self.handle_regular_chat_message(message)

        except Exception as e:
            self.metrics.errors += 1
            self.logger.error(f"Error processing message: {e}", exc_info=True)

    async def is_bot_mention(self, content: str) -> bool:
        """Check if message mentions the bot."""
        return any(word in content for word in self.config.bot_trigger_words) or \
               f"@{self.config.twitch.BOT_NAME.lower()}" in content

    async def handle_bot_mention(self, message: Message):
        """Handle messages that mention the bot."""
        try:
            self.logger.debug(f"Handling bot mention: {message.content}")
            response = await self.bot.generate_chatgpt_response(message.content)
            response = self.bot.personality.format_response(response, {"user": message.author.name})
            await self.send_message(message.channel.name, response, tts=True)
        except Exception as e:
            self.logger.error(f"Error handling bot mention: {e}", exc_info=True)
            await self.send_error_message(message.channel.name)

    async def handle_command(self, message: Message):
        """Handle bot commands."""
        try:
            self.logger.debug(f"Handling command: {message.content}")
            await self.bot.command_handler.handle_command(message)
        except Exception as e:
            self.logger.error(f"Error handling command: {e}", exc_info=True)
            await self.send_error_message(message.channel.name)

    async def handle_streamer_message(self, message: Message):
        """Handle messages from the streamer."""
        self.logger.debug(f"Handling streamer message: {message.content}")
        # Add special handling for streamer messages if needed
        await self.handle_regular_chat_message(message)

    async def handle_regular_chat_message(self, message: Message):
        """Handle regular chat messages."""
        self.logger.debug(f"Handling regular chat message: {message.content}")
        self.message_cache[message.id] = {
            'content': message.content,
            'author': message.author.name,
            'timestamp': datetime.now()
        }

        # Check for flight-related keywords and respond accordingly
        flight_keywords = ['altitude', 'speed', 'heading', 'weather', 'airport']
        if any(keyword in message.content.lower() for keyword in flight_keywords):
            await self.handle_flight_related_message(message)
        
        # Check if user has been greeted
        user_state = self.user_states.get(message.author.name)
        if user_state and not user_state.has_been_greeted:
            await self.send_greeting(message.author.name, message.channel.name)
            user_state.has_been_greeted = True

    async def handle_flight_related_message(self, message: Message):
        """Handle messages related to flight information."""
        try:
            if 'altitude' in message.content.lower():
                flight_data = await self.bot.littlenavmap.get_current_flight_data()
                if flight_data:
                    response = f"Current altitude is {flight_data['aircraft']['altitude']:,.0f} feet. Comply."
                    await self.send_message(message.channel.name, response, tts=True)
            elif 'weather' in message.content.lower():
                sim_info = await self.bot.littlenavmap.get_sim_info()
                if sim_info:
                    response = self.bot.littlenavmap.format_weather_data(sim_info)
                    await self.send_message(message.channel.name, response, tts=True)
        except Exception as e:
            self.logger.error(f"Error handling flight-related message: {e}", exc_info=True)

    async def should_filter_message(self, message: Message) -> bool:
        """Check if message should be filtered."""
        if await self.is_spam(message):
            await self.handle_spam(message)
            return True
        if await self.contains_blocked_content(message):
            await self.handle_blocked_content(message)
            return True
        if await self.is_on_cooldown(message):
            return True
        if await self.is_repeated_message(message):
            await self.handle_repeated_message(message)
            return True
        return False

    async def is_spam(self, message: Message) -> bool:
        """Check if message is spam."""
        user = message.author.name
        now = datetime.now()
        self.spam_protection[user] = [
            t for t in self.spam_protection[user] 
            if now - t < timedelta(seconds=10)
        ]
        self.spam_protection[user].append(now)
        return len(self.spam_protection[user]) > 5

    async def handle_spam(self, message: Message):
        """Handle spam messages."""
        response = self.bot.personality.format_response(
            "Excessive message frequency detected. Reduce transmission rate.",
            {"user": message.author.name}
        )
        await self.send_message(message.channel.name, response)

    async def contains_blocked_content(self, message: Message) -> bool:
        """Check if message contains blocked content."""
        return any(phrase in message.content.lower() for phrase in self.blocked_phrases)

    async def handle_blocked_content(self, message: Message):
        """Handle messages with blocked content."""
        response = self.bot.personality.format_response(
            "Message contains prohibited content. Adjust your communication parameters.",
            {"user": message.author.name}
        )
        await self.send_message(message.channel.name, response)

    async def is_on_cooldown(self, message: Message) -> bool:
        """Check if user is on cooldown."""
        if message.author.is_mod:
            return False
        
        user_state = self.user_states.get(message.author.name)
        if not user_state or not user_state.last_command:
            return False
        
        cooldown = timedelta(seconds=3)  # Default cooldown
        if user_state.is_subscriber:
            cooldown = timedelta(seconds=1)  # Reduced cooldown for subscribers
            
        return datetime.now() - user_state.last_command < cooldown

    async def is_repeated_message(self, message: Message) -> bool:
        """Check if message is a repeated message."""
        user_state = self.user_states.get(message.author.name)
        if not user_state:
            return False
        
        if user_state.last_message_content == message.content:
            return True
        return False

    async def handle_repeated_message(self, message: Message):
        """Handle repeated messages."""
        response = self.bot.personality.format_response(
            "Repetitive messaging detected. Vary your communication.",
            {"user": message.author.name}
        )
        await self.send_message(message.channel.name, response)

    async def update_user_state(self, message: Message):
        """Update user state information."""
        username = message.author.name
        if username not in self.user_states:
            self.user_states[username] = UserState(
                username=username,
                first_seen=datetime.now()
            )
        
        user_state = self.user_states[username]
        user_state.last_message = datetime.now()
        user_state.is_subscriber = message.author.is_subscriber
        user_state.last_message_content = message.content
        
        if message.content.startswith(self.config.twitch.PREFIX):
            user_state.last_command = datetime.now()

    def update_message_metrics(self, message: Message):
        """Update metrics for each message."""
        self.metrics.total_messages += 1
        self.metrics.last_message_time = datetime.now()
        self.metrics.users_active.add(message.author.name)
        self.metrics.message_frequency[message.author.name] += 1

    async def send_message(self, channel: str, content: str, tts: bool = False):
        """Send a message to a channel with rate limiting."""
        try:
            await self.rate_limiter.acquire()
            if len(content) > 490:
                await self._send_long_message(channel, content, tts)
            else:
                await self.bot.get_channel(channel).send(content)
                if tts:
                    await self.bot.tts_manager.speak(content)
        except Exception as e:
            self.logger.error(f"Error sending message: {e}", exc_info=True)

    async def _send_long_message(self, channel: str, content: str, tts: bool = False):
        """Send a long message by splitting it into multiple messages."""
        parts = [content[i:i + 490] for i in range(0, len(content), 490)]
        for part in parts:
            await self.bot.get_channel(channel).send(part)
            if tts:
                await self.bot.tts_manager.speak(part)
            await asyncio.sleep(0.1)  # Small delay between messages

    async def send_error_message(self, channel: str):
        """Send an error message to the channel."""
        error_message = self.bot.personality.format_response(
            "Error in command execution. Your inefficiency has been noted.",
            {}
        )
        await self.send_message(channel, error_message)

    async def send_greeting(self, username: str, channel: str):
        """Send a greeting message to a user."""
        greeting = self.bot.personality.get_greeting(username)
        await self.send_message(channel, greeting, tts=True)

    async def _process_message_queue(self):
        """Process messages from the queue."""
        while True:
            try:
                message = await self.message_queue.get()
                await self._process_message(message)
                self.message_queue.task_done()
            except Exception as e:
                self.logger.error(f"Error processing message from queue: {e}", exc_info=True)
            await asyncio.sleep(0.1)

    async def _update_metrics(self):
        """Update chat metrics periodically."""
        while True:
            try:
                self.metrics.users_active = {
                    user for user, state in self.user_states.items()
                    if state.last_message and datetime.now() - state.last_message < timedelta(minutes=5)
                }
                
                self.logger.info(
                    f"Chat Metrics - Messages: {self.metrics.total_messages}, "
                    f"Commands: {self.metrics.commands_processed}, "
                    f"Mentions: {self.metrics.bot_mentions}, "
                    f"Active Users: {len(self.metrics.users_active)}"
                )
                
                await asyncio.sleep(300)  # Update every 5 minutes
            except Exception as e:
                self.logger.error(f"Error updating metrics: {e}", exc_info=True)
                await asyncio.sleep(60)  # Retry after 1 minute on error

    async def close(self):
        """Clean up resources."""
        if self._processor_task:
            self._processor_task.cancel()
        if self._metrics_task:
            self._metrics_task.cancel()
            
        try:
            if self._processor_task:
                await self._processor_task
            if self._metrics_task:
                await self._metrics_task
        except asyncio.CancelledError:
            pass
        
        self.logger.info("Chat manager closed")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()