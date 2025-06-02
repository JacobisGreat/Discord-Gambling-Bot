# Crypto Discord Bot 🎲💰

A feature-rich Discord bot for cryptocurrency-based gambling and wallet management. This bot allows users to deposit crypto, play games like coinflip, tip other users, and manage their balances within Discord servers.

## Features 🌟

### 🎯 Gambling Games
- **Coinflip**: Bet on heads or tails with other users or against the bot
- **Leaderboard**: Track top players and their winnings

### 💎 Cryptocurrency Support
- **Multi-currency**: Supports Bitcoin (BTC), Litecoin (LTC), and Tether (USDT@TRX)
- **Real-time pricing**: Live USD conversion using CoinGecko API
- **Automated deposits**: Webhook-based deposit tracking with confirmations

### 💸 Wallet Management
- **Balance tracking**: Individual user balance management
- **Deposits**: Generate unique wallet addresses for deposits
- **Withdrawals**: Send crypto to external wallets
- **Tipping**: Send funds between Discord users

### 🛠️ Admin Features
- **Balance management**: Admins can set user balances
- **Transaction monitoring**: Real-time deposit and withdrawal tracking
- **Support tickets**: Built-in ticket system for user support

### ⚡ Performance Optimizations
- **Caching system**: Optimized data loading with TTL caching
- **Async operations**: Non-blocking I/O for better performance
- **Rate limiting**: Price API caching to prevent rate limits

## Installation 🚀

### Prerequisites
- Python 3.8+
- Discord Bot Token
- ngrok (for webhook handling)
- Cryptocurrency wallet API access

### 1. Clone the Repository
```bash
git clone <repository-url>
cd crypto-discord-bot
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Setup
Create a `.env` file in the root directory:
```env
DISCORD_TOKEN=your_discord_bot_token
# Add other necessary API keys and configuration
```

### 4. Initialize Data Files
Create the following JSON files in the root directory:
- `balances.json`: `{}`
- `wallets.json`: `{}`
- `deposits.json`: `{}`
- `withdrawals.json`: `{}`
- `gameNumber.json`: `{"coinflip": 1}`
- `ticket_status.json`: `{}`

### 5. Run the Bot
```bash
python bot.py
```

## Usage 📖

### Basic Commands

#### Balance Management
- `!balance` - Check your current balance
- `!deposit` - Generate a deposit address
- `!withdraw <amount> <currency> <address>` - Withdraw funds

#### Gaming
- `/coinflip <amount> <side>` - Start a coinflip game
  - Choose heads or tails
  - Other users can join or you can call the bot
- `!leaderboard` - View top players

#### Social Features
- `!tip <user> <amount>` - Tip another user
- `!ping` - Check bot responsiveness

#### Admin Commands (Restricted)
- `!setbal <user> <amount>` - Set user balance
- Ticket system commands for support

### Example Gameplay

1. **Deposit funds**: Use `!deposit` to get a wallet address
2. **Wait for confirmation**: Bot will notify you when deposits are confirmed
3. **Start gambling**: Use `/coinflip 10 heads` to bet $10 on heads
4. **Compete**: Other users can join your game or you can play against the bot
5. **Win/Lose**: Winnings are automatically added to your balance

## Project Structure 📁

```
├── bot.py                 # Main bot file with core functionality
├── cogs/                  # Bot command modules
│   ├── balance.py        # Balance checking commands
│   ├── coinflip.py       # Coinflip game logic
│   ├── deposit.py        # Deposit address generation
│   ├── deposits.py       # Deposit tracking
│   ├── leaderboard.py    # Player rankings
│   ├── ping.py           # Basic ping command
│   ├── setbal.py         # Admin balance management
│   ├── ticket.py         # Support ticket system
│   ├── tip.py            # User tipping system
│   ├── withdraw.py       # Withdrawal processing
│   └── withdraws.py      # Withdrawal tracking
├── requirements.txt       # Python dependencies
├── balances.json         # User balance storage
├── wallets.json          # Wallet address mappings
├── deposits.json         # Deposit transaction records
├── withdrawals.json      # Withdrawal transaction records
├── gameNumber.json       # Game numbering system
└── ticket_status.json    # Support ticket statuses
```

## Technical Details ⚙️

### Architecture
- **Discord.py**: Modern async Discord API wrapper
- **Flask**: Webhook server for crypto callbacks
- **ngrok**: Tunnel for webhook accessibility
- **aiofiles**: Async file I/O operations
- **CoinGecko API**: Real-time cryptocurrency pricing

### Data Storage
- JSON-based file storage for simplicity
- Cached data loading with TTL for performance
- Async file operations to prevent blocking

### Security Features
- Input validation for all user commands
- Balance verification before transactions
- Admin-only commands with permission checks
- Error handling and logging throughout

### Performance Optimizations
- LRU cache for price data (60-second TTL)
- Async operations for all I/O
- Optimized callback handling
- Reduced file I/O with caching

## Contributing 🤝

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License 📝

This project is provided as-is for educational purposes. Please ensure compliance with local laws regarding cryptocurrency and gambling applications.

## Support 💬

For support, open a ticket using the bot's built-in ticket system or create an issue in this repository.

## Disclaimer ⚠️

This bot involves cryptocurrency transactions and gambling mechanics. Use responsibly and ensure compliance with your local laws and Discord's Terms of Service. 