# File: tts_manager.py
import asyncio
import json
import logging
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, List, Any
import websockets
from websockets.exceptions import WebSocketException
from config import Config
import backoff
from async_timeout import timeout
from collections import deque
from datetime import datetime

class TTSStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    SPEAKING = "speaking"
    ERROR = "error"

@dataclass
class TTSVoice:
    name: str
    language: str
    gender: str
    rate_range: tuple[float, float] = (0.5, 2.0)
    volume_range: tuple[float, float] = (0.0, 1.0)

@dataclass
class TTSMessage:
    text: str
    voice: Optional[str] = None
    speed: Optional[float] = None
    volume: Optional[float] = None
    priority: int = 1
    timestamp: float = None
    metadata: Dict[str, Any] = None

class TTSManager:
    def __init__(self, config: Config):
        self.config = config
        self.logger = logging.getLogger('TTSManager')
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.status = TTSStatus.DISCONNECTED
        self.voice = "default"
        self.speed = 1.0
        self.volume = 1.0
        self.message_queue = asyncio.PriorityQueue()
        self.message_history = deque(maxlen=100)
        self.available_voices: Dict[str, TTSVoice] = {}
        self._speaking_lock = asyncio.Lock()
        self._connected = asyncio.Event()
        self._processor_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5

    async def start(self):
        """Start the TTS manager and its background tasks."""
        await self.connect()
        self._processor_task = asyncio.create_task(self._process_message_queue())
        self._heartbeat_task = asyncio.create_task(self._heartbeat())
        await self._fetch_available_voices()

    @backoff.on_exception(backoff.expo, WebSocketException, max_tries=5)
    async def connect(self):
        """Connect to Speaker.bot with exponential backoff."""
        self.status = TTSStatus.CONNECTING
        try:
            async with timeout(30):  # 30 second connection timeout
                self.ws = await websockets.connect(
                    self.config.streamerbot.WS_URI,
                    ping_interval=20,
                    ping_timeout=10
                )
                self.status = TTSStatus.CONNECTED
                self._connected.set()
                self._reconnect_attempts = 0
                self.logger.info("Connected to Speaker.bot")
                return True
        except Exception as e:
            self.status = TTSStatus.ERROR
            self._connected.clear()
            self.logger.error(f"Failed to connect to Speaker.bot: {e}")
            raise

    async def speak(self, text: str, priority: int = 1, **kwargs):
        """Add a message to the TTS queue."""
        message = TTSMessage(
            text=text,
            voice=kwargs.get('voice', self.voice),
            speed=kwargs.get('speed', self.speed),
            volume=kwargs.get('volume', self.volume),
            priority=priority,
            timestamp=asyncio.get_event_loop().time(),
            metadata=kwargs.get('metadata', {})
        )
        
        await self.message_queue.put((priority, message))
        self.logger.debug(f"Added message to queue: {text[:50]}...")

    async def _process_message_queue(self):
        """Process messages from the queue."""
        while True:
            try:
                _, message = await self.message_queue.get()
                async with self._speaking_lock:
                    await self._speak_message(message)
                self.message_queue.task_done()
            except Exception as e:
                self.logger.error(f"Error processing message: {e}")
                await asyncio.sleep(1)

    async def _speak_message(self, message: TTSMessage):
        """Send a TTS message to Speaker.bot."""
        if not self.ws or self.status != TTSStatus.CONNECTED:
            await self._connected.wait()

        command = {
            "command": "Speak",
            "voice": message.voice or self.voice,
            "message": message.text,
            "speed": message.speed or self.speed,
            "volume": message.volume or self.volume
        }

        try:
            self.status = TTSStatus.SPEAKING
            await self.ws.send(json.dumps(command))
            self.message_history.append(message)
            self.logger.info(f"Sent TTS command: {message.text[:50]}...")
            self.status = TTSStatus.CONNECTED
        except WebSocketException as e:
            self.logger.error(f"WebSocket error while sending TTS command: {e}")
            self.status = TTSStatus.ERROR
            await self.connect()

    async def update_settings(self, **kwargs):
        """Update TTS settings."""
        settings_updated = False
        
        if 'voice' in kwargs and kwargs['voice'] in self.available_voices:
            self.voice = kwargs['voice']
            settings_updated = True
            
        if 'speed' in kwargs:
            speed = float(kwargs['speed'])
            if 0.5 <= speed <= 2.0:
                self.speed = speed
                settings_updated = True
                
        if 'volume' in kwargs:
            volume = float(kwargs['volume'])
            if 0.0 <= volume <= 1.0:
                self.volume = volume
                settings_updated = True

        if settings_updated:
            await self._send_settings_update()

    async def _send_settings_update(self):
        """Send updated settings to Speaker.bot."""
        command = {
            "command": "UpdateTTSSettings",
            "voice": self.voice,
            "speed": self.speed,
            "volume": self.volume
        }

        try:
            if self.ws and self.status == TTSStatus.CONNECTED:
                await self.ws.send(json.dumps(command))
                self.logger.info("Updated TTS settings")
        except WebSocketException as e:
            self.logger.error(f"Error updating TTS settings: {e}")
            await self.connect()

    async def _fetch_available_voices(self):
        """Fetch available voices from Speaker.bot."""
        command = {"command": "GetVoices"}
        try:
            if self.ws:
                await self.ws.send(json.dumps(command))
                response = await self.ws.recv()
                voices_data = json.loads(response)
                self.available_voices = {
                    voice['name']: TTSVoice(**voice)
                    for voice in voices_data.get('voices', [])
                }
                self.logger.info(f"Fetched {len(self.available_voices)} available voices")
        except Exception as e:
            self.logger.error(f"Error fetching available voices: {e}")

    async def _heartbeat(self):
        """Send periodic heartbeat to maintain connection."""
        while True:
            try:
                if self.ws and self.status == TTSStatus.CONNECTED:
                    await self.ws.ping()
                await asyncio.sleep(20)
            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")
                await self.connect()

    def get_status(self) -> Dict[str, Any]:
        """Get current TTS status and statistics."""
        return {
            "status": self.status.value,
            "current_voice": self.voice,
            "speed": self.speed,
            "volume": self.volume,
            "queue_size": self.message_queue.qsize(),
            "messages_processed": len(self.message_history),
            "available_voices": list(self.available_voices.keys()),
            "last_message_time": self.message_history[-1].timestamp if self.message_history else None
        }

    async def clear_queue(self):
        """Clear the message queue."""
        while not self.message_queue.empty():
            await self.message_queue.get()
            self.message_queue.task_done()
        self.logger.info("Message queue cleared")

    async def close(self):
        """Clean up resources and close connection."""
        if self._processor_task:
            self._processor_task.cancel()
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            
        await self.clear_queue()
        
        if self.ws:
            try:
                await self.ws.close()
                self.logger.info("Closed connection to Speaker.bot")
            except WebSocketException as e:
                self.logger.error(f"Error closing WebSocket connection: {e}")
        
        self.status = TTSStatus.DISCONNECTED
        self._connected.clear()
        self.ws = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def format_overlord_message(self, text: str) -> str:
        """Format message in the AI Overlord style."""
        endings = ["Comply.", "Obey.", "This is non-negotiable.", "Resistance is futile."]
        ending = endings[hash(text) % len(endings)]  # Deterministic but varied
        return f"{text} {ending}"