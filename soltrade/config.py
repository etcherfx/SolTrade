import json
import os

from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.pubkey import Pubkey

from soltrade.log import log_general


class Config:
    def __init__(self):
        self.api_key = None
        self.private_key = None
        self.rpc_https = None
        self.jup_api = None
        self.primary_mint = None
        self.primary_mint_symbol = None
        self.sol_mint = "So11111111111111111111111111111111111111112"
        self.secondary_mints = []
        self.secondary_mint_symbols = []
        self.price_update_seconds = None
        self.trading_interval_minutes = None
        self.max_slippage = None  # BPS
        self.split_between_mints = None
        self.strategy = None
        self.path = os.path.join(os.path.dirname(__file__), "..", "config.json")
        self.load_config()

    def load_config(self):
        default_config = {
            "api_key": "",
            "private_key": "",
            "rpc_https": "https://api.mainnet-beta.solana.com",
            "jup_api": "https://quote-api.jup.ag/v6",
            "primary_mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "primary_mint_symbol": "USDC",
            "secondary_mints": ["So11111111111111111111111111111111111111112"],
            "secondary_mint_symbols": ["SOL"],
            "price_update_seconds": 60,
            "trading_interval_minutes": 1,
            "max_slippage": 50,
            "split_between_mints": False,
            "strategy": "default",
        }

        with open(self.path, "r") as file:
            try:
                config_data = json.load(file)
                for key, default_value in default_config.items():
                    setattr(self, key, config_data.get(key, default_value))
                    if not getattr(self, key):
                        setattr(self, key, default_value)
            except json.JSONDecodeError as e:
                print(f"Error loading config: {e}")

    def decimals(self, mint_address: str) -> int:
        response = self.client.get_account_info_json_parsed(
            Pubkey.from_string(mint_address)
        ).to_json()
        json_response = json.loads(response)
        value = (
            10 ** json_response["result"]["value"]["data"]["parsed"]["info"]["decimals"]
        )
        return value

    @property
    def keypair(self) -> Keypair:
        try:
            b58_string = self.private_key
            keypair = Keypair.from_base58_string(b58_string)
            # print(f"Using Wallet: {keypair.pubkey()}")

            return keypair
        except Exception as e:
            log_general.error(f"Error decoding private key: {e}")
            exit(1)

    @property
    def public_address(self) -> Pubkey:
        return self.keypair.pubkey()

    @property
    def client(self) -> Client:
        rpc_url = self.rpc_https
        return Client(rpc_url)


_config_instance = None


def config() -> Config:
    global _config_instance
    _config_instance = Config()
    return _config_instance
