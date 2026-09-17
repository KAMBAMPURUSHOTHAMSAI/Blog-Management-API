from django.contrib import admin

from .models import (
    BillingHistory,
    SubscriptionPlan,
    BlogUser,
)


# =========================================================
# Subscription Plan Admin
# =========================================================

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "name",
        "price",
        "max_posts",
        "max_images_per_post",
        "max_likes",
        "max_comments",
        "duration_days",
        "is_active",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "name",
    )

    ordering = (
        "id",
    )


# =========================================================
# Billing History Admin
# =========================================================

@admin.register(BillingHistory)
class BillingHistoryAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "user_id",
        "plan_id",
        "price",
        "transaction_id",
        "status",
        "start_date",
        "end_date",
        "created_at",
    )

    list_filter = (
        "status",
    )

    search_fields = (
        "transaction_id",
    )

    ordering = (
        "-created_at",
    )

    readonly_fields = (
        "id",
        "user_id",
        "plan_id",
        "price",
        "start_date",
        "end_date",
        "transaction_id",
        "invoice_path",
        "status",
        "created_at",
    )
# =========================================================
# Blog User Admin
# =========================================================

@admin.register(BlogUser)
class BlogUserAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "username",
        "email",
        "subscription_plan_id",
        "subscription_start_date",
        "subscription_end_date",
    )

    search_fields = (
        "username",
        "email",
    )

    list_filter = (
        "subscription_plan_id",
    )

    ordering = (
        "id",
    )

    readonly_fields = (
        "id",
        "username",
        "email",
        "subscription_plan_id",
        "subscription_start_date",
        "subscription_end_date",
    )