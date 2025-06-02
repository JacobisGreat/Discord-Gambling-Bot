import discord
from discord.ext import commands
import json

class Leaderboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="leaderboard", description="Show the leaderboard for most coin-flipped and most deposited.")
    async def leaderboard(self, ctx):
        """
        Command to display two leaderboards: Most Money Coin Flipped and Most Deposited.
        Usage: /leaderboard
        """
        try:
            # Load the necessary JSON files
            with open("balances.json", "r") as f:
                balances = json.load(f)

            with open("gameNumber.json", "r") as f:
                game_data = json.load(f)  # Tracks money gambled in coin flips

            with open("deposits.json", "r") as f:
                deposits = json.load(f)  # Tracks total deposits

            # Sort users by most money coin flipped
            coin_flipped_leaderboard = sorted(game_data.items(), key=lambda x: x[1], reverse=True)

            # Sort users by most money deposited
            deposited_leaderboard = sorted(deposits.items(), key=lambda x: x[1], reverse=True)

            # Build the leaderboard strings
            coin_flipped_str = ""
            for i, (user_id, amount) in enumerate(coin_flipped_leaderboard[:10], start=1):  # Top 10
                user = await self.bot.fetch_user(int(user_id))
                username = user.display_name if user else "Unknown User"
                coin_flipped_str += f"**{i}. {username}** - ${amount:.2f}\n"

            deposited_str = ""
            for i, (user_id, amount) in enumerate(deposited_leaderboard[:10], start=1):  # Top 10
                user = await self.bot.fetch_user(int(user_id))
                username = user.display_name if user else "Unknown User"
                deposited_str += f"**{i}. {username}** - ${amount:.2f}\n"

            # Create an embed to display the leaderboards
            embed = discord.Embed(
                title="🏆 Leaderboard",
                color=0x000000  # Black color
            )
            embed.add_field(name="💰 Most Money Coin Flipped", value=coin_flipped_str if coin_flipped_str else "No data available.", inline=False)
            embed.add_field(name="📥 Most Deposited", value=deposited_str if deposited_str else "No data available.", inline=False)
            embed.set_footer(text="Keep flipping and depositing to climb the leaderboard!")

            # Send the embed
            await ctx.send(embed=embed)

        except Exception as e:
            # Handle any errors
            await ctx.send("⚠️ An error occurred while fetching the leaderboard.")
            print(f"Error in leaderboard command: {e}")

# Setup function to add the cog to the bot
async def setup(bot):
    await bot.add_cog(Leaderboard(bot))