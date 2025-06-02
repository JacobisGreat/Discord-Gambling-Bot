import discord
from discord.ext import commands
import time
import logging

logger = logging.getLogger(__name__)

class PingCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @discord.app_commands.command(name="ping", description="Check bot latency and responsiveness")
    async def ping(self, interaction: discord.Interaction):
        """Enhanced ping command with detailed latency information"""
        try:
            # Measure response time
            start_time = time.perf_counter()
            await interaction.response.defer()
            response_time = (time.perf_counter() - start_time) * 1000

            # Get bot latency
            bot_latency = round(self.bot.latency * 1000, 2)

            # Create embed with latency information
            embed = discord.Embed(
                title="🏓 Pong!",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="Bot Latency", 
                value=f"`{bot_latency}ms`", 
                inline=True
            )
            embed.add_field(
                name="Response Time", 
                value=f"`{response_time:.2f}ms`", 
                inline=True
            )
            
            # Add status indicator based on latency
            if bot_latency < 100:
                status = "🟢 Excellent"
            elif bot_latency < 200:
                status = "🟡 Good"
            elif bot_latency < 500:
                status = "🟠 Fair"
            else:
                status = "🔴 Poor"
                
            embed.add_field(
                name="Connection Status", 
                value=status, 
                inline=True
            )
            
            embed.set_footer(text="Bot is operational and ready to serve!")
            embed.timestamp = discord.utils.utcnow()

            await interaction.followup.send(embed=embed)
            
            logger.info(f"Ping command executed - Bot latency: {bot_latency}ms, Response time: {response_time:.2f}ms")

        except Exception as e:
            logger.error(f"Error in ping command: {e}")
            try:
                await interaction.followup.send("❌ An error occurred while checking latency.", ephemeral=True)
            except:
                pass

async def setup(bot):
    await bot.add_cog(PingCog(bot))
