# from django.db.models.signals import post_save
# from django.dispatch import receiver

# from user_app.models import User

# from .models import Wallet


# @receiver(post_save, sender=User)
# def create_wallet_for_new_user(sender, instance: User, created: bool, **kwargs) -> None:
#     """Auto-create a Wallet whenever a new User is saved."""
#     if created:
#         Wallet.objects.create(user=instance)
