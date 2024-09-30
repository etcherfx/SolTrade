import os
import json
import base58

from solders.pubkey import Pubkey
from solders.keypair import Keypair
from solana.rpc.api import Client
from soltrade.log import log_general
from dotenv import load_dotenv


class Config:
    def __init__(self, path):
        load_dotenv()
        self.api_key = None
        self.private_key = None
        self.rpc_https = None
        self.primary_mint = None
        self.primary_mint_symbol = None
        self.sol_mint = "So11111111111111111111111111111111111111112"
        self.secondary_mint = None
        self.secondary_mint_symbol = None
        self.price_update_seconds = None
        self.trading_interval_minutes = None
        self.slippage = None  # BPS
        self.computeUnitPriceMicroLamports = None
        self.telegram = None
        self.tg_bot_token = None
        self.tg_bot_uid = None
        self.path = os.path.join(os.path.dirname(path), "config.json")
        self.load_config()

    def load_config(self):
        self.api_key = os.getenv("API_KEY")
        self.private_key = os.getenv("WALLET_PRIVATE_KEY")

        default_config = {
            "rpc_https": "https://api.mainnet-beta.solana.com/",
            "primary_mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "primary_mint_symbol": "USDC",
            "secondary_mint": "So11111111111111111111111111111111111111112",
            "secondary_mint_symbol": "SOL",
            "price_update_seconds": 30,
            "trading_interval_minutes": 0.5,
            "slippage": 50,
            "telegram": None,
            "tg_bot_token": None,
            "tg_bot_uid": None,
            "verbose": True,
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
        rpc_url = self.custom_rpc_https
        return Client(rpc_url)

    @property
    def decimals(self) -> int:
        response = self.client.get_account_info_json_parsed(
            Pubkey.from_string(config().secondary_mint)
        ).to_json()
        json_response = json.loads(response)
        value = (
            10 ** json_response["result"]["value"]["data"]["parsed"]["info"]["decimals"]
        )
        return value


_config_instance = None


def config() -> Config:
    global _config_instance
    _config_instance = Config()
    return _config_instance
