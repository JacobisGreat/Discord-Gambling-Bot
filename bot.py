import discord
from discord.ext import commands
from dotenv import load_dotenv
import json
import os
import requests
import asyncio
from flask import Flask, request, jsonify
from threading import Thread
import subprocess
import time
import aiohttp
import aiofiles
from functools import lru_cache
from typing import Dict, Optional, Any
import logging

# -----------------------------------------
# 1) Setup logging and load environment variables
# -----------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# -----------------------------------------
# 2) Cache and optimization setup
# -----------------------------------------
class DataCache:
    def __init__(self):
        self._wallets_cache = None
        self._balances_cache = None
        self._last_wallets_update = 0
        self._last_balances_update = 0
        self._cache_ttl = 30  # 30 seconds cache
        
    async def get_wallets(self) -> Dict:
        """Get wallets with caching"""
        current_time = time.time()
        if (self._wallets_cache is None or 
            current_time - self._last_wallets_update > self._cache_ttl):
            try:
                async with aiofiles.open("wallets.json", "r") as f:
                    content = await f.read()
                    self._wallets_cache = json.loads(content)
                    self._last_wallets_update = current_time
            except Exception as e:
                logger.error(f"Error loading wallets: {e}")
                return {}
        return self._wallets_cache or {}
    
    async def get_balances(self) -> Dict:
        """Get balances with caching"""
        current_time = time.time()
        if (self._balances_cache is None or 
            current_time - self._last_balances_update > self._cache_ttl):
            try:
                async with aiofiles.open("balances.json", "r") as f:
                    content = await f.read()
                    self._balances_cache = json.loads(content)
                    self._last_balances_update = current_time
            except Exception as e:
                logger.error(f"Error loading balances: {e}")
                return {}
        return self._balances_cache or {}
    
    async def update_balance(self, user_id: str, new_balance: float) -> None:
        """Update balance in cache and file"""
        if self._balances_cache is None:
            await self.get_balances()
        
        self._balances_cache[user_id] = new_balance
        try:
            async with aiofiles.open("balances.json", "w") as f:
                await f.write(json.dumps(self._balances_cache, indent=4))
            self._last_balances_update = time.time()
        except Exception as e:
            logger.error(f"Error updating balances: {e}")

# Global cache instance
data_cache = DataCache()

# Currency mappings (constants)
CURRENCY_MAP = {
    "btc": "bitcoin",
    "ltc": "litecoin", 
    "usdt@trx": "tether"
}

CRYPTO_CONVERSION_RATE = 100_000_000  # For satoshi-like conversions

# -----------------------------------------
# 3) Optimized price fetching with caching
# -----------------------------------------
@lru_cache(maxsize=32)
def get_cached_price(currency: str, cache_time: int) -> float:
    """Cache prices for 60 seconds intervals"""
    return _fetch_price_sync(currency)

def _fetch_price_sync(currency: str) -> float:
    """Synchronous price fetch for caching"""
    crypto_name = CURRENCY_MAP.get(currency)
    if not crypto_name:
        logger.warning(f"Unknown currency: {currency}")
        return 0.0
        
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={crypto_name}&vs_currencies=usd"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()[crypto_name]["usd"]
    except Exception as e:
        logger.error(f"Error fetching USD value for {currency}: {e}")
    return 0.0

async def convert_to_usd(value: float, currency: str) -> float:
    """Convert crypto value to USD with caching"""
    # Use current minute as cache key for 60-second cache
    cache_time = int(time.time() // 60)
    usd_rate = get_cached_price(currency, cache_time)
    return (value / CRYPTO_CONVERSION_RATE) * usd_rate

# -----------------------------------------
# 4) Flask tracking server setup
# -----------------------------------------
app = Flask(__name__)
ngrok_url = None

@app.route("/callback", methods=["POST"])
def callback():
    """Optimized callback handler"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data received"}), 400
            
        logger.info(f"Callback received: {data}")

        # Extract necessary details from callback
        tx_hash = data.get("input_transaction_hash")
        confirmations = data.get("confirmations", 0)
        input_address = data.get("input_address")
        value = data.get("value")
        currency = data.get("currency")

        # Validate required fields
        if not all([tx_hash, input_address, value, currency]):
            logger.warning("Missing required fields in callback")
            return jsonify({"error": "Missing required fields"}), 400

        # Schedule async operations
        asyncio.run_coroutine_threadsafe(
            handle_callback_async(tx_hash, confirmations, input_address, value, currency),
            bot.loop
        )

        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        logger.error(f"Error in callback: {e}")
        return jsonify({"error": "Internal server error"}), 500

async def handle_callback_async(tx_hash: str, confirmations: int, input_address: str, 
                               value: float, currency: str) -> None:
    """Handle callback operations asynchronously"""
    try:
        # DM Handling: Notify only at 0 and 1 confirmation
        if confirmations <= 1:
            await notify_user_async(input_address, tx_hash, confirmations, value, currency)

        # Handle balance update only when confirmations = 1
        if confirmations == 1:
            await update_balance_async(input_address, value, currency, tx_hash)

        # Update the payment processing message with transaction hash (for withdrawals)
        if tx_hash:
            await update_payment_message_async(tx_hash, input_address, currency)
            
    except Exception as e:
        logger.error(f"Error handling callback async: {e}")

async def update_payment_message_async(tx_hash: str, input_address: str, currency: str) -> None:
    """Optimized payment message update"""
    try:
        async with aiofiles.open("withdrawals.json", "r") as f:
            content = await f.read()
            withdrawals = json.loads(content)

        # Find the relevant withdrawal entry
        for user_id, withdrawal_list in withdrawals.items():
            for withdrawal in withdrawal_list:
                if (withdrawal.get("input_address") == input_address and 
                    withdrawal.get("currency") == currency):
                    
                    user_channel_id = withdrawal.get("channel_id")
                    message_id = withdrawal.get("message_id")

                    if user_channel_id and message_id:
                        await update_embed_message(user_channel_id, message_id, tx_hash, currency)
                    return
                    
    except Exception as e:
        logger.error(f"Error updating payment message: {e}")

async def update_embed_message(channel_id: int, message_id: int, tx_hash: str, currency: str) -> None:
    """Update embed message with transaction hash"""
    try:
        channel = bot.get_channel(channel_id)
        if not channel:
            logger.warning(f"Channel {channel_id} not found")
            return

        message = await channel.fetch_message(message_id)
        if not message:
            logger.warning(f"Message {message_id} not found")
            return

        embed = discord.Embed(
            description=f"<:checkmarkkk:1290435916841877525> Your {currency.capitalize()} payment has been sent successfully. "
                        f"Here's the [TXID](https://blockchair.com/{currency}/transaction/{tx_hash}).",
            color=discord.Color.green()
        )
        await message.edit(embed=embed)
        
    except Exception as e:
        logger.error(f"Error updating embed message: {e}")

async def notify_user_async(input_address: str, tx_hash: str, confirmations: int, 
                           value: float, currency: str) -> None:
    """Optimized user notification"""
    try:
        wallets = await data_cache.get_wallets()
        
        for user_id, user_wallets in wallets.items():
            for crypto_key, address in user_wallets.items():
                if address == input_address:
                    user = bot.get_user(int(user_id))
                    if user:
                        await send_dm(user, tx_hash, confirmations, value, currency)
                    return
                    
    except Exception as e:
        logger.error(f"Error notifying user: {e}")

async def send_dm(user: discord.User, tx_hash: str, confirmations: int, 
                  value: float, currency: str) -> None:
    """Send DM with transaction info"""
    try:
        blockchain_url = f"https://blockchair.com/{CURRENCY_MAP[currency]}/transaction/{tx_hash}"
        value_usd = await convert_to_usd(value, currency)

        if confirmations == 0:
            embed = discord.Embed(
                title="Pending Deposit",
                description=f"We have detected a pending deposit from your {currency.upper()} address.",
                color=discord.Color.orange()
            )
            embed.add_field(name="Amount", value=f"${value_usd:.2f}", inline=True)
            embed.add_field(name="Blockchain", value=f"[Click Here]({blockchain_url})", inline=True)
            embed.add_field(name="Confirmations", value="0/1", inline=True)
            embed.set_footer(text="This transaction will be automatically credited once confirmed.")
            
        elif confirmations == 1:
            embed = discord.Embed(
                title="Transaction Confirmed",
                description=f"Your {currency.upper()} deposit has been confirmed.",
                color=discord.Color.green()
            )
            embed.add_field(name="Amount", value=f"${value_usd:.2f}", inline=True)
            embed.add_field(name="Blockchain", value=f"[Click Here]({blockchain_url})", inline=True)
            embed.add_field(name="Confirmations", value="1/1", inline=True)

        await user.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Error sending DM to user {user.id}: {e}")

async def update_balance_async(input_address: str, value: float, currency: str, tx_hash: str) -> None:
    """Optimized balance update"""
    try:
        wallets = await data_cache.get_wallets()
        balances = await data_cache.get_balances()

        for user_id, user_wallets in wallets.items():
            for crypto_key, address in user_wallets.items():
                if address == input_address:
                    if user_id not in balances:
                        balances[user_id] = 0.0

                    value_usd = await convert_to_usd(value, currency)
                    new_balance = balances[user_id] + value_usd

                    # Update balance using cache
                    await data_cache.update_balance(user_id, new_balance)

                    logger.info(f"User {user_id}'s new balance is ${new_balance:.2f}")

                    # Record the deposit
                    deposits_cog = bot.get_cog('DepositsCog')
                    if deposits_cog:
                        deposits_cog.record_deposit(
                            user_id=str(user_id),
                            currency=currency,
                            amount=value_usd,
                            tx_hash=tx_hash
                        )

                    # Notify the deposit channel
                    await notify_deposit_channel(user_id, value_usd, currency)
                    return
                    
    except Exception as e:
        logger.error(f"Error updating balance: {e}")

async def notify_deposit_channel(user_id: str, value_usd: float, currency: str) -> None:
    """Notify deposit channel with optimized user fetching"""
    try:
        deposit_channel_id = int(os.getenv("DEPOSIT_CHANNEL_ID"))
        channel = bot.get_channel(deposit_channel_id)
        if not channel:
            logger.error(f"Deposit channel {deposit_channel_id} not found")
            return

        user = await bot.fetch_user(int(user_id))
        user_name = user.name if user else "Unknown User"

        embed = discord.Embed(
            title="New Deposit Confirmed!",
            description=f"A deposit has been confirmed for {user_name}.",
            color=discord.Color.green()
        )
        embed.add_field(name="User", value=user_name, inline=True)
        embed.add_field(name="Amount (USD)", value=f"${value_usd:.2f}", inline=True)
        embed.add_field(name="Currency", value=currency.upper(), inline=True)
        embed.set_footer(text="Deposit successfully credited.")

        await channel.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Error notifying deposit channel: {e}")

def run_flask():
    """Run Flask server with optimized settings"""
    app.run(host="0.0.0.0", port=5000, threaded=True)

# -----------------------------------------
# 5) Optimized ngrok setup
# -----------------------------------------
def run_ngrok():
    """Start ngrok with better error handling"""
    global ngrok_url
    logger.info("Starting ngrok...")

    try:
        ngrok_process = subprocess.Popen(
            ["ngrok", "http", "5000"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        time.sleep(3)  # Give ngrok more time to initialize

        response = requests.get("http://localhost:4040/api/tunnels", timeout=10)
        tunnels = response.json().get("tunnels", [])
        
        if tunnels:
            ngrok_url = tunnels[0]["public_url"]
            logger.info(f"ngrok URL: {ngrok_url}/callback")
        else:
            logger.warning("No ngrok tunnels found. Please check ngrok installation.")
            
    except Exception as e:
        logger.error(f"Error starting ngrok: {e}")

@bot.event
async def on_ready():
    """Bot ready event with better logging"""
    logger.info(f'Logged in as {bot.user}')
    await bot.tree.sync()
    logger.info(f"Slash commands synced for {bot.user}")

    if ngrok_url:
        logger.info(f"ngrok public URL for callbacks: {ngrok_url}")
    else:
        logger.warning("No ngrok URL available")

async def load_extensions():
    """Load extensions with error handling"""
    cogs_dir = './cogs'
    if not os.path.exists(cogs_dir):
        logger.warning("Cogs directory not found")
        return
        
    for filename in os.listdir(cogs_dir):
        if filename.endswith('.py') and not filename.startswith('__'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                logger.info(f"Loaded extension: {filename}")
            except Exception as e:
                logger.error(f"Failed to load extension {filename}: {e}")

async def main():
    """Main function with improved error handling and startup sequence"""
    try:
        # 1) Start Flask in a separate thread
        flask_thread = Thread(target=run_flask, daemon=True)
        flask_thread.start()
        logger.info("Flask server started")

        # 2) Start ngrok
        ngrok_thread = Thread(target=run_ngrok, daemon=True)
        ngrok_thread.start()
        logger.info("ngrok thread started")

        # 3) Start the Discord bot
        async with bot:
            await load_extensions()
            await bot.start(os.getenv('DISCORD_TOKEN'))
            
    except Exception as e:
        logger.error(f"Error in main: {e}")
        raise

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")