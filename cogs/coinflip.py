import discord
import random
import json
import asyncio
from discord import app_commands
from discord.ext import commands
from datetime import datetime

class CoinflipView(discord.ui.View):
    def __init__(self, initiator_id: int, amount: float, chosen_side: str, game_number: int, start_time: int, bot):
        super().__init__(timeout=120)
        self.initiator_id = initiator_id
        self.amount = amount
        self.chosen_side = chosen_side
        self.opponent_id = None
        self.opponent_is_bot = False
        self.game_started = False
        self.result = None  # Will dynamically determine the result
        self.game_number = game_number
        self.start_time = start_time
        self.bot = bot

    async def update_balance(self, user_id: int, amount: float, won: bool, cancel: bool = False):
        with open("balances.json", "r") as f:
            balances = json.load(f)

        if str(user_id) in balances:
            if won:
                balances[str(user_id)] += amount * 2  # Winner gets double their bet
            elif cancel:
                balances[str(user_id)] += amount  # Refund on cancel
            else:
                balances[str(user_id)] -= amount  # Deduct amount for the loser

        with open("balances.json", "w") as f:
            json.dump(balances, f, indent=4)

    def determine_rigged_outcome(self, user_balance: float):
        """Determine if the game should be rigged based on the bet-to-balance ratio."""
        if self.amount > 0.8 * user_balance:
            # Force the bot to win by selecting the opposite side of the user's choice
            return "Heads" if self.chosen_side.lower() == "tails" else "Tails"
        return None

    def decrease_win_probability(self):
        """Reduce the user's chance of winning after every win."""
        # Default win probability is 50%
        self.win_probability = getattr(self, "win_probability", 0.5)
        self.win_probability = max(self.win_probability - 0.1, 0.1)  # Minimum 10% chance of winning

    def rigged_coinflip(self, user_balance):
        """Determine the coinflip result, possibly rigged based on balance and bet."""
        rigged_result = self.determine_rigged_outcome(user_balance)
        if rigged_result:
            return rigged_result

        # Use a decreasing win probability to make it harder to win
        if random.random() < getattr(self, "win_probability", 0.5):
            return self.chosen_side
        return "Heads" if self.chosen_side.lower() == "tails" else "Tails"

    async def start_countdown(self, interaction: discord.Interaction):
        for i in range(10, 0, -1):
            embed = interaction.message.embeds[0]
            embed.description = f"Game starting in {i} seconds..."
            await interaction.edit_original_response(embed=embed, view=self)
            await asyncio.sleep(1)

        with open("balances.json", "r") as f:
            balances = json.load(f)
        user_balance = balances.get(str(self.initiator_id), 0)

        # Determine the result, possibly rigged
        self.result = self.rigged_coinflip(user_balance)

        # Determine the winner
        winner_id = self.initiator_id if self.result.lower() == self.chosen_side.lower() else self.opponent_id
        loser_id = self.opponent_id if winner_id == self.initiator_id else self.initiator_id
        winner = interaction.guild.get_member(winner_id).mention if winner_id != "PvP Bot" else "PvP Bot"

        if self.result.lower() == self.chosen_side.lower():
            self.decrease_win_probability()

        await self.update_embed_on_completion(interaction, winner, winner_id, loser_id)

    async def update_embed_on_completion(self, interaction: discord.Interaction, winner: str, winner_id: int, loser_id: int):
        embed = interaction.message.embeds[0]
        embed.title = f"Coinflip #{self.game_number} Result!"
        embed.description = f"The coin landed on **{self.result}**!\n\n**{winner}** wins **${self.amount * 2:.2f}**!"
        embed.color = discord.Color.green() if winner_id == self.initiator_id else discord.Color.red()

        await self.update_balance(winner_id, self.amount, won=True)
        await interaction.edit_original_response(embed=embed, view=None)

    @discord.ui.button(label="Join Coinflip", style=discord.ButtonStyle.green, custom_id="join_coinflip")
    async def join_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        with open("balances.json", "r") as f:
            balances = json.load(f)

        if str(interaction.user.id) not in balances or balances[str(interaction.user.id)] < self.amount:
            await interaction.followup.send("You don't have enough balance to join this game.", ephemeral=True)
            return

        if interaction.user.id == self.initiator_id:
            await interaction.followup.send("You can't join your own game!", ephemeral=True)
            return
        if self.opponent_id is None:
            await self.update_balance(interaction.user.id, self.amount, won=False)
            self.opponent_id = interaction.user.id
            await self.update_embed_on_join(interaction)
            await self.start_countdown(interaction)
        else:
            await interaction.followup.send("Someone has already joined the game.", ephemeral=True)

    async def update_embed_on_join(self, interaction: discord.Interaction):
        embed = interaction.message.embeds[0]
        competitor_name = "PvP Bot" if self.opponent_is_bot else interaction.guild.get_member(self.opponent_id).mention
        embed.add_field(name="Competitor", value=f"{competitor_name} **|** {'Heads' if self.chosen_side == 'tails' else 'Tails'}", inline=True)
        embed.add_field(name="Fee", value="$0.00", inline=True)
        embed.title = f"Coinflip #{self.game_number} Ongoing!"
        self.game_started = True
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="Cancel Coinflip", style=discord.ButtonStyle.red, custom_id="cancel_coinflip")
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if interaction.user.id != self.initiator_id:
            await interaction.followup.send("Only the game initiator can cancel the game.", ephemeral=True)
            return
        if self.game_started:
            await interaction.followup.send("You can't cancel the game after someone has joined or the bot has been called.", ephemeral=True)
            return
        await self.update_balance(self.initiator_id, self.amount, won=False, cancel=True)
        embed = discord.Embed(
            title=f"Coinflip #{self.game_number} Canceled!",
            color=discord.Color.red()
        )
        embed.add_field(name="Author", value=f"<@{self.initiator_id}> **|** {self.chosen_side.capitalize()}", inline=True)
        embed.add_field(name="Value", value=f"${self.amount:.3f}", inline=True)
        embed.add_field(name="Started", value=f"<t:{self.start_time}:R>", inline=True)
        embed.set_footer(text="This coinflip was canceled.")
        await interaction.edit_original_response(embed=embed, view=None)
        self.stop()

    @discord.ui.button(label="Call Bot", style=discord.ButtonStyle.blurple, custom_id="call_bot")
    async def call_bot_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        if interaction.user.id != self.initiator_id:
            await interaction.followup.send("Only the game creator can call the bot.", ephemeral=True)
            return

        if self.opponent_id is None:
            self.opponent_id = "PvP Bot"
            self.opponent_is_bot = True
            await self.update_embed_on_join(interaction)
            await self.start_countdown(interaction)


class CoinflipCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def get_game_number(self):
        try:
            with open("gameNumber.json", "r") as f:
                game_data = json.load(f)
        except FileNotFoundError:
            game_data = {"coinflip": 1}
        game_number = game_data.get("coinflip", 1)
        game_data["coinflip"] = game_number + 1
        with open("gameNumber.json", "w") as f:
            json.dump(game_data, f, indent=4)
        return game_number

    @app_commands.command(name="coinflip", description="Start a coinflip game!")
    @app_commands.choices(side=[
        app_commands.Choice(name="Heads", value="heads"),
        app_commands.Choice(name="Tails", value="tails")
    ])
    async def coinflip(self, interaction: discord.Interaction, amount: app_commands.Range[float, 0.01, None], side: app_commands.Choice[str]):
        user_id = interaction.user.id
        with open("balances.json", "r") as f:
            balances = json.load(f)
        if str(user_id) not in balances or balances[str(user_id)] < amount:
            await interaction.response.send_message("You don't have enough balance to place this bet.", ephemeral=True)
            return
        balances[str(user_id)] -= amount
        with open("balances.json", "w") as f:
            json.dump(balances, f, indent=4)
        game_number = await self.get_game_number()
        start_time = int(datetime.now().timestamp())
        embed = discord.Embed(
            title=f"Coinflip #{game_number} Started!",
            description=f"Game started by {interaction.user.mention} betting **${amount:.3f}** on **{side.name.capitalize()}**!",
            color=3066993
        )
        embed.add_field(name="Author", value=f"{interaction.user.mention} **|** {side.name.capitalize()}", inline=True)
        embed.add_field(name="Value", value=f"${amount:.3f}", inline=True)
        embed.add_field(name="Started", value=f"<t:{start_time}:R>", inline=True)
        embed.set_footer(text="You can cancel this coinflip below.")
        view = CoinflipView(user_id, amount, side.value, game_number=game_number, start_time=start_time, bot=self.bot)
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(CoinflipCog(bot))
