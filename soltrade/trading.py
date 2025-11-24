import asyncio
import os
import pandas as pd
import requests
import time
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich import box
from apscheduler.schedulers.background import BlockingScheduler

from soltrade.config import config
from soltrade.log import log_general, log_transaction
from soltrade.strategy import (
    strategy,
    calc_stoploss,
    calc_trailing_stoploss,
    calc_entry_price,
    calc_takeprofit,
    set_position,
)
from soltrade.transactions import perform_swap
from soltrade.wallet import find_balance

config_instance = config()
primary_mint = config_instance.primary_mint
primary_mint_symbol = config_instance.primary_mint_symbol
secondary_mints = config_instance.secondary_mints
secondary_mint_symbols = config_instance.secondary_mint_symbols
api_key = config_instance.api_key
trading_interval_minutes = config_instance.trading_interval_minutes
price_update_seconds = config_instance.price_update_seconds

initial_primary_balance = find_balance(primary_mint)
initial_secondary_balances = [find_balance(mint) for mint in secondary_mints]


def fetch_price(mint: str) -> float:
    """Fetch token price from Jupiter Price API v3 with error handling."""
    url = "https://lite-api.jup.ag/price/v3"
    params = {"ids": mint}
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        response_json = response.json()
        
        mint_data = response_json.get(mint, {})
        price = float(mint_data.get("usdPrice", 0))
        if price == 0:
            log_general.warning(f"Price for {mint} is 0 or not available")
        return price
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            log_general.error("401 Unauthorized: Endpoint requires Pro plan, falling back to lite-api")
        else:
            log_general.error(f"HTTP error fetching price for {mint}: {e}")
        return 0.0
    except Exception as e:
        log_general.error(f"Failed to fetch price for {mint}: {e}")
        return 0.0


initial_primary_price = fetch_price(primary_mint)
initial_secondary_prices = [fetch_price(mint) for mint in secondary_mints]

# Track first run to avoid clearing initial startup messages
_first_run = True

console = Console()


def fetch_candlestick(primary_mint_symbol: str, secondary_mint_symbol: str) -> dict:
    """Fetch candlestick data from CryptoCompare API."""
    url = "https://min-api.cryptocompare.com/data/v2/histominute"
    headers = {"authorization": api_key}
    params = {
        "tsym": primary_mint_symbol,
        "fsym": secondary_mint_symbol,
        "limit": 50,
        "aggregate": trading_interval_minutes,
    }
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        response_json = response.json()
        if response_json.get("Response") == "Error":
            log_general.error(response_json.get("Message"))
            exit()
        return response_json
    except Exception as e:
        log_general.error(f"Failed to fetch candlestick data: {e}")
        exit()


def format_as_money(value):
    return "${:,.2f}".format(value)


def perform_analysis():
    global _first_run
    
    # Clear screen on subsequent runs, skip on first to preserve startup messages
    if not _first_run:
        os.system('cls' if os.name == 'nt' else 'clear')
    else:
        _first_run = False
        
    log_general.debug("Soltrade is analyzing the market; no trade has been executed.")
    data_frames = []

    for secondary_mint, secondary_mint_symbol in zip(
        secondary_mints, secondary_mint_symbols
    ):
        candle_json = fetch_candlestick(primary_mint_symbol, secondary_mint_symbol)
        candle_dict = candle_json["Data"]["Data"]
        columns = ["close", "high", "low", "open", "time"]
        new_df = pd.DataFrame(candle_dict, columns=columns)
        new_df["time"] = pd.to_datetime(new_df["time"], unit="s")
        new_df = strategy(new_df)
        new_df["total_profit"] = 0
        new_df["mint"] = secondary_mint_symbol
        new_df["position"] = False
        data_file_path = f"data/{secondary_mint_symbol}_data.csv"

        try:
            existing_df = read_dataframe_from_csv(data_file_path)
            if existing_df["position"].iat[-1]:
                columns_to_merge = [
                    "position",
                    "entry_price",
                    "takeprofit",
                    "stoploss",
                    "trailing_stoploss",
                    "trailing_stoploss_target",
                ]

                for col in columns_to_merge:
                    new_df[col] = existing_df.iloc[-1][col]

            df = new_df
        except FileNotFoundError:
            df = new_df

        data_frames.append(df)

    combined_df = pd.concat(data_frames, axis=0)
    combined_df.drop_duplicates(subset=["time", "mint"], keep="last", inplace=True)

    console.print(Panel.fit(
        "🔍 [bold yellow]Analyzing Market Data...[/bold yellow]",
        border_style="yellow"
    ))
    console.print("")

    current_primary_balance = find_balance(primary_mint)
    current_secondary_balances = [find_balance(mint) for mint in secondary_mints]
    initial_total_value = (initial_primary_balance * initial_primary_price) + sum(
        initial_secondary_balance * initial_secondary_price
        for initial_secondary_balance, initial_secondary_price in zip(
            initial_secondary_balances, initial_secondary_prices
        )
    )
    current_total_value = (current_primary_balance * fetch_price(primary_mint)) + sum(
        current_secondary_balance * fetch_price(secondary_mint)
        for current_secondary_balance, secondary_mint in zip(
            current_secondary_balances, secondary_mints
        )
    )
    total_profit = current_total_value - initial_total_value
    
    profit_color = "green" if total_profit >= 0 else "red"
    profit_symbol = "📈" if total_profit >= 0 else "📉"
    
    wallet_info = Table.grid(padding=(0, 2))
    wallet_info.add_column(style="bold cyan", justify="right", no_wrap=True)
    wallet_info.add_column(style="white", no_wrap=True)
    
    wallet_info.add_row("💰 Primary Balance:", f"{current_primary_balance:.4f} {primary_mint_symbol}")
    wallet_info.add_row("📌 Reserved for Fees:", f"0.02 {primary_mint_symbol}")
    wallet_info.add_row("💵 Portfolio Value:", format_as_money(current_total_value))
    wallet_info.add_row(f"{profit_symbol} Total Profit:", f"[{profit_color}]{format_as_money(total_profit)}[/{profit_color}]")
    
    console.print(Panel(wallet_info, title="💼 Wallet Overview", border_style="cyan", padding=(1, 2), expand=False))
    console.print("")

    last_rows = combined_df.groupby("mint").tail(1)

    pivot_columns = [
        "close",
        "ema_s",
        "ema_m",
        "upper_bband",
        "lower_bband",
        "rsi",
        "entry",
        "exit",
        "entry_price",
        "stoploss",
        "takeprofit",
        "trailing_stoploss",
        "trailing_stoploss_target",
        "position",
    ]

    pivot_columns = [col for col in pivot_columns if col in last_rows.columns]
    last_rows_pivoted = last_rows.pivot(
        index="mint", columns="time", values=pivot_columns
    )
    last_rows_pivoted.columns = [f"{col[0]}" for col in last_rows_pivoted.columns]
    last_rows_pivoted = last_rows_pivoted.T

    custom_headers = {
        "close": "Price",
        "ema_s": "EMA Short",
        "ema_m": "EMA Medium",
        "upper_bband": "Upper Bollinger Band",
        "lower_bband": "Lower Bollinger Band",
        "rsi": "RSI",
        "entry": "Entry Signal",
        "exit": "Exit Signal",
        "entry_price": "Entry Price",
        "stoploss": "Stoploss",
        "takeprofit": "Take Profit",
        "trailing_stoploss": "Trailing Stoploss",
        "trailing_stoploss_target": "Trailing Stoploss Target",
        "position": "Position",
    }
    last_rows_pivoted.rename(index=custom_headers, inplace=True)

    last_rows_pivoted.loc["Price"] = last_rows_pivoted.loc["Price"].apply(
        format_as_money
    )

    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    market_table = Table(
        title=f"📊 [bold cyan]Market Analysis[/bold cyan] [dim]({timestamp})[/dim]", 
        box=box.ROUNDED, 
        show_header=True,
        header_style="bold magenta",
        border_style="cyan",
        row_styles=["", "dim"]
    )
    
    market_table.add_column("📈 Metric", style="bold yellow", no_wrap=True, width=25)
    for col in last_rows_pivoted.columns:
        market_table.add_column(str(col), style="cyan", justify="right", width=15)
    
    for idx in last_rows_pivoted.index:
        row_data = [str(idx)]
        for col in last_rows_pivoted.columns:
            value = last_rows_pivoted.loc[idx, col]
            
            if idx == "Entry Signal" and value:
                value_str = f"[bold green]✓ BUY[/bold green]"
            elif idx == "Exit Signal" and value:
                value_str = f"[bold red]✗ SELL[/bold red]"
            elif idx in ["Entry Signal", "Exit Signal"]:
                value_str = "[dim]-[/dim]"
            else:
                value_str = str(value)
            
            row_data.append(value_str)
        market_table.add_row(*row_data)
    
    console.print(market_table)
    console.print("")

    for df, secondary_mint, secondary_mint_symbol in zip(
        data_frames, secondary_mints, secondary_mint_symbols
    ):
        data_file_path = f"data/{secondary_mint_symbol}_data.csv"
        if not df["position"].iat[-1]:
            handle_buy_signal(df, secondary_mint, data_file_path, secondary_mint_symbol)
        else:
            handle_sell_signal(
                df, secondary_mint, data_file_path, secondary_mint_symbol
            )

    for remaining in range(price_update_seconds, 0, -1):
        print(
            f"\033[2m⏱️  Next update in {remaining} seconds | Press Ctrl+C to stop\033[0m",
            end="\r",
            flush=True
        )
        time.sleep(1)
    
    print(" " * 80, end="\r", flush=True)


def handle_buy_signal(df, secondary_mint, data_file_path, secondary_mint_symbol):
    input_amount = find_balance(primary_mint)
    if df["entry"].iat[-1] == 1:
        mint_symbol = df["mint"].iat[0]
        if input_amount <= 0:
            log_transaction.info(
                f"SolTrade has detected a buy signal, but does not have enough {primary_mint_symbol} to trade."
            )
            return False
        log_transaction.info(
            f"SolTrade has detected a buy signal for {mint_symbol} using {input_amount} {primary_mint_symbol}."
        )
        is_swapped = asyncio.run(
            perform_swap(
                input_amount,
                primary_mint,
                secondary_mint,
                primary_mint_symbol,
                secondary_mint_symbol,
            )
        )
        if is_swapped:
            df = calc_entry_price(df)
            df = calc_stoploss(df)
            df = calc_takeprofit(df)
            df = calc_trailing_stoploss(df)
            df = set_position(df, True)
            save_dataframe_to_csv(df, data_file_path)
            return True
        return False
    return False


def handle_sell_signal(df, secondary_mint, data_file_path, secondary_mint_symbol):
    input_amount = find_balance(secondary_mint)
    df = calc_trailing_stoploss(df)

    if df["exit"].iat[-1] == 1:
        mint_symbol = df["mint"].iat[0]
        log_transaction.info(
            f"SolTrade has detected a sell signal for {input_amount} {mint_symbol}."
        )
        is_swapped = asyncio.run(
            perform_swap(
                input_amount,
                secondary_mint,
                primary_mint,
                secondary_mint_symbol,
                primary_mint_symbol,
            )
        )
        if is_swapped:
            df = set_position(df, False)
            df = df.drop(
                columns=[
                    "stoploss",
                    "entry_price",
                    "trailing_stoploss",
                    "trailing_stoploss_target",
                    "takeprofit",
                ]
            )
            save_dataframe_to_csv(df, data_file_path)
            return True
        return False
    return False


def start_trading():
    log_general.info("Soltrade has now initialized the trading algorithm.")
    perform_analysis()
    trading_sched = BlockingScheduler()
    trading_sched.add_job(
        perform_analysis, "interval", seconds=price_update_seconds, max_instances=3
    )
    
    try:
        trading_sched.start()
    except (KeyboardInterrupt, SystemExit):
        console.print("\n[yellow]⏹️  Shutting down SolTrade...[/yellow]")
        trading_sched.shutdown()
        log_general.info("SolTrade has been stopped by user.")


def save_dataframe_to_csv(df, file_path):
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        df.to_csv(file_path, index=False)
        log_general.info(f"Data successfully saved to {file_path}")
    except Exception as e:
        log_general.error(f"Failed to save data to {file_path}: {e}")


def read_dataframe_from_csv(file_path):
    return pd.read_csv(file_path)
