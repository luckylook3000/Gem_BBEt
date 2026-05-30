import os
import sys
import subprocess

# ==========================================
# 🚨 AUTO-INSTALLER (Fixes Build Errors)
# ==========================================
def install_requirements():
    try:
        import discord
        import dotenv
    except ImportError:
        print("📦 Installing libraries... please wait...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "discord.py", "python-dotenv"])
        print("✅ Libraries installed! Restarting...")
        os.execv(sys.executable, ['python'] + sys.argv)

install_requirements()

import discord
import random
import asyncio
import json
import time
from discord import app_commands, Interaction, Embed
from discord.ext import commands
from discord.ui import Button, View
from dotenv import load_dotenv

# ==========================================
# 1. TOKEN & CONFIG
# ==========================================
load_dotenv()
TOKEN = os.environ.get("TOKEN")

if not TOKEN:
    print("❌ ERROR: No TOKEN found in Secrets! Add a secret named 'TOKEN'.")
    sys.exit()

Config = {
    "Bot Name": "Gem Bet",
    "Bot Icon": "https://cdn.discordapp.com/icons/1314565811410829332/a_f59d3588d80ec8f0ab041a65d6c5a761.gif?size=1024",
}

# ==========================================
# 2. AUTO-DATABASE SYSTEM
# ==========================================
DB_FILE = "data.json"

def init_db():
    if not os.path.exists(DB_FILE):
        with open(DB_FILE, "w") as f:
            json.dump({"users": {}}, f, indent=4)

def load_db():
    try:
        with open(DB_FILE, "r") as f: return json.load(f)
    except: return {"users": {}}

def save_db(data):
    with open(DB_FILE, "w") as f: json.dump(data, f, indent=4)

def get_bal(uid):
    data = load_db()
    return data['users'].get(str(uid), {}).get("Gems", 1000)

def update_bal(uid, amt):
    data = load_db()
    uid = str(uid)
    if uid not in data['users']:
        data['users'][uid] = {"Gems": 1000}
    data['users'][uid]['Gems'] += amt
    save_db(data)
    return data['users'][uid]['Gems']

def add_suffix(val):
    val = abs(val)
    if val >= 1e12: return f"{val/1e12:.1f}T"
    if val >= 1e9: return f"{val/1e9:.1f}B"
    if val >= 1e6: return f"{val/1e6:.1f}M"
    if val >= 1e3: return f"{val/1e3:.1f}K"
    return str(val)

def suffix_to_int(s):
    s = s.lower()
    suffixes = {'k': 1e3, 'm': 1e6, 'b': 1e9, 't': 1e12}
    if s[-1] in suffixes: return int(float(s[:-1]) * suffixes[s[-1]])
    return int(s)

# ==========================================
# 3. GAME LOCKS
# ==========================================
active_games = {}
game_cooldowns = {}

async def can_play(user_id):
    now = time.time()
    if user_id in active_games:
        return False, "You already have a game in progress! ⏳"
    if user_id in game_cooldowns and (now - game_cooldowns[user_id]) < 1.0:
        return False, "Slow down! 1 second cooldown. ⏱️"
    return True, None

# ==========================================
# 4. BOT CORE
# ==========================================
class GemBetBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Slash commands synced!")

bot = GemBetBot()

def get_embed(title, desc, color=0x3471eb):
    embed = discord.Embed(title=title, description=desc, color=color)
    embed.set_footer(text="GemBet💎 | Virtual Games")
    return embed

@bot.command()
async def sync(ctx):
    await bot.tree.sync(guild=ctx.guild)
    await ctx.send("🚀 **Commands Synced! Restart Discord (Ctrl+R).**")

@bot.tree.command(name="balance", description="Check your gems")
async def balance(interaction: discord.Interaction, user: discord.Member = None):
    uid = str((user or interaction.user).id)
    await interaction.response.send_message(embed=get_embed("💰 Balance", f"{user or interaction.user} has **{add_suffix(get_bal(uid))}** gems.", 0x00ff00))

@bot.tree.command(name="tip", description="Tip a user")
async def tip(interaction: discord.Interaction, member: discord.Member, amount: str):
    uid = str(interaction.user.id)
    amt = suffix_to_int(amount)
    if get_bal(uid) < amt: return await interaction.response.send_message("❌ Not enough gems!", ephemeral=True)
    update_bal(uid, -amt)
    update_bal(str(member.id), amt)
    await interaction.response.send_message(embed=get_embed("💸 Tip Sent", f"{interaction.user.mention} tipped {member.mention} **{add_suffix(amt)}** gems!", 0xf1c40f))

# --- GAMES ---
@bot.tree.command(name="dice", description="Bet on high or low")
@app_commands.choices(choice=[app_commands.Choice(name="High", value="high"), app_commands.Choice(name="Low", value="low")])
async def dice(interaction: discord.Interaction, bet: str, choice: str):
    uid = str(interaction.user.id)
    can, msg = await can_play(uid)
    if not can: return await interaction.response.send_message(msg, ephemeral=True)
    amt = suffix_to_int(bet)
    if get_bal(uid) < amt: return await interaction.response.send_message("❌ Not enough gems!", ephemeral=True)
    active_games[uid] = True
    update_bal(uid, -amt)
    await interaction.response.send_message(embed=get_embed("🎲 Dice", f"Spinning... 🎰"))
    await asyncio.sleep(1)
    roll = random.randint(1, 6)
    win = (choice == 'high' and roll >= 4) or (choice == 'low' and roll <= 3)
    if win:
        update_bal(uid, amt * 2)
        res, col = f"🎉 **WIN!** Rolled {roll}. Won **{add_//suffix(amt*2)}** gems!", 0x00ff00
    else:
        res, col = f"💀 **LOSS!** Rolled {roll}. Lost **{add_suffix(amt)}** gems!", 0xff0000
    await interaction.edit_original_response(embed=get_//embed("🎲 Result", f"{res}\nBalance: **{add_suffix(get_bal(uid))}**", col))
    del active_games[uid]
    game_cooldowns[uid] = time.time()

@bot.tree.command(name="blackjack", description="Play 21!")
async def blackjack(interaction: discord.Interaction, bet: str):
    uid = str(interaction.user.id)
    can, msg = await can_play(uid)
    if not can: return await interaction.response.send_message(msg, ephemeral=True)
    amt = suffix_to_int(bet)
    if get_bal(uid) < amt: return await interaction.response.send_message("❌ Not enough gems!", ephemeral=True)
    active_games[uid] = True
    update_bal(uid, -amt)
    p = [random.randint(2, 11), random.randint(2, 11)]
    d = [random.randint(2, 11), random.randint(2, 11)]
    class BJView(discord.ui.View):
        def __init__(self, user, bet, p, d):
            super().__init__(timeout=60)
            self.user, self.bet, self.p, self.d = user, bet, p, d
        @discord.ui.button(label="Hit", style=discord.ButtonStyle.green)
        async def hit(self, inter, btn):
            if inter.user.id != self.user: return await inter.response.defer()
            self.p.append(random.randint(2, 11))
            if sum(self.p) > 21:
                await inter.response.edit_message(content=f"💥 **BUST!** Total {sum(self.p)}. Lost {add_suffix(self.bet)} gems.", embed=None, view=None)
                active_games.pop(str(self.user), None)
                game_cooldowns[str(self.user)] = time.time()
            else:
                await inter.response.edit_message(content=f"🃏 Hand: `{self.p}` (Total: {sum(self.p)})", view=self)
        @discord.ui.button(label="Stand", style=discord.ButtonStyle.red)
        async def stand(self, inter, btn):
            if inter.user.id != self.user: return await inter.response.defer()
            while sum(self.d) < 17: self.d.append(random.randint(2, 11))
            p_sum, d_sum = sum(self.p), sum(self.d)
            if d_sum > 21 or p_sum > d_sum:
                update_bal(str(self.user), self.bet * 2)
                res = "🎉 **WIN!**"
            elif p_sum < d_sum:
                res = "💀 **LOSS!**"
            else:
                update_bal(str(self.user), self.bet)
                res = "🤝 **TIE!**"
            await inter.response.edit_message(content=f"{res}\nPlayer: {p_sum} | Dealer: {d_sum}", embed=None, view=None)
            active_games.pop(str(self.user), None)
            game_cooldowns[str(self.user)] = time.time()
    await interaction.response.send_message(f"🃏 **Blackjack!** Your hand: `{p}` (Total: {sum(p)})\nDealer shows: `{d[0]}`", view=BJView(interaction.user.id, amt, p, d))

# --- MODS ---
@bot.tree.command(name="add", description="[MOD] Add gems")
async def add(interaction: discord.Interaction, member: discord.Member, amount: str):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("❌ No permission!", ephemeral=True)
    amt = suffix_to_int(amount)
    update_bal(str(member.id), amt)
    await interaction.response.send_message(embed=get_embed("➕ Added", f"Added **{add_suffix(amt)}** to {member.mention}", 0x00ff00))

@bot.tree.command(name="remove", description="[MOD] Remove gems")
async def remove(interaction: discord.Interaction, member: discord.Member, amount: str):
    if not interaction.user.guild_permissions.administrator: return await interaction.response.send_message("❌ No permission!", ephemeral=True)
    amt = suffix_to_int(amount)
    update_bal(str(member.id), -amt)
    await interaction.response.send_message(embed=get_embed("➖ Removed", f"Removed **{add_suffix(amt)}** from {member.mention}", 0xff0000))

@bot.event
async def on_ready():
    init_db()
    print(f'👑 Gem Bet is ONLINE as {bot.user}')

bot.run(TOKEN)
