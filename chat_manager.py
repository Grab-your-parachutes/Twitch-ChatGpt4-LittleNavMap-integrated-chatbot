# File: chat_manager.py
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict
from twitchio.message import Message
from src.config import Config
from cachetools import TTLCache
import re

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

        self.tokens = min(self.max_tokens, self.tokens + time_passed * time_passed * self.rate)
        if self.tokens < 1.0:
            await asyncio.sleep((1.0 - self.tokens) / self.rate)
        self.tokens -= 1.0

class ChatManager:
    def __init__(self, bot, config):
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
        
    async def should_filter_message(self, message: Message) -> bool:
        """Check if a message should be filtered (ignored)."""
        if message.echo:
            return True  # Ignore messages from the bot itself

        if message.author is None:
            self.logger.warning("Message with no author detected.")
            return True

        author_name = message.author.name.lower()
        if author_name in self.config.twitch.IGNORE_LIST:
            return True  # Ignore messages from users in the ignore list
        
        if author_name == self.bot.nick.lower() or author_name == "grab_your_parachutes": 
            return False # Do not filter bot's own messages or your username

        if await self.detect_spam(message):
            self.logger.warning(f"Spam detected from {author_name}: {message.content}")
            return True

        for phrase in self.blocked_phrases:
            if phrase in message.content.lower():
                self.logger.warning(f"Blocked phrase detected from {author_name}: {message.content}")
                return True
        return False

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
            
    async def _process_message_queue(self):
        """Process messages from the queue."""
        while True:
            try:
                message = await self.message_queue.get()
                await self.rate_limiter.acquire()  # Apply rate limiting

                content = message.content.lower()

                if await self.is_bot_mention(content):
                    await self.handle_bot_mention(message)
                    self.metrics.bot_mentions += 1
                elif content.startswith(self.config.twitch.PREFIX):
                    await self.bot.command_handler.handle_command(message)
                    self.metrics.commands_processed += 1
                elif message.author.name.lower() == self.config.twitch.CHANNEL.lower():
                    # Handle streamer's messages if needed
                    pass

                self.message_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.metrics.errors += 1
                self.logger.error(f"Error processing message: {e}", exc_info=True)

    async def should_filter_message(self, message: Message) -> bool:
        """Check if a message should be filtered (ignored)."""
        if message.echo:
            return True  # Ignore messages from the bot itself

        if message.author is None:
            self.logger.warning("Message with no author detected.")
            return True

        author_name = message.author.name.lower()
        if author_name in self.config.twitch.IGNORE_LIST:
            return True  # Ignore messages from users in the ignore list

        if await self.detect_spam(message):
            self.logger.warning(f"Spam detected from {author_name}: {message.content}")
            return True

        for phrase in self.blocked_phrases:
            if phrase in message.content.lower():
                self.logger.warning(f"Blocked phrase detected from {author_name}: {message.content}")
                return True
        return False

    def update_message_metrics(self, message: Message):
        """Update chat metrics based on a new message."""
        self.metrics.total_messages += 1
        self.metrics.last_message_time = datetime.now()
        self.metrics.users_active.add(message.author.name)
        self.metrics.message_frequency[message.author.name] += 1
        
    async def update_user_state(self, message: Message):
        """Update user state for loyalty, greetings, and other tracking."""
        username = message.author.name.lower()

        if username not in self.user_states:
            self.user_states[username] = UserState(
                username=username,
                first_seen=datetime.now()
            )

        user_state = self.user_states[username]
        user_state.last_message = datetime.now()
        user_state.last_message_content = message.content
        user_state.is_subscriber = message.author.is_subscriber

        if not user_state.has_been_greeted:
            greeting = self.bot.personality.get_greeting(username)
            await self.send_message(message.channel.name, greeting, tts=True)
            user_state.has_been_greeted = True

    async def is_bot_mention(self, content: str) -> bool:
        """Check if the bot was mentioned in a message."""
        bot_name = self.bot.nick.lower()
        return any(trigger in content for trigger in [bot_name] + self.config.bot_trigger_words)

    async def handle_bot_mention(self, message: Message):
        """Handle direct mentions of the bot."""
        content = message.content.strip()
        prompt = content.replace(self.bot.nick, "").strip()
        await self.respond_to_mention(message, prompt)

    async def respond_to_mention(self, message: Message, prompt: str):
        """Generate and send a response to a mention."""
        try:
            if prompt:
                # Cache based on prompt and channel
                cache_key = (prompt, message.channel.name)
                if cache_key in self.message_cache:
                    response = self.message_cache[cache_key]
                    self.logger.info("Using cached response")
                else:
                    response = await self.bot.generate_chatgpt_response(prompt)
                    self.message_cache[cache_key] = response
                    self.logger.info("Generating new response")
            else:
                response = self.bot.personality.format_response(
                    "You summoned me, {user_title} {user}?",
                    {"user": message.author.name}
                )

            await self.send_message(message.channel.name, response, tts=True)
        except Exception as e:
            self.logger.error(f"Error responding to mention: {e}", exc_info=True)
            error_message = self.bot.personality.get_error_response(
                "timeout",
                {"user": message.author.name}
            )
            await message.channel.send(error_message)

    async def detect_spam(self, message: Message) -> bool:
        """Detect and handle spam messages."""
        author = message.author.name.lower()
        content = message.content.lower()

        now = datetime.now()
        self.spam_protection[author] = [
            msg_time for msg_time in self.spam_protection[author]
            if (now - msg_time).total_seconds() < 60  # Keep track of messages in the last minute
        ]

        self.spam_protection[author].append(now)
        if len(self.spam_protection[author]) > 5: # Threshold for spam detection
            return True  # More than 5 messages in the last minute

        # Additional spam detection criteria
        if any(content == msg for msg in [msg_data.last_message_content for msg_data in self.user_states.values() if msg_data.last_message_content]):
             self.logger.warning("Spam detected (repeated message).")
             return True

        if len(set(content)) < 5 and len(content) > 20:  # Low character diversity in long messages
            self.logger.warning("Spam detected (low character diversity).")
            return True

        return False
        
    async def send_message(self, channel: str, message: str, tts: bool = False):
        """Send a message to a channel with optional TTS."""
        try:
            await self.rate_limiter.acquire()
            if channel_obj := self.bot.get_channel(channel):
                await channel_obj.send(message)
                if tts:
                    await self.bot.tts_manager.speak(message)
            else:
                self.logger.error(f"Channel not found: {channel}")
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")

    async def _update_metrics(self):
        """Update chat metrics periodically."""
        while True:
            try:
                await asyncio.sleep(30) # Update every 30 seconds
                # Reset active user count if no messages have been sent in the last minute
                if self.metrics.last_message_time is not None and (datetime.now() - self.metrics.last_message_time).total_seconds() > 60:
                    self.metrics.users_active = set()
                    self.metrics.message_frequency.clear()
            except asyncio.CancelledError:
                   break
            except Exception as e:
                self.logger.error(f"Error updating chat metrics: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def close(self):
        """Clean up resources."""
        if self._processor_task:
            self._processor_task.cancel()
        if self._metrics_task:
            self._metrics_task.cancel()

        try:
            await self.message_queue.join()
        except asyncio.CancelledError:
             pass

        self.logger.info("Chat manager closed")

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()