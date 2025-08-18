import discord
from discord.ext import commands, tasks
import aiohttp
import json
import os
from datetime import datetime

TOKEN = "Discord_Token"
SERVER_IP = "SERVER_IP"
SERVER_PORT = "SERVER_PORT"
CHANNEL_ID = 1406392294164267222

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

# متغیرهای جهانی
previous_players = set()
current_online_names = {}  # {نام نرمال‌شده: (نام اصلی, ID)}
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
vip_players = load_vip_list()  # {نام نرمال‌شده: {"name": نام اصلی, "last_id": آخرین ID}}

def chunk_list(lst, chunk_size):
    return [lst[i:i+chunk_size] for i in range(0, len(lst), chunk_size)]

async def send_embeds_to_channel(embeds):
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        for embed in embeds:
            await channel.send(embed=embed)

def detect_server_reset(current_ids):
    """تشخیص ریست سرور با شرایط مشخص"""
    # اگر سرور خالی بود و بازیکنان جدید از 1 شروع شدند
    if not previous_players and current_ids == {"1"}:
        return True
        
    try:
        # تبدیل IDها به اعداد صحیح
        current_ids_int = [int(id) for id in current_ids if id.isdigit()]
        previous_ids_int = [int(id) for id in previous_players if id.isdigit()]
        
        # اگر لیست IDها خالی باشد
        if not current_ids_int or not previous_ids_int:
            return False
            
        # اگر بیشترین ID فعلی کوچک باشد و قبلاً IDهای بزرگ داشتیم
        if (max(current_ids_int) < 10 and 
            previous_players and 
            max(previous_ids_int) > 50):
            return True
    except:
        pass
        
    return False

def normalize_name(name):
    """نرمال‌سازی نام برای مقایسه یکسان"""
    return name.strip().lower()

@bot.event
async def on_ready():
    global vip_players
    print(f"Bot be onvan {bot.user} vared Discord shod!")
    
    # ذخیره لیست VIP به فرمت جدید
    save_vip_list(vip_players)
    
    await bot.tree.sync()
    print("Dastoorate slash be roozrasi shodand!")
    check_players.start()

@tasks.loop(seconds=10)
async def check_players():
    global previous_players, saved_player_data, vip_players, current_online_names
    
    # پاک‌سازی لیست بازیکنان آنلاین برای پر کردن مجدد
    current_online_names.clear()
    
    url = f"http://{SERVER_IP}:{SERVER_PORT}/players.json"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=20) as response:
                if response.status == 200:
                    content = await response.text()
                    players = json.loads(content)
                    
                    current_players = {str(player['id']): player for player in players}
                    current_player_ids = set(current_players.keys())
                    
                    # تشخیص ریست سرور
                    if detect_server_reset(current_player_ids):
                        print("Server reset shod! Pak kardane saved_player_data")
                        saved_player_data = {}
                        # ذخیره فایل خالی
                        save_player_data(saved_player_data)
                    
                    channel = bot.get_channel(CHANNEL_ID)
                    
                    # جمع‌آوری نام‌های آنلاین و به‌روزرسانی ID
                    for player in players:
                        player_id = str(player['id'])
                        player_name = player['name']
                        normalized_name = normalize_name(player_name)
                        
                        # ذخیره نام اصلی و ID فعلی
                        current_online_names[normalized_name] = (player_name, player_id)
                        
                        # به‌روزرسانی ID در لیست VIP
                        if normalized_name in vip_players:
                            vip_players[normalized_name]["last_id"] = player_id
                    
                    # پردازش بازیکنان جدید
                    new_ids = current_player_ids - previous_players
                    if new_ids:
                        for pid in new_ids:
                            player = current_players[pid]
                            player_name = player['name']
                            normalized_name = normalize_name(player_name)
                            
                            # بررسی وضعیت VIP بودن بر اساس نام
                            is_vip = normalized_name in vip_players
                            
                            # رنگ‌بندی: VIP سبز، غیر VIP آبی
                            color = discord.Color.green() if is_vip else discord.Color.blue()
                            
                            status = "VIP Join" if is_vip else "Join"
                            embed = discord.Embed(
                                description=(f"**Status:** {status}\n"
                                             f"**Name:** {player_name}\n"
                                             f"**ID:** {pid}"),
                                color=color,
                            )
                            if channel:
                                await channel.send(embed=embed)
                    
                    # پردازش بازیکنان خارج شده
                    left_ids = previous_players - current_player_ids
                    if left_ids:
                        for pid in left_ids:
                            player_data = saved_player_data.get(pid, {})
                            player_name = player_data.get('name', 'Name not found')
                            normalized_name = normalize_name(player_name)
                            
                            # بررسی وضعیت VIP بودن بر اساس نام
                            is_vip = normalized_name in vip_players
                            
                            # رنگ‌بندی: VIP قرمز، غیر VIP نارنجی
                            color = discord.Color.red() if is_vip else discord.Color.orange()
                            
                            status = "VIP Leave" if is_vip else "Leave"
                            embed = discord.Embed(
                                description=(f"**Status:** {status}\n"
                                             f"**Name:** {player_name}\n"
                                             f"**ID:** {pid}"),
                                color=color,
                            )
                            if channel:
                                await channel.send(embed=embed)
                    
                    previous_players = current_player_ids
                    
                    # به‌روزرسانی اطلاعات بازیکنان
                    for player in players:
                        pid = str(player['id'])
                        player_name = player['name']
                        
                        # ذخیره اطلاعات بدون وابستگی به شناسه‌ها
                        saved_player_data[pid] = {
                            "name": player_name,
                            "last_seen": datetime.now().isoformat()
                        }
                    
                    save_player_data(saved_player_data)
                    save_vip_list(vip_players)  # ذخیره IDهای به‌روزرسانی شده
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
                            color=discord.Color.blue()
                        )
                        for player in chunk:
                            player_id = str(player['id'])
                            player_name = player['name']
                            ping = player.get('ping', 'No ping data')
                            normalized_name = normalize_name(player_name)
                            
                            # بررسی وضعیت VIP بودن بر اساس نام
                            is_vip = normalized_name in vip_players
                            display_name = f"🌟 {player_name}" if is_vip else player_name
                            
                            embed.add_field(
                                name=f"{player_id} - {display_name}",
                                value=f"**Ping:** {ping} ms\n**Status:** Online",
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
    
    # یافتن اطلاعات بازیکن
    player_data = saved_player_data.get(player_id)
    if not player_data:
        await interaction.response.send_message(
            f"Player ba ID `{player_id}` peyda nashod. Motmaen shavid dar server online ast.",
            ephemeral=True
        )
        return
    
    player_name = player_data.get('name', 'Unknown')
    normalized_name = normalize_name(player_name)
    
    # بررسی وجود قبلی در لیست VIP
    if normalized_name in vip_players:
        # به‌روزرسانی ID
        vip_players[normalized_name]["last_id"] = player_id
        save_vip_list(vip_players)
        await interaction.response.send_message(
            f"ID baraye VIP **{player_name}** be `{player_id}` be‌روز shod!",
            ephemeral=True
        )
        return
    
    # افزودن به لیست VIP
    vip_players[normalized_name] = {
        "name": player_name,
        "last_id": player_id,
        "added_at": datetime.now().isoformat()
    }
    save_vip_list(vip_players)
    
    # بررسی وضعیت آنلاین
    is_online = normalized_name in current_online_names
    status = "Online" if is_online else "Offline"
    
    await interaction.response.send_message(
        f"Player **{player_name}** (ID: `{player_id}`) be list VIP ezafe shod!\n"
        f"Status: {status}",
        ephemeral=True
    )

@bot.tree.command(name="remove", description="Hazf kardan Player az list VIP")
async def remove_vip(interaction: discord.Interaction, player_name: str):
    global vip_players
    
    # نرمال‌سازی نام
    normalized_name = normalize_name(player_name)
    
    # حذف از لیست VIP
    if normalized_name in vip_players:
        player_data = vip_players[normalized_name]
        del vip_players[normalized_name]
        save_vip_list(vip_players)
        await interaction.response.send_message(
            f"Player **{player_data['name']}** az list VIP hazf shod!",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"Player ba name `{player_name}` dar list VIP peyda nashod!",
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
    
    for normalized_name, data in vip_players.items():
        player_name = data.get('name', 'Name not found')
        player_id = data.get('last_id', 'ID not found')
        added_at = data.get('added_at', 'N/A')
        
        # بررسی وضعیت آنلاین
        is_online = normalized_name in current_online_names
        online_status = "🟢 Online" if is_online else "🔴 Offline"
        
        embed.add_field(
            name=f"{player_name} (ID: {player_id})",
            value=f"**Status:** {online_status}\n**Added:** {added_at[:10]}",
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

# دستور برای همگام‌سازی دستورات اسلش
@bot.command()
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("Dastoorat sync shodand!")

bot.run(TOKEN)