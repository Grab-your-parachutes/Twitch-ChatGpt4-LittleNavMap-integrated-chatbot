# Twitch AI Overlord Bot

This is a feature-rich Twitch bot designed to manage a flight simulation channel with an AI Overlord personality. It integrates with LittleNavmap for flight data, uses OpenAI for chat responses, and **Streamer.bot with Speaker.bot for TTS**.

## Features

*   **AI Overlord Personality:**
    *   Defined personality with traits, speech patterns, interests, and quirks.
    *   Manages user loyalty levels with titles and perks.
    *   Issues random decrees in chat.
*   **LittleNavmap Integration:**
    *   Fetches real-time flight simulation data (altitude, speed, heading, position, wind, etc.).
    *   Provides formatted flight status, weather, and airport information.
*   **Command Handling:**
    *   Robust command system with cooldowns and permissions.
    *   Supports custom commands and aliases.
    *   Includes commands for flight data, stream management, TTS, and more.
*   **Chat Management:**
    *   Filters spam and repeated messages.
    *   Handles bot mentions and responds using OpenAI.
    *   Tracks chat metrics and user activity.
*   **Text-to-Speech (TTS):**
    *   Uses **Streamer.bot with Speaker.bot** for TTS output.
    *   Allows users to adjust voice, speed, and volume.
*   **Database Integration:**
    *   Uses MongoDB to store conversation history, user data, alerts, and flight data.
    *   Performs periodic backups and metrics updates.
*   **Configuration:**
    *   Loads configuration from environment variables or a YAML file.
    *   Includes validation for configuration values.
*   **Logging:**
    *   Comprehensive logging system for debugging and monitoring.
*   **Error Handling:**
    *   Graceful error handling throughout the application.
*   **Asynchronous Operations:**
    *   Uses `asyncio` for concurrent operations.
*   **Sentry Integration:**
    *   Optional integration with Sentry for error tracking.
*   **Message Splitting:**
    *   Automatically splits long messages into multiple parts to avoid Twitch character limits.

## Setup

### Prerequisites

*   Python 3.10 or higher
*   MongoDB
*   **Streamer.bot with Speaker.bot**
*   LittleNavmap
*   Twitch Account
*   OpenAI API Key

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```
2.  **Create a virtual environment:**
    ```bash
    python -m venv .venv
    ```
3.  **Activate the virtual environment:**
    *   **Windows:**
        ```bash
        .venv\Scripts\activate
        ```
    *   **macOS/Linux:**
        ```bash
        source .venv/bin/activate
        ```
4.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
5.  **Configure environment variables:**
    *   Create a `.env` file in the root directory based on `.example.env.txt`.
    *   Fill in the required values for Twitch, OpenAI, **Streamer.bot**, MongoDB, etc.
    *   Alternatively, you can set the environment variables directly in your system.
    *   You can also use a `config.yaml` file by setting the `CONFIG_FILE` environment variable.
6.  **Set up MongoDB:**
    *   Ensure MongoDB is running and accessible.
    *   Create a database with the name specified in your `.env` file (`MONGO_DB_NAME`).
7.  **Set up Streamer.bot:**
    *   Ensure Streamer.bot is running and accessible.
    *   Configure the WebSocket URI in your `.env` file (`STREAMERBOT_WS_URI`).
    *   **Note:** This bot uses **Speaker.bot** for TTS, which is a plugin for Streamer.bot.
8.  **Set up LittleNavmap:**
    *   Ensure LittleNavmap is running and accessible.
    *   Configure the base URL in your `.env` file (`LITTLENAVMAP_URL`).
9.  **Set up Sentry (Optional):**
    *   Create a Sentry project and obtain the DSN.
    *   Set the `SENTRY_DSN` environment variable.

### Running the Bot

1.  **Activate the virtual environment (if not already active):**
    ```bash
    .venv\Scripts\activate  # Windows
    source .venv/bin/activate # macOS/Linux
    ```
2.  **Run the bot:**
    ```bash
    python main.py
    ```

### Testing

1.  **Run tests:**
    ```bash
    pytest
    ```

## Bot Commands

### Flight Information

*   `!status` or `!flightstatus`: Get detailed flight status.
*   `!brief`: Get a brief flight status update.
*   `!weather`: Get current weather information.
*   `!airport <ICAO>`: Get airport information.

### Stream Management (Moderator Only)

*   `!settitle <title>`: Set stream title.
*   `!setgame <game>`: Set stream game/category.
*   `!timeout <username> <duration_in_seconds>`: Timeout a user.
*   `!clearchat`: Clear chat messages.
*   `!addalert <name> <message>`: Add a custom alert.

### Text-to-Speech (TTS)

*   `!tts [voice|speed|volume] [value]`: Update TTS settings.

### Bot Utility

*   `!stats`: Get bot and command statistics.
*   `!alert <name>`: Trigger a saved alert.
*   `!say <message>`: Make the bot say something.
*   `!help` or `!help <command>`: Display help information.
*   `!addcom <command> <response>`: Add a custom command (Moderator Only).
*   `!delcom <command>`: Delete a custom command (Moderator Only).
*   `!editcom <command> <new response>`: Edit a custom command (Moderator Only).
*   `!alias <new command> <existing command>`: Add a command alias (Moderator Only).

## Configuration

The bot can be configured using environment variables or a `config.yaml` file. The following settings are available:

*   **Twitch:**
    *   `TWITCH_OAUTH_TOKEN`: Twitch OAuth token.
    *   `TWITCH_CHANNEL`: Twitch channel name.
    *   `BOT_NAME`: Bot's Twitch username.
    *   `BROADCASTER_ID`: Twitch broadcaster ID.
    *   `BOT_PREFIX`: Command prefix (default: `!`).
*   **Database:**
    *   `MONGO_URI`: MongoDB connection URI.
    *   `MONGO_DB_NAME`: MongoDB database name.
*   **OpenAI:**
    *   `CHATGPT_API_KEY`: OpenAI API key.
    *   `OPENAI_MODEL`: OpenAI model (default: `gpt-4`).
    *   `OPENAI_MAX_TOKENS`: Maximum tokens for OpenAI responses.
    *   `OPENAI_TEMPERATURE`: Temperature for OpenAI responses.
*   **Voice:**
    *   `VOICE_ENABLED`: Enable voice commands (default: `True`).
    *   `VOICE_PREFIX`: Voice command prefix (default: `Hey Overlord`).
    *   `VOICE_COMMAND_TIMEOUT`: Voice command timeout.
    *   `VOICE_COMMAND_PHRASE_LIMIT`: Voice command phrase limit.
    *   `VOICE_COMMAND_LANGUAGE`: Voice command language (default: `en-US`).
*   **Streamer.bot:**
    *   `STREAMERBOT_WS_URI`: Streamer.bot WebSocket URI.
*   **LittleNavmap:**
    *   `LITTLENAVMAP_URL`: LittleNavmap API base URL.
*   **Bot:**
    *   `BOT_TRIGGER_WORDS`: Comma-separated list of words that trigger the bot.
    *   `BOT_PERSONALITY`: Bot's personality description.
    *   `VERBOSE`: Enable verbose logging (default: `False`).
    *   `CONFIG_FILE`: Path to a YAML configuration file (optional).
    *   `SENTRY_DSN`: Sentry DSN for error tracking (optional).

## Contributing

Contributions are welcome! Please follow these steps:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Make your changes and commit them with clear messages.
4.  Push your branch to your fork.
5.  Submit a pull request.

## License

This project is licensed under the [MIT License] 
Copyright <2024> <Matthew Cummins>

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE..

## Contact

If you have any questions or suggestions, feel free to contact me at xbard at protonmail.com.