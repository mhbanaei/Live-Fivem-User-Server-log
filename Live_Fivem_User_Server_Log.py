import discord
from discord.ext import commands, tasks
import aiohttp
import json
import os
from datetime import datetime

# ====== تنظیمات ======
TOKEN = "Discord_token"
SERVER_IP = "SERVER_IP"
SERVER_PORT = "SERVER_PORT"
CHANNEL_ID = 1406392294164267222

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

# فایل‌ها
saved_player_data_file = "saved_player_data.json"
vip_list_file = "vip_players.json"
alias_list_file = "aliases.json"

# متغیرهای در حال اجرا
previous_players = set()
current_online_players = {}
max_seen_id = 0  # بیشترین ID مشاهده شده

# ---------- توابع کمکی برای فایل ----------
def load_json_file(path, default=None):
    if default is None:
        default = {}
    if os.path.exists(path):
        if os.stat(path).st_size == 0:
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return default
    return default

def save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# بارگذاری اولیه
saved_player_data = load_json_file(saved_player_data_file)
vip_players = load_json_file(vip_list_file)
aliases = load_json_file(alias_list_file)

# بارگذاری بیشترین ID مشاهده شده از فایل
max_seen_id_file = "max_seen_id.txt"
if os.path.exists(max_seen_id_file):
    try:
        with open(max_seen_id_file, "r") as f:
            max_seen_id = int(f.read().strip())
    except:
        max_seen_id = 0

# ---------- توابع کمکی ----------
def chunk_list(lst, chunk_size):
    return [lst[i:i+chunk_size] for i in range(0, len(lst), chunk_size)]

def detect_server_reset(current_ids):
    """تشخیص ریست سرور بر اساس بیشترین ID مشاهده شده"""
    global max_seen_id
    
    if not current_ids:
        return False
        
    try:
        # تبدیل IDهای فعلی به اعداد
        curr_ids = [int(pid) for pid in current_ids if pid.isdigit()]
        
        if not curr_ids:
            return False
            
        curr_max = max(curr_ids)
        
        # اگر ID=1 وجود دارد و قبلاً IDهای بالا دیده‌ایم
        if '1' in current_ids and max_seen_id > 20 and curr_max < 10:
            return True
            
    except Exception as e:
        print(f"Error in detect_server_reset: {e}")
        
    return False

def get_steam_name(player_data):
    """استخراج Steam Name از اطلاعات بازیکن"""
    identifiers = player_data.get('identifiers', [])
    steam_id = next((i.split(':', 1)[1] for i in identifiers if i.startswith('steam:')), None)
    return steam_id or player_data.get('name', 'Unknown')

def get_player_display_name(steam_name):
    """نام نمایشی بر اساس Alias و Steam Name"""
    # جستجو براساس steam_name در aliases
    for alias_data in aliases.values():
        if isinstance(alias_data, dict) and alias_data.get("steam_name") == steam_name and alias_data.get("alias"):
            return alias_data["alias"]
    
    # در نهایت نام واقعی
    return steam_name

def get_vip_status(steam_name):
    """بررسی وضعیت VIP بودن بر اساس Steam Name"""
    for vip_data in vip_players.values():
        if vip_data.get('steam_name') == steam_name:
            return True
    return False

def get_vip_id(steam_name):
    """پیدا کردن ID مربوط به Steam Name در لیست VIP"""
    for vip_id, vip_data in vip_players.items():
        if vip_data.get('steam_name') == steam_name:
            return vip_id
    return None

async def send_channel_message(embed):
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send(embed=embed)

# ---------- رویدادها و تسک‌ها ----------
@bot.event
async def on_ready():
    print(f"Bot be onvan {bot.user} vared Discord shod!")
    await bot.tree.sync()
    print("Dastoorate slash be roozrasi shodand!")
    if not check_players.is_running():
        check_players.start()

@tasks.loop(seconds=10)
async def check_players():
    global previous_players, saved_player_data, current_online_players, max_seen_id

    current_online_players.clear()
    url = f"http://{SERVER_IP}:{SERVER_PORT}/players.json"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=20) as response:
                if response.status != 200:
                    print("Server Error, Please Check Database")
                    return

                content = await response.text()
                players = json.loads(content)

                # ساخت دیکشنری به‌وسیله player_id
                current_players = {str(p['id']): p for p in players}
                current_player_ids = set(current_players.keys())

                # به روزرسانی بیشترین ID مشاهده شده
                try:
                    curr_ids = [int(pid) for pid in current_player_ids if pid.isdigit()]
                    if curr_ids:
                        current_max = max(curr_ids)
                        if current_max > max_seen_id:
                            max_seen_id = current_max
                            # ذخیره بیشترین ID در فایل
                            with open("max_seen_id.txt", "w") as f:
                                f.write(str(max_seen_id))
                except:
                    pass

                # تشخیص ریست سرور با منطق جدید
                if detect_server_reset(current_player_ids):
                    print("Server reset shod! Pak kardane saved_player_data...")
                    
                    # فقط saved_player_data پاک می‌شود
                    saved_player_data = {}
                    save_json_file(saved_player_data_file, saved_player_data)
                    
                    print("Saved player data pak shod, VIP va aliases hefz shodand.")
                    
                    # همچنین previous_players را پاک می‌کنیم تا از تشخیص مجدد جلوگیری شود
                    previous_players = set()

                channel = bot.get_channel(CHANNEL_ID)

                # پردازش بازیکنان
                for p in players:
                    pid = str(p['id'])
                    pname = p.get('name', 'Unknown')
                    steam_name = get_steam_name(p)

                    current_online_players[pid] = steam_name

                    # ایجاد یا بروزرسانی اطلاعات بازیکن
                    if pid in saved_player_data:
                        saved_player_data[pid]["last_seen"] = datetime.now().isoformat()
                    else:
                        saved_player_data[pid] = {
                            "name": pname,
                            "steam_name": steam_name,
                            "last_seen": datetime.now().isoformat()
                        }

                # پردازش بازیکنان جدید (Join)
                new_ids = current_player_ids - previous_players
                if new_ids:
                    for pid in new_ids:
                        player = current_players[pid]
                        steam_name = get_steam_name(player)

                        display_name = get_player_display_name(steam_name)
                        is_vip = get_vip_status(steam_name)

                        color = discord.Color.green() if is_vip else discord.Color.blue()
                        status = "VIP Join" if is_vip else "Join"
                        embed = discord.Embed(
                            description=(f"**Status:** {status}\n"
                                         f"**Name:** {display_name}\n"
                                         f"**ID:** {pid}"),
                            color=color,
                        )
                        if channel:
                            await channel.send(embed=embed)

                # پردازش بازیکنان خارج شده (Leave)
                left_ids = previous_players - current_player_ids
                if left_ids:
                    for pid in left_ids:
                        pdata = saved_player_data.get(pid, {})
                        steam_name = pdata.get('steam_name', 'Unknown')

                        display_name = get_player_display_name(steam_name)
                        is_vip = get_vip_status(steam_name)
                                
                        color = discord.Color.red() if is_vip else discord.Color.orange()
                        status = "VIP Leave" if is_vip else "Leave"
                        embed = discord.Embed(
                            description=(f"**Status:** {status}\n"
                                         f"**Name:** {display_name}\n"
                                         f"**ID:** {pid}"),
                            color=color,
                        )
                        if channel:
                            await channel.send(embed=embed)

                previous_players = current_player_ids
                save_json_file(saved_player_data_file, saved_player_data)

    except Exception as e:
        print("Error dar daryaft etelaat Player:", e)

# ---------- دستورات اسلش و معمولی ----------
@bot.tree.command(name="players", description="Namayesh list Player online server")
async def players(interaction: discord.Interaction):
    url = f"http://{SERVER_IP}:{SERVER_PORT}/players.json"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    await interaction.response.send_message("Error dar daryaft etelaat server!", ephemeral=True)
                    return

                content = await response.text()
                players_data = json.loads(content)
                if not players_data:
                    await interaction.response.send_message("Hich Playeri online nist.", ephemeral=True)
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
                        steam_name = get_steam_name(player)

                        display_name = get_player_display_name(steam_name)
                        is_vip = get_vip_status(steam_name)
                                
                        if is_vip:
                            display_name = f"🌟 {display_name}"

                        embed.add_field(
                            name=f"{player_id} - {display_name}",
                            value=f"**Steam Name:** {steam_name}",
                            inline=False
                        )
                    embeds.append(embed)

                await interaction.response.send_message(embed=embeds[0])
                for emb in embeds[1:]:
                    await interaction.followup.send(embed=emb)
    except Exception as e:
        await interaction.response.send_message(f"Error dar ersale darkhast: {e}", ephemeral=True)

@bot.tree.command(name="add", description="Ezafe kardan Player be list VIP (bar asas steam name)")
async def add_vip(interaction: discord.Interaction, player_id: str):
    global vip_players
    pdata = saved_player_data.get(player_id)
    if not pdata:
        await interaction.response.send_message(
            f"Player ba ID `{player_id}` peyda nashod. Motmaen shavid dar server online ast.",
            ephemeral=True
        )
        return

    steam_name = pdata.get('steam_name', 'Unknown')
    
    # بررسی اینکه آیا این بازیکن قبلاً VIP شده
    if get_vip_status(steam_name):
        await interaction.response.send_message(
            f"Player **{steam_name}** ghablan dar list VIP bood!",
            ephemeral=True
        )
        return

    vip_players[player_id] = {
        "name": steam_name,
        "steam_name": steam_name,
        "added_at": datetime.now().isoformat()
    }
    save_json_file(vip_list_file, vip_players)

    is_online = player_id in current_online_players
    status = "Online" if is_online else "Offline"

    await interaction.response.send_message(
        f"Player **{steam_name}** (ID: `{player_id}`) be list VIP ezafe shod!\nStatus: {status}",
        ephemeral=True
    )

@bot.tree.command(name="remove", description="Hazf kardan Player az list VIP (bar asas steam name)")
async def remove_vip(interaction: discord.Interaction, player_id: str):
    global vip_players
    if player_id in vip_players:
        steam_name = vip_players[player_id].get('steam_name', 'Nashnakhte')
        del vip_players[player_id]
        save_json_file(vip_list_file, vip_players)
        await interaction.response.send_message(
            f"Player **{steam_name}** (ID: `{player_id}`) az list VIP hazf shod!",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"Player ba ID `{player_id}` dar list VIP peyda nashod!",
            ephemeral=True
        )

@bot.tree.command(name="vlist", description="Namayesh list VIP haye server (bar asas steam name)")
async def vip_list(interaction: discord.Interaction):
    if not vip_players:
        await interaction.response.send_message("Hich Playeri dar list VIP nist!", ephemeral=True)
        return

    # ایجاد مجموعه‌ای از Steam Name بازیکنان آنلاین
    online_steam_names = set(current_online_players.values())

    embed = discord.Embed(title="List VIP haye server", color=discord.Color.gold())
    
    # لیست VIPها را بر اساس وضعیت آنلاین/آفلاین مرتب می‌کنیم
    sorted_vips = sorted(vip_players.items(), 
                         key=lambda x: x[1].get('steam_name', '') in online_steam_names, 
                         reverse=True)
    
    for pid, data in sorted_vips:
        steam_name = data.get('steam_name', 'Name not found')
        added = data.get('added_at', 'N/A')
        display_name = get_player_display_name(steam_name)
        
        # بررسی آنلاین بودن بر اساس Steam Name
        is_online = steam_name in online_steam_names
        online_status = "🟢 Online" if is_online else "🔴 Offline"
        
        # اگر آنلاین است، ID فعلی را پیدا کن
        current_id = pid
        if is_online:
            for online_id, online_steam in current_online_players.items():
                if online_steam == steam_name:
                    current_id = online_id
                    break

        embed.add_field(
            name=f"{display_name} (ID: {current_id})",
            value=f"**Status:** {online_status}\n**Added:** {added[:10]}\n**Steam Name:** {steam_name}",
            inline=False
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="alias", description="Set or remove alias for a player (bar asas steam name)")
async def set_alias(interaction: discord.Interaction, player_info: str):
    global aliases

    parts = player_info.split(' ', 1)
    if len(parts) < 1:
        await interaction.response.send_message("Format ghalat: /alias [player_id] [name]", ephemeral=True)
        return

    player_id = parts[0]
    alias_name = parts[1] if len(parts) > 1 else None

    # پیدا کردن Steam Name بازیکن
    steam_name = None
    if player_id in saved_player_data:
        steam_name = saved_player_data[player_id].get('steam_name')
    else:
        # اگر در saved_player_data نیست، از لیست آنلاین‌ها بررسی کن
        steam_name = current_online_players.get(player_id)

    if not steam_name:
        await interaction.response.send_message(
            f"Player ba ID `{player_id}` peyda nashod. Motmaen shavid dar server online ast.",
            ephemeral=True
        )
        return

    # حذف alias اگر نام خالی بود
    if not alias_name or alias_name.strip() == "":
        for alias_id, alias_data in list(aliases.items()):
            if alias_data.get('steam_name') == steam_name:
                del aliases[alias_id]
                save_json_file(alias_list_file, aliases)
                await interaction.response.send_message(
                    f"Alias baraye **{steam_name}** hazf shod!", ephemeral=True
                )
                return
        
        await interaction.response.send_message(
            f"Baraye **{steam_name}** aliasi set nashode!", ephemeral=True
        )
        return

    # ذخیره alias بر اساس Steam Name
    aliases[player_id] = {
        "alias": alias_name,
        "steam_name": steam_name
    }
    save_json_file(alias_list_file, aliases)

    await interaction.response.send_message(
        f"Alias baraye **{steam_name}** set shod:\n**{alias_name}**",
        ephemeral=True
    )

# دستورات کنترلی ساده
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
        await ctx.send("Bot dar hal hazer darhale barrasi vaziyat Player nist.")

@bot.command()
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("Dastoorat sync shodand!")

if __name__ == '__main__':
    if TOKEN == "YOUR_DISCORD_BOT_TOKEN":
        print("WARNING: You are using the placeholder token. Replace it with your real bot token if you want to run.")
    bot.run(TOKEN)