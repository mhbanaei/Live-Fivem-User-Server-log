# Live FiveM User Server Log Discord Bot

This Discord bot monitors a FiveM (or any game server providing a `players.json` endpoint) server and reports player joins and leaves to a specified Discord channel. It also provides a slash command to list currently online players.

## Features

*   **Discord Bot Integration:** Uses `discord.py` to connect to Discord.
*   **Player Monitoring:** Periodically fetches `players.json` from the game server (default: every 10 seconds).
*   **Join/Leave Notifications:** Sends embedded messages to a designated channel when players join or leave the server.
*   **Data Persistence:** Saves basic player info (name, SteamID) locally in `saved_player_data.json` to provide names for players who have left.
*   **Player List Command:** Includes a `/players` slash command to display a detailed list of online players (ID, Name, SteamID, Ping).
*   **Control Commands:** Basic text commands (`!start`, `!stop` - Note: prefix might be `/` depending on your `command_prefix` setting) to manage the monitoring task (though it starts automatically on bot ready).

## How to Use

### 1. Setup Your Environment

*   **Install Python:** Ensure you have Python 3.8 or newer installed.
*   **Install Dependencies:** Open your terminal or command prompt and run:
    ```bash
    pip install discord.py aiohttp
    ```

### 2. Configure the Bot

Open the Python script (`your_script_name.py`) and modify the following configuration variables at the top:

*   `TOKEN`: Replace `"Discord_Token"` with your actual Discord bot token.
    *   *How to get a bot token:* [Discord Developer Portal](https://discord.com/developers/applications)
*   `SERVER_IP`: Set this to the IP address of your game server.
*   `SERVER_PORT`: Set this to the port where the game server provides the `players.json` file (e.g., the FXServer web server port, often 30120).
*   `CHANNEL_ID`: Replace `1338616403057705023` with the numerical ID of the Discord channel where you want the join/leave messages to be sent.
    *   *How to get a channel ID:* Enable Developer Mode in Discord settings (User Settings > Advanced > Developer Mode), then right-click the channel and select "Copy Channel ID".

### 3. Run the Bot

Execute the script from your terminal:

```bash
python your_script_name.py
```

Replace `your_script_name.py` with the actual name of your Python file. The bot will log in and automatically start monitoring the server.

### 4. Using Commands in Discord

*   **List Players:** Type `/players` in any channel the bot has access to. It will display the list of currently online players.
*   **Start/Stop Monitoring (Optional):**
    *   `!start` (or `/start` if `command_prefix` is `/`): Manually starts the player checking task if it was stopped.
    *   `!stop` (or `/stop`): Manually stops the player checking task.

## Notes

*   The bot requires the `players.json` endpoint to be accessible from where the bot is running. Ensure your server's firewall allows connections to the specified IP and port.
*   The `saved_player_data.json` file is used to remember player names for the "leave" messages, as the `players.json` only contains currently online players.
*   Error handling is basic. Check the console output where the bot is running for potential errors (e.g., connection issues, invalid JSON).
