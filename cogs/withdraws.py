import discord
from discord import app_commands
from discord.ext import commands
import json
import aiofiles
import logging
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

class WithdrawsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._withdrawals_cache = {}
        self._cache_expiry = {}
        self._cache_ttl = 30  # 30 seconds cache

    async def _get_withdrawals(self) -> Dict[str, List]:
        """Get withdrawals with caching"""
        current_time = time.time()
        
        if (not self._withdrawals_cache or 
            current_time - self._cache_expiry.get('withdrawals', 0) > self._cache_ttl):
            try:
                async with aiofiles.open("withdrawals.json", "r") as f:
                    content = await f.read()
                    self._withdrawals_cache = json.loads(content)
                    self._cache_expiry['withdrawals'] = current_time
            except FileNotFoundError:
                logger.info("withdrawals.json not found, creating empty withdrawals data")
                self._withdrawals_cache = {}
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding withdrawals.json: {e}")
                self._withdrawals_cache = {}
            except Exception as e:
                logger.error(f"Unexpected error loading withdrawals: {e}")
                self._withdrawals_cache = {}
        
        return self._withdrawals_cache

    def _format_currency_name(self, currency: str) -> str:
        """Format currency name for display"""
        currency_map = {
            "btc": "Bitcoin",
            "ltc": "Litecoin", 
            "eth": "Ethereum",
            "usdt@trx": "Tether"
        }
        return currency_map.get(currency.lower(), currency.capitalize())

    def _get_blockchain_url(self, currency: str, tx_hash: str) -> str:
        """Generate blockchain explorer URL"""
        currency_map = {
            "btc": "bitcoin",
            "ltc": "litecoin",
            "eth": "ethereum", 
            "usdt@trx": "tether"
        }
        blockchain_name = currency_map.get(currency.lower(), currency.lower())
        return f"https://blockchair.com/{blockchain_name}/transaction/{tx_hash}"

    def _get_status_emoji(self, tx_hash: str) -> str:
        """Get status emoji based on transaction hash"""
        if tx_hash and tx_hash != "N/A" and tx_hash != "pending":
            return "✅"  # Completed
        else:
            return "⏳"  # Pending

    @app_commands.command(name="withdraws", description="Check your recent withdrawal history")
    async def withdraws(self, interaction: discord.Interaction):
        """Show user's withdrawal history with enhanced formatting"""
        try:
            await interaction.response.defer()
            user_id = str(interaction.user.id)

            # Load the withdrawal history with caching
            withdrawals = await self._get_withdrawals()

            if user_id not in withdrawals or len(withdrawals[user_id]) == 0:
                embed = discord.Embed(
                    title="No Withdrawals Found",
                    description="You have no recorded withdrawals yet.",
                    color=discord.Color.orange()
                )
                embed.add_field(
                    name="💡 How to Withdraw",
                    value="Use `/withdraw` command to make your first withdrawal!",
                    inline=False
                )
                embed.set_footer(text="Your withdrawal history will appear here once you make transactions")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Build the description for the embed using withdrawal history
            description_lines = []
            total_withdrawn = 0.0
            
            for record in withdrawals[user_id]:
                try:
                    currency_name = self._format_currency_name(record["currency"])
                    amount = record["amount"]
                    total_withdrawn += amount
                    
                    amount_text = f"**${amount:.2f}**"
                    tx_hash = record.get("tx_hash", "N/A")
                    timestamp = record["timestamp"]
                    
                    status_emoji = self._get_status_emoji(tx_hash)
                    
                    if tx_hash and tx_hash != "N/A" and tx_hash != "pending":
                        blockchain_url = self._get_blockchain_url(record["currency"], tx_hash)
                        blockchain_link = f"[View Transaction]({blockchain_url})"
                    else:
                        blockchain_link = "Pending"
                    
                    description_lines.append(
                        f"{status_emoji} {currency_name} | {amount_text} | {blockchain_link} | <t:{timestamp}:R>"
                    )
                    
                except KeyError as e:
                    logger.warning(f"Missing field in withdrawal record: {e}")
                    continue
                except Exception as e:
                    logger.error(f"Error processing withdrawal record: {e}")
                    continue

            if not description_lines:
                embed = discord.Embed(
                    title="Invalid Withdrawal Data",
                    description="Your withdrawal records contain invalid data.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            description = "\n".join(description_lines)

            # Create an enhanced embed to show the withdrawal history
            embed = discord.Embed(
                title="Recent Withdrawals",
                description=description,
                color=discord.Color.blue()
            )
            
            # Add summary information
            embed.add_field(
                name="📊 Summary",
                value=f"**Total Withdrawn:** ${total_withdrawn:.2f}\n**Transactions:** {len(description_lines)}",
                inline=False
            )
            
            # Add legend
            embed.add_field(
                name="Legend",
                value="✅ Completed | ⏳ Pending",
                inline=False
            )
            
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            embed.set_footer(text=f"Showing {len(description_lines)} withdrawal transactions")

            await interaction.followup.send(embed=embed, ephemeral=False)
            
            logger.info(f"Withdrawal history retrieved for user {user_id}: {len(description_lines)} transactions")

        except Exception as e:
            logger.error(f"Unexpected error in withdraws command: {e}")
            try:
                embed = discord.Embed(
                    title="Error",
                    description="❌ An unexpected error occurred while fetching your withdrawal history.",
                    color=discord.Color.red()
                )
                embed.set_footer(text="Please try again later or contact support")
                await interaction.followup.send(embed=embed, ephemeral=True)
            except:
                pass

async def setup(bot):
    await bot.add_cog(WithdrawsCog(bot))
