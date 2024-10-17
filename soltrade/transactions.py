import asyncio
import base64
import json
import os
import pandas as pd

import httpx
from solana.rpc.core import RPCException
from solana.rpc.types import TxOpts
from solders import message
from solders.signature import Signature
from solders.transaction import VersionedTransaction

from soltrade.config import config
from soltrade.log import log_general, log_transaction


class MarketPosition:
    def __init__(self, path):
        self.path = path
        self.is_open = False
        self.sl = 0
        self.tp = 0
        self.ensure_directory_exists()

    def ensure_directory_exists(self):
        directory = os.path.dirname(self.path)
        if not os.path.exists(directory):
            os.makedirs(directory)


_market_instance = None


def market(path=None):
    global _market_instance
    if _market_instance is None and path is not None:
        _market_instance = MarketPosition(path)
    return _market_instance


# Returns the route to be manipulated in createTransaction()
async def create_exchange(
    input_amount: int, input_token_mint: str, output_token_mint
) -> dict:
    log_transaction.info(
        f"SolTrade is creating exchange for {input_amount} {input_token_mint}"
    )

    token_decimals = config().decimals(output_token_mint)

    # Finds the response and converts it into a readable array
    api_link = f"{config().jup_api}/quote?inputMint={input_token_mint}&outputMint={output_token_mint}&amount={int(input_amount * token_decimals)}&platformFeeBps=100"
    log_transaction.info(f"Soltrade API Link: {api_link}")
    async with httpx.AsyncClient() as client:
        response = await client.get(api_link)
        return response.json()


# Returns the swap_transaction to be manipulated in sendTransaction()
async def create_transaction(quote: dict) -> dict:
    log_transaction.info(
        f"""SolTrade is creating transaction for the following quote: 
{quote}"""
    )

    # Parameters used for the Jupiter POST request
    parameters = {
        "quoteResponse": quote,
        "userPublicKey": str(config().public_address),
        "wrapAndUnwrapSol": True,
        "computeUnitPriceMicroLamports": 20 * 14000,  # fee of roughly $.04  :shrug:
        "feeAccount": "44jKKtkFEo3doi9E9aqMpDrKSpAvRSDHosNQWLFPL5Qr",
        "dynamicSlippage": {"maxBps": (config().max_slippage)},
    }

    # Returns the JSON parsed response of Jupiter
    async with httpx.AsyncClient() as client:
        if config().jup_api == "https://api.jup.ag/swap/v6":
            response = await client.post(
                f"{config().jup_api}/transaction", json=parameters
            )
        else:
            response = await client.post(f"{config().jup_api}/swap", json=parameters)
        return response.json()


# Deserializes and sends the transaction from the swap information given
def send_transaction(swap_transaction: dict, opts: TxOpts) -> Signature:
    raw_txn = VersionedTransaction.from_bytes(base64.b64decode(swap_transaction))
    signature = config().keypair.sign_message(
        message.to_bytes_versioned(raw_txn.message)
    )
    signed_txn = VersionedTransaction.populate(raw_txn.message, [signature])

    result = config().client.send_raw_transaction(bytes(signed_txn), opts)
    txid = result.value
    log_transaction.info(f"Soltrade TxID: {txid}")
    return txid


def find_transaction_error(txid: Signature) -> dict:
    json_response = (
        config()
        .client.get_transaction(txid, max_supported_transaction_version=0)
        .to_json()
    )
    parsed_response = json.loads(json_response)["result"]["meta"]["err"]
    return parsed_response


def find_last_valid_block_height() -> dict:
    json_response = (
        config().client.get_latest_blockhash(commitment="confirmed").to_json()
    )
    parsed_response = json.loads(json_response)["result"]["value"][
        "lastValidBlockHeight"
    ]
    return parsed_response


# Uses the previous functions and parameters to exchange Solana token currencies
async def perform_swap(
    sent_amount: float,
    sent_token_mint: str,
    output_token_mint: str,
    sent_token_symbol: str,
    output_token_symbol: str,
):
    log_general.info("SolTrade is taking a market position.")

    quote = trans = opts = txid = tx_error = None
    is_tx_successful = False

    for i in range(0, 3):
        if not is_tx_successful:
            try:
                quote = await create_exchange(
                    sent_amount, sent_token_mint, output_token_mint
                )
                trans = await create_transaction(quote)
                opts = TxOpts(
                    skip_preflight=False,
                    preflight_commitment="confirmed",
                    last_valid_block_height=find_last_valid_block_height(),
                )
                txid = send_transaction(trans["swapTransaction"], opts)
            except Exception:
                if RPCException:
                    log_general.warning(
                        f"SolTrade failed to complete transaction {i}. Retrying."
                    )
                    continue
                else:
                    raise
            for i in range(0, 3):
                try:
                    await asyncio.sleep(35)
                    tx_error = find_transaction_error(txid)
                    if not tx_error:
                        is_tx_successful = True
                        break
                except TypeError:
                    log_general.warning(
                        "SolTrade failed to verify the existence of the transaction. Retrying."
                    )
                    continue
        else:
            break

    if tx_error or not is_tx_successful:
        log_general.error(
            "SolTrade failed to complete the transaction due to slippage issues with Jupiter."
        )
        return False

    decimals = config().decimals(output_token_mint)
    bought_amount = int(quote["outAmount"]) / decimals
    log_transaction.info(
        f"Sold {sent_amount} {sent_token_symbol} for {bought_amount:.2f} {output_token_symbol}"
    )
    return True
