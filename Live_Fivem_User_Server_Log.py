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
server_state_file = "server_state.json"  # فایل جدید برای ذخیره وضعیت سرور

# متغیرهای در حال اجرا
previous_players = set()
current_online_players = {}

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
server_state = load_json_file(server_state_file, {"last_session_id": 0, "session_players": {}})

# ---------- توابع کمکی ----------
def chunk_list(lst, chunk_size):
    return [lst[i:i+chunk_size] for i in range(0, len(lst), chunk_size)]

def detect_server_reset(current_ids):
    """تشخیص ریست سرور با منطق بهبود یافته"""
    global previous_players, server_state
    
    if not previous_players:
        return False
        
    # اگر تعداد بازیکنان از ۵۰ به کمتر از ۵ کاهش یابد (ریست سرور)
    if len(previous_players) > 50 and len(current_ids) < 5:
        return True
        
    # اگر IDهای قبلی بزرگ بودند و الان همه کوچک هستند
    try:
        prev_ids = [int(pid) for pid in previous_players if pid.isdigit()]
        curr_ids = [int(pid) for pid in current_ids if pid.isdigit()]
        
        if not prev_ids or not curr_ids:
            return False
            
        prev_max = max(prev_ids)
        curr_max = max(curr_ids)
        
        # اگر قبلی بیشتر از 50 بود و الان کمتر از 10 است
        if prev_max > 50 and curr_max < 10:
            return True
    except:
        pass
        
    return False

def get_stable_player_id(player_data):
    """ایجاد یک شناسه پایدار برای بازیکن بر اساس steamID یا ترکیب name و ID"""
    identifiers = player_data.get('identifiers', [])
    steam_id = next((i.split(':', 1)[1] for i in identifiers if i.startswith('steam:')), None)
    
    if steam_id:
        return f"steam_{steam_id}"
    
    # اگر steamID موجود نبود، از ترکیب name و ID استفاده می‌کنیم
    player_name = player_data.get('name', 'Unknown')
    player_id = str(player_data.get('id', '0'))
    return f"name_{player_name}_{player_id}"

def get_player_display_name(player_id, player_name):
    """نام نمایشی بر اساس Alias"""
    pid = str(player_id)
    
    # 1) براساس id
    if pid in aliases and isinstance(aliases[pid], dict) and aliases[pid].get("alias"):
        return aliases[pid]["alias"]
    
    # 2) جستجو براساس steam_name
    for v in aliases.values():
        if isinstance(v, dict) and v.get("steam_name") == player_name and v.get("alias"):
            return v.get("alias")
    
    # 3) استفاده از شناسه پایدار برای پیدا کردن alias
    stable_id = None
    for stable_key, player_data in saved_player_data.items():
        if player_data.get('name') == player_name:
            stable_id = stable_key
            break
            
    if stable_id and stable_id in aliases and isinstance(aliases[stable_id], dict) and aliases[stable_id].get("alias"):
        return aliases[stable_id]["alias"]
    
    # در نهایت نام واقعی
    return player_name

def migrate_player_data(old_id, new_id, player_name):
    """مهاجرت داده‌های بازیکن از ID قدیمی به جدید"""
    global saved_player_data, vip_players, aliases
    
    # مهاجرت saved_player_data
    stable_id = None
    for key, data in saved_player_data.items():
        if data.get('name') == player_name:
            stable_id = key
            break
            
    if stable_id and stable_id != new_id:
        if new_id not in saved_player_data:
            saved_player_data[new_id] = saved_player_data[stable_id]
        if stable_id in saved_player_data:
            del saved_player_data[stable_id]
    
    # مهاجرت vip_players
    for pid, vip_data in list(vip_players.items()):
        if vip_data.get('name') == player_name and pid != new_id:
            vip_players[new_id] = vip_data
            if pid in vip_players:
                del vip_players[pid]
    
    # مهاجرت aliases
    for pid, alias_data in list(aliases.items()):
        if alias_data.get('steam_name') == player_name and pid != new_id:
            aliases[new_id] = alias_data
            if pid in aliases:
                del aliases[pid]
    
    # ذخیره تغییرات
    save_json_file(saved_player_data_file, saved_player_data)
    save_json_file(vip_list_file, vip_players)
    save_json_file(alias_list_file, aliases)

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
    global previous_players, saved_player_data, vip_players, aliases, current_online_players, server_state

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

                # تشخیص ریست سرور
                if detect_server_reset(current_player_ids):
                    print("Server reset shod! Anghlab dar data haye bazikonan...")
                    
                    # ایجاد نگاشت بین بازیکنان قدیمی و جدید بر اساس نام
                    migration_map = {}
                    
                    for new_id, new_player in current_players.items():
                        new_name = new_player.get('name', 'Unknown')
                        
                        # پیدا کردن ID قدیمی بر اساس نام
                        for old_id, old_data in saved_player_data.items():
                            if old_data.get('name') == new_name and old_id not in migration_map.values():
                                migration_map[old_id] = new_id
                                break
                    
                    # مهاجرت داده‌ها
                    new_saved_data = {}
                    for old_id, new_id in migration_map.items():
                        if old_id in saved_player_data:
                            new_saved_data[new_id] = saved_player_data[old_id]
                            new_saved_data[new_id]['last_seen'] = datetime.now().isoformat()
                    
                    # اضافه کردن بازیکنان جدید که مهاجرت نشدند
                    for new_id, new_player in current_players.items():
                        if new_id not in new_saved_data:
                            identifiers = new_player.get('identifiers', [])
                            steamid = next((i.split(':', 1)[1] for i in identifiers if i.startswith('steam:')), None)
                            
                            new_saved_data[new_id] = {
                                "name": new_player.get('name', 'Unknown'),
                                "steamid": steamid,
                                "last_seen": datetime.now().isoformat()
                            }
                    
                    saved_player_data = new_saved_data
                    save_json_file(saved_player_data_file, saved_player_data)
                    print(f"{len(migration_map)} bazikon migrate shodand.")

                # پردازش بازیکنان
                channel = bot.get_channel(CHANNEL_ID)

                # بروزرسانی اطلاعات بازیکنان حاضر
                for p in players:
                    pid = str(p['id'])
                    pname = p.get('name', 'Unknown')
                    identifiers = p.get('identifiers', []) if isinstance(p.get('identifiers', []), list) else []
                    steamid = next((i.split(':', 1)[1] for i in identifiers if i.startswith('steam:')), None)

                    current_online_players[pid] = pname

                    # ایجاد یا بروزرسانی اطلاعات بازیکن
                    if pid in saved_player_data:
                        saved_player_data[pid]["last_seen"] = datetime.now().isoformat()
                        # بروزرسانی نام در صورت تغییر
                        if saved_player_data[pid].get('name') != pname:
                            saved_player_data[pid]['name'] = pname
                    else:
                        saved_player_data[pid] = {
                            "name": pname,
                            "steamid": steamid,
                            "last_seen": datetime.now().isoformat()
                        }

                # پردازش بازیکنان جدید (Join)
                new_ids = current_player_ids - previous_players
                if new_ids:
                    for pid in new_ids:
                        player = current_players[pid]
                        pname = player.get('name', 'Unknown')
                        
                        # بررسی و مهاجرت داده‌های قدیمی بر اساس نام
                        migrate_player_data(None, pid, pname)

                        display_name = get_player_display_name(pid, pname)
                        is_vip = str(pid) in vip_players

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
                        pname = pdata.get('name', 'Name not found')

                        display_name = get_player_display_name(pid, pname)
                        is_vip = str(pid) in vip_players
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
                        player_name = player.get('name', 'Unknown')
                        ping = player.get('ping', 'No ping data')

                        display_name = get_player_display_name(player_id, player_name)
                        is_vip = player_id in vip_players
                        if is_vip:
                            display_name = f"🌟 {display_name}"

                        embed.add_field(
                            name=f"{player_id} - {display_name}",
                            value=f"**Ping:** {ping} ms",
                            inline=False
                        )
                    embeds.append(embed)

                await interaction.response.send_message(embed=embeds[0])
                for emb in embeds[1:]:
                    await interaction.followup.send(embed=emb)
    except Exception as e:
        await interaction.response.send_message(f"Error dar ersale darkhast: {e}", ephemeral=True)

@bot.tree.command(name="add", description="Ezafe kardan Player be list VIP (bar asas player_id)")
async def add_vip(interaction: discord.Interaction, player_id: str):
    global vip_players
    pdata = saved_player_data.get(player_id)
    if not pdata:
        await interaction.response.send_message(
            f"Player ba ID `{player_id}` peyda nashod. Motmaen shavid dar server online ast.",
            ephemeral=True
        )
        return

    if player_id in vip_players:
        await interaction.response.send_message(
            f"Player **{pdata.get('name','Unknown')}** ghablan dar list VIP bood!",
            ephemeral=True
        )
        return

    vip_players[player_id] = {
        "name": pdata.get('name', 'Unknown'),
        "added_at": datetime.now().isoformat()
    }
    save_json_file(vip_list_file, vip_players)

    is_online = player_id in current_online_players
    status = "Online" if is_online else "Offline"

    await interaction.response.send_message(
        f"Player **{pdata.get('name','Unknown')}** (ID: `{player_id}`) be list VIP ezafe shod!\nStatus: {status}",
        ephemeral=True
    )

@bot.tree.command(name="remove", description="Hazf kardan Player az list VIP (bar asas player_id)")
async def remove_vip(interaction: discord.Interaction, player_id: str):
    global vip_players
    if player_id in vip_players:
        pname = vip_players[player_id].get('name', 'Nashnakhte')
        del vip_players[player_id]
        save_json_file(vip_list_file, vip_players)
        await interaction.response.send_message(
            f"Player **{pname}** (ID: `{player_id}`) az list VIP hazf shod!",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"Player ba ID `{player_id}` dar list VIP peyda nashod!",
            ephemeral=True
        )

@bot.tree.command(name="vlist", description="Namayesh list VIP haye server (bar asas player_id)")
async def vip_list(interaction: discord.Interaction):
    if not vip_players:
        await interaction.response.send_message("Hich Playeri dar list VIP nist!", ephemeral=True)
        return

    embed = discord.Embed(title="List VIP haye server", color=discord.Color.gold())
    for pid, data in vip_players.items():
        pname = data.get('name', 'Name not found')
        added = data.get('added_at', 'N/A')
        display_name = get_player_display_name(pid, pname)
        is_online = pid in current_online_players
        online_status = "🟢 Online" if is_online else "🔴 Offline"

        embed.add_field(
            name=f"{display_name} (ID: {pid})",
            value=f"**Status:** {online_status}\n**Added:** {added[:10]}",
            inline=False
        )

    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="alias", description="Set or remove alias for a player (bar asas player_id)")
async def set_alias(interaction: discord.Interaction, player_info: str):
    global aliases

    parts = player_info.split(' ', 1)
    if len(parts) < 1:
        await interaction.response.send_message("Format ghalat: /alias [player_id] [name]", ephemeral=True)
        return

    player_id = parts[0]
    alias_name = parts[1] if len(parts) > 1 else None

    # حذف alias اگر نام خالی بود
    if not alias_name or alias_name.strip() == "":
        if player_id in aliases:
            del aliases[player_id]
            save_json_file(alias_list_file, aliases)
            await interaction.response.send_message(
                f"Alias baraye ID `{player_id}` hazf shod!", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"Baraye ID `{player_id}` aliasi set nashode!", ephemeral=True
            )
        return

    # پیدا کردن steam name جهت ذخیره در aliases.json:
    steam_name = saved_player_data.get(player_id, {}).get('name')
    if not steam_name:
        steam_name = current_online_players.get(player_id)

    steam_name = steam_name or "Unknown"

    aliases[player_id] = {
        "alias": alias_name,
        "steam_name": steam_name
    }
    save_json_file(alias_list_file, aliases)

    player_name = saved_player_data.get(player_id, {}).get('name', steam_name)
    await interaction.response.send_message(
        f"Alias baraye **{player_name}** (ID: `{player_id}`) set shod:\n**{alias_name}**",
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