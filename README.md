This project provides an AI-powered chatbot for Twitch streamers focused on flight simulation.  The bot integrates with Little Navmap, OpenAI's ChatGPT, text-to-speech (TTS) using Streamer.Bot, and a database for persistent storage.  It offers features like flight status updates, real-time weather information, AI-generated conversation, custom commands, alerts, and more, all presented with a distinct "AI Overlord" personality.

## Features

* **Flight Status Integration:**  Real-time flight data displayed in chat, including altitude, speed, heading, and flight phase (using Little Navmap).
* **AI Chat:**  Engages with viewers using OpenAI's ChatGPT, providing dynamic and contextual conversation.
* **Text-to-Speech (TTS):**  Uses Streamer.Bot for voice alerts and responses, enhancing the interactive experience.
* **Customizable Personality:**  The bot adopts an "AI Overlord" persona, issuing decrees, making sarcastic remarks, and engaging in playful banter.  This can be adjusted.
* **Custom Commands:**  Moderators can add, delete, and edit custom commands for unique interactions.
* **Alerts:**  Set up and trigger custom alerts for specific events or milestones.
* **METAR Integration:** Fetches and displays real-world weather data in METAR format (using CheckWX).
* **Database Persistence:**  Uses MongoDB to store conversation history, custom commands, user loyalty data, and alerts.
* **Command Cooldowns and Permissions:**  Prevent command spam and restrict certain commands to moderators or other user groups.

## Installation

**Clone the Repository:**

git clone https://github.com/Grab-your-parachutes/Twitch-ChatGpt4-LittleNavMap-integrated-chatbot.git


Set Up a Virtual Environment:

python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows


Install Dependencies:

pip install -r requirements.txt


Configuration:

Create a .env file: Copy the .env.example file to .env and fill in the required values:

TWITCH_OAUTH_TOKEN: Your Twitch OAuth token. Must begin with oauth:.

TWITCH_CHANNEL: Your Twitch channel name.

BOT_NAME: The bot's username on Twitch.

BROADCASTER_ID: Your Twitch broadcaster ID.

MONGO_URI: Your MongoDB connection URI.

MONGO_DB_NAME: The name of your MongoDB database.

CHATGPT_API_KEY: Your OpenAI API key.

STREAMERBOT_WS_URI: Your Streamer.Bot WebSocket URI. Must begin with ws://.

LITTLENAVMAP_URL: The URL of your Little Navmap instance (including port if necessary). Defaults to http://localhost:8965.

OPENWEATHERMAP_API_KEY: Your OpenWeatherMap API key.

CHECKWX_API_KEY: Your CheckWX API key.

Adjust Other Settings: You can customize the bot's personality, trigger words, commands, and other settings in the config.py and personality.py files.

Usage
Start Little Navmap: Ensure Little Navmap is running and its web server is enabled.

Start Streamer.Bot: Make sure Streamer.Bot is running and connected to your Twitch channel. Set up a Speaker.Bot action in Streamer.Bot to receive WebSocket commands on a specified port. Streamer.Bot will output the synthesised speech to your chosen audio device.

Run the Bot:

python main.py


The bot will connect to Twitch and begin listening for commands and mentions in your channel.

Commands
!status: Displays detailed current flight status information.

!brief: Provides a concise flight status summary.

!weather: Shows current weather conditions in the simulator.

!metar <ICAO_CODE>: Retrieves and displays real-world weather data in METAR format for the specified ICAO code.

!airport <ICAO>: Gets information about an airport.

!location: Show's the aircrafts latitude and longitude.

!stats: Displays bot statistics and uptime.

!help: Shows the list of available commands.

!addcom (mod only): Adds a custom command.

!delcom (mod only): Deletes a custom command.

!editcom (mod only): Edits a custom command.

!alias (mod only): Creates an alias for an existing command.

!timeout <username> <duration> (mod only): Times out a user in chat.

!clearchat (mod only): Clears the chat.

!addalert (mod only): Adds a custom alert.

!alert: Triggers a saved alert.

!say: Makes the bot say a message.

!settitle (mod only): Sets the stream title (not yet implemented).

!setgame (mod only): Sets the stream game/category (not yet implemented).

This project will be in active development, there are files and functions present that are not yet fully integrated.

Contributing

Contributions are welcome! Feel free to open issues or submit pull requests.

License

This project is licensed under the MIT License.
