import discord
from discord import app_commands
from discord.ext import commands
import json
import time
import aiofiles
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class DepositsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._deposits_cache = {}
        self._cache_expiry = {}
        self._cache_ttl = 30  # 30 seconds cache

    async def _get_deposits(self) -> Dict[str, List]:
        """Get deposits with caching"""
        current_time = time.time()
        
        if (not self._deposits_cache or 
            current_time - self._cache_expiry.get('deposits', 0) > self._cache_ttl):
            try:
                async with aiofiles.open("deposits.json", "r") as f:
                    content = await f.read()
                    self._deposits_cache = json.loads(content)
                    self._cache_expiry['deposits'] = current_time
            except FileNotFoundError:
                logger.info("deposits.json not found, creating empty deposits data")
                # Create the file with empty data
                self._deposits_cache = {}
                await self._save_deposits()
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding deposits.json: {e}")
                self._deposits_cache = {}
            except Exception as e:
                logger.error(f"Unexpected error loading deposits: {e}")
                self._deposits_cache = {}
        
        return self._deposits_cache

    async def _save_deposits(self) -> None:
        """Save deposits to file and update cache"""
        try:
            async with aiofiles.open("deposits.json", "w") as f:
                await f.write(json.dumps(self._deposits_cache, indent=4))
            self._cache_expiry['deposits'] = time.time()
        except Exception as e:
            logger.error(f"Error saving deposits: {e}")

    def _format_currency_name(self, currency: str) -> str:
        """Format currency name for display"""
        currency_map = {
            "btc": "Bitcoin",
            "ltc": "Litecoin", 
            "usdt@trx": "Tether"
        }
        return currency_map.get(currency.lower(), currency.capitalize())

    def _get_blockchain_url(self, currency: str, tx_hash: str) -> str:
        """Generate blockchain explorer URL"""
        currency_map = {
            "btc": "bitcoin",
            "ltc": "litecoin",
            "usdt@trx": "tether"
        }
        blockchain_name = currency_map.get(currency.lower(), currency.lower())
        return f"https://blockchair.com/{blockchain_name}/transaction/{tx_hash}"

    @app_commands.command(name="deposits", description="Check your recent deposits")
    async def deposits(self, interaction: discord.Interaction):
        """Show user's deposit history with optimized performance"""
        try:
            await interaction.response.defer()
            user_id = str(interaction.user.id)

            # Load the deposit history with caching
            deposits = await self._get_deposits()

            if user_id not in deposits or len(deposits[user_id]) == 0:
                embed = discord.Embed(
                    title="No Deposits Found",
                    description="You have no recorded deposits yet.",
                    color=discord.Color.orange()
                )
                embed.set_footer(text="Start depositing to see your history here!")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Build the description for the embed using deposit history
            description_lines = []
            for record in deposits[user_id]:
                try:
                    currency_name = self._format_currency_name(record["currency"])
                    amount = f"**${record['amount']:.2f}**"
                    tx_hash = record["tx_hash"]
                    timestamp = record["timestamp"]
                    
                    blockchain_url = self._get_blockchain_url(record["currency"], tx_hash)
                    blockchain_link = f"[View Transaction]({blockchain_url})"
                    
                    description_lines.append(
                        f"{currency_name} | {amount} | {blockchain_link} | <t:{timestamp}:R>"
                    )
                except KeyError as e:
                    logger.warning(f"Missing field in deposit record: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing deposit record: {e}")
                    continue

            if not description_lines:
                embed = discord.Embed(
                    title="Invalid Deposit Data",
                    description="Your deposit records contain invalid data.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            description = "\n".join(description_lines)

            # Create an embed to show the deposit history
            embed = discord.Embed(
                title="Recent Deposits",
                description=description,
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            embed.set_footer(text=f"Showing {len(description_lines)} recent deposits")

            await interaction.followup.send(embed=embed, ephemeral=False)

        except Exception as e:
            logger.error(f"Unexpected error in deposits command: {e}")
            try:
                embed = discord.Embed(
                    title="Error",
                    description="An unexpected error occurred while fetching deposits.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            except:
                pass

    def record_deposit(self, user_id: str, currency: str, amount: float, tx_hash: str) -> None:
        """
        Record a new deposit in the deposits.json file with validation
        
        Parameters:
        user_id (str): The Discord user ID
        currency (str): The cryptocurrency used (e.g., 'btc', 'ltc')
        amount (float): The deposit amount in USD
        tx_hash (str): The transaction hash
        """
        try:
            # Validate inputs
            if not all([user_id, currency, tx_hash]):
                logger.error("Missing required parameters for deposit recording")
                return

            if not isinstance(amount, (int, float)) or amount <= 0:
                logger.error(f"Invalid amount for deposit: {amount}")
                return

            # Use cached data if available
            if not self._deposits_cache:
                # Force cache refresh
                import asyncio
                asyncio.create_task(self._get_deposits())

            # Initialize user's deposit list if it doesn't exist
            if user_id not in self._deposits_cache:
                self._deposits_cache[user_id] = []

            # Create new deposit record
            deposit_record = {
                "currency": currency.lower(),
                "amount": float(amount),
                "tx_hash": str(tx_hash),
                "timestamp": int(time.time())
            }

            # Add new deposit to user's history
            self._deposits_cache[user_id].append(deposit_record)

            # Keep only the last 20 deposits (increased from 10)
            self._deposits_cache[user_id] = self._deposits_cache[user_id][-20:]

            # Save updated deposits asynchronously
            import asyncio
            asyncio.create_task(self._save_deposits())

            logger.info(f"Recorded deposit for user {user_id}: {amount} USD in {currency}")

        except Exception as e:
            logger.error(f"Error recording deposit: {e}")

async def setup(bot):
    await bot.add_cog(DepositsCog(bot))