import discord
from discord.ext import commands, tasks
import aiohttp
import json
import os
from datetime import datetime

# ====== تنظیمات ======
# اگر می‌خوای توکن رو مستقیم داخل فایل بذاری، مقدار زیر رو با توکن واقعی جایگزین کن.
TOKEN = "YOUR_DISCORD_BOT_TOKEN"

SERVER_IP = "Server_ip"
SERVER_PORT = "SERVER_PORT"
CHANNEL_ID = ChannelID

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="/", intents=intents)

# فایل‌ها
saved_player_data_file = "saved_player_data.json"
vip_list_file = "vip_players.json"   # keyed by player_id
alias_list_file = "aliases.json"     # keyed by player_id -> {"alias": "...", "steam_name": "..."}

# متغیرهای در حال اجرا
previous_players = set()
current_online_players = {}  # keyed by player_id -> player_name

# ---------- توابع کمکی برای فایل ----------
def load_json_file(path):
    if os.path.exists(path):
        if os.stat(path).st_size == 0:
            return {}
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json_file(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

# بارگذاری اولیه
saved_player_data = load_json_file(saved_player_data_file)
vip_players = load_json_file(vip_list_file)  # {player_id: {name, added_at}}
aliases = load_json_file(alias_list_file)    # {player_id: {"alias": alias_name, "steam_name": steam_name}}

# ---------- توابع کمکی ----------
def chunk_list(lst, chunk_size):
    return [lst[i:i+chunk_size] for i in range(0, len(lst), chunk_size)]

def detect_server_reset(current_ids):
    """تشخیص ریست سرور با شرایط مشخص (بدون وابستگی به steamid)"""
    global previous_players
    if not previous_players and current_ids == {"1"}:
        return True
    try:
        current_ids_int = [int(i) for i in current_ids if i.isdigit()]
        previous_ids_int = [int(i) for i in previous_players if i.isdigit()]
        if not current_ids_int or not previous_ids_int:
            return False
        if (max(current_ids_int) < 10 and previous_players and max(previous_ids_int) > 50):
            return True
    except Exception:
        pass
    return False

def get_player_display_name(player_id, player_name):
    """نام نمایشی بر اساس Alias:
       1) ابتدا بر اساس key=player_id
       2) در صورت نبود، بر اساس steam_name موجود در aliases جستجو می‌کنیم"""
    pid = str(player_id)
    # 1) براساس id
    if pid in aliases and isinstance(aliases[pid], dict) and aliases[pid].get("alias"):
        return aliases[pid]["alias"]
    # 2) جستجو براساس steam_name
    for v in aliases.values():
        if isinstance(v, dict) and v.get("steam_name") == player_name and v.get("alias"):
            return v.get("alias")
    # در نهایت نام واقعی
    return player_name

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
    global previous_players, saved_player_data, vip_players, aliases, current_online_players

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

                # ساخت دیکشنری به‌وسیله player_id (داخل بازی)
                current_players = {str(p['id']): p for p in players}
                current_player_ids = set(current_players.keys())

                # تشخیص ریست سرور
                if detect_server_reset(current_player_ids):
                    print("Server reset shod! Pak kardane saved_player_data")
                    saved_player_data = {}
                    save_json_file(saved_player_data_file, saved_player_data)
                    # اما aliases.json و vip_players.json را حذف نکنیم — آنها براساس اسم هم شناسايی خواهند شد

                channel = bot.get_channel(CHANNEL_ID)

                # --- ابتدا: بررسی و منتقل‌سازی آلیاس/VIP براساس steam name حتی اگر saved_player_data ریست شده باشد ---
                # برای هر پلیر جاری:
                for p in players:
                    pid = str(p['id'])
                    pname = p.get('name', 'Unknown')

                    # 1) اگر در aliases یک ورودی وجود داره که steam_name==pname و key != pid و اون key الان آنلاین نیست،
                    #    اون ورودی رو به pid منتقل کن
                    to_move_alias_keys = [k for k,v in aliases.items()
                                          if k != pid and isinstance(v, dict) and v.get("steam_name") == pname and k not in current_player_ids]
                    for old_key in to_move_alias_keys:
                        aliases[pid] = aliases.pop(old_key)
                        # بروزرسانی steam_name روی رکورد جدید (ممکنه همون باشه)
                        aliases[pid]["steam_name"] = pname
                        save_json_file(alias_list_file, aliases)
                        print(f"Alias moved by name: {old_key} -> {pid} ({pname})")

                    # 2) اگر در vip_players ورودی‌ای وجود داره با name == pname و key != pid و old key الان آنلاین نیست،
                    #    منتقل کن
                    to_move_vip_keys = [k for k,v in vip_players.items()
                                        if k != pid and isinstance(v, dict) and v.get("name") == pname and k not in current_player_ids]
                    for old_key in to_move_vip_keys:
                        vip_players[pid] = vip_players.pop(old_key)
                        # اطمینان از بروزرسانی نام داخل رکورد vip
                        vip_players[pid]["name"] = pname
                        save_json_file(vip_list_file, vip_players)
                        print(f"VIP moved by name: {old_key} -> {pid} ({pname})")

                    # 3) همچنین اگر saved_player_data حاوی old_id هایی با همان نام بود، آنها را پاک و انتقال‌های لازم رو انجام می‌دهیم
                    old_ids = [old_pid for old_pid, d in saved_player_data.items()
                               if old_pid != pid and d.get('name') == pname]
                    for old in old_ids:
                        if old not in current_player_ids:
                            # اگر alias با old وجود داره و هنوز نرفته بود، منتقل کن
                            if old in aliases:
                                aliases[pid] = aliases.pop(old)
                                aliases[pid]["steam_name"] = pname
                                save_json_file(alias_list_file, aliases)
                                print(f"Alias moved from saved_data: {old} -> {pid} ({pname})")
                            # اگر vip با old وجود داره
                            if old in vip_players:
                                vip_players[pid] = vip_players.pop(old)
                                vip_players[pid]["name"] = pname
                                save_json_file(vip_list_file, vip_players)
                                print(f"VIP moved from saved_data: {old} -> {pid} ({pname})")
                            # پاک کردن saved_player_data قدیمی
                            saved_player_data.pop(old, None)
                            save_json_file(saved_player_data_file, saved_player_data)

                # ذخیره/بروزرسانی اطلاعات بازیکنان حاضر
                for p in players:
                    pid = str(p['id'])
                    pname = p.get('name', 'Unknown')
                    identifiers = p.get('identifiers', []) if isinstance(p.get('identifiers', []), list) else []
                    # اگر steamid در دسترس بود ذخیره می‌کنیم ولی استفاده نمی‌کنیم (endpoint ممکنه hide باشه)
                    steamid = next((i.split(':', 1)[1] for i in identifiers if i.startswith('steam:')), None)

                    current_online_players[pid] = pname

                    saved_player_data[pid] = {
                        "name": pname,
                        # اگر steamid موجود باشه ذخیره می‌کنیم؛ در غیر این صورت مقدار None قرار میدیم
                        "steamid": steamid or None,
                        "last_seen": datetime.now().isoformat()
                    }

                # پردازش بازیکنان جدید (Join)
                new_ids = current_player_ids - previous_players
                if new_ids:
                    for pid in new_ids:
                        player = current_players[pid]
                        pname = player.get('name', 'Unknown')

                        display_name = get_player_display_name(pid, pname)

                        # بررسی VIP بر اساس player_id (کلید: id داخل بازی)
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
        # اگر در saved_player_data نبود، تلاش می‌کنیم از current_online_players بگیریم
        steam_name = current_online_players.get(player_id)

    # fall back
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
    if TOKEN == "YOUR_BOT_TOKEN":
        print("WARNING: You are using the placeholder token. Replace it with your real bot token if you want to run.")
    bot.run(TOKEN)
