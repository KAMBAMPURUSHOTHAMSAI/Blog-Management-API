from django.db import models


# =========================================================
# Subscription Plan
# =========================================================

class SubscriptionPlan(models.Model):
    id = models.IntegerField(
        primary_key=True
    )

    name = models.CharField(
        max_length=50
    )

    price = models.FloatField()

    max_posts = models.IntegerField(
        null=True,
        blank=True
    )

    max_images_per_post = models.IntegerField(
        null=True,
        blank=True
    )

    max_likes = models.IntegerField(
        null=True,
        blank=True
    )

    max_comments = models.IntegerField(
        null=True,
        blank=True
    )

    duration_days = models.IntegerField()

    is_active = models.BooleanField()

    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "subscription_plans"

    def __str__(self):
        return self.name


# =========================================================
# Billing History
# =========================================================

class BillingHistory(models.Model):
    id = models.IntegerField(
        primary_key=True
    )

    user_id = models.IntegerField()

    plan_id = models.IntegerField(
        null=True,
        blank=True
    )

    price = models.FloatField()

    start_date = models.DateTimeField()

    end_date = models.DateTimeField()

    transaction_id = models.CharField(
        max_length=100
    )

    invoice_path = models.CharField(
        max_length=500,
        null=True,
        blank=True
    )

    status = models.CharField(
        max_length=30
    )

    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "billing_history"

    def __str__(self):
        return self.transaction_id

# =========================================================
# Blog User
# =========================================================

class BlogUser(models.Model):
    id = models.IntegerField(
        primary_key=True
    )

    username = models.CharField(
        max_length=150
    )

    email = models.EmailField()


    subscription_plan_id = models.IntegerField(
        null=True,
        blank=True
    )

    subscription_start_date = models.DateTimeField(
        null=True,
        blank=True
    )

    subscription_end_date = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        managed = False
        db_table = "users"

    def __str__(self):
        return self.username