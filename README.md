<div align ="center">

<img src="projectInfo/icon.png" width="180">

# SolTrade

<span style="font-size:18px;">A Solana trading bot with lots of features.</span>

[![CodeFactor](https://www.codefactor.io/repository/github/etcherfx/soltrade/badge/main?style=for-the-badge)](https://www.codefactor.io/repository/github/etcherfx/soltrade/overview/main)
[![License](https://img.shields.io/github/license/etcherfx/soltrade?style=for-the-badge)](https://github.com/etcherfx/soltrade/blob/main/LICENSE)
[![GitHub issues](https://img.shields.io/github/issues/etcherfx/soltrade?style=for-the-badge)](https://github.com/etcherfx/soltrade/issues) <br>
[![GitHub Release](https://img.shields.io/github/release/etcherfx/soltrade?include_prereleases&style=for-the-badge)](https://github.com/etcherfx/soltrade/releases/latest)

</div>

## Links 🔗

- [Releases](https://github.com/etcherfx/SolTrade/releases)

## Projects Used 🛠️

- [noahtheprogrammer's soltrade](https://github.com/noahtheprogrammer/soltrade)

## Features 📂

- **Custom strategies**: Create your own trading strategies and use them with SolTrade. Customize parameters like `stoploss`, `trailing_stoploss`, `takeprofit`, etc to fit your needs
- **Multiple token trading**: Instead of waiting for one token to meet trading conditions, you can analyze multiple tokens to increase trade chances, given you have a good RPC and self-hosted or paid Jupiter API.

## Term Definitions 📚

- **Primary Mint**: The token you want to trade with, usually a stablecoin like USDC
- **Secondary Mint**: The token you want to trade for, like SOL or any other Solana token
- **Trading Intervals**: The time interval between each technical analysis (whether current conditions are fit to trade), in minutes
- **Price Update Interval**: The time interval between each price update, in seconds
- **Max Slippage**: The maximum percentage difference between the expected price and the executed price when making a trade
- **Strategy**: The trading strategy you want to use, like `default` or your own custom strategy

## Setup 🔧

- Sign up for a [CryptoCompare API key](https://www.cryptocompare.com/cryptopian/api-keys)
- Create a new wallet on [Phantom](https://phantom.app/) or any other Solana wallet solely for SolTrade
- Deposit however much of the primary token you want to trade with into your wallet and at least `~0.1 $SOL` to cover transaction fees

## Configuration ⚙️

- Make a copy of the `config.json.sample` file and rename it to `config.json`
- Fill in / edit the following parameters in the `config.json` file or leave them default:
  | Parameter | Description | Default |
  |----------------------------|-----------------------------------------------------------|:---------:|
  | `api_key` | Your CryptoCompare API key | `Null` |
  | `private_key` | Your Solana wallet private key | `Null` |
  | `rpc_https` | HTTPS endpoint of your RPC | `https://api.mainnet-beta.solana.co` |
  | `jup_api` | Jupiter API endpoint | `https://api.jup.ag/swap/v1` |
  |`primary_mint`| Token address of main currency |`EPjF..v`|
  |`primary_mint_symbol`| Token symbol of main token |`USDC`|
  |`secondary_mints`| Token adress of each custom token(s) seperated by `,` in a list `[]` |`[So11..2]`|
  |`secondary_mint_symbols`| Token symbol of custom token(s) seperated by `,` in a list `[]` |`[SOL]`|
  |`price_update_seconds`| Second-based time interval between token price updates |`60`|
  |`trading_interval_minutes`| Minute-based time interval for technical analysis |`1`|
  |`max_slippage`| Maximum slippage % in BPS utilized by Jupiter during transactions |`50`|
  |`strategy`| The strategy you want to trade with |`default`|

## Installation 🛠️

- Set Windows PowerShell execution policy to `RemoteSigned`:
  ```
  Set-ExecutionPolicy RemoteSigned
  ```
- Install `poetry` via `pip`:
  ```
  pip install poetry
  ```
- Set poetry to create virtual environments in the project directory:
  ```
  poetry config virtualenvs.in-project true
  ```
- Go into the project root directory and nstall the dependencies:
  ```
  poetry install
  ```
- Install the poetry shell plugin:
  ```
  poetry self add poetry-plugin-shell
  ```

## Usage 🚀

- Enter the virtual environment:
  ```
  poetry shell
  ```
- Start the bot:
  ```
  python main.py
  ```

## Custom Strategies 📈

> [!NOTE]  
> `{Your Strategy Name}` is just a placeholder for your strategy name. Replace it with your actual strategy name without the `{}`.

- Create a new Python file in the `strategies` directory named `{Your Strategy Name}_strategy.py`
- Create a class named `{Your Strategy Name}Strategy` (all one word with the first letter being a capital letter) that inherits from the `BaseStrategy` class
- Create a `__init__` method that takes in the following parameters:
  ```
  def __init__(self, df: pd.DataFrame):
    self.df = df
    self.stoploss =
    self.takeprofit =
    self.trailing_stoploss =
    self.trailing_stoploss_target =
  ```
- Create a `apply_strategy` method that is called by the bot to apply the strategy:
  ```
  def apply_strategy(self):
    if config().strategy == "{Your Strategy Name}":
      # Your strategy logic here
  ```
- Then, change the config `strategy` parameter to `{Your Strategy Name}`
- Lastly, feel free to make a pull request to add your strategy to the main project

## Donations 💸

Similar to the original project, SolTrade does not currently include a platform fee and will remain open-source forever. However, if you would like to support the project, you can donate to the following Solana wallet address:

```
22gwSXc7mvp6UZwgDouhQuJ5AmHN3oxLNGULkARmT3PV
```

## Disclaimer ⚠️

This project is a fork of [noahtheprogrammer's soltrade](https://github.com/noahtheprogrammer/soltrade) and is not affiliated with the original project in any way. I am not responsible for any losses you may incur while using this software. Use at your own risk.
