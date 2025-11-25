<h1 align="center">
  <img src="projectInfo/banner.png" alt="SolTrade Banner" width="850">
</h1>

<div align="center">

[![CodeFactor](https://www.codefactor.io/repository/github/etcherfx/soltrade/badge/main?style=for-the-badge)](https://www.codefactor.io/repository/github/etcherfx/soltrade/overview/main)
[![License](https://img.shields.io/github/license/etcherfx/soltrade?style=for-the-badge)](https://github.com/etcherfx/soltrade/blob/main/LICENSE)
[![GitHub issues](https://img.shields.io/github/issues/etcherfx/soltrade?style=for-the-badge)](https://github.com/etcherfx/soltrade/issues)
[![GitHub Release](https://img.shields.io/github/release/etcherfx/soltrade?include_prereleases&style=for-the-badge)](https://github.com/etcherfx/soltrade/releases/latest)

**A Solana trading bot with lots of features.**

Hard fork of noahtheprogrammer's [soltrade](https://github.com/noahtheprogrammer/soltrade)

</div>

## 📖 Table of Contents

- [📖 Table of Contents](#-table-of-contents)
- [🔗 Links](#-links)
- [📂 Features](#-features)
- [📚 Term Definitions](#-term-definitions)
- [🔧 Prerequisites](#-prerequisites)
- [⚙️ Configuration](#️-configuration)
- [🛠️ Installation](#️-installation)
- [📈 Custom Strategies](#-custom-strategies)
- [💸 Donations](#-donations)
- [⚠️ Disclaimer](#️-disclaimer)

## 🔗 Links 

- [Releases](https://github.com/etcherfx/SolTrade/releases)

## 📂 Features 

- **Custom strategies**: Create your own trading strategies and use them with SolTrade. Customize parameters like `stoploss`, `trailing_stoploss`, `takeprofit`, etc to fit your needs
- **Multiple token trading**: Instead of waiting for one token to meet trading conditions, you can analyze multiple tokens to increase trade chances

## 📚 Term Definitions

- **Primary Mint**: The token you want to trade with, usually a stablecoin like USDC
- **Secondary Mint**: The token you want to trade for, like SOL or any other Solana token
- **Trading Intervals**: The time interval between each technical analysis (whether current conditions are fit to trade), in minutes
- **Price Update Interval**: The time interval between each price update, in seconds
- **Max Slippage**: The maximum percentage difference between the expected price and the executed price when making a trade
- **Strategy**: The trading strategy you want to use, like `default` or your own custom strategy

## 🔧 Prerequisites 

- Sign up for a [CryptoCompare API key](https://www.cryptocompare.com/cryptopian/api-keys)
- Sign up for a free [Jupiter API key](https://portal.jup.ag/) (required for Ultra Swap API only)
- Create a new wallet on [Jupiter Wallet](https://jup.ag/) [Phantom](https://phantom.app/) or any other Solana wallet solely for SolTrade
- Deposit however much of the primary token you want to trade with into your wallet and at least `~0.2 $SOL` to cover transaction fees

## ⚙️ Configuration 

- Make a copy of the `config.json.sample` file and rename it to `config.json`
- Fill in / edit the following parameters in the `config.json` file or leave them default:
  | Parameter                  | Description                                                          |                Default                |
  | -------------------------- | -------------------------------------------------------------------- | :-----------------------------------: |
  | `api_key`                  | Your CryptoCompare API key                                           |                `Null`                 |
  | `jupiter_api_key`          | Your Jupiter API key from portal.jup.ag                              |                `Null`                 |
  | `private_key`              | Your Solana wallet private key                                       |                `Null`                 |
  | `rpc_https`                | HTTPS endpoint of your RPC (for balance checks & token info)         | `https://api.mainnet-beta.solana.com` |
  | `jup_api`                  | Jupiter Ultra API endpoint                                           |     `https://api.jup.ag/ultra/v1`     |
  | `primary_mint`             | Token address of main currency                                       |               `EPjF..v`               |
  | `primary_mint_symbol`      | Token symbol of main token                                           |                `USDC`                 |
  | `secondary_mints`          | Token adress of each custom token(s) seperated by `,` in a list `[]` |              `[So11..2]`              |
  | `secondary_mint_symbols`   | Token symbol of custom token(s) seperated by `,` in a list `[]`      |                `[SOL]`                |
  | `price_update_seconds`     | Second-based time interval between token price updates               |                 `60`                  |
  | `trading_interval_minutes` | Minute-based time interval for technical analysis                    |                  `1`                  |
  | `max_slippage`             | Maximum slippage % in BPS                                            |                 `50`                  |
  | `strategy`                 | The strategy you want to trade with                                  |               `default`               |

## 🛠️ Installation

- Install Microsoft Visual C++ Build Tools from [here](https://visualstudio.microsoft.com/visual-cpp-build-tools/)
- Install TA-Lib from [here](https://ta-lib.org/install/)
- Install UV:
  - Windows:
    ```
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```
  - Linux / macOS:
    ```
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```
- Navigate over to the project root directory and run `main.py`:
  ```
  uv run main.py
  ```

## 📈 Custom Strategies 

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

## 💸 Donations

Similar to the original project, SolTrade does not currently include a platform fee and will remain open-source forever. However, if you would like to support the project, you can donate to the following Solana wallet address:

```
22gwSXc7mvp6UZwgDouhQuJ5AmHN3oxLNGULkARmT3PV
```

## ⚠️ Disclaimer

I am not responsible for any losses you may incur while using this software. Use at your own risk.
