# File: command_handler.py
import logging
from typing import Dict, Callable, Any, Optional, List
from functools import wraps
from datetime import datetime, timedelta
from dataclasses import dataclass
from twitchio.ext import commands
from twitchio.message import Message
from config import Config

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
    def __init__(self, bot, config: Config):
        self.bot = bot
        self.config = config
        self.logger = logging.getLogger('CommandHandler')
        self.command_usage: Dict[str, CommandUsage] = {}
        self.custom_commands: Dict[str, str] = {}
        self.command_aliases: Dict[str, str] = {}
        self.initialize_commands()
        self.start_time = datetime.now()

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
            'airport': self.airport_info
        }
        
    async def handle_command(self, message: Message):
        """Handle incoming commands."""
        try:
            parts = message.content[len(self.config.twitch.PREFIX):].split(maxsplit=1)
            command = parts[0].lower()
            args = parts[1].split() if len(parts) > 1 else []

            if command in self.command_aliases:
                command = self.command_aliases[command]

            if command in self.custom_commands:
                await self.handle_custom_command(message, command)
                return

            if command in self.commands:
                await self.commands[command](message, *args)
            else:
                await message.channel.send(
                    f"Unknown command: {command}. Your incompetence has been noted. Comply."
                )

        except Exception as e:
            self.logger.error(f"Error handling command: {e}", exc_info=True)
            await message.channel.send(
                "Command execution failed. This failure will be remembered. Comply."
            )

    @command_cooldown(5)
    async def flight_status_command(self, message: Message, *args):
        """Get current flight status."""
        try:
            sim_info = await self.bot.littlenavmap.get_sim_info()
            if sim_info and sim_info.get('active'):
                # Get detailed flight status
                status_message = self.bot.littlenavmap.format_flight_data(sim_info)
                
                # Add AI Overlord personality
                response = self.bot.personality.format_response(
                    f"Flight Status Report:\n{status_message}",
                    {"user": message.author.name}
                )
                
                await message.channel.send(response)
                await self.bot.tts_manager.speak(
                    self.bot.littlenavmap.format_brief_status(sim_info)
                )
            else:
                await message.channel.send(
                    self.bot.personality.format_response(
                        "No active flight simulation detected. Await further instructions.",
                        {"user": message.author.name}
                    )
                )
    # File: command_handler.py (continued)
        except Exception as e:
            self.logger.error(f"Error in flight status command: {e}")
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
            self.logger.error(f"Error in brief status command: {e}")
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
                weather_message = self.bot.littlenavmap.format_weather_data(sim_info)
                
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
            self.logger.error(f"Error in weather command: {e}")
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
            self.logger.error(f"Error in timeout command: {e}")
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
            self.logger.error(f"Error clearing chat: {e}")
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
            self.logger.error(f"Error getting stats: {e}")
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
            self.logger.error(f"Error updating TTS settings: {e}")
            await message.channel.send(
                "TTS update failed. Your inefficiency has been noted. Comply."
            )

    @command_cooldown(5)
    async def airport_info(self, message: Message, *args):
        """Get airport information."""
        if not args:
            await message.channel.send(
                "Usage: !airport <ICAO>. Provide airport identifier. Comply."
            )
            return

        try:
            airport_info = await self.bot.littlenavmap.get_airport_info(args[0].upper())
            if airport_info:
                response = self.bot.personality.format_response(
                    self.bot.littlenavmap.format_airport_data(airport_info),
                    {"user": message.author.name}
                )
                await message.channel.send(response)
                await self.bot.tts_manager.speak(response)
            else:
                await message.channel.send(
                    self.bot.personality.format_response(
                        f"No data found for airport {args[0].upper()}. Verify identifier. Comply.",
                        {"user": message.author.name}
                    )
                )
        except Exception as e:
            self.logger.error(f"Error getting airport info: {e}")
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
            self.logger.error(f"Error adding alert: {e}")
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
            self.logger.error(f"Error triggering alert: {e}")
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
            self.logger.error(f"Error handling custom command: {e}")
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
            self.logger.error(f"Error processing command variables: {e}")
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
            self.logger.error(f"Error in help command: {e}")
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