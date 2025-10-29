import json
import os

from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.pubkey import Pubkey

from soltrade.log import log_general


class Config:
    def __init__(self):
        self.api_key = None
        self.jupiter_api_key = None
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
        self.max_slippage = None
        self.strategy = None
        self.path = os.path.join(os.path.dirname(__file__), "..", "config.json")
        self._client = None
        self._decimals_cache = {}
        self.load_config()

    def load_config(self):
        default_config = {
            "api_key": "",
            "jupiter_api_key": "",
            "private_key": "",
            "rpc_https": "https://api.mainnet-beta.solana.com",
            "jup_api": "https://api.jup.ag/ultra/v1",
            "primary_mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            "primary_mint_symbol": "USDC",
            "secondary_mints": ["So11111111111111111111111111111111111111112"],
            "secondary_mint_symbols": ["SOL"],
            "price_update_seconds": 60,
            "trading_interval_minutes": 1,
            "max_slippage": 50,
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
        
        self._validate_config()
    
    def _validate_config(self):
        """Validate that critical configuration fields are properly set."""
        if not self.private_key or self.private_key == "":
            log_general.warning("Private key is not set in config.json. Bot cannot trade.")
        
        if not self.api_key or self.api_key == "":
            log_general.warning("CryptoCompare API key is not set in config.json. Price data unavailable.")
        
        if not self.jupiter_api_key or self.jupiter_api_key == "":
            log_general.warning("Jupiter API key is not set in config.json. Required for api.jup.ag endpoint.")
        
        if not self.rpc_https:
            log_general.error("RPC endpoint is not set in config.json.")
            
        if not self.jup_api:
            log_general.error("Jupiter API endpoint is not set in config.json.")

    def decimals(self, mint_address: str) -> int:
        """Get token decimals with caching to avoid repeated RPC calls."""
        if mint_address in self._decimals_cache:
            return self._decimals_cache[mint_address]
        
        response = self.client.get_account_info_json_parsed(
            Pubkey.from_string(mint_address)
        ).to_json()
        json_response = json.loads(response)
        value = (
            10 ** json_response["result"]["value"]["data"]["parsed"]["info"]["decimals"]
        )
        
        self._decimals_cache[mint_address] = value
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
        """Cached RPC client to avoid creating new connections."""
        if self._client is None:
            self._client = Client(self.rpc_https)
        return self._client


_config_instance = None


def config() -> Config:
    """Singleton pattern to ensure only one Config instance exists."""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance
