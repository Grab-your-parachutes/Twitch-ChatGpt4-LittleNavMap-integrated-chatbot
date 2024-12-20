# File: generate_streamerbot_commands.py
import json

def generate_streamerbot_commands(commands, websocket_url):
    """Generates Streamer.bot commands from a list of voice commands."""
    output_commands = []
    for voice_phrase, bot_command in commands.items():
        if "{phrase:" in bot_command:
            match_type = "startsWith"
        else:
            match_type = "contains"
        
        output_commands.append({
            "voice_phrase": voice_phrase,
            "match_type": match_type,
            "websocket_url": websocket_url,
            "bot_command": bot_command
        })
    return output_commands

if __name__ == "__main__":
    voice_commands = {
        "Hey Overlord, what's the status?": "!status",
        "Hey Overlord, give me a brief status.": "!brief",
        "Hey Overlord, what's the weather?": "!weather",
        "Hey Overlord, airport info for ": "!airport {phrase:1}",
        "Hey Overlord, set the title to ": "!settitle {phrase:1}",
        "Hey Overlord, set the game to ": "!setgame {phrase:1}",
        "Hey Overlord, timeout ": "!timeout {phrase:1} {phrase:2}",
        "Hey Overlord, clear the chat": "!clearchat",
        "Hey Overlord, add alert ": "!addalert {phrase:1} {phrase:2}",
        "Hey Overlord, set voice to ": "!tts voice {phrase:1}",
        "Hey Overlord, set speed to ": "!tts speed {phrase:1}",
        "Hey Overlord, set volume to ": "!tts volume {phrase:1}",
        "Hey Overlord, what are the stats?": "!stats",
        "Hey Overlord, trigger alert ": "!alert {phrase:1}",
        "Hey Overlord, say ": "!say {phrase:1}",
        "Hey Overlord, help": "!help",
        "Hey Overlord, help with ": "!help {phrase:1}",
        "Hey Overlord, add command ": "!addcom {phrase:1} {phrase:2}",
        "Hey Overlord, delete command ": "!delcom {phrase:1}",
        "Hey Overlord, edit command ": "!editcom {phrase:1} {phrase:2}",
        "Hey Overlord, add alias ": "!alias {phrase:1} {phrase:2}"
    }
    
    websocket_url = "ws://localhost:7580"  # Replace with your bot's WebSocket URL
    output = generate_streamerbot_commands(voice_commands, websocket_url)
    
    print("Streamer.bot commands:")
    for command in output:
        print(f"  Voice Phrase: {command['voice_phrase']}")
        print(f"  Match Type: {command['match_type']}")
        print(f"  WebSocket URL: {command['websocket_url']}")
        print(f"  Bot Command: {command['bot_command']}")
        print("-" * 20)