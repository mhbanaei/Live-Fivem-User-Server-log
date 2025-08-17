import discord
from discord.ext import commands, tasks
import aiohttp
import json
import os
from datetime import datetime

TOKEN = "Discord_Token"
SERVER_IP = "Server_IP"
SERVER_PORT = "Server_Port"
CHANNEL_ID = 1406392294164267222

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

previous_players = set()
saved_player_data_file = "saved_player_data.json"
vip_list_file = "vip_players.json"

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

def load_vip_list():
    if os.path.exists(vip_list_file):
        if os.stat(vip_list_file).st_size == 0:
            return {}
        with open(vip_list_file, "r", encoding="utf-8") as file:
            return json.load(file)
    return {}

def save_vip_list(data):
    with open(vip_list_file, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

saved_player_data = load_saved_player_data()
vip_players = load_vip_list()

def chunk_list(lst, chunk_size):
    return [lst[i:i+chunk_size] for i in range(0, len(lst), chunk_size)]

async def send_embeds_to_channel(embeds):
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        for embed in embeds:
            await channel.send(embed=embed)

@bot.event
async def on_ready():
    print(f"Bot be onvan {bot.user} vared Discord shod!")
    await bot.tree.sync()
    print("Dastoorate slash be roozrasi shodand!")
    check_players.start()

@tasks.loop(seconds=10)
async def check_players():
    global previous_players, saved_player_data, vip_players
    url = f"http://{SERVER_IP}:{SERVER_PORT}/players.json"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=20) as response:
                if response.status == 200:
                    content = await response.text()
                    players = json.loads(content)
                    
                    current_players = {str(player['id']): player for player in players}
                    current_player_ids = set(current_players.keys())
                    
                    channel = bot.get_channel(CHANNEL_ID)
                    
                    # Process joins
                    new_ids = current_player_ids - previous_players
                    if new_ids:
                        for pid in new_ids:
                            player = current_players[pid]
                            identifiers = player.get('identifiers', [])
                            
                            # Extract SteamID
                            steamid = next((id.split(':')[1] for id in identifiers if id.startswith('steam:')), None)
                            
                            # Check VIP status by Player ID
                            is_vip = pid in vip_players
                            color = discord.Color.gold() if is_vip else discord.Color.green()

                            embed = discord.Embed(
                                description=(f"**Name:** {player['name']}\n"
                                             f"**ID:** {pid}"),
                                color=color,
                            )
                            if channel:
                                await channel.send(embed=embed)
                    
                    # Process leaves
                    left_ids = previous_players - current_player_ids
                    if left_ids:
                        for pid in left_ids:
                            player_data = saved_player_data.get(pid, {})
                            name = player_data.get('name', 'Name not found')
                            
                            # Check VIP status by Player ID
                            is_vip = pid in vip_players
                            color = discord.Color.gold() if is_vip else discord.Color.red()

                            embed = discord.Embed(
                                description=(f"**Name:** {name}\n"
                                             f"**ID:** {pid}"),
                                color=color,
                            )
                            if channel:
                                await channel.send(embed=embed)
                    
                    previous_players = current_player_ids
                    
                    # Update player data
                    for player in players:
                        pid = str(player['id'])
                        identifiers = player.get('identifiers', [])
                        
                        # Extract SteamID
                        steamid = next((id.split(':')[1] for id in identifiers if id.startswith('steam:')), None)
                        
                        if pid not in saved_player_data:
                            saved_player_data[pid] = {
                                "name": player['name'],
                                "steamid": steamid
                            }
                        else:
                            # Update SteamID if available
                            if steamid:
                                saved_player_data[pid]['steamid'] = steamid
                    
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
                    total_players = len(players_data)
                    embeds = []
                    for i, chunk in enumerate(chunk_list(players_data, 25)):
                        embed = discord.Embed(
                            title=f"List Player online (Ghesmat {i+1}) - {total_players} Player", 
                            color=discord.Color.yellow()
                        )
                        for player in chunk:
                            player_id = str(player['id'])
                            player_name = player['name']
                            ping = player.get('ping', 'No ping data')
                            
                            # Check VIP status by Player ID
                            is_vip = player_id in vip_players
                            display_name = f"🌟 {player_name}" if is_vip else player_name

                            embed.add_field(
                                name=f"{player_id} - {display_name}",
                                value=f"Ping: {ping} ms",
                                inline=False
                            )
                        embeds.append(embed)

                    await interaction.response.send_message(embed=embeds[0])
                    for embed in embeds[1:]:
                        await interaction.followup.send(embed=embed)
                else:
                    await interaction.response.send_message("Error dar daryaft etelaat server!")
    except Exception as e:
        await interaction.response.send_message(f"Error dar ersale darkhast: {e}")

@bot.tree.command(name="add", description="Ezafe kardan Player be list VIP")
async def add_vip(interaction: discord.Interaction, player_id: str):
    global vip_players
    
    # Find player data
    player_data = saved_player_data.get(player_id)
    if not player_data:
        await interaction.response.send_message(
            f"Player ba ID `{player_id}` peyda nashod. Motmaen shavid dar server online ast.",
            ephemeral=True
        )
        return
    
    steamid = player_data.get('steamid', '')
    
    # Check if already VIP
    if player_id in vip_players:
        await interaction.response.send_message(
            f"Player **{player_data['name']}** ghablan dar list VIP bood!",
            ephemeral=True
        )
        return
    
    # Add to VIP list
    vip_players[player_id] = {
        "name": player_data['name'],
        "steamid": steamid,
        "added_at": datetime.now().isoformat()
    }
    
    save_vip_list(vip_players)
    await interaction.response.send_message(
        f"Player **{player_data['name']}** (ID: `{player_id}`) be list VIP ezafe shod!",
        ephemeral=True
    )

@bot.tree.command(name="remove", description="Hazf kardan Player az list VIP")
async def remove_vip(interaction: discord.Interaction, player_id: str):
    global vip_players
    
    # Check if player is in VIP list
    if player_id in vip_players:
        player_name = vip_players[player_id].get('name', 'Nashnakhte')
        del vip_players[player_id]
        save_vip_list(vip_players)
        await interaction.response.send_message(
            f"Player **{player_name}** (ID: `{player_id}`) az list VIP hazf shod!",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"Player ba ID `{player_id}` dar list VIP peyda nashod!",
            ephemeral=True
        )

@bot.tree.command(name="vlist", description="Namayesh list VIP haye server")
async def vip_list(interaction: discord.Interaction):
    if not vip_players:
        await interaction.response.send_message("Hich Playeri dar list VIP nist!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="List VIP haye server",
        color=discord.Color.gold()
    )
    
    for player_id, data in vip_players.items():
        player_name = data.get('name', 'Name not found')
        steamid = data.get('steamid', 'No SteamID')
        added_at = data.get('added_at', 'N/A')
        
        embed.add_field(
            name=f"🟢 {player_name} (ID: {player_id})",
            value=f"**SteamID:** {steamid}\n**Added:** {added_at[:10]}",
            inline=False
        )
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

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

# Command for syncing slash commands
@bot.command()
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("Dastoorat sync shodand!")

bot.run(TOKEN)