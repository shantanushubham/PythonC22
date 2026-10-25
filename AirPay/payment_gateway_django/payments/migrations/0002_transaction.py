import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.DeleteModel(name="Payment"),
        migrations.CreateModel(
            name="Transaction",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "method",
                    models.CharField(
                        choices=[("CARD", "Card"), ("UPI", "Upi"), ("NETBANKING", "Netbanking")],
                        max_length=16,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("SUCCESS", "Success"),
                            ("FAILED", "Failed"),
                            ("EXPIRED", "Expired"),
                            ("CANCELLED", "Cancelled"),
                        ],
                        default="PENDING",
                        max_length=16,
                    ),
                ),
                ("amount_paise", models.BigIntegerField()),
                ("currency", models.CharField(default="INR", max_length=3)),
                ("reference", models.CharField(blank=True, default="", max_length=64)),
                ("description", models.CharField(blank=True, default="", max_length=50)),
                ("return_url", models.CharField(blank=True, default="", max_length=500)),
                ("redirect_url", models.CharField(blank=True, default="", max_length=500)),
                ("rail_transaction_id", models.CharField(blank=True, default="", max_length=80)),
                ("rail_reference", models.CharField(blank=True, default="", max_length=40)),
                ("instrument", models.JSONField(default=dict)),
                ("failure_reason", models.CharField(blank=True, default="", max_length=200)),
                ("failure_code", models.CharField(blank=True, default="", max_length=40)),
                ("credited_at", models.DateTimeField(blank=True, null=True)),
                ("idempotency_key", models.CharField(blank=True, default="", max_length=255)),
                ("request_fingerprint", models.CharField(blank=True, default="", max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="transactions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="transaction",
            index=models.Index(fields=["customer", "-created_at"], name="payments_tr_custome_f99334_idx"),
        ),
        migrations.AddIndex(
            model_name="transaction",
            index=models.Index(fields=["rail_transaction_id"], name="payments_tr_rail_tr_507322_idx"),
        ),
        migrations.AddConstraint(
            model_name="transaction",
            constraint=models.UniqueConstraint(
                condition=~models.Q(("idempotency_key", "")),
                fields=("customer", "idempotency_key"),
                name="unique_transaction_idempotency_key",
            ),
        ),
    ]
