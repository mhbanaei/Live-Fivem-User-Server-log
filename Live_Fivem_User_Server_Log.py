import discord
from discord.ext import commands, tasks
import aiohttp
import json
import os
from datetime import datetime

# Tanzimat asli
TOKEN = "Discord_Token"  # Token bot
SERVER_IP = "Server_ip"           # IP server
SERVER_PORT = "Server_port"              # Port server
CHANNEL_ID = 1338616403057705023    # Shenase Channel baraye ersale payamhaye khodkar

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

# Motaghayer haye sarsari baraye negahdari vaziyat Player va zakhire sazi etelaat
previous_players = set()
saved_player_data_file = "saved_player_data.json"

def load_saved_player_data():
    if os.path.exists(saved_player_data_file):
        if os.stat(saved_player_data_file).st_size == 0:
            return {}
        with open(saved_player_data_file, "r", encoding="utf-8") as file:
            return json.load(file)
    return {}

def save_player_data(data):
    with open(saved_player_data_file, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

saved_player_data = load_saved_player_data()

def chunk_list(lst, chunk_size):
    """List vorudi ra be bakhsh haye kuchaktar ba andaze moshakhas taghsim mikonad"""
    return [lst[i:i+chunk_size] for i in range(0, len(lst), chunk_size)]

async def send_embeds_to_channel(embeds):
    """Ersale yek list Embed be Channel ta'yin shode"""
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        for embed in embeds:
            await channel.send(embed=embed)
    else:
        print("Channel mored nazar peyda nashod!")

@bot.event
async def on_ready():
    print(f"Bot be onvan {bot.user} vared Discord shod!")
    # Hamagamsazi global (bedune ta'yin guild)
    await bot.tree.sync()
    print("Dastoorate slash be roozrasi shodand!")
    check_players.start()  # Shorou' barrasi vaziyat Player

@tasks.loop(seconds=10)
async def check_players():
    global previous_players, saved_player_data
    url = f"http://{SERVER_IP}:{SERVER_PORT}/players.json"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=20) as response:
                if response.status == 200:
                    content = await response.text()
                    players = json.loads(content)
                    
                    # Sakht dictionary az Player-e fa'ali (kelidha be shekle reshte)
                    current_players = {str(player['id']): player for player in players}
                    current_player_ids = set(current_players.keys())
                    
                    # Daryafte Channel mored nazar baraye ersale e'lanha
                    channel = bot.get_channel(CHANNEL_ID)
                    if not channel:
                        print("Channel mored nazar peyda nashod!")
                    
                    # Tashkhise Player jadid (vorud)
                    new_ids = current_player_ids - previous_players
                    if new_ids:
                        for pid in new_ids:
                            player = current_players[pid]
                            embed = discord.Embed(
                                title="Player vard shod",
                                description=(
                                    f"**Name:** {player['name']}\n"
                                    f"**ID:** {pid}\n"
                                    f"**SteamID:** {player.get('identifiers', ['Name not found'])[0]}"
                                ),
                                color=discord.Color.green(),
                            )
                            if channel:
                                await channel.send(embed=embed)
                            else:
                                print(f"Player joined: {player['name']} (ID: {pid})")
                    
                    # Tashkhise Playerani ke kharej shodeand (khorooj)
                    left_ids = previous_players - current_player_ids
                    if left_ids:
                        for pid in left_ids:
                            name = saved_player_data.get(pid, {}).get('name', 'Name not found')
                            embed = discord.Embed(
                                title="Player kharej shod",
                                description=(
                                    f"**Name:** {name}\n"
                                    f"**ID:** {pid}"
                                ),
                                color=discord.Color.red(),
                                timestamp=datetime.utcnow()
                            )
                            if channel:
                                await channel.send(embed=embed)
                            else:
                                print(f"Player left: {name} (ID: {pid})")
                    
                    # Update set Player ghabli baraye tekrar badi
                    previous_players = current_player_ids
                    
                    # Update etelaat zakhire shode Player
                    for player in players:
                        pid = str(player['id'])
                        if pid not in saved_player_data:
                            saved_player_data[pid] = {
                                "name": player['name'],
                                "steamid": player.get('identifiers', ['Name not found'])[0]
                            }
                    
                    # Agar tanha Player online, Player ba ID 1 bashad, baghie etelaat pak shavad
                    if current_player_ids == {"1"}:
                        saved_player_data = {k: v for k, v in saved_player_data.items() if k == "1"}
                    
                    save_player_data(saved_player_data)
                else:
                    print("Server Error, Please Check Database")
    except Exception as e:
        print("Error dar daryaft etelaat Player:", e)

@bot.tree.command(name="players", description="Namayesh list Player online server")
async def players(interaction: discord.Interaction):
    url = f"http://{SERVER_IP}:{SERVER_PORT}/players.json"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    content = await response.text()
                    players_data = json.loads(content)
                    if not players_data:
                        await interaction.response.send_message("Hich Playeri online nist.")
                        return
                    total_players = len(players_data)  # Tarif total_players be onvan tedade kol Player
                    embeds = []
                    for i, chunk in enumerate(chunk_list(players_data, 25)):
                        embed = discord.Embed(
                            title=f"List Player online (Ghesmat {i+1}) - {total_players} Player", 
                            color=discord.Color.yellow()
                        )
                        for player in chunk:
                            steamid = player.get('identifiers', ['Name not found'])[0]
                            player_id = player['id']
                            player_name = player['name']
                            ping = player.get('ping', 'Name not found')
                            embed.add_field(name=f"{player_id} - {player_name}",
                                            value=f"SteamID: {steamid}\nPing: {ping} ms", inline=False)
                        embeds.append(embed)
                    await interaction.response.send_message(embed=embeds[0])
                    for embed in embeds[1:]:
                        await interaction.followup.send(embed=embed)
                else:
                    await interaction.response.send_message("Error dar daryaft etelaat server!")
    except Exception as e:
        await interaction.response.send_message(f"Error dar ersale darkhast: {e}")

@bot.command()
async def start(ctx):
    if not check_players.is_running():
        check_players.start()
        await ctx.send("Bot shorou' be barrasi vaziyat Player kard!")
    else:
        await ctx.send("Bot dar hal hazer dar hale barrasi vaziyat Player ast.")

@bot.command()
async def stop(ctx):
    if check_players.is_running():
        check_players.stop()
        await ctx.send("Barrasi vaziyat Player motavaqef shod.")
    else:
        await ctx.send("Bot dar hal hazer dar hale barrasi vaziyat Player nist.")

bot.run(TOKEN)
