from django.db import models

from user_app.models import User


class BankAccount(models.Model):
    """
    BA — a user can link many bank accounts (M : 1 with User).
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bank_accounts")

    account_no = models.CharField(max_length=20)
    ifsc_code = models.CharField(max_length=11)          # standard IFSC length
    account_name = models.CharField(max_length=100)       # name on the account
    bank_name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # one user cannot link the same account number twice
        constraints = [
            models.UniqueConstraint(
                fields=["user", "account_no"], name="unique_account_per_user"
            )
        ]

    def __str__(self) -> str:
        return f"BankAccount({self.account_name} | {self.account_no} | {self.ifsc_code})"
