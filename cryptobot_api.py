#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Crypto Pay API Client
Based on official documentation: https://help.send.tg/en/articles/10279948-crypto-pay-api
"""

import requests
import json
import hashlib
import hmac
from typing import Dict, List, Optional, Union
from datetime import datetime, timezone

class CryptoPayAPI:
    """Crypto Pay API Client"""
    
    def __init__(self, api_token: str, testnet: bool = False):
        """
        Initialize Crypto Pay API client
        
        Args:
            api_token: API token from @CryptoBot or @CryptoTestnetBot
            testnet: Use testnet (default: False for mainnet)
        """
        self.api_token = api_token
        self.testnet = testnet
        
        if testnet:
            self.base_url = "https://testnet-pay.crypt.bot"
            self.bot_username = "@CryptoTestnetBot"
        else:
            self.base_url = "https://pay.crypt.bot"
            self.bot_username = "@CryptoBot"
    
    def _make_request(self, method: str, params: Dict = None) -> Dict:
        """Make API request"""
        url = f"{self.base_url}/api/{method}"
        headers = {
            "Crypto-Pay-API-Token": self.api_token,
            "Content-Type": "application/json"
        }
        
        try:
            if params:
                response = requests.post(url, json=params, headers=headers, timeout=30)
            else:
                response = requests.get(url, headers=headers, timeout=30)
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            return {
                "ok": False,
                "error": f"Request failed: {str(e)}"
            }
        except json.JSONDecodeError as e:
            return {
                "ok": False,
                "error": f"Invalid JSON response: {str(e)}"
            }
    
    def get_me(self) -> Dict:
        """Test your app's authentication token"""
        return self._make_request("getMe")
    
    def create_invoice(
        self,
        amount: Union[str, float],
        asset: str = "USDT",
        currency_type: str = "crypto",
        fiat: str = None,
        accepted_assets: List[str] = None,
        description: str = None,
        hidden_message: str = None,
        paid_btn_name: str = None,
        paid_btn_url: str = None,
        payload: str = None,
        allow_comments: bool = True,
        allow_anonymous: bool = True,
        expires_in: int = None,
        swap_to: str = None
    ) -> Dict:
        """
        Create a new invoice
        
        Args:
            amount: Amount of the invoice
            asset: Cryptocurrency code (USDT, TON, BTC, ETH, LTC, BNB, TRX, USDC)
            currency_type: "crypto" or "fiat"
            fiat: Fiat currency code (USD, EUR, RUB, BYN, UAH, etc.)
            accepted_assets: List of accepted cryptocurrencies
            description: Invoice description
            hidden_message: Hidden message for the invoice
            paid_btn_name: Button label (viewItem, openChannel, openBot, callback)
            paid_btn_url: Button URL
            payload: Additional data
            allow_comments: Allow user comments
            allow_anonymous: Allow anonymous payments
            expires_in: Payment time limit in seconds
            swap_to: Asset to swap to
        """
        params = {
            "amount": str(amount),
            "asset": asset,
            "currency_type": currency_type
        }
        
        if fiat:
            params["fiat"] = fiat
        if accepted_assets:
            params["accepted_assets"] = ",".join(accepted_assets)
        if description:
            params["description"] = description
        if hidden_message:
            params["hidden_message"] = hidden_message
        if paid_btn_name:
            params["paid_btn_name"] = paid_btn_name
        if paid_btn_url:
            params["paid_btn_url"] = paid_btn_url
        if payload:
            params["payload"] = payload
        if allow_comments is not None:
            params["allow_comments"] = allow_comments
        if allow_anonymous is not None:
            params["allow_anonymous"] = allow_anonymous
        if expires_in:
            params["expires_in"] = expires_in
        if swap_to:
            params["swap_to"] = swap_to
        
        return self._make_request("createInvoice", params)
    
    def get_invoices(
        self,
        asset: str = None,
        invoice_ids: List[int] = None,
        status: str = None,
        offset: int = 0,
        count: int = 100
    ) -> Dict:
        """Get invoices list"""
        params = {
            "offset": offset,
            "count": count
        }
        
        if asset:
            params["asset"] = asset
        if invoice_ids:
            params["invoice_ids"] = ",".join(map(str, invoice_ids))
        if status:
            params["status"] = status
        
        return self._make_request("getInvoices", params)
    
    def delete_invoice(self, invoice_id: int) -> Dict:
        """Delete invoice"""
        params = {"invoice_id": invoice_id}
        return self._make_request("deleteInvoice", params)
    
    def get_balance(self) -> Dict:
        """Get app balance"""
        return self._make_request("getBalance")
    
    def get_exchange_rates(self) -> Dict:
        """Get exchange rates"""
        return self._make_request("getExchangeRates")
    
    def get_currencies(self) -> Dict:
        """Get supported currencies"""
        return self._make_request("getCurrencies")
    
    def transfer(
        self,
        user_id: int,
        asset: str,
        amount: Union[str, float],
        spend_id: str = None,
        comment: str = None
    ) -> Dict:
        """
        Transfer coins to user
        
        Args:
            user_id: Telegram user ID
            asset: Cryptocurrency code
            amount: Amount to transfer
            spend_id: Unique spend ID
            comment: Transfer comment
        """
        params = {
            "user_id": str(user_id),
            "asset": asset,
            "amount": str(amount)
        }
        
        if spend_id:
            params["spend_id"] = spend_id
        if comment:
            params["comment"] = comment
        
        return self._make_request("transfer", params)
    
    def get_transfers(
        self,
        asset: str = None,
        transfer_ids: List[int] = None,
        offset: int = 0,
        count: int = 100
    ) -> Dict:
        """Get transfers list"""
        params = {
            "offset": offset,
            "count": count
        }
        
        if asset:
            params["asset"] = asset
        if transfer_ids:
            params["transfer_ids"] = ",".join(map(str, transfer_ids))
        
        return self._make_request("getTransfers", params)
    
    def get_stats(self) -> Dict:
        """Get app statistics"""
        return self._make_request("getStats")
    
    def create_check(
        self,
        asset: str,
        amount: Union[str, float],
        payload: str = None
    ) -> Dict:
        """Create a check"""
        params = {
            "asset": asset,
            "amount": str(amount)
        }
        
        if payload:
            params["payload"] = payload
        
        return self._make_request("createCheck", params)
    
    def delete_check(self, check_id: int) -> Dict:
        """Delete a check"""
        params = {"check_id": check_id}
        return self._make_request("deleteCheck", params)
    
    def get_checks(
        self,
        asset: str = None,
        check_ids: List[int] = None,
        offset: int = 0,
        count: int = 100
    ) -> Dict:
        """Get checks list"""
        params = {
            "offset": offset,
            "count": count
        }
        
        if asset:
            params["asset"] = asset
        if check_ids:
            params["check_ids"] = ",".join(map(str, check_ids))
        
        return self._make_request("getChecks", params)
    
    @staticmethod
    def verify_webhook_signature(token: str, body: str, signature: str) -> bool:
        """
        Verify webhook signature
        
        Args:
            token: API token
            body: Raw request body
            signature: crypto-pay-api-signature header value
            
        Returns:
            True if signature is valid
        """
        try:
            # Create secret key from token
            secret = hashlib.sha256(token.encode()).digest()
            
            # Create HMAC signature
            hmac_signature = hmac.new(
                secret,
                body.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac_signature == signature
            
        except Exception:
            return False
    
    def test_connection(self) -> Dict:
        """Test API connection and return detailed info"""
        result = self.get_me()
        
        if result.get("ok"):
            app_info = result.get("result", {})
            return {
                "ok": True,
                "app_id": app_info.get("app_id"),
                "name": app_info.get("name"),
                "payment_processing_bot_username": app_info.get("payment_processing_bot_username"),
                "bot_username": self.bot_username,
                "testnet": self.testnet
            }
        else:
            return result
    
    def get_uah_to_usd_rate(self) -> float:
        """Get UAH to USD exchange rate from external API"""
        try:
            # Using exchangerate-api.com (free tier)
            response = requests.get("https://api.exchangerate-api.com/v4/latest/UAH", timeout=10)
            if response.status_code == 200:
                data = response.json()
                return float(data.get('rates', {}).get('USD', 0.025))
        except Exception as e:
            print(f"[cryptobot_api] Error getting UAH rate: {e}")
        
        # Fallback rate
        return 0.025

# Convenience function for easy import
def create_cryptopay_client(api_token: str, testnet: bool = False) -> CryptoPayAPI:
    """Create CryptoPay API client"""
    return CryptoPayAPI(api_token, testnet)