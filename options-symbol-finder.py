import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'charles-schwab-authentication-module'))
from schwab_auth import SchwabAuth
import httpx
from typing import Optional, Dict, List
import os
import csv
from datetime import datetime

class OptionsSymbolFinder:
    def __init__(self, auth: Optional[SchwabAuth] = None):
        self.auth = auth or SchwabAuth()
        
    def get_expiration_chain(self, symbol: str) -> List[Dict]:
        """
        Fetch the expiration chain for a given symbol from Schwab's API.
        
        Args:
            symbol (str): The stock symbol (e.g., 'AAPL')
            
        Returns:
            List[Dict]: List of expiration dates and their details
        """
        try:
            # Get fresh token
            access_token = self.auth.get_valid_access_token(use_gcs_refresh_token=True)
            if not access_token:
                raise Exception("Failed to get valid access token")
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            url = f"https://api.schwabapi.com/marketdata/v1/expirationchain?symbol={symbol}"
            
            with httpx.Client() as client:
                response = client.get(url, headers=headers)
                
            if response.status_code != 200:
                raise Exception(f"Expiration chain request failed: {response.status_code} - {response.text}")
            
            data = response.json()
            return data.get('expirationList', [])
            
        except Exception as e:
            print(f"❌ Error getting expiration chain: {e}")
            return []
    
    def find_expiration_date(self, symbol: str, days_to_expiration: int) -> Optional[str]:
        """
        Find the first expiration date that is greater than or equal to the specified days to expiration.
        
        Args:
            symbol (str): The stock symbol (e.g., 'AAPL')
            days_to_expiration (int): Minimum number of days to expiration
            
        Returns:
            Optional[str]: The expiration date in YYYY-MM-DD format, or None if not found
        """
        try:
            expiration_chain = self.get_expiration_chain(symbol)
            if not expiration_chain:
                return None
            
            # Sort by days to expiration
            sorted_chain = sorted(expiration_chain, key=lambda x: x['daysToExpiration'])
            
            # Find the first expiration date that meets or exceeds our target
            for expiration in sorted_chain:
                if expiration['daysToExpiration'] >= days_to_expiration:
                    return expiration['expirationDate']
            
            # If no expiration date meets the criteria, return the furthest expiration
            return sorted_chain[-1]['expirationDate'] if sorted_chain else None
            
        except Exception as e:
            print(f"❌ Error finding expiration date: {e}")
            return None

    def get_all_option_chains(self, symbol: str, expiration_date: str) -> Dict:
        """
        Fetch all option chains for a given symbol and expiration date.
        
        Args:
            symbol (str): The stock symbol (e.g., 'AAPL')
            expiration_date (str): The expiration date in YYYY-MM-DD format
            
        Returns:
            Dict: The option chain data
        """
        try:
            # Get fresh token
            access_token = self.auth.get_valid_access_token(use_gcs_refresh_token=True)
            if not access_token:
                raise Exception("Failed to get valid access token")
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            url = f"https://api.schwabapi.com/marketdata/v1/chains"
            params = {
                'symbol': symbol,
                'contractType': 'ALL',
                'strikeCount': '8',
                'fromDate': expiration_date,
                'toDate': expiration_date
            }
            
            with httpx.Client() as client:
                response = client.get(url, headers=headers, params=params)
                
            if response.status_code != 200:
                raise Exception(f"Option chains request failed: {response.status_code} - {response.text}")
            
            return response.json()
            
        except Exception as e:
            print(f"❌ Error getting option chains: {e}")
            return {}

    def get_option_symbols(self, symbol: str, expiration_date: str) -> Dict[str, List[str]]:
        """
        Get option symbols for the nearest strike price plus 3 strikes above and 3 strikes below for both calls and puts.
        
        Args:
            symbol (str): The stock symbol (e.g., 'AAPL')
            expiration_date (str): The expiration date in YYYY-MM-DD format
            
        Returns:
            Dict[str, List[str]]: Dictionary with 'calls' and 'puts' lists containing option symbols for 7 strikes total
        """
        try:
            # Get all option chains in one call
            all_chains = self.get_all_option_chains(symbol, expiration_date)
            
            option_symbols = {
                'calls': [],
                'puts': []
            }
            
            # Get current underlying price to find nearest strike
            underlying_price = all_chains.get('underlyingPrice', 0)
            
            # Collect all available strikes for calls and puts
            call_strikes = []
            put_strikes = []
            
            # Extract all call strikes
            if 'callExpDateMap' in all_chains:
                for exp_key, strikes in all_chains['callExpDateMap'].items():
                    for strike, options in strikes.items():
                        strike_price = float(strike)
                        call_strikes.append(strike_price)
                        # Get the first call option for this strike
                        for option in options:
                            if option['putCall'] == 'CALL':
                                option_symbols['calls'].append(option['symbol'])
                                break
            
            # Extract all put strikes
            if 'putExpDateMap' in all_chains:
                for exp_key, strikes in all_chains['putExpDateMap'].items():
                    for strike, options in strikes.items():
                        strike_price = float(strike)
                        put_strikes.append(strike_price)
                        # Get the first put option for this strike
                        for option in options:
                            if option['putCall'] == 'PUT':
                                option_symbols['puts'].append(option['symbol'])
                                break
            
            # Sort strikes and find nearest strike
            call_strikes.sort()
            put_strikes.sort()
            
            # Find nearest strike for calls
            nearest_call_strike = min(call_strikes, key=lambda x: abs(x - underlying_price))
            nearest_call_index = call_strikes.index(nearest_call_strike)
            
            # Find nearest strike for puts
            nearest_put_strike = min(put_strikes, key=lambda x: abs(x - underlying_price))
            nearest_put_index = put_strikes.index(nearest_put_strike)
            
            # Get the 7 strikes for calls (nearest + 3 above + 3 below)
            call_start_index = max(0, nearest_call_index - 3)
            call_end_index = min(len(call_strikes), nearest_call_index + 4)
            selected_call_strikes = call_strikes[call_start_index:call_end_index]
            
            # Get the 7 strikes for puts (nearest + 3 above + 3 below)
            put_start_index = max(0, nearest_put_index - 3)
            put_end_index = min(len(put_strikes), nearest_put_index + 4)
            selected_put_strikes = put_strikes[put_start_index:put_end_index]
            
            # Clear and rebuild the option symbols lists with only the selected strikes
            option_symbols['calls'] = []
            option_symbols['puts'] = []
            
            # Get call symbols for selected strikes
            if 'callExpDateMap' in all_chains:
                for exp_key, strikes in all_chains['callExpDateMap'].items():
                    for strike, options in strikes.items():
                        strike_price = float(strike)
                        if strike_price in selected_call_strikes:
                            for option in options:
                                if option['putCall'] == 'CALL':
                                    option_symbols['calls'].append(option['symbol'])
                                    break
            
            # Get put symbols for selected strikes
            if 'putExpDateMap' in all_chains:
                for exp_key, strikes in all_chains['putExpDateMap'].items():
                    for strike, options in strikes.items():
                        strike_price = float(strike)
                        if strike_price in selected_put_strikes:
                            for option in options:
                                if option['putCall'] == 'PUT':
                                    option_symbols['puts'].append(option['symbol'])
                                    break
            
            return option_symbols
            
        except Exception as e:
            print(f"❌ Error getting option symbols: {e}")
            return {'calls': [], 'puts': []}

    def get_option_symbols_for_multiple_symbols(self, symbols: List[str], days_to_expiration: int) -> Dict[str, Dict[str, List[str]]]:
        """
        Get option symbols for multiple symbols with the same days to expiration.
        
        Args:
            symbols (List[str]): List of stock symbols (e.g., ['AAPL', 'SPY'])
            days_to_expiration (int): Minimum number of days to expiration
            
        Returns:
            Dict[str, Dict[str, List[str]]]: Dictionary with symbol as key and 'calls'/'puts' lists as values
        """
        all_option_symbols = {}
        
        for symbol in symbols:
            try:
                print(f"🔍 Processing {symbol}...")
                
                # Get expiration date for this symbol
                expiration_date = self.find_expiration_date(symbol, days_to_expiration)
                if not expiration_date:
                    print(f"❌ No suitable expiration date found for {symbol}")
                    continue
                
                print(f"📅 {symbol} expiration date: {expiration_date}")
                
                # Get option symbols for this symbol
                option_symbols = self.get_option_symbols(symbol, expiration_date)
                
                if not option_symbols['calls'] and not option_symbols['puts']:
                    print(f"❌ No option symbols found for {symbol}")
                    continue
                
                all_option_symbols[symbol] = option_symbols
                print(f"✅ {symbol}: {len(option_symbols['calls'])} calls, {len(option_symbols['puts'])} puts")
                
            except Exception as e:
                print(f"❌ Error processing {symbol}: {e}")
                continue
        
        return all_option_symbols

def main():
    # Example usage
    manager = OptionsDataManager()
    
    # Get option symbols for AAPL with 2 DTE
    symbols = ['SPY', 'QQQ']
    days_to_expiration = 2
    
    result = manager.get_option_symbols_for_multiple_symbols(symbols, days_to_expiration)
    
    for symbol, option_data in result.items():
        print(f"\n📊 {symbol} Option Symbols:")
        print(f"Calls: {option_data['calls']}")
        print(f"Puts: {option_data['puts']}")

if __name__ == "__main__":
    main()