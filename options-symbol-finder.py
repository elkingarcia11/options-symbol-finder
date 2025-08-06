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

    def get_regular_hours_price(self, symbol: str) -> float:
        """
        Get the regular trading hours price for the underlying symbol.
        Uses open price (after settling) or previous close, avoiding pre-market/after-hours gaps.
        Waits until 9:30:30 AM ET if market just opened to let prices settle.
        
        Args:
            symbol (str): The stock symbol (e.g., 'AAPL')
            
        Returns:
            float: Regular session price
        """
        try:
            # Wait for market to settle if we're just after opening
            self._wait_for_market_settlement()
            
            # Get fresh token
            access_token = self.auth.get_valid_access_token(use_gcs_refresh_token=True)
            if not access_token:
                raise Exception("Failed to get valid access token")
            
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Accept': 'application/json'
            }
            
            # Get quote data which includes regular session prices
            url = f"https://api.schwabapi.com/marketdata/v1/quotes?symbols={symbol}"
            
            with httpx.Client() as client:
                response = client.get(url, headers=headers)
                
            if response.status_code != 200:
                raise Exception(f"Quote request failed: {response.status_code} - {response.text}")
            
            quote_data = response.json()
            
            if symbol not in quote_data:
                raise Exception(f"No quote data found for {symbol}")
            
            quote = quote_data[symbol]
            
            # Use lastPrice from quote section
            if 'quote' in quote and 'lastPrice' in quote['quote'] and quote['quote']['lastPrice'] > 0:
                regular_price = quote['quote']['lastPrice']
                print(f"💰 Using last price for {symbol}: ${regular_price:.2f}")
                return regular_price
            
            else:
                raise Exception(f"No valid lastPrice found in quote data for {symbol}")
                
        except Exception as e:
            print(f"❌ Error getting regular hours price for {symbol}: {e}")
            return 0
    
    def _wait_for_market_settlement(self):
        """
        Wait until 9:31 AM after market open for prices to settle after opening auction.
        This avoids selecting strikes based on opening auction volatility and gives
        a full minute for market makers to establish proper spreads.
        """
        try:
            from datetime import datetime, time
            import pytz
            import time as time_module
            
            # Define ET timezone and market settlement time
            et_tz = pytz.timezone('US/Eastern')
            
            now_et = datetime.now(et_tz)
            current_time = now_et.time()
            current_date = now_et.date()
            
            # Check if it's a weekday and within the settlement window
            if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                market_opens = time(9, 30, 0)   # 9:30:00 AM ET
                settlement_time = time(9, 31, 0)  # 9:31:00 AM ET (1 full minute)
                
                # If we're between 9:30:00 and 9:31:00, wait for settlement
                if market_opens <= current_time < settlement_time:
                    settlement_dt = datetime.combine(current_date, settlement_time)
                    settlement_dt = et_tz.localize(settlement_dt)
                    
                    wait_seconds = (settlement_dt - now_et).total_seconds()
                    
                    if wait_seconds > 0:
                        print(f"⏳ Market just opened, waiting {wait_seconds:.0f}s until 9:31 AM for price settlement...")
                        print(f"   This ensures strikes are based on settled prices, not opening auction volatility")
                        time_module.sleep(wait_seconds)
                        print(f"✅ Price settlement period complete (9:31 AM), proceeding with strike generation")
                        
        except Exception as e:
            # Don't fail the whole process if settlement wait fails
            print(f"⚠️ Warning: Could not check market settlement timing: {e}")

    def get_option_symbols(self, symbol: str, expiration_date: str) -> Dict[str, List[str]]:
        """
        Get option symbols using round down/up strategy for strike selection.
        Uses regular trading hours price and waits until 9:31 AM for price settlement.
        
        Market Timing Strategy:
        - Waits until 9:31 AM (1 minute after open) for price settlement
        - Uses openPrice > closePrice > lastPrice priority for pricing
        - Avoids pre-market/after-hours gaps and opening auction volatility
        
        Strike Selection Strategy (4 strikes total):
        CALLS (2 strikes below current price):
        - Round down (current price): floor of current price
        - Round down - 1: one strike below floor
        
        PUTS (2 strikes above current price):  
        - Round up (current price): ceil of current price
        - Round up + 1: one strike above ceil
        
        Example: Price $631.50 → Calls [C630, C631] + Puts [P632, P633]
        
        Args:
            symbol (str): The stock symbol (e.g., 'AAPL')
            expiration_date (str): The expiration date in YYYY-MM-DD format
            
        Returns:
            Dict[str, List[str]]: Dictionary with 'calls' and 'puts' lists containing option symbols for up to 4 strikes
        """
        try:
            # Get all option chains in one call
            all_chains = self.get_all_option_chains(symbol, expiration_date)
            
            option_symbols = {
                'calls': [],
                'puts': [],
                'strikes': {
                    'calls': [],
                    'puts': []
                }
            }
            
            # Get regular trading hours price instead of current option chain price
            underlying_price = self.get_regular_hours_price(symbol)
            
            if underlying_price <= 0:
                # Fallback to option chain price if regular hours price fails
                underlying_price = all_chains.get('underlyingPrice', 0)
                print(f"⚠️ Fallback to option chain price for {symbol}: ${underlying_price:.2f}")
            
            print(f"🎯 Strike selection for {symbol} based on price: ${underlying_price:.2f}")
            
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
            
            # Sort strikes
            call_strikes.sort()
            put_strikes.sort()
            
            # Calculate target strikes: calls below current price, puts above current price
            round_down_strike = int(underlying_price)  # Floor of current price
            round_up_strike = round_down_strike + 1    # Ceiling of current price
            
            # CALLS: Track 2 strikes below current price (round down, round down - 1)
            target_call_strikes = [
                round_down_strike,      # Round down (current price)
                round_down_strike - 1   # Round down - 1
            ]
            
            # PUTS: Track 2 strikes above current price (round up, round up + 1)  
            target_put_strikes = [
                round_up_strike,        # Round up (current price)
                round_up_strike + 1     # Round up + 1
            ]
            
            print(f"🎯 Price ${underlying_price:.2f} → Calls {target_call_strikes} | Puts {target_put_strikes}")
            
            # Filter to only include strikes that actually exist in the option chain
            selected_call_strikes = [strike for strike in target_call_strikes if strike in call_strikes]
            selected_put_strikes = [strike for strike in target_put_strikes if strike in put_strikes]
            
            print(f"📈 Available call strikes: {selected_call_strikes}")
            print(f"📉 Available put strikes: {selected_put_strikes}")
            
            # Store the selected strikes for reference
            option_symbols['strikes']['calls'] = selected_call_strikes
            option_symbols['strikes']['puts'] = selected_put_strikes
            
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
    symbol_finder = OptionsSymbolFinder()
    
    # Get option symbols for AAPL with 2 DTE
    symbols = ['SPY', 'QQQ']
    days_to_expiration = 2
    
    result = symbol_finder.get_option_symbols_for_multiple_symbols(symbols, days_to_expiration)
    
    for symbol, option_data in result.items():
        print(f"\n📊 {symbol} Option Symbols:")
        print(f"Calls: {option_data['calls']}")
        print(f"Puts: {option_data['puts']}")

if __name__ == "__main__":
    main()