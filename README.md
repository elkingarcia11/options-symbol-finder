# Options Symbol Finder

A Python tool for fetching option chain data from Charles Schwab API, specifically designed to get option symbols for the 7 closest strikes (current +3 above, +3 below) for both calls and puts at the closest expiration date.

## Features

- 🔐 **Schwab API Integration**: Uses Charles Schwab authentication module for secure API access
- 📊 **Option Chain Analysis**: Fetches option chains and identifies closest strikes
- 🎯 **Precise Strike Selection**: Returns 7 strikes centered around the current underlying price
- 📅 **Flexible Expiration**: Finds closest expiration date ≥ specified days to expiration
- 🔄 **Multi-Symbol Support**: Process multiple symbols simultaneously
- ☁️ **Cloud Storage**: Automatic token management with Google Cloud Storage

## Prerequisites

- Python 3.6+
- Charles Schwab Developer Account
- Google Cloud Storage Account (for token management)
- Schwab API credentials

## Installation

1. **Clone the repository with submodules:**

   ```bash
   git clone --recursive <repository-url>
   cd options-data-manager
   ```

2. **Create and activate virtual environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Initialize submodules:**
   ```bash
   git submodule update --init --recursive
   ```

## Setup

### 1. Schwab API Credentials

Create a `.env` file in the project root:

```env
SCHWAB_APP_KEY=your_app_key_here
SCHWAB_APP_SECRET=your_app_secret_here
GCS_BUCKET_NAME=your_gcs_bucket_name
GOOGLE_APPLICATION_CREDENTIALS=/path/to/your/service-account-key.json
```

### 2. Get Schwab API Credentials

1. Visit the [Charles Schwab Developer Portal](https://developer.schwab.com/)
2. Create a developer account
3. Register a new application
4. Note your App Key and App Secret
5. Set your redirect URI to `https://127.0.0.1`

### 3. Google Cloud Storage Setup

1. Create a Google Cloud Storage bucket for token storage
2. Set up a service account with Storage Object Admin permissions
3. Download the service account key (JSON format)
4. Configure the `GOOGLE_APPLICATION_CREDENTIALS` environment variable

## Usage

### Basic Usage

```python
from options_data_manager import OptionsDataManager

# Initialize the manager
manager = OptionsDataManager()

# Get option symbols for SPY with 2 DTE
symbols = ['SPY']
days_to_expiration = 2

result = manager.get_option_symbols_for_multiple_symbols(symbols, days_to_expiration)

# Print results
for symbol, option_data in result.items():
    print(f"\n📊 {symbol} Option Symbols:")
    print(f"Calls: {option_data['calls']}")
    print(f"Puts: {option_data['puts']}")
```

### Multiple Symbols

```python
# Get option symbols for multiple symbols
symbols = ['SPY', 'QQQ', 'AAPL']
days_to_expiration = 5

result = manager.get_option_symbols_for_multiple_symbols(symbols, days_to_expiration)
```

### Run from Command Line

```bash
python options-data-manager.py
```

## API Reference

### OptionsDataManager Class

#### `__init__(auth=None)`

Initialize the options data manager.

**Parameters:**

- `auth` (SchwabAuth, optional): Schwab authentication instance

#### `get_expiration_chain(symbol)`

Fetch the expiration chain for a given symbol.

**Parameters:**

- `symbol` (str): Stock symbol (e.g., 'SPY')

**Returns:**

- `List[Dict]`: List of expiration dates and details

#### `find_expiration_date(symbol, days_to_expiration)`

Find the closest expiration date ≥ specified days to expiration.

**Parameters:**

- `symbol` (str): Stock symbol
- `days_to_expiration` (int): Minimum days to expiration

**Returns:**

- `Optional[str]`: Expiration date in YYYY-MM-DD format

#### `get_all_option_chains(symbol, expiration_date)`

Fetch all option chains for a symbol and expiration date.

**Parameters:**

- `symbol` (str): Stock symbol
- `expiration_date` (str): Expiration date in YYYY-MM-DD format

**Returns:**

- `Dict`: Option chain data

#### `get_option_symbols(symbol, expiration_date)`

Get option symbols for 7 closest strikes (current +3 above, +3 below).

**Parameters:**

- `symbol` (str): Stock symbol
- `expiration_date` (str): Expiration date in YYYY-MM-DD format

**Returns:**

- `Dict[str, List[str]]`: Dictionary with 'calls' and 'puts' lists

#### `get_option_symbols_for_multiple_symbols(symbols, days_to_expiration)`

Main function to get option symbols for multiple symbols.

**Parameters:**

- `symbols` (List[str]): List of stock symbols
- `days_to_expiration` (int): Minimum days to expiration

**Returns:**

- `Dict[str, Dict[str, List[str]]]`: Dictionary with symbol as key and option data as values

## Workflow

1. **Input**: Symbol(s) and days to expiration
2. **Get Current Price**: Fetch current underlying price from Schwab API
3. **Find Expiration**: Locate closest expiration date ≥ input DTE
4. **Get Option Chains**: Fetch all available strikes for the expiration
5. **Find Closest Strike**: Identify strike price closest to current underlying price
6. **Select 7 Strikes**: Return strikes (current +3 above, +3 below) for calls and puts
7. **Return Symbols**: Provide option symbols for the selected strikes

## Example Output

```
🔍 Processing SPY...
📅 SPY expiration date: 2024-01-19
✅ SPY: 7 calls, 7 puts

📊 SPY Option Symbols:
Calls: ['SPY   240119C00480000', 'SPY   240119C00485000', ...]
Puts: ['SPY   240119P00480000', 'SPY   240119P00485000', ...]
```

## Dependencies

- `httpx`: HTTP client for API requests
- `google-cloud-storage`: Cloud storage integration
- `python-dotenv`: Environment variable management
- `requests`: HTTP library
- `pytest`: Testing framework

## File Structure

```
options-data-manager/
├── options-data-manager.py          # Main application
├── requirements.txt                 # Python dependencies
├── README.md                        # This file
├── .env                             # Environment variables (create this)
├── service-account-credentials.json # GCS credentials
└── charles-schwab-authentication-module/  # Schwab auth submodule
    ├── schwab_auth.py
    ├── requirements.txt
    └── gcs-python-module/           # GCS submodule
```

## Error Handling

The application includes comprehensive error handling for:

- Missing environment variables
- API authentication failures
- Network connectivity issues
- Invalid symbol or expiration date
- Missing option chain data

## Troubleshooting

### Common Issues

1. **Import Error**: Ensure submodules are initialized with `git submodule update --init --recursive`
2. **Authentication Error**: Verify Schwab API credentials in `.env` file
3. **GCS Error**: Check Google Cloud Storage credentials and bucket permissions
4. **No Option Data**: Verify symbol exists and has options available

### Debug Mode

Enable debug output by setting environment variable:

```bash
export DEBUG=true
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License.

## Disclaimer

This tool is for educational and development purposes. Always follow Charles Schwab's API terms of service and rate limiting guidelines.

## Support

For issues related to:

- **Schwab API**: Contact Charles Schwab Developer Support
- **This Tool**: Open an issue in this repository
