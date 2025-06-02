import discord
from discord import app_commands
from discord.ext import commands
import json
import aiohttp
import aiofiles
import logging
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class DepositCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._wallets_cache = {}
        self._cache_expiry = {}
        self._cache_ttl = 30  # 30 seconds cache
        self._api_url = "https://apirone.com/api/v2/accounts/apr-6fdfe29aad0a408dca1607d12c5e63e2/addresses"

    async def _get_wallets(self) -> Dict[str, Dict]:
        """Get wallets with caching"""
        current_time = time.time()
        
        if (not self._wallets_cache or 
            current_time - self._cache_expiry.get('wallets', 0) > self._cache_ttl):
            try:
                async with aiofiles.open("wallets.json", "r") as f:
                    content = await f.read()
                    self._wallets_cache = json.loads(content)
                    self._cache_expiry['wallets'] = current_time
            except FileNotFoundError:
                logger.info("wallets.json not found, creating empty wallets data")
                self._wallets_cache = {}
                await self._save_wallets()
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding wallets.json: {e}")
                self._wallets_cache = {}
            except Exception as e:
                logger.error(f"Unexpected error loading wallets: {e}")
                self._wallets_cache = {}
        
        return self._wallets_cache

    async def _save_wallets(self) -> None:
        """Save wallets to file and update cache"""
        try:
            async with aiofiles.open("wallets.json", "w") as f:
                await f.write(json.dumps(self._wallets_cache, indent=4))
            self._cache_expiry['wallets'] = time.time()
        except Exception as e:
            logger.error(f"Error saving wallets: {e}")

    async def _generate_address(self, cryptocurrency: str) -> Optional[str]:
        """Generate new wallet address using async HTTP request"""
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                async with session.post(
                    self._api_url, 
                    json={"currency": cryptocurrency},
                    headers={"Content-Type": "application/json"}
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        if "address" in data:
                            logger.info(f"Generated new {cryptocurrency} address: {data['address'][:10]}...")
                            return data["address"]
                        else:
                            logger.error(f"Address not found in API response for {cryptocurrency}")
                            return None
                    else:
                        logger.error(f"API request failed for {cryptocurrency}: Status {response.status}")
                        return None
                        
        except aiohttp.ClientError as e:
            logger.error(f"Network error generating {cryptocurrency} address: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error generating {cryptocurrency} address: {e}")
            return None

    def _get_currency_info(self, crypto: str) -> tuple[str, str]:
        """Get display name and emoji for cryptocurrency"""
        currency_info = {
            "btc": ("Bitcoin", "₿"),
            "ltc": ("Litecoin", "Ł"),
            "usdt@trx": ("Tether (TRC-20)", "₮")
        }
        return currency_info.get(crypto, (crypto.upper(), "🔹"))

    @app_commands.command(name="deposit", description="Generate or retrieve your cryptocurrency deposit address")
    @app_commands.choices(cryptocurrency=[
        app_commands.Choice(name="Bitcoin", value="btc"),
        app_commands.Choice(name="Litecoin", value="ltc"),
        app_commands.Choice(name="Tether (TRC-20)", value="usdt@trx"),
    ])
    async def deposit(self, interaction: discord.Interaction, cryptocurrency: str):
        """Enhanced deposit command with better UX and error handling"""
        try:
            await interaction.response.defer()
            user_id = str(interaction.user.id)

            # Load wallets from cache
            wallets = await self._get_wallets()

            # Get currency display info
            currency_name, currency_symbol = self._get_currency_info(cryptocurrency)

            # Check if user already has a wallet for this cryptocurrency
            if user_id in wallets and cryptocurrency in wallets[user_id]:
                existing_address = wallets[user_id][cryptocurrency]
                
                embed = discord.Embed(
                    title=f"{currency_symbol} {currency_name} Deposit Address",
                    description=f"Your existing {currency_name} deposit address:",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="Address", 
                    value=f"`{existing_address}`", 
                    inline=False
                )
                embed.add_field(
                    name="⚠️ Important", 
                    value=f"Only send {currency_name} to this address. Sending other cryptocurrencies may result in permanent loss.", 
                    inline=False
                )
                embed.set_thumbnail(url=interaction.user.display_avatar.url)
                embed.set_footer(text="Deposits are automatically credited after confirmation")
                
                await interaction.followup.send(embed=embed)
                return

            # Show generating message
            generating_embed = discord.Embed(
                title="Generating Address...",
                description=f"🔄 Creating your {currency_name} deposit address...",
                color=discord.Color.orange()
            )
            await interaction.followup.send(embed=generating_embed)

            # Generate new address
            new_address = await self._generate_address(cryptocurrency)
            
            if new_address:
                # Save the new address to cache and file
                if user_id not in self._wallets_cache:
                    self._wallets_cache[user_id] = {}
                
                self._wallets_cache[user_id][cryptocurrency] = new_address
                await self._save_wallets()

                # Create success embed
                embed = discord.Embed(
                    title=f"{currency_symbol} {currency_name} Deposit Address Generated",
                    description=f"Your new {currency_name} deposit address has been created:",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="Address", 
                    value=f"`{new_address}`", 
                    inline=False
                )
                embed.add_field(
                    name="⚠️ Important", 
                    value=f"Only send {currency_name} to this address. Sending other cryptocurrencies may result in permanent loss.", 
                    inline=False
                )
                embed.add_field(
                    name="📋 How to Use", 
                    value=f"1. Copy the address above\n2. Send {currency_name} to this address\n3. Your balance will be automatically credited after confirmation", 
                    inline=False
                )
                embed.set_thumbnail(url=interaction.user.display_avatar.url)
                embed.set_footer(text="Keep this address safe for future deposits")

                # Edit the original generating message
                await interaction.edit_original_response(embed=embed)
                
                logger.info(f"Generated {cryptocurrency} address for user {user_id}")

            else:
                # Address generation failed
                embed = discord.Embed(
                    title="Address Generation Failed",
                    description=f"❌ Failed to generate {currency_name} address. Please try again later.",
                    color=discord.Color.red()
                )
                embed.add_field(
                    name="What to do?", 
                    value="• Try again in a few minutes\n• Contact support if the issue persists", 
                    inline=False
                )
                embed.set_footer(text="Our technical team has been notified")
                
                await interaction.edit_original_response(embed=embed)
                
                logger.error(f"Failed to generate {cryptocurrency} address for user {user_id}")

        except Exception as e:
            logger.error(f"Unexpected error in deposit command: {e}")
            try:
                embed = discord.Embed(
                    title="Error",
                    description="❌ An unexpected error occurred while processing your request.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            except:
                pass

async def setup(bot):
    await bot.add_cog(DepositCog(bot))
