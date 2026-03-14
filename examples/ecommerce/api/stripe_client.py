"""Stripe payment API client."""


class StripeClient:
    api_key: str

    def create_charge(self, amount: float) -> bool:
        return True

    def create_refund(self, transaction_id: str) -> bool:
        return True
