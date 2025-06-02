import discord
from discord import app_commands
from discord.ext import commands
import json
import aiofiles
import logging
import time
from typing import Dict, Set

logger = logging.getLogger(__name__)

# List of whitelisted user IDs - consider moving to environment variables for better security
WHITELIST: Set[int] = {
    1290257492361609287,
    1079860384950915202,
    1211102231781449759  # Add more IDs as needed
}

class SetBalanceCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._balance_cache = {}
        self._cache_expiry = {}
        self._cache_ttl = 30  # 30 seconds cache

    async def _get_balances(self) -> Dict[str, float]:
        """Get balances with caching"""
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

    async def _log_balance_change(self, admin_user: discord.User, target_user: discord.Member, 
                                 old_balance: float, new_balance: float) -> None:
        """Log balance changes for audit purposes"""
        log_entry = {
            "timestamp": int(time.time()),
            "admin_id": admin_user.id,
            "admin_name": admin_user.display_name,
            "target_id": target_user.id,
            "target_name": target_user.display_name,
            "old_balance": old_balance,
            "new_balance": new_balance,
            "change": new_balance - old_balance
        }
        
        try:
            # Log to admin audit file
            async with aiofiles.open("admin_audit.json", "a") as f:
                await f.write(json.dumps(log_entry) + "\n")
        except Exception as e:
            logger.error(f"Error writing audit log: {e}")

    def _validate_amount(self, amount: float) -> tuple[bool, str]:
        """Validate balance amount"""
        if not isinstance(amount, (int, float)):
            return False, "Amount must be a number"
        
        if amount < 0:
            return False, "Balance cannot be negative"
        
        if amount > 10000000:  # 10 million limit
            return False, "Balance cannot exceed $10,000,000"
        
        return True, ""

    def _is_authorized(self, user_id: int) -> bool:
        """Check if user is authorized to use this command"""
        return user_id in WHITELIST

    @app_commands.command(name="setbal", description="Set a user's balance (Whitelisted users only).")
    @app_commands.describe(
        member="The user whose balance to set",
        amount="The new balance amount (0 or higher)"
    )
    async def set_balance(self, interaction: discord.Interaction, member: discord.Member, 
                         amount: app_commands.Range[float, 0.0, 10000000.0]):
        """
        Enhanced setbal command with audit logging and better security
        """
        try:
            await interaction.response.defer()

            # Authorization check
            if not self._is_authorized(interaction.user.id):
                embed = discord.Embed(
                    title="Access Denied",
                    description="⚠️ You are not authorized to use this command.",
                    color=discord.Color.red()
                )
                embed.set_footer(text="Contact an administrator if you believe this is an error")
                await interaction.followup.send(embed=embed, ephemeral=True)
                
                # Log unauthorized access attempt
                logger.warning(f"Unauthorized setbal attempt by {interaction.user.id} ({interaction.user.display_name})")
                return

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

            # Prevent setting balance for bots
            if member.bot:
                embed = discord.Embed(
                    title="Invalid Target",
                    description="⚠️ You cannot set balance for bots.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Load balances with caching
            balances = await self._get_balances()
            user_id = str(member.id)

            # Get old balance for audit logging
            old_balance = float(balances.get(user_id, 0.0))

            # Set the new balance
            self._balance_cache[user_id] = float(amount)

            # Save updated balances
            await self._save_balances()

            # Log the change for audit purposes
            await self._log_balance_change(interaction.user, member, old_balance, amount)

            # Create success embed
            embed = discord.Embed(
                title="Balance Updated Successfully",
                description=f"{interaction.user.mention} has set {member.mention}'s balance to **${amount:.2f}**.",
                color=discord.Color.green()
            )
            
            if old_balance != amount:
                change = amount - old_balance
                change_text = f"+${change:.2f}" if change > 0 else f"-${abs(change):.2f}"
                embed.add_field(
                    name="Previous Balance", 
                    value=f"${old_balance:.2f}", 
                    inline=True
                )
                embed.add_field(
                    name="Change", 
                    value=change_text, 
                    inline=True
                )
            
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="Whitelisted Action • Changes are logged for audit")
            
            # Send the embed as a response
            await interaction.followup.send(embed=embed)

            # Log successful operation
            logger.info(f"Balance set by {interaction.user.id} for {member.id}: ${old_balance:.2f} -> ${amount:.2f}")

        except app_commands.AppCommandError as e:
            logger.error(f"App command error in setbal: {e}")
            embed = discord.Embed(
                title="Command Error",
                description="⚠️ There was an error with the command parameters.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Unexpected error in setbal command: {e}")
            embed = discord.Embed(
                title="Error",
                description="⚠️ An unexpected error occurred while setting the balance.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

# Setup function to add the cog to the bot
async def setup(bot):
    await bot.add_cog(SetBalanceCog(bot))