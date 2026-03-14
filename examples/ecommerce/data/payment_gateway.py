"""Payment processing — data layer."""

from api.stripe_client import StripeClient  # VIOLATION: data -> networking (upward from data's perspective? No, networking is below data in layer_order, so this is fine)


class PaymentGateway:
    stripe: StripeClient

    def charge(self, amount: float) -> bool:
        return self.stripe.create_charge(amount)

    def refund(self, transaction_id: str) -> bool:
        return self.stripe.create_refund(transaction_id)
