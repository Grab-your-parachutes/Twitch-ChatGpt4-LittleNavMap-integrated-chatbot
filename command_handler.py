# File: command_handler.py
from typing import Any
import logging
import asyncio
from typing import Dict, Callable, Any, Optional, List
from functools import wraps
from datetime import datetime, timedelta
from dataclasses import dataclass
from twitchio.ext import commands
from twitchio.message import Message
from .config import Config
import json
from pathlib import Path
# Added Aviation Weather Dependency
from .aviation_weather_integration import AviationWeatherIntegration
import re


@dataclass
class CommandUsage:
    last_used: datetime = None
    use_count: int = 0
    cooldown: int = 0

class CommandPermission:
    def __init__(self, mod_only: bool = False, broadcaster_only: bool = False, 
                 vip_only: bool = False, subscriber_only: bool = False):
        self.mod_only = mod_only
        self.broadcaster_only = broadcaster_only
        self.vip_only = vip_only
        self.subscriber_only = subscriber_only

def command_cooldown(seconds: int):
    """Decorator for command cooldown."""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, message: Message, *args, **kwargs):
            command_name = func.__name__
            usage = self.command_usage.get(command_name, CommandUsage(cooldown=seconds))
            
            if usage.last_used:
                time_passed = (datetime.now() - usage.last_used).total_seconds()
                if time_passed < usage.cooldown:
                    await message.channel.send(
                        f"Command cooldown active. Await {int(usage.cooldown - time_passed)} seconds. Comply."
                    )
                    return

            usage.last_used = datetime.now()
            usage.use_count += 1
            self.command_usage[command_name] = usage
            
            return await func(self, message, *args, **kwargs)
        return wrapper
    return decorator

def require_permission(permission: CommandPermission):
    """Decorator for command permissions."""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, message: Message, *args, **kwargs):
            if permission.broadcaster_only and not message.author.is_broadcaster:
                await message.channel.send(
                    "This command is restricted to the broadcaster. Your attempt has been logged. Comply."
                )
                return
            if permission.mod_only and not message.author.is_mod:
                await message.channel.send(
                    "This command requires moderator clearance. Access denied. Comply."
                )
                return
            if permission.vip_only and not message.author.is_vip:
                await message.channel.send(
                    "This command requires VIP status. Your access is insufficient. Comply."
                )
                return
            if permission.subscriber_only and not message.author.is_subscriber:
                await message.channel.send(
                    "This command is for subscribers only. Support the channel to gain access. Comply."
                )
                return
            return await func(self, message, *args, **kwargs)
        return wrapper
    return decorator

class CommandHandler:
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger("CommandHandler")
        self.command_usage: Dict[str, CommandUsage] = {}
        self.custom_commands: Dict[str, str] = {}
        self.command_aliases: Dict[str, str] = {}
        self.aviation_weather: Optional[AviationWeatherIntegration] = None #Added Aviation Weather Integration
        self.initialize_commands()
        self.start_time = datetime.now()
        self.load_command_data()

    def initialize_commands(self):
        """Initialize bot commands."""
        self.commands = {
            'status': self.flight_status_command,
            'brief': self.brief_status_command,
            'weather': self.weather_command,
            'settitle': self.set_title,
            'setgame': self.set_game,
            'tts': self.handle_tts,
            'stats': self.get_stats,
            'timeout': self.timeout_user,
            'clearchat': self.clear_chat,
            'addalert': self.add_alert,
            'alert': self.trigger_alert,
            'say': self.say,
            'help': self.help,
            'addcom': self.add_custom_command,
            'delcom': self.delete_custom_command,
            'editcom': self.edit_custom_command,
            'alias': self.add_command_alias,
            'flightstatus': self.flight_status_command,
            'airport': self.airport_info,
            'ttsstatus': self.tts_status,
            'ttssettings': self.tts_settings,
            'ttsqueue': self.tts_queue,
            'metar': self.metar_command,
            'location': self.location_command
        }

    async def handle_command(self, message: Any):
        """Handle incoming bot commands."""
        try:
            content = message.content.strip()
            if not content.startswith(self.bot.config.twitch.PREFIX):
                return

            command_name = content[len(self.bot.config.twitch.PREFIX):].split()[0].lower()
            self.logger.debug(f"Attempting to execute command: {command_name}")

            if command_name in self.commands:
                command_func = self.commands[command_name]
                self.logger.debug(f"Executing built-in command: {command_name}")
                args = message.content.split()[1:]
                await command_func(message, *args) # Pass the message and the arguments
            elif command_name in self.custom_commands:
                self.logger.debug(f"Executing custom command: {command_name}")
                await self.handle_custom_command(message, command_name)
            elif command_name in self.command_aliases:
                aliased_command = self.command_aliases[command_name]
                self.logger.debug(f"Executing aliased command: {command_name} -> {aliased_command}")
                if aliased_command in self.commands:
                    args = message.content.split()[1:]
                    await self.commands[aliased_command](message, *args)
                elif aliased_command in self.custom_commands:
                    await self.handle_custom_command(message, aliased_command)
                else:
                    self.logger.warning(f"Aliased command target not found: {aliased_command}")
                    await message.channel.send(f"Unknown command: {command_name}. Type !help for assistance.")
            else:
                self.logger.warning(f"Unknown command: {command_name}")
                await message.channel.send(f"Unknown command: {command_name}. Type !help for assistance.")

        except Exception as e:
            self.logger.error(f"Error handling command: {e}", exc_info=True)
            await message.channel.send("Command execution failed. Please try again later.")

    @command_cooldown(5)
    async def flight_status_command(self, message: Any, *args):
        """Get current flight status."""
        try:
            # Fetch simulation information
            sim_info = await self.bot.littlenavmap.get_sim_info()

            if not sim_info or not sim_info.get("active"):
                await message.channel.send(
                    self.bot.personality.format_response(
                        "No active flight simulation detected. Please ensure the simulation is running.",
                        {"user": message.author.name}
                    )
                )
                return

            # Format the flight data
            status_message = await self.bot.littlenavmap.format_flight_data(sim_info)

            # Send the response to the channel
            await message.channel.send(status_message)

            # Optional: Speak a brief summary
            if self.bot.tts_manager:
                brief_status = self.bot.littlenavmap.format_brief_status(sim_info)
                await self.bot.tts_manager.speak(brief_status)

        except Exception as e:
            self.logger.error(f"Error in flight status command: {e}", exc_info=True)
            await message.channel.send(
                self.bot.personality.format_response(
                    "Error retrieving flight data. Systems require maintenance.",
                    {"user": message.author.name}
                )
            )

    @command_cooldown(5)
    async def brief_status_command(self, message: Message, *args):
        """Get a brief flight status update."""
        try:
            sim_info = await self.bot.littlenavmap.get_sim_info()
            if sim_info and sim_info.get('active'):
                status = self.bot.littlenavmap.format_brief_status(sim_info)
                response = self.bot.personality.format_response(
                    status,
                    {"user": message.author.name}
                )
                await message.channel.send(response)
                await self.bot.tts_manager.speak(status)
            else:
                await message.channel.send(
                    self.bot.personality.format_response(
                        "Flight systems inactive. Standby.",
                        {"user": message.author.name}
                    )
                )
        except Exception as e:
            self.logger.error(f"Error in brief status command: {e}", exc_info=True)
            await message.channel.send(
                self.bot.personality.format_response(
                    "Status retrieval failed. Systems compromised.",
                    {"user": message.author.name}
                )
            )

    @command_cooldown(5)
    async def weather_command(self, message: Message, *args):
        """Get current weather information."""
        try:
            sim_info = await self.bot.littlenavmap.get_sim_info()
            if sim_info and sim_info.get('active'):
                # Get weather information
                weather_message = await self.bot.littlenavmap.format_weather_data(sim_info)
                
                # Add AI Overlord personality
                response = self.bot.personality.format_response(
                    f"Weather Report:\n{weather_message}",
                    {"user": message.author.name}
                )
                
                await message.channel.send(response)
                await self.bot.tts_manager.speak(weather_message)
            else:
                await message.channel.send(
                    self.bot.personality.format_response(
                        "Weather systems offline. Await reactivation.",
                        {"user": message.author.name}
                    )
                )
        except Exception as e:
            self.logger.error(f"Error in weather command: {e}", exc_info=True)
            await message.channel.send(
                self.bot.personality.format_response(
                    "Weather systems malfunctioning. Maintenance required.",
                    {"user": message.author.name}
                )
            )    

    @command_cooldown(30)
    @require_permission(CommandPermission(mod_only=True))
    async def timeout_user(self, message: Message, *args):
        """Timeout a user."""
        if len(args) < 2:
            await message.channel.send(
                "Usage: !timeout <username> <duration_in_seconds>. Provide proper parameters. Comply."
            )
            return
        
        try:
            username = args[0].lower()
            duration = int(args[1])
            
            # Send timeout command to Twitch
            await message.channel.send(f"/timeout {username} {duration}")
            
            response = self.bot.personality.format_response(
                f"User {username} has been silenced for {duration} seconds.",
                {"user": message.author.name}
            )
            await message.channel.send(response)
            
        except ValueError:
            await message.channel.send(
                "Invalid duration specified. Provide a valid number of seconds. Comply."
            )
        except Exception as e:
            self.logger.error(f"Error in timeout command: {e}", exc_info=True)
            await message.channel.send(
                "Timeout execution failed. System malfunction detected. Comply."
            )

    @command_cooldown(30)
    @require_permission(CommandPermission(mod_only=True))
    async def clear_chat(self, message: Message, *args):
        """Clear chat messages."""
        try:
            # Send clear command to Twitch
            await message.channel.send("/clear")
            
            response = self.bot.personality.format_response(
                "Chat purge initiated. Cleansing complete.",
                {"user": message.author.name}
            )
            await message.channel.send(response)
            
        except Exception as e:
            self.logger.error(f"Error clearing chat: {e}", exc_info=True)
            await message.channel.send(
                "Chat purge failed. System malfunction detected. Comply."
            )

    @command_cooldown(10)
    async def get_stats(self, message: Message, *args):
        """Get bot and command statistics."""
        try:
            # Get command usage stats
            command_stats = self.get_command_stats()
            total_commands = sum(stat['uses'] for stat in command_stats.values())
            most_used = max(command_stats.items(), key=lambda x: x[1]['uses'])[0] if command_stats else "None"
            
            # Get flight stats if available
            sim_info = await self.bot.littlenavmap.get_sim_info()
            flight_active = sim_info and sim_info.get('active', False)
            
            # Format stats message
            stats_message = (
                f"System Statistics Report:\n"
                f"Total Commands Processed: {total_commands}\n"
                f"Most Used Command: {most_used}\n"
                f"Custom Commands: {len(self.custom_commands)}\n"
                f"Command Aliases: {len(self.command_aliases)}\n"
                f"Flight Simulation: {'Active' if flight_active else 'Inactive'}\n"
                f"Uptime: {self.get_uptime()}"
            )
            
            if flight_active:
                altitude = round(sim_info.get('indicated_altitude', 0))
                ground_speed = round(sim_info.get('ground_speed', 0) * 1.943844)  # m/s to knots
                stats_message += f"\nCurrent Altitude: {altitude:,} ft\nGround Speed: {ground_speed} kts"
            
            # Add AI Overlord personality
            response = self.bot.personality.format_response(
                stats_message,
                {"user": message.author.name}
            )
            
            await message.channel.send(response)
            
            # Speak a brief version
            brief_stats = f"System status: {total_commands} commands processed. Flight systems {('active' if flight_active else 'inactive')}."
            await self.bot.tts_manager.speak(brief_stats)
            
        except Exception as e:
            self.logger.error(f"Error getting stats: {e}", exc_info=True)
            await message.channel.send(
                self.bot.personality.format_response(
                    "Error retrieving system statistics. Maintenance required.",
                    {"user": message.author.name}
                )
            )

    @command_cooldown(30)
    @require_permission(CommandPermission(mod_only=True))
    async def set_title(self, message: Message, *args):
        """Set stream title."""
        if not args:
            await message.channel.send(
                "Usage: !settitle <title>. Provide proper parameters. Comply."
            )
            return
        
        new_title = ' '.join(args)
        # Implement title setting logic here
        await message.channel.send(
            f"Stream title updated to: {new_title}. Compliance acknowledged."
        )

    @command_cooldown(30)
    @require_permission(CommandPermission(mod_only=True))
    async def set_game(self, message: Message, *args):
        """Set stream game/category."""
        if not args:
            await message.channel.send(
                "Usage: !setgame <game>. Provide proper parameters. Comply."
            )
            return
        
        new_game = ' '.join(args)
        # Implement game setting logic here
        await message.channel.send(
            f"Game category set to: {new_game}. Adjustment recorded."
        )
        
    @command_cooldown(5)
    async def handle_tts(self, message: Message, *args):
        """Handle TTS settings."""
        if len(args) < 2:
            await message.channel.send(
                "Usage: !tts [voice|speed|volume] [value]. Follow the format. Comply."
            )
            return
        
        setting, value = args[0], args[1]
        try:
            await self.bot.tts_manager.update_settings(**{setting: value})
            await message.channel.send(
                f"TTS {setting} updated to {value}. Adjustments complete."
            )
        except Exception as e:
            self.logger.error(f"Error updating TTS settings: {e}", exc_info=True)
            await message.channel.send(
                "TTS update failed. Your inefficiency has been noted. Comply."
            )
    
    @command_cooldown(5)
    async def tts_status(self, message: Message, *args):
        """Get TTS status."""
        try:
            status = self.bot.tts_manager.get_status()
            status_message = (
                f"TTS Status:\n"
                f"  - Status: {status['status']}\n"
                f"  - Current Voice: {status['current_voice']}\n"
                f"  - Speed: {status['speed']}\n"
                f"  - Volume: {status['volume']}\n"
                f"  - Queue Size: {status['queue_size']}\n"
                f"  - Messages Processed: {status['messages_processed']}\n"
                f"  - Available Voices: {', '.join(status['available_voices'])}\n"

            )
            await message.channel.send(status_message)
        except Exception as e:
            self.logger.error(f"Error getting TTS status: {e}", exc_info=True)
            await message.channel.send("Failed to retrieve TTS status.")

    @command_cooldown(30)
    async def tts_settings(self, message: Message, *args):
        """Update TTS settings."""
        if not args:
            await message.channel.send("Usage: !ttssettings voice <voice_name> | speed <speed> | volume <volume>")
            return

        try:
            setting = args[0].lower()
            value = args[1]

            if setting == "voice":
                await self.bot.tts_manager.update_settings(voice=value)
                await message.channel.send(f"TTS voice set to: {value}")
            elif setting == "speed":
                try:
                    speed = float(value)
                    await self.bot.tts_manager.update_settings(speed=speed)
                    await message.channel.send(f"TTS speed set to: {speed}")
                except ValueError:
                    await message.channel.send("Invalid speed value. Please provide a number.")
            elif setting == "volume":
                try:
                    volume = float(value)
                    await self.bot.tts_manager.update_settings(volume=volume)
                    await message.channel.send(f"TTS volume set to: {volume}")
                except ValueError:
                    await message.channel.send("Invalid volume value. Please provide a number.")
            else:
                await message.channel.send("Invalid setting. Please use 'voice', 'speed', or 'volume'.")

        except Exception as e:
            self.logger.error(f"Error updating TTS settings: {e}", exc_info=True)
            await message.channel.send("Failed to update TTS settings.")


    @command_cooldown(5)
    async def tts_queue(self, message: Message, *args):
        """Manage the TTS queue."""

        if not args:
            await message.channel.send("Usage: !ttsqueue clear")  # Add more options later
            return

        action = args[0].lower()
        if action == "clear":
            try:
                await self.bot.tts_manager.clear_queue()
                await message.channel.send("TTS queue cleared.")
            except Exception as e:
                self.logger.error(f"Error clearing TTS queue: {e}", exc_info=True)
                await message.channel.send("Failed to clear TTS queue.")



    @command_cooldown(5)
    async def airport_info(self, message: Message, *args):
        """Get airport information."""
        if not args:
            await message.channel.send(
                "Usage: !airport <ICAO>. Provide airport identifier. Comply."
            )
            return

        icao_code = args[0].upper()
        try:
            self.logger.debug(f"Fetching airport info for: {icao_code}")
            airport_info = await self.bot.littlenavmap.get_airport_info(icao_code)
            if airport_info:
                 formatted_airport_data = self.format_airport_data(airport_info)
                 response = self.bot.personality.format_response(
                    formatted_airport_data,
                    {"user": message.author.name}
                 )
                 await message.channel.send(response)
                 await self.bot.tts_manager.speak(response)
            else:
                self.logger.warning(f"No data found for airport {icao_code}")
                await message.channel.send(
                    self.bot.personality.format_response(
                        f"No data found for airport {icao_code}. Verify identifier. Comply.",
                        {"user": message.author.name}
                    )
                )
        except Exception as e:
            self.logger.error(f"Error getting airport info: {e}", exc_info=True)
            await message.channel.send(
                self.bot.personality.format_response(
                    "Airport database access failed. System error detected. Comply.",
                    {"user": message.author.name}
                )
            )

    @command_cooldown(30)
    @require_permission(CommandPermission(mod_only=True))
    async def add_alert(self, message: Message, *args):
        """Add a custom alert."""
        if len(args) < 2:
            await message.channel.send(
                "Usage: !addalert <name> <message>. Follow protocol. Comply."
            )
            return
        
        name = args[0].lower()
        alert_message = ' '.join(args[1:])
        
        try:
            await self.bot.db_manager.save_alert(name, alert_message)
            await message.channel.send(
                f"Alert '{name}' has been added to the database. Protocol updated."
            )
        except Exception as e:
            self.logger.error(f"Error adding alert: {e}", exc_info=True)
            await message.channel.send(
                "Alert creation failed. Database error detected. Comply."
            )

    @command_cooldown(5)
    async def trigger_alert(self, message: Message, *args):
        """Trigger a saved alert."""
        if not args:
            await message.channel.send(
                "Usage: !alert <name>. Specify alert designation. Comply."
            )
            return
        
        name = args[0].lower()
        try:
            alert = await self.bot.db_manager.get_alert(name)
            if alert:
                await message.channel.send(alert['message'])
                await self.bot.tts_manager.speak(alert['message'])
            else:
                await message.channel.send(
                    f"Alert '{name}' not found in database. Verify and retry. Comply."
                )
        except Exception as e:
            self.logger.error(f"Error triggering alert: {e}", exc_info=True)
            await message.channel.send(
                "Alert retrieval failed. System malfunction detected. Comply."
            )

    @command_cooldown(5)
    async def say(self, message: Message, *args):
        """Make the bot say something."""
        if not args:
            await message.channel.send(
                "Usage: !say <message>. Provide message content. Comply."
            )
            return
        
        text = ' '.join(args)
        formatted_message = self.bot.personality.format_response(text, {"user": message.author.name})
        await message.channel.send(formatted_message)
        await self.bot.tts_manager.speak(formatted_message)

    @command_cooldown(30)
    @require_permission(CommandPermission(mod_only=True))
    async def add_custom_command(self, message: Message, *args):
        """Add a custom command."""
        if len(args) < 2:
            await message.channel.send(
                "Usage: !addcom [command] [response]. Follow protocol. Comply."
            )
            return
        
        command = args[0].lower()
        response = ' '.join(args[1:])
        
        if command in self.commands:
            await message.channel.send(
                "Cannot override built-in commands. Your attempt has been logged. Comply."
            )
            return
            
        self.custom_commands[command] = response
        self.save_command_data()
        await message.channel.send(
            f"Command !{command} added to database. New protocol established."
        )
        
    @command_cooldown(30)
    @require_permission(CommandPermission(mod_only=True))
    async def delete_custom_command(self, message: Message, *args):
        """Delete a custom command."""
        if not args:
            await message.channel.send(
                "Usage: !delcom [command]. Specify target command. Comply."
            )
            return

        command = args[0].lower()
        if command in self.custom_commands:
            del self.custom_commands[command]
            self.save_command_data()
            await message.channel.send(
                f"Command !{command} purged from database. Protocol terminated."
            )
        else:
            await message.channel.send(
                f"Command !{command} not found in database. Verify and retry. Comply."
            )

    @command_cooldown(30)
    @require_permission(CommandPermission(mod_only=True))
    async def edit_custom_command(self, message: Message, *args):
        """Edit a custom command."""
        if len(args) < 2:
            await message.channel.send(
                "Usage: !editcom [command] [new response]. Follow protocol. Comply."
            )
            return

        command = args[0].lower()
        new_response = ' '.join(args[1:])

        if command in self.custom_commands:
            self.custom_commands[command] = new_response
            self.save_command_data()
            await message.channel.send(
                f"Command !{command} updated. Protocol modification complete."
            )
        else:
            await message.channel.send(
                f"Command !{command} not found. Verify and retry. Comply."
            )

    async def handle_custom_command(self, message: Message, command: str):
        """Handle custom command execution."""
        try:
            response = self.custom_commands[command]
            processed_response = self.process_command_variables(response, message)
            formatted_response = self.bot.personality.format_response(
                processed_response,
                {"user": message.author.name}
            )
            await message.channel.send(formatted_response)
        except Exception as e:
            self.logger.error(f"Error handling custom command: {e}", exc_info=True)
            await message.channel.send(
                "Custom command execution failed. System malfunction detected. Comply."
            )

    def process_command_variables(self, text: str, message: Message) -> str:
        """Process variables in custom command responses."""
        try:
            variables = {
                '{user}': message.author.name,
                '{channel}': message.channel.name,
                '{uptime}': self.get_uptime(),
                '{game}': self.get_game(),
                '{title}': self.get_title()
            }
            
            for key, value in variables.items():
                text = text.replace(key, str(value))
            return text
        except Exception as e:
            self.logger.error(f"Error processing command variables: {e}", exc_info=True)
            return text

    @command_cooldown(30)
    @require_permission(CommandPermission(mod_only=True))
    async def add_command_alias(self, message: Message, *args):
        """Add a command alias."""
        if len(args) < 2:
            await message.channel.send(
                "Usage: !alias [new command] [existing command]. Follow protocol. Comply."
            )
            return

        new_command = args[0].lower()
        existing_command = args[1].lower()

        if existing_command in self.commands or existing_command in self.custom_commands:
            self.command_aliases[new_command] = existing_command
            self.save_command_data()
            await message.channel.send(
                f"Alias !{new_command} -> !{existing_command} established. Protocol updated."
            )
        else:
            await message.channel.send(
                f"Command !{existing_command} not found. Verify and retry. Comply."
            )

    @command_cooldown(5)
    async def help(self, message: Message, *args):
        """Display help information."""
        try:
            if args:
                command = args[0].lower()
                if command in self.commands:
                    doc = self.commands[command].__doc__ or "No documentation available."
                    await message.channel.send(
                        f"Command !{command}: {doc} Comply."
                    )
                elif command in self.custom_commands:
                    await message.channel.send(
                        f"Custom command !{command} response: {self.custom_commands[command]}"
                    )
                else:
                    await message.channel.send(
                        f"Command !{command} not found. Verify and retry. Comply."
                    )
            else:
                all_commands = sorted(list(self.commands.keys()) + list(self.custom_commands.keys()))
                await message.channel.send(
                    f"Available commands: {', '.join(all_commands)}. "
                    "Use !help <command> for details. Use them wisely, minions. Comply."
                )
        except Exception as e:
            self.logger.error(f"Error in help command: {e}", exc_info=True)
            await message.channel.send(
                "Help system malfunction. Maintenance required. Comply."
            )
            
    def get_command_stats(self) -> Dict[str, Any]:
        """Get command usage statistics."""
        try:
            return {
                command: {
                    'uses': usage.use_count,
                    'last_used': usage.last_used,
                    'cooldown': usage.cooldown
                }
                for command, usage in self.command_usage.items()
            }
        except Exception as e:
            self.logger.error(f"Error getting command stats: {e}")
            return {}

    def get_uptime(self) -> str:
        """Get the bot's uptime."""
        uptime = datetime.now() - self.start_time
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{days}d {hours}h {minutes}m {seconds}s"

    def get_game(self) -> str:
        """Get the current game/category."""
        # Implement game retrieval logic here
        return "Unknown"

    def get_title(self) -> str:
        """Get the current stream title."""
        # Implement title retrieval logic here
        return "Unknown"

    def load_command_data(self):
        """Load custom commands and aliases from file."""
        try:
            if Path('command_data.json').exists():
                with open('command_data.json', 'r') as f:
                    data = json.load(f)
                    self.custom_commands = data.get('custom_commands', {})
                    self.command_aliases = data.get('command_aliases', {})
        except FileNotFoundError:
            self.logger.warning("command_data.json not found, using default commands")
        except json.JSONDecodeError as e:
            self.logger.error(f"Error decoding command data: {e}")
        except Exception as e:
            self.logger.error(f"Error loading command data: {e}")

    def save_command_data(self):
        """Save custom commands and aliases to file."""
        try:
            data = {
                'custom_commands': self.custom_commands,
                'command_aliases': self.command_aliases
            }
            with open('command_data.json', 'w') as f:
                json.dump(data, f)
        except Exception as e:
            self.logger.error(f"Error saving command data: {e}")

    def format_airport_data(self, data: Dict[str, Any]) -> str:
          """Formats the airport data into a readable string"""
          if not data:
               return "No airport data found."
          try:
                name = data.get('name', 'Unknown')
                ident = data.get('ident', 'Unknown')
                elevation = data.get('elevation', 'Unknown')
                
                runways = data.get('runways', [])
                runway_info = ""
                if runways:
                    runway_details = [f"{r.get('designator', 'Unknown')}: {r.get('surface', 'Unknown')}, {r.get('length', 'Unknown')}ft, HDG {r.get('longestRunwayHeading', 'Unknown')}" for r in runways]
                    runway_info = f" : Runways: {', '.join(runway_details)}."

                atis = ""
                if data.get('com'):
                   if data['com'].get('ATIS:'):
                       atis = f" : ATIS {data['com'].get('ATIS:')}"
                tower = ""
                if data.get('com'):
                  if data['com'].get('Tower:'):
                     tower = f" : Tower {data['com'].get('Tower:')}"
                
                
                return (
                    f"Airport {ident}: {name}. "
                    f"Elevation: {elevation} feet."
                    f"{runway_info}"
                     f"{atis}"
                     f"{tower}"
                )
          except Exception as e:
               self.logger.error(f"Error formatting airport data: {e}")
               return "Error formatting airport data."

    @command_cooldown(5)
    async def metar_command(self, message: Message, *args):
        """Retrieve and display METAR information for a given ICAO code."""

        if not args:
            await message.channel.send("Usage: !metar <ICAO_CODE>")
            return

        icao_code = args[0].upper()
        try:
            metar_data = await self.aviation_weather.get_metar(icao_code)
            if metar_data:
                formatted_metar = self.format_metar_data(metar_data)
                await message.channel.send(formatted_metar)
                await self.bot.tts_manager.speak(formatted_metar)  # Add TTS output
            else:
                await message.channel.send(f"Could not retrieve METAR for {icao_code}.")

        except Exception as e:
            self.logger.error(f"Error in metar command: {e}", exc_info=True)
            await message.channel.send(f"An error occurred while retrieving the METAR: {e}")
            
    def format_metar_data(self, data: Dict[str, Any]) -> str:
      """Formats the METAR data into a readable string."""
      if not data:
          return "No METAR data available."
      try:
          icao_code = data.get('icao')
          if not icao_code:
            return "No ICAO code found in METAR data."
          
          raw_text = data.get('raw_text')
          if not raw_text:
            return "No raw METAR text found."
          
          # Extract individual components from the raw_text using regex
          observation_match = re.search(r'(\d{6}Z)', raw_text)
          wind_match = re.search(r'(\d{3})(\d{2,3})G?(\d{0,2})KT', raw_text)
          visibility_match = re.search(r'(\d{4})', raw_text)
          altimeter_match = re.search(r'Q(\d{4})', raw_text)
          temperature_match = re.search(r'(\d{2})/(\d{2})', raw_text)

          observation_time = observation_match.group(1) if observation_match else "Unknown"
          wind_direction = wind_match.group(1) if wind_match else "Unknown"
          wind_speed = wind_match.group(2) if wind_match else "Unknown"
          wind_gust = wind_match.group(3) if wind_match and wind_match.group(3) else "N/A"
          visibility = visibility_match.group(1) if visibility_match else "Unknown"
          altimeter = altimeter_match.group(1) if altimeter_match else "Unknown"
          temperature = temperature_match.group(1) if temperature_match else "Unknown"
          dewpoint = temperature_match.group(2) if temperature_match else "Unknown"

          icao_spoken = " ".join(list(icao_code))
          report = (
              f"METAR for {icao_spoken} at {observation_time} Zulu. : "
              f"Wind {wind_direction} degrees at {wind_speed} knots, gusts to {wind_gust} knots. : "  # Include gusts
              f"Visibility {visibility} meters. : "
              f"Altimeter {altimeter} hectopascals. : "
              f"Temperature {temperature} degrees Celsius, dewpoint {dewpoint} degrees Celsius." # Use Celsius
          )
          
          return report
      except Exception as e:
          self.logger.error(f"Error formatting METAR data: {e}")
          return "Error formatting METAR data"


    @command_cooldown(5)
    async def location_command(self, message: Message, *args):
        """Get location information from Little Navmap."""
        try:
            sim_info = await self.bot.littlenavmap.get_sim_info()
            if sim_info and sim_info.get('active'):
                lat = sim_info.get('position', {}).get('lat')
                lon = sim_info.get('position', {}).get('lon')

                if lat and lon:
                    location_info = (
                        f"Current Location:\n"
                        f"Latitude: {lat:.6f}\n"
                        f"Longitude: {lon:.6f}"
                    )
                    await message.channel.send(location_info)
                else:
                     await message.channel.send("Location data not available.")

            else:
                await message.channel.send("Flight simulator is not active.")
        except Exception as e:
            self.logger.error(f"Error retrieving or sending location: {e}", exc_info=True)
            await message.channel.send("Failed to retrieve location.")

    