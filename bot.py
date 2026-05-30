import os
import discord
import random
import asyncio
import json
import math
import time
import re
import requests
import aiohttp
from datetime import datetime, timezone
from enum import Enum
from discord import app_commands, Interaction, Embed
from discord.ext import commands
from discord.ui import Button, View
from dotenv import load_dotenv

# ==========================================
# 1. CONFIG & SECRETS
# ==========================================
load_dotenv()
TOKEN = os.getenv("TOKEN")

Config = {
    "Bot Name": "Gem Bet",
    "Bot Icon": "https://cdn.discordapp.com/icons/1314565811410829332/a_f59d3588d80ec8f0ab041a65d6c5a761.gif?size=1024",
    "Towers": {"WinChance": 45, "Multis": [1.42, 2.02, 2.86, 4.05, 5.69]},
    "Mines": {"House": 0.25},
    "Logs": 1314565812950007837,
    "Coinflip": {"1v1": "1314565812950007831", "House": 5},
    "Rains": {"Channel": "1314565812950007834"},
    "AdminCommands": {
        "UserID": ["1177041430502461523", "1216488230245892186", "1278257618758139905", "1144624389556551750", "1124671288527560844", "1085730642928607272", "1310620656865378355"],
        "OwnerID": ["1177041430502461523"],
    },
    "Withdraws": {"Webhook": "https://discord.com/api/webhooks/1321614565557141608/AyTZcbIPYY2ys2uxx75KT_HYM2MZvzO0w-AM1kuTRU1qGa1l0fs8XwhP7ZQaM"},
    "Affiliates": {"Webhook": "https://discord.com/api/webhooks/1321614563569045596/2w9FsfpUnAb28BxgUP0y16WQENPPUVsd4I6nZw3zGximxfkPyqvhtvyA5EcSERT"},
    "Tips": {"Webhook": "https://discord.com/api/webhooks/13216145638702/DwlmXUmA7nwfK-IfdyHmsW86GCsQtCzTpp5jitY9Zhen9Q4hmOmsL"},
    "Promocodes": {"Webhook": "https://discord.com/api/webhooks/1321614562520207431/McdDfjVImju1YWovQIDeHma_AbSJrvscE2vn1kUKEP_C", "RoleID": "1314565811410829334"},
    "Rakeback": 1,
}

# ==========================================
# 2. DATABASE ENGINE (Auto-Healing)
# ==========================================
def init_db():
    files = {
        "data.json": {"users": {}},
        "withdraws.json": [],
        "promocodes.json": [],
        "history.json": {},
        "admins.json": {},
        "deposits.json": []
    }
    for filename, default in files.items():
        if not os.path.exists(filename):
            with open(filename, "w") as f: json.dump(default, f, indent=4)

def readdata():
    try:
        with open("data.json", "r") as f: return json.load(f)
    except: return {"users": {}}

def writedata(data):
    with open("data.json", "w") as f: json.dump(data, f, indent=4)

def register_user(uid):
    data = readdata()
    if uid not in data['users']:
        data["users"][uid] = {
            "Gems": 1000, "Wagered": 0, "Net Profit": 0, "Deposited": 0,
            "Withdrawn": 0, "Affiliate": None, "Affiliate Earnings": 0,
            "Tips Got": 0, "Tips Sent": 0, "Total Rained": 0, "Rain Earnings": 0,
            "linkedusername": None
        }
        writedata(data)

def get_gems(uid):
    data = readdata()
    return data['users'].get(uid, {}).get("Gems", 1000)

def add_gems(uid, amount):
    data = readdata()
    if uid not in data['users']: register_user(uid)
    data['users'][uid]['Gems'] += amount
    writedata(data)

def subtract_gems(uid, amount):
    data = readdata()
    if uid in data['users']:
        data['users'][uid]['Gems'] -= amount
        writedata(data)

def add_suffix(val):
    val = abs(val)
    if val >= 1e15: return f"{val/1e15:.1f}Q"
    if val >= 1e12: return f"{val/1e12:.1f}T"
    if val >= 1e9: return f"{val/1e9:.1f}B"
    if val >= 1e6: return f"{val/1e6:.1f}M"
    if val >= 1e3: return f"{val/1e3:.1f}K"
    return str(val)

def suffix_to_int(s):
    s = s.lower()
    suffixes = {'k': 1e3, 'm': 1e6, 'b': 1e9, 't': 1e12, 'q': 1e15}
    if s[-1] in suffixes: return int(float(s[:-1]) * suffixes[s[-1]])
    return int(s)

def log_transaction(user_id, description):
    try:
        with open("history.json", "r") as f: history = json.load(f)
    except: history = {}
    timestamp = int(datetime.now(timezone.utc).timestamp())
    record = f"{description} | {timestamp}"
    if user_id not in history: history[user_id] = []
    history[user_id].insert(0, record)
    with open("history.json", "w") as f: json.dump(history, f, indent=4)

# ==========================================
# 3. GAME LOCKS & COOLDOWNS
# ==========================================
active_games = {}
game_cooldowns = {}

async def can_play(user_id):
    now = time.time()
    if user_id in active_games:
        return False, "You already have a game in progress! Finish it first. ⏳"
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
        print("✅ Gem Bet Professional Synced!")

bot = GemBetBot()

def get_embed(title, desc, color=0x3471eb):
    embed = discord.Embed(title=title, description=desc, color=color)
    embed.set_footer(text="GemBet💎 | Virtual Games", icon_url=Config["Bot Icon"])
    return embed

@bot.command()
async def sync(ctx):
    await bot.tree.sync(guild=ctx.guild)
    await ctx.send("🚀 **Commands Synced! Restart Discord (Ctrl+R).**")

# --- PUBLIC ECONOMY ---
@bot.tree.command(name="balance", description="Check your gems")
async def balance(interaction: discord.Interaction, user: discord.Member = None):
    uid = str((user or interaction.user).id)
    register_user(uid)
    await interaction.response.send_message(embed=get_embed("💰 Balance", f"{user or interaction.user} has **{add_suffix(get_gems(uid))}** gems.", 0x00ff00))

@bot.tree.command(name="tip", description="Tip a user")
async def tip(interaction: discord.Interaction, member: discord.Member, amount: str):
    uid = str(interaction.user.id)
    amt = suffix_to_int(amount)
    if get_gems(uid) < amt: return await interaction.response.send_message("❌ Insufficient gems!", ephemeral=True)
    subtract_gems(uid, amt)
    add_gems(str(member.id), amt)
    log_transaction(uid, f"Tipped -{add_suffix(amt)} 💎")
    log_transaction(str(member.id), f"Received +{add_suffix(amt)} 💎 from {interaction.user.mention}")
    await interaction.response.send_message(embed=get_embed("💸 Tip Sent", f"{interaction.user.mention} tipped {member.mention} **{add_suffix(amt)}** gems!", 0xf1c40f))

# --- BLACKJACK (The Professional Version) ---
CARDS = {
    "S": "♠️", "H": "❤️", "D": "♦️", "C": "♣️"
}
VALUES = {"2":"2","3":"3","4":"4","5":"5","6":"6","7":"7","8":"8","9":"9","10":"10","J":"J","Q":"Q","K,K":"K","A":"A"}

def get_card_img(card):
    # Simple Card Mapping for Visuals
    return f"```{card}```"

def calc_bj(hand):
    val = 0
    aces = 0
    for c in hand:
        if c[0] in ["J", "Q", "K"]: val += 10
        elif c[0] == "A": val += 11; aces += 1
        else: val += int(c[0])
    while val > 21 and aces:
        val -= 10
        aces -= 1
    return val

@bot.tree.command(name="blackjack", description="Play High-Stakes Blackjack")
async def blackjack(interaction: discord.Interaction, bet: str):
    uid = str(interaction.user.id)
    can, msg = await can_play(uid)
    if not can: return await interaction.response.send_message(msg, ephemeral=True)
    
    amt = suffix_to_int(bet)
    if get_gems(uid) < amt: return await interaction.response.send_message("❌ Insufficient gems!", ephemeral=True)

    active_games[uid] = True
    subtract_gems(uid, amt)

    deck = [f"{v}{s}" for s in "SHDC" for v in ["2","3","4"," kind","5","6","7","8","9","10","J","Q","K","A"]]
    random.shuffle(deck)
    
    p_hand = [deck.pop(), deck.pop()]
    d_hand = [deck.pop(), deck.pop()]

    class BJView(discord.ui.View):
        def __init__(self, user, bet, p, d, deck):
            super().__init__(timeout=60)
            self.user, self.bet, self.p, self.d, self.deck = user, bet, p, d
            self.first_move = True

        @discord.ui.button(label="Hit 🃏", style=discord.ButtonStyle.green)
        async def hit(self, inter, btn):
            if inter.user.id != self.user: return await inter.response.defer()
            self.first_move = False
            self.p.append(self.deck.pop())
            if calc_bj(self.p) > 21:
                await inter.response.edit_message(content=f"💥 **BUST!** Total {calc_bj(self.p)}. Lost {add_suffix(self.bet)} gems.", embed=None, view=None)
                active_games.pop(str(self.user), None)
                game_cooldowns[str(self.user)] = time.time()
            else:
                await inter.response.edit_message(content=f"🃏 Hand: `{self.p}` (Total: {calc_bj(self.p)})", view=self)

        @discord.ui.button(label="Stand ✋", style=discord.ButtonStyle.red)
        async def stand(self, inter, btn):
            if inter.user.id != self.user: return await inter.response.defer()
            while calc_bj(self.d) < 17: self.d.append(self.deck.pop())
            p_sum, d_sum = calc_bj(self.p), calc_bj(self.d)
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

        @discord.ui.button(label="Double 💰", style=discord.ButtonStyle.blurple)
        async def double(self, inter, btn):
            if inter.user.id != self.user or not self.first_move: 
                return await inter.response.send_message("Double down only on 1st move!", ephemeral=True)
            
            if get_gems(str(self.user)) < self.bet:
                return await inter.response.send_message("Not enough gems to double!", ephemeral=True)
            
            update_bal(str(self.user), -self.bet)
            self.bet *= 2
            self.first_move = False
            self.p.append(self.deck.pop())
            if calc_bj(self.p) > 21:
                await inter.response.edit_message(content=f"💥 **BUST!** Lost {add_suffix(self.bet)} gems.", embed=None, view=None)
                active_games.pop(str(self.user), None)
                game_cooldowns[str(self.user)] = time.time()
            else:
                await inter.response.edit_message(content=f"🃏 Hand: `{self.p}` (Total: {calc_bj(self.p)})", view=self)

    await interaction.response.send_message(f"🃏 **Blackjack!** Your hand: `{p}` (Total: {calc_bj(p)})\nDealer shows: `{d[0]}`", view=BJView(interaction.user.id, amt, p, d, deck))

# --- ADMIN TOOLS ---
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
