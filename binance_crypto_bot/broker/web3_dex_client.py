"""
web3_dex_client.py — Web3 & Decentralized Exchange (PancakeSwap/Uniswap) Client wrapper.
"""

from typing import Dict, Any, Optional
import time
from binance_crypto_bot.config import (
    WEB3_RPC_URL, WEB3_PRIVATE_KEY, WEB3_CHAIN_ID,
    PANCAKESWAP_ROUTER_BSC, GAS_LIMIT, MAX_SLIPPAGE_PCT
)
from binance_crypto_bot.utils.logger import logger

# Minimal ERC20 & Uniswap/PancakeSwap Router ABI for token swaps
ROUTER_ABI = [
    {
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "amountOutMin", "type": "uint256"},
            {"name": "path", "type": "address[]"},
            {"name": "to", "type": "address"},
            {"name": "deadline", "type": "uint256"}
        ],
        "name": "swapExactTokensForTokens",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"name": "amountIn", "type": "uint256"},
            {"name": "path", "type": "address[]"}
        ],
        "name": "getAmountsOut",
        "outputs": [{"name": "amounts", "type": "uint256[]"}],
        "stateMutability": "view",
        "type": "function"
    }
]

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "success", "type": "bool"}],
        "type": "function"
    }
]

class Web3DexClient:
    def __init__(self, rpc_url: str = WEB3_RPC_URL, private_key: str = WEB3_PRIVATE_KEY, router_address: str = PANCAKESWAP_ROUTER_BSC):
        self.rpc_url = rpc_url
        self.private_key = private_key
        self.router_address = router_address
        self.w3 = None
        self.account = None
        self._connected = False
        
        self.init_web3()

    def init_web3(self):
        """Initialize web3 connection."""
        try:
            from web3 import Web3
            self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
            if self.w3.is_connected():
                self._connected = True
                if self.private_key:
                    self.account = self.w3.eth.account.from_key(self.private_key)
                    logger.info(f"Web3 connected. Wallet Address: {self.account.address}")
                else:
                    logger.info("Web3 connected in READ-ONLY mode (No Private Key provided).")
            else:
                logger.warning(f"Could not connect to Web3 RPC at {self.rpc_url}")
        except Exception as e:
            logger.error(f"Web3 initialization error: {e}")
            self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def get_wallet_balance(self) -> float:
        """Get native coin balance (BNB / ETH) in Ether units."""
        if not self._connected or not self.account:
            return 0.0
        try:
            wei_balance = self.w3.eth.get_balance(self.account.address)
            return float(self.w3.from_wei(wei_balance, 'ether'))
        except Exception as e:
            logger.error(f"Failed to fetch Web3 balance: {e}")
            return 0.0

    def get_token_balance(self, token_address: str) -> float:
        """Get ERC20 token balance."""
        if not self._connected or not self.account:
            return 0.0
        try:
            checksum_token = self.w3.to_checksum_address(token_address)
            contract = self.w3.eth.contract(address=checksum_token, abi=ERC20_ABI)
            raw_balance = contract.functions.balanceOf(self.account.address).call()
            return float(raw_balance) / (10**18)  # Assuming 18 decimals
        except Exception as e:
            logger.error(f"Error fetching token balance: {e}")
            return 0.0

    def execute_swap(self, token_in: str, token_out: str, amount_in_wei: int, slippage_pct: float = MAX_SLIPPAGE_PCT) -> Dict[str, Any]:
        """Build, sign, and broadcast a DEX swap transaction."""
        if not self._connected or not self.account:
            return {"status": "error", "message": "Web3 client not connected or wallet unconfigured"}

        try:
            checksum_router = self.w3.to_checksum_address(self.router_address)
            router_contract = self.w3.eth.contract(address=checksum_router, abi=ROUTER_ABI)

            path = [self.w3.to_checksum_address(token_in), self.w3.to_checksum_address(token_out)]
            
            # Query expected output amount
            amounts_out = router_contract.functions.getAmountsOut(amount_in_wei, path).call()
            expected_out = amounts_out[-1]
            min_out = int(expected_out * (1 - slippage_pct))

            deadline = int(time.time()) + 600  # 10 minute deadline
            nonce = self.w3.eth.get_transaction_count(self.account.address)
            gas_price = self.w3.eth.gas_price

            tx = router_contract.functions.swapExactTokensForTokens(
                amount_in_wei,
                min_out,
                path,
                self.account.address,
                deadline
            ).build_transaction({
                'from': self.account.address,
                'nonce': nonce,
                'gas': GAS_LIMIT,
                'gasPrice': gas_price,
                'chainId': WEB3_CHAIN_ID
            })

            signed_tx = self.w3.eth.account.sign_transaction(tx, private_key=self.private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            logger.info(f"Web3 Swap Executed! Tx Hash: {tx_hash.hex()}")

            return {
                "status": "success",
                "tx_hash": tx_hash.hex(),
                "expected_out": expected_out,
                "path": path
            }
        except Exception as e:
            logger.error(f"Web3 DEX Swap Error: {e}")
            return {"status": "error", "message": str(e)}
