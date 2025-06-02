import discord
from discord import app_commands
from discord.ext import commands
import json
import aiofiles
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class TipCog(commands.Cog):
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
                await self._save_balances()
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding balances.json: {e}")
                self._balance_cache = {}
            except Exception as e:
                logger.error(f"Unexpected error loading balances: {e}")
                self._balance_cache = {}
        
        return self._balance_cache

    async def _save_balances(self) -> None:
        """Save balances to file and update cache"""
        try:
            async with aiofiles.open("balances.json", "w") as f:
                await f.write(json.dumps(self._balance_cache, indent=4))
            self._cache_expiry['balances'] = time.time()
        except Exception as e:
            logger.error(f"Error saving balances: {e}")

    def _validate_amount(self, amount: float) -> tuple[bool, str]:
        """Validate tip amount"""
        if not isinstance(amount, (int, float)):
            return False, "Amount must be a number"
        
        if amount <= 0:
            return False, "Amount must be greater than 0"
        
        if amount < 0.01:
            return False, "Minimum tip amount is $0.01"
        
        if amount > 1000000:
            return False, "Maximum tip amount is $1,000,000"
        
        return True, ""

    @app_commands.command(name="tip", description="Tip another user by adding to their balance.")
    @app_commands.describe(
        member="The user you want to tip",
        amount="The amount to tip (minimum $0.01)"
    )
    async def tip(self, interaction: discord.Interaction, member: discord.Member, amount: app_commands.Range[float, 0.01, 1000000]):
        """
        Enhanced tip command with validation and better UX
        """
        try:
            await interaction.response.defer()

            # Input validation
            is_valid, error_msg = self._validate_amount(amount)
            if not is_valid:
                embed = discord.Embed(
                    title="Invalid Amount",
                    description=f"⚠️ {error_msg}",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Prevent self-tipping
            if member.id == interaction.user.id:
                embed = discord.Embed(
                    title="Self-Tip Not Allowed",
                    description="⚠️ You cannot tip yourself!",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Prevent tipping bots
            if member.bot:
                embed = discord.Embed(
                    title="Bot Tip Not Allowed",
                    description="⚠️ You cannot tip bots!",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Load balances with caching
            balances = await self._get_balances()

            # Get sender and recipient IDs
            sender_id = str(interaction.user.id)
            recipient_id = str(member.id)

            # Initialize balances if they don't exist
            if sender_id not in balances:
                balances[sender_id] = 0.0
            if recipient_id not in balances:
                balances[recipient_id] = 0.0

            # Convert to float for safety
            sender_balance = float(balances[sender_id])
            recipient_balance = float(balances[recipient_id])

            # Check if sender has enough balance
            if sender_balance < amount:
                embed = discord.Embed(
                    title="Insufficient Balance",
                    description=f"⚠️ You don't have enough balance to tip **${amount:.2f}**.\n"
                               f"Your current balance is **${sender_balance:.2f}**.",
                    color=discord.Color.red()
                )
                embed.set_footer(text="Use /deposit to add funds to your balance")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Process the tip
            new_sender_balance = sender_balance - amount
            new_recipient_balance = recipient_balance + amount

            # Update cache
            self._balance_cache[sender_id] = new_sender_balance
            self._balance_cache[recipient_id] = new_recipient_balance

            # Save to file
            await self._save_balances()

            # Create success embed
            embed = discord.Embed(
                title="Tip Successful! 💸",
                description=f"{interaction.user.mention} tipped {member.mention} **${amount:.2f}**!",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Your New Balance", 
                value=f"**${new_sender_balance:.2f} USD**", 
                inline=True
            )
            embed.add_field(
                name=f"{member.display_name}'s New Balance", 
                value=f"**${new_recipient_balance:.2f} USD**", 
                inline=True
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="Thank you for spreading the love!")

            # Send the embed as a response
            await interaction.followup.send(embed=embed)

            # Log the transaction
            logger.info(f"Tip successful: {interaction.user.id} -> {member.id}, amount: ${amount:.2f}")

        except app_commands.AppCommandError as e:
            logger.error(f"App command error in tip: {e}")
            embed = discord.Embed(
                title="Command Error",
                description="⚠️ There was an error with the command parameters.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Unexpected error in tip command: {e}")
            embed = discord.Embed(
                title="Error",
                description="⚠️ An unexpected error occurred while processing the tip.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

# Setup function to add the cog to the bot
async def setup(bot):
    await bot.add_cog(TipCog(bot))