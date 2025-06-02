import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View
import json
import os
import requests

# Define the paths for wallet and ticket status files
WALLET_FILE = "wallets.json"
TICKET_STATUS_FILE = "ticket_status.json"

# Define constants for cryptocurrencies and API URL for address generation
CRYPTOCURRENCIES = ["btc", "ltc", "usdt@trx"]
API_URL = "https://apirone.com/api/v2/accounts/apr-6fdfe29aad0a408dca1607d12c5e63e2/addresses"

# Ensure the necessary JSON files exist and are initialized
for file in [WALLET_FILE, TICKET_STATUS_FILE]:
    if not os.path.isfile(file):
        with open(file, "w") as f:
            json.dump({}, f)

# Function to load data from a JSON file
def load_json(file_path):
    with open(file_path, "r") as f:
        return json.load(f)

# Function to save data to a JSON file
def save_json(file_path, data):
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)

# Function to generate a new wallet address for a specified cryptocurrency
def generate_wallet(cryptocurrency):
    try:
        url = f"https://apirone.com/api/v2/accounts/apr-6fdfe29aad0a408dca1607d12c5e63e2/addresses"
        response = requests.post(url, json={"currency": cryptocurrency})
        
        # Handle cases where the response is not in JSON format or is empty
        if response.status_code == 200 and response.content:
            address_data = response.json()
            if "address" in address_data:
                return address_data["address"]
            else:
                print(f"Error: Address not found in response for {cryptocurrency}. Response: {address_data}")
                return None
        else:
            print(f"Error: Failed to generate {cryptocurrency} address. Status code: {response.status_code}, Response: {response.content}")
            return None
    except Exception as e:
        print(f"Exception occurred while generating {cryptocurrency} address: {str(e)}")
        return None

# Button to show crypto addresses
class CryptoButton(Button):
    def __init__(self):
        super().__init__(label="Crypto", emoji="<:crypto:1290392014839480483>", style=discord.ButtonStyle.secondary, custom_id="crypto_button")

    async def callback(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        # Load wallets from wallets.json
        try:
            with open(WALLET_FILE, "r") as f:
                wallets = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            wallets = {}

        # Check and generate any missing wallet addresses
        if user_id not in wallets:
            wallets[user_id] = {}

        for crypto in CRYPTOCURRENCIES:
            if crypto not in wallets[user_id]:
                new_wallet = generate_wallet(crypto)
                if new_wallet:
                    wallets[user_id][crypto] = new_wallet

        # Save the updated wallet data
        with open(WALLET_FILE, "w") as f:
            json.dump(wallets, f, indent=4)

        # Prepare wallet details
        btc_wallet = wallets[user_id].get('btc', 'Not Available')
        ltc_wallet = wallets[user_id].get('ltc', 'Not Available')
        usdt_wallet = wallets[user_id].get('usdt@trx', 'Not Available')

        # Create the new embed structure
        crypto_embed = discord.Embed(
            title="Crypto Deposits",
            description="You may send any amount of crypto to the addresses below which will automatically be credited once certain confirmations.",
            color=000000
        )

        # Use the provided emotes
        crypto_embed.add_field(name="<:btc:1290391638845165711>  Bitcoin", value=btc_wallet, inline=True)
        crypto_embed.add_field(name="<:ltc:1290391870765138052>  Litecoin", value=ltc_wallet, inline=True)
        crypto_embed.add_field(name="<:tether:1290393776329592855>  Tether (TRC-20)", value=usdt_wallet, inline=True)
        crypto_embed.set_footer(text="Press the buttons below for easy copy paste access.")

        # Create the buttons for each crypto address
        view = View(timeout=None)
        view.add_item(BtcAddressButton(user_id))
        view.add_item(LtcAddressButton(user_id))
        view.add_item(TetherAddressButton(user_id))

        # Send the embed as a non-ephemeral reply without additional messages
        await interaction.response.send_message(embed=crypto_embed, view=view, ephemeral=False)

# Button to send Bitcoin address
class BtcAddressButton(Button):
    def __init__(self, user_id):
        super().__init__(label="", style=discord.ButtonStyle.primary, custom_id="btc_address_button", emoji="<:btc:1290391638845165711>")
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            # Load wallets from the JSON file
            wallets = load_json(WALLET_FILE)
            btc_wallet = wallets.get(self.user_id, {}).get('btc', 'Address not available')
            await interaction.followup.send(content=f"{btc_wallet}", ephemeral=False)
        except Exception as e:
            await interaction.followup.send(f"Failed to get Bitcoin address: {str(e)}", ephemeral=True)
# Button for PayPal
class PaypalButton(Button):
    def __init__(self):
        super().__init__(label="Paypal", style=discord.ButtonStyle.secondary, custom_id="paypal_button", emoji="<:PayPal:1290391956270223360>")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("Coming Soon! Stay tuned.", ephemeral=True)

# Button for Cash App
class CashAppButton(Button):
    def __init__(self):
        super().__init__(label="Cashapp", style=discord.ButtonStyle.secondary, custom_id="cashapp_button", emoji="<:cashapp:1290391927304360067>")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message("Coming Soon! Stay tuned.", ephemeral=True)

# Button to send Litecoin address
class LtcAddressButton(Button):
    def __init__(self, user_id):
        super().__init__(label="", style=discord.ButtonStyle.primary, custom_id="ltc_address_button", emoji="<:ltc:1290391870765138052>")
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            # Load wallets from the JSON file
            wallets = load_json(WALLET_FILE)
            ltc_wallet = wallets.get(self.user_id, {}).get('ltc', 'Address not available')
            await interaction.followup.send(content=f"{ltc_wallet}", ephemeral=False)
        except Exception as e:
            await interaction.followup.send(f"Failed to get Litecoin address: {str(e)}", ephemeral=True)

# Button to send Tether address
class TetherAddressButton(Button):
    def __init__(self, user_id):
        super().__init__(label="", style=discord.ButtonStyle.primary, custom_id="usdt_address_button", emoji="<:tether:1290393776329592855>")
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            # Load wallets from the JSON file
            wallets = load_json(WALLET_FILE)
            usdt_wallet = wallets.get(self.user_id, {}).get('usdt@trx', 'Address not available')
            await interaction.followup.send(content=f"{usdt_wallet}", ephemeral=False)
        except Exception as e:
            await interaction.followup.send(f"Failed to get Tether address: {str(e)}", ephemeral=True)

class TicketButton(Button):
    def __init__(self):
        super().__init__(label="📧 Open Ticket", style=discord.ButtonStyle.primary, custom_id="open_ticket_button")

    async def callback(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user

        # Load ticket status from the file
        ticket_status = load_json(TICKET_STATUS_FILE)

        # Check if user has an existing ticket
        existing_ticket_name = ticket_status.get(str(member.id))
        if existing_ticket_name:
            # Restore access to the existing ticket
            existing_ticket = discord.utils.get(guild.text_channels, name=existing_ticket_name)
            if existing_ticket:
                await existing_ticket.set_permissions(member, read_messages=True, send_messages=True)
                await interaction.response.send_message(
                    f"You already have a ticket opened. Find it here: {existing_ticket.mention}",
                    ephemeral=True
                )
                return

        # Check if a category named "tickets" exists, if not, create it
        category = discord.utils.get(guild.categories, name="tickets")
        if category is None:
            category = await guild.create_category("tickets")

        # Create a new text channel for the ticket under the "tickets" category
        ticket_channel = await category.create_text_channel(f'ticket-{member.display_name.lower()}', overwrites={
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        })

        # Save the ticket status with the channel name
        ticket_status[str(member.id)] = ticket_channel.name
        save_json(TICKET_STATUS_FILE, ticket_status)

        # First embed: Welcome message
        welcome_embed = discord.Embed(
            title="Welcome to HighBetz! To get started, check out your options below.",
            color=0
        )
        welcome_embed.set_footer(text="Close this ticket by reacting with 🔒")

        # Second embed: Options with buttons
        options_embed = discord.Embed(
            title="Please select the currency you will be sending from",
            color=0
        )

        # Define the payment buttons and the Close Ticket button
        buttons = [
            CryptoButton(),  # Crypto button
            PaypalButton(),  # PayPal button
            CashAppButton(),  # Cash App button
            CloseButton()  # Close Ticket button
        ]

        # Create a view and add the buttons to it
        view = View(timeout=None)
        for button in buttons:
            view.add_item(button)

        # Send the two separate embeds in the ticket channel
        await ticket_channel.send(embed=welcome_embed)
        await ticket_channel.send(embed=options_embed, view=view)

        await interaction.response.send_message(f'Ticket created: {ticket_channel.mention}', ephemeral=True)

class CloseButton(Button):
    def __init__(self):
        super().__init__(label="", style=discord.ButtonStyle.danger, custom_id="close_ticket_button", emoji="🔒")  # Only lock emoji without label

    async def callback(self, interaction: discord.Interaction):
        channel = interaction.channel
        member = interaction.user

        # Set permissions to hide the channel from the user who requested the close
        await channel.set_permissions(member, read_messages=False, send_messages=False)

        await interaction.response.send_message(
            "Ticket closed. You can reopen it by clicking the 'Open Ticket' button again.",
            ephemeral=True
        )
        await channel.send(f"{member.mention} has closed this ticket.", delete_after=5)

class Ticket(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ticket_panel", description="Create a new ticket panel for users")
    async def ticket_panel(self, interaction: discord.Interaction):
        # Check if the user has the manage_channels permission
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("You don't have permission to do this.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Deposit here",
            description="Deposit Cryptocurrencies, Cashapp and Paypal by pressing 📧 below.",
            color=000000
        )
        embed.set_footer(
            text="Courtesy of Highnotes",
        )

        button = TicketButton()
        view = View(timeout=None)  # Persistent view for ticket panel
        view.add_item(button)

        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("Ticket panel created.", ephemeral=True)

async def setup(bot):
    # Create a view instance with all items and add it to bot
    view = View(timeout=None)  # Create a persistent view instance
    view.add_item(TicketButton())  # Add TicketButton
    view.add_item(CryptoButton())  # Add CryptoButton
    view.add_item(CloseButton())  # Add CloseButton

    # Register the view with the bot
    bot.add_view(view)  # Register the persistent view with the bot

    await bot.add_cog(Ticket(bot))