import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import requests
from datetime import datetime

class WithdrawalView(discord.ui.View):
    def __init__(self, bot, user_id, currency, amount, address, channel_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.user_id = user_id
        self.currency = currency
        self.amount = amount
        self.address = address
        self.channel_id = channel_id  # Channel to update the processing embed

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        # Replace user embed with the "Processing" embed
        channel = await self.bot.fetch_channel(self.channel_id)
        processing_embed = discord.Embed(
            description=":hourglass_flowing_sand: Withdrawal is processing...",
            color=discord.Color.orange()
        )
        message = await channel.send(embed=processing_embed)

        # Send admin embed to admin channel
        admin_channel_id = int(os.getenv("withdrawl"))
        admin_channel = self.bot.get_channel(admin_channel_id)
        if admin_channel:
            admin_embed = discord.Embed(
                title="New Withdrawal Request",
                description=f"User: <@{self.user_id}>\nCurrency: {self.currency.upper()}\nAmount: ${self.amount:.2f} USD\n"
                            f"Address: `{self.address}`",
                color=discord.Color.orange()
            )
            admin_embed.add_field(name="Request ID", value=f"{message.id}", inline=True)
            admin_embed.set_footer(text="Admin confirmation required.")
            admin_view = AdminView(self.bot, self.user_id, self.currency, self.amount, self.address, message.id, channel.id)
            await admin_channel.send(embed=admin_embed, view=admin_view)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        # Refund user and notify cancellation
        with open("balances.json", "r") as f:
            balances = json.load(f)
        if str(self.user_id) in balances:
            balances[str(self.user_id)] += self.amount
        with open("balances.json", "w") as f:
            json.dump(balances, f, indent=4)

        embed = discord.Embed(
            description="Withdrawal request canceled. Your balance has been refunded.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

class AdminView(discord.ui.View):
    def __init__(self, bot, user_id, currency, amount, address, request_id, user_channel_id):
        super().__init__(timeout=None)
        self.bot = bot
        self.user_id = user_id
        self.currency = currency
        self.amount = amount
        self.address = address
        self.request_id = request_id
        self.user_channel_id = user_channel_id

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        try:
            account = os.getenv("account")
            transfer_key = os.getenv("transfer_key")

            # Fetch exchange rate and convert USD to crypto
            def fetch_exchange_rate(currency):
                crypto_map = {
                    "btc": "bitcoin",
                    "ltc": "litecoin",
                    "eth": "ethereum",
                    "usdt@trx": "tether"
                }
                crypto_name = crypto_map.get(currency)
                if not crypto_name:
                    return None
                url = f"https://api.coingecko.com/api/v3/simple/price?ids={crypto_name}&vs_currencies=usd"
                response = requests.get(url)
                if response.status_code == 200:
                    return response.json().get(crypto_name, {}).get("usd")
                return None

            exchange_rate = fetch_exchange_rate(self.currency)
            if not exchange_rate:
                await interaction.followup.send(
                    f"Failed to fetch exchange rate for {self.currency.upper()}. Please try again later.",
                    ephemeral=True
                )
                return

            crypto_amount = self.amount / exchange_rate  # Amount in cryptocurrency

            def convert_to_smallest_unit(amount, currency):
                if currency in ["btc", "ltc"]:
                    return int(amount * 100_000_000)  # 8 decimal places
                elif currency == "eth":
                    return int(amount * 10**18)  # 18 decimal places
                elif currency == "usdt@trx":
                    return int(amount * 10**6)  # 6 decimal places
                return int(amount)

            smallest_unit_amount = convert_to_smallest_unit(crypto_amount, self.currency)

            # Fetch wallet balance
            balance_url = f"https://apirone.com/api/v2/accounts/{account}/balance"
            balance_response = requests.get(balance_url)
            if balance_response.status_code != 200:
                await interaction.followup.send(
                    f"Failed to retrieve account balance. Status Code: {balance_response.status_code}, Response: {balance_response.text}",
                    ephemeral=True
                )
                return

            balance_data = balance_response.json()
            available_balance = 0
            for item in balance_data.get("balance", []):
                if item["currency"] == self.currency:
                    available_balance = item["available"]
                    break

            if available_balance < smallest_unit_amount:
                available_in_standard_units = available_balance / 100_000_000  # Adjust for LTC
                requested_in_standard_units = smallest_unit_amount / 100_000_000  # Adjust for LTC
                await interaction.followup.send(
                    f"Not enough funds. Available: {available_in_standard_units:.8f} {self.currency.upper()}, "
                    f"Requested: {requested_in_standard_units:.8f} {self.currency.upper()}",
                    ephemeral=True
                )
                return

            # Prepare and send the withdrawal request
            url = f"https://apirone.com/api/v2/accounts/{account}/transfer"
            headers = {'Content-Type': 'application/json'}
            payload = {
                "currency": self.currency,
                "transfer-key": transfer_key,
                "destinations": [{"address": self.address, "amount": smallest_unit_amount}],
                "fee": "normal",
                "subtract-fee-from-amount": True
            }

            response = requests.post(url, headers=headers, json=payload)

            if response.status_code == 200 and response.content:
                response_data = response.json()
                print(f"Response Data: {response_data}")

                # Extract TXID directly from the response
                tx_hash = "N/A"
                if "txs" in response_data and isinstance(response_data["txs"], list) and len(response_data["txs"]) > 0:
                    tx_hash = response_data["txs"][0]

                # Log the withdrawal
                log_withdrawal(self.user_id, self.amount, self.currency, tx_hash, int(datetime.now().timestamp()))

                # Map currency codes to full blockchain names for the explorer
                blockchain_names = {
                    "btc": "bitcoin",
                    "ltc": "litecoin",
                    "eth": "ethereum",
                    "usdt@trx": "tether"
                }
                blockchain_name = blockchain_names.get(self.currency, self.currency)

                # Format the URL for the blockchain explorer
                explorer_url = f"https://blockchair.com/{blockchain_name}/transaction/{tx_hash}?from=apirone"

                # Update the user's embed with the real TXID and the explorer link
                user_channel = self.bot.get_channel(self.user_channel_id)
                if user_channel:
                    message = await user_channel.fetch_message(self.request_id)
                    confirm_embed = discord.Embed(
                        description=f":white_check_mark: Withdrawal confirmed! Your {blockchain_name.capitalize()} payment of **${self.amount:.2f}** has been sent successfully.\n"
                                    f"Transaction ID: [View Transaction]({explorer_url})",
                        color=discord.Color.green()
                    )
                    await message.edit(embed=confirm_embed)
                    # Notify the user with a mention
                    await user_channel.send(f"<@{self.user_id}>, your withdrawal has been confirmed!")

            else:
                # Handle API errors
                user_channel = self.bot.get_channel(self.user_channel_id)
                if user_channel:
                    message = await user_channel.fetch_message(self.request_id)
                    error_embed = discord.Embed(
                        description=f":x: Withdrawal failed. Status Code: {response.status_code}, Response: {response.text}",
                        color=discord.Color.red()
                    )
                    await message.edit(embed=error_embed)
                await interaction.followup.send(
                    f"Failed to process withdrawal. Status Code: {response.status_code}, Response: {response.text}",
                    ephemeral=False
                )

        except Exception as e:
            # Handle unexpected errors
            print(f"Unexpected error during withdrawal: {str(e)}")
            user_channel = self.bot.get_channel(self.user_channel_id)
            if user_channel:
                message = await user_channel.fetch_message(self.request_id)
                error_embed = discord.Embed(
                    description=":x: Withdrawal failed due to an unexpected error. Please contact support.",
                    color=discord.Color.red()
                )
                await message.edit(embed=error_embed)
            await interaction.followup.send(f"Error during withdrawal: {str(e)}", ephemeral=False)







    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(view=self)

        # Update the processing embed in the user's channel to show cancellation
        user_channel = self.bot.get_channel(self.user_channel_id)
        if user_channel:
            message = await user_channel.fetch_message(self.request_id)
            deny_embed = discord.Embed(
                description=":x: Withdrawal canceled by the admin.",
                color=discord.Color.red()
            )
            await message.edit(embed=deny_embed)

def log_withdrawal(user_id, amount, currency, tx_hash, timestamp):
    """Logs withdrawal details to withdrawals.json."""
    try:
        with open("withdrawals.json", "r") as f:
            withdrawals = json.load(f)
    except FileNotFoundError:
        withdrawals = {}

    if user_id not in withdrawals:
        withdrawals[user_id] = []

    withdrawals[user_id].append({
        "currency": currency,
        "amount": amount,
        "tx_hash": tx_hash,
        "timestamp": timestamp
    })

    with open("withdrawals.json", "w") as f:
        json.dump(withdrawals, f, indent=4)

class WithdrawCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="withdraw", description="Withdraw your balance to a specified address")
    @app_commands.choices(currency=[
        app_commands.Choice(name="Bitcoin", value="btc"),
        app_commands.Choice(name="Litecoin", value="ltc"),
        app_commands.Choice(name="Ethereum", value="eth"),
        app_commands.Choice(name="Tether (USDT@TRX)", value="usdt@trx")
    ])
    async def withdraw(self, interaction: discord.Interaction, currency: app_commands.Choice[str], amount: app_commands.Range[float, 0.01, None], address: str):
        user_id = str(interaction.user.id)

        with open("balances.json", "r") as f:
            balances = json.load(f)

        if user_id not in balances or balances[user_id] < amount:
            await interaction.response.send_message("You don't have enough balance to make this withdrawal.", ephemeral=True)
            return

        balances[user_id] -= amount
        with open("balances.json", "w") as f:
            json.dump(balances, f, indent=4)

        embed = discord.Embed(
            title="Withdrawal Request",
            description=f"Currency: {currency.name}\nAmount: **${amount:.2f}**\nAddress: `{address}`\n\nPlease confirm or deny this request.",
            color=discord.Color.orange()
        )
        view = WithdrawalView(self.bot, user_id, currency.value, amount, address, interaction.channel.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

async def setup(bot):
    await bot.add_cog(WithdrawCog(bot))
