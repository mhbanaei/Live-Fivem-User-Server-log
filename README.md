# FiveM Discord VIP & Alias Management Bot

A **Discord bot** for FiveM servers that provides:
- Player join/leave notifications in a Discord channel.
- VIP player management via slash commands.
- Alias system to assign custom names to players.
- Server reset detection to prevent ID conflicts.

---

## ✅ Features
- **Live Player Tracking**  
  Monitors players from FiveM `/players.json` endpoint every 10 seconds.
  
- **Alias System**  
  - Assign custom aliases to players using `/alias [player_id] [alias_name]`.
  - Automatically updates alias when player reconnects (even after server reset).
  - Stores aliases in `aliases.json`.

- **VIP Management**  
  - Add or remove players to VIP list using `/add` and `/remove`.
  - Persistent VIP data stored in `vip_players.json`.
  
- **Server Reset Detection**  
  - Detects when server IDs reset (start from `1`) and clears `saved_player_data.json` to prevent conflicts.

- **Discord Integration**  
  - Sends join/leave notifications with VIP status to a specific Discord channel.
  - All management via Discord slash commands.

---

## 📂 File Structure
```
/bot-directory/
│
├── saved_player_data.json   # Stores temporary session data (clears after reset)
├── vip_players.json         # Stores VIP players persistently
├── aliases.json             # Stores aliases persistently
├── main.py                  # Bot script
```

---

## 🔧 Configuration
1. **Set your bot token and server info** in the script:
   ```python
   TOKEN = "YOUR_DISCORD_BOT_TOKEN"
   SERVER_IP = "your-server-ip"
   SERVER_PORT = "your-server-port"
   CHANNEL_ID = 123456789012345678  # Your Discord channel ID
   ```

2. Make sure your FiveM server’s `/players.json` endpoint is accessible.

---

## 🚀 Installation
1. Install dependencies:
   ```
   pip install discord.py aiohttp
   ```
2. Run the bot:
   ```
   python main.py
   ```

---

## 🛠 Commands
### Slash Commands:
- `/players` – Show all online players (with VIP and alias info).
- `/add [player_id]` – Add a player to the VIP list.
- `/remove [player_id]` – Remove a player from the VIP list.
- `/vlist` – Show all VIP players with online status.
- `/alias [player_id] [alias_name]` – Set or remove an alias for a player.  
  - To remove an alias, leave `[alias_name]` empty.

### Normal Commands:
- `/start` – Start player status checks (if stopped).
- `/stop` – Stop player status checks.
- `/sync` – Sync Discord slash commands.

---

## ⚠️ Important Notes
- **Do not delete `vip_players.json` or `aliases.json`** unless you want to reset all data.
- `saved_player_data.json` will automatically reset when the server restarts and IDs start from `1`.
- Steam IDs are optional; this bot works with **server IDs** only.

---
