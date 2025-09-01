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
    
    # 3) جستجو بر اساس نام (برای زمانی که ID تغییر کرده اما نام ثابت است)
    for alias_id, alias_data in aliases.items():
        if isinstance(alias_data, dict) and alias_data.get("steam_name") == player_name:
            return alias_data.get("alias", player_name)
    
    # در نهایت نام واقعی
    return player_name

def find_player_id_by_name(player_name):
    """پیدا کردن ID بازیکن بر اساس نام"""
    for pid, data in saved_player_data.items():
        if data.get('name') == player_name:
            return pid
    return None

def update_player_id(old_id, new_id, player_name):
    """به‌روزرسانی ID بازیکن در سیستم"""
    global saved_player_data, vip_players, aliases
    
    # به‌روزرسانی saved_player_data
    if old_id in saved_player_data:
        saved_player_data[new_id] = saved_player_data[old_id]
        del saved_player_data[old_id]
    
    # به‌روزرسانی vip_players
    if old_id in vip_players:
        vip_players[new_id] = vip_players[old_id]
        del vip_players[old_id]
    
    # به‌روزرسانی aliases
    if old_id in aliases:
        aliases[new_id] = aliases[old_id]
        del aliases[old_id]
    
    # ذخیره تغییرات
    save_json_file(saved_player_data_file, saved_player_data)
    save_json_file(vip_list_file, vip_players)
    save_json_file(alias_list_file, aliases)
    
    print(f"Player ID updated: {old_id} -> {new_id} ({player_name})")

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

                # پردازش بازیکنان و به‌روزرسانی IDها
                for p in players:
                    pid = str(p['id'])
                    pname = p.get('name', 'Unknown')
                    identifiers = p.get('identifiers', []) if isinstance(p.get('identifiers', []), list) else []
                    steamid = next((i.split(':', 1)[1] for i in identifiers if i.startswith('steam:')), None)

                    # بررسی آیا این بازیکن با نام دیگر قبلاً وجود داشته
                    old_id = find_player_id_by_name(pname)
                    if old_id and old_id != pid:
                        # به‌روزرسانی ID بازیکن
                        update_player_id(old_id, pid, pname)

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

                        display_name = get_player_display_name(pid, pname)
                        
                        # بررسی VIP بودن بر اساس نام
                        is_vip = False
                        vip_id = None
                        for vid, vip_data in vip_players.items():
                            if vip_data.get('name') == pname:
                                is_vip = True
                                vip_id = vid
                                break

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
                        
                        # بررسی VIP بودن بر اساس نام
                        is_vip = False
                        for vip_id, vip_data in vip_players.items():
                            if vip_data.get('name') == pname:
                                is_vip = True
                                break
                                
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
                        
                        # بررسی VIP بودن بر اساس نام
                        is_vip = False
                        for vip_id, vip_data in vip_players.items():
                            if vip_data.get('name') == player_name:
                                is_vip = True
                                break
                                
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

    player_name = pdata.get('name', 'Unknown')
    
    # بررسی اینکه آیا این بازیکن قبلاً با نام دیگری VIP شده
    for vip_id, vip_data in list(vip_players.items()):
        if vip_data.get('name') == player_name:
            await interaction.response.send_message(
                f"Player **{player_name}** ghablan dar list VIP bood! (ba ID ghabli: {vip_id})",
                ephemeral=True
            )
            return

    vip_players[player_id] = {
        "name": player_name,
        "added_at": datetime.now().isoformat()
    }
    save_json_file(vip_list_file, vip_players)

    is_online = player_id in current_online_players
    status = "Online" if is_online else "Offline"

    await interaction.response.send_message(
        f"Player **{player_name}** (ID: `{player_id}`) be list VIP ezafe shod!\nStatus: {status}",
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

    # ایجاد مجموعه‌ای از نام بازیکنان آنلاین
    online_names = set(current_online_players.values())

    embed = discord.Embed(title="List VIP haye server", color=discord.Color.gold())
    for pid, data in vip_players.items():
        pname = data.get('name', 'Name not found')
        added = data.get('added_at', 'N/A')
        display_name = get_player_display_name(pid, pname)
        
        # بررسی آنلاین بودن بر اساس نام
        is_online = pname in online_names
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