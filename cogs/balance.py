import discord
from discord import app_commands
from discord.ext import commands
import json
import aiofiles
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class BalanceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._balance_cache = {}
        self._cache_expiry = {}
        self._cache_ttl = 30  # 30 seconds cache

    async def _get_balances(self) -> Dict[str, float]:
        """Get balances with caching"""
        import time
        current_time = time.time()
        
        if (not self._balance_cache or 
            current_time - self._cache_expiry.get('balances', 0) > self._cache_ttl):
            try:
                async with aiofiles.open("balances.json", "r") as f:
                    content = await f.read()
                    self._balance_cache = json.loads(content)
                    self._cache_expiry['balances'] = current_time
            except FileNotFoundError:
                logger.warning("balances.json not found, creating empty balance data")
                self._balance_cache = {}
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding balances.json: {e}")
                self._balance_cache = {}
            except Exception as e:
                logger.error(f"Unexpected error loading balances: {e}")
                self._balance_cache = {}
        
        return self._balance_cache

    @app_commands.command(name="balance", description="Check your or another user's balance in USD")
    @app_commands.describe(user="The user whose balance you want to check")
    async def balance(self, interaction: discord.Interaction, user: discord.User = None):
        """Check user balance with optimized caching and error handling"""
        try:
            await interaction.response.defer()
            
            # If no user is provided, default to the interaction user
            target_user = user if user else interaction.user
            user_id = str(target_user.id)

            # Load the balance data using caching
            balances = await self._get_balances()

            # If the user doesn't have a balance
            if user_id not in balances:
                embed = discord.Embed(
                    title="No Balance Found",
                    description=f"{target_user.display_name} doesn't have any balance yet.",
                    color=discord.Color.orange()
                )
                await interaction.followup.send(embed=embed)
                return

            # Ensure the balance is a number, either integer or float
            try:
                total_usd = float(balances[user_id])
            except (ValueError, TypeError):
                logger.error(f"Invalid balance format for user {user_id}: {balances[user_id]}")
                total_usd = 0.0

            # Create an embed to display the balance
            embed = discord.Embed(
                title=f"{target_user.display_name}'s Balance",
                description=f"The total balance is **${total_usd:.2f} USD**",
                color=0x000000
            )
            embed.set_thumbnail(url=target_user.display_avatar.url)
            embed.set_footer(text="Balance updated in real-time")
            
            await interaction.followup.send(embed=embed)

        except discord.errors.InteractionResponded:
            logger.warning("Interaction already responded to")
        except Exception as e:
            logger.error(f"Unexpected error in balance command: {e}")
            try:
                embed = discord.Embed(
                    title="Error",
                    description="An unexpected error occurred while fetching the balance.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            except:
                pass  # If we can't even send an error message, just log it

async def setup(bot):
    await bot.add_cog(BalanceCog(bot))
