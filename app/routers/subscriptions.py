from datetime import timedelta
from pathlib import Path
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import (
    BillingHistory,
    SubscriptionPlan,
    User,
    utc_now,
)
from app.schemas import (
    BillingHistoryResponse,
    SubscribeRequest,
    SubscriptionPlanResponse,
    SubscriptionResponse,
)
from app.services.notification_service import (
    create_subscription_notification,
)


# =========================================================
# Router
# =========================================================

router = APIRouter(
    prefix="/subscriptions",
    tags=["Subscriptions"],
)


# =========================================================
# Invoice Directory
# =========================================================

INVOICE_DIR = Path("media/invoices")

INVOICE_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# =========================================================
# Friendly Plan Limit Message
# =========================================================

PLAN_LIMIT_MESSAGE = (
    "You’ve reached your plan limit. "
    "Kindly upgrade your plan to continue."
)


# =========================================================
# Generate Fake Invoice PDF
# =========================================================

def generate_invoice_pdf(
    user: User,
    plan: SubscriptionPlan,
    start_date,
    end_date,
    transaction_id: str,
) -> str:
    """
    Generate a fake invoice PDF using ReportLab.
    """

    invoice_filename = (
        f"invoice_{transaction_id}.pdf"
    )

    invoice_path = INVOICE_DIR / invoice_filename

    document = SimpleDocTemplate(
        str(invoice_path),
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )

    styles = getSampleStyleSheet()

    title_style = styles["Title"]
    heading_style = styles["Heading2"]
    normal_style = styles["Normal"]

    story = []

    # -----------------------------------------------------
    # Invoice Title
    # -----------------------------------------------------

    story.append(
        Paragraph(
            "BLOG MANAGEMENT API",
            title_style,
        )
    )

    story.append(
        Spacer(1, 10)
    )

    story.append(
        Paragraph(
            "Subscription Invoice",
            heading_style,
        )
    )

    story.append(
        Spacer(1, 20)
    )

    # -----------------------------------------------------
    # Customer Information
    # -----------------------------------------------------

    customer_data = [
        ["User Name", user.username],
        ["Email", user.email],
        ["Plan", plan.name],
        ["Price", f"₹{plan.price:.2f}"],
        [
            "Start Date",
            start_date.strftime("%Y-%m-%d %H:%M:%S"),
        ],
        [
            "End Date",
            end_date.strftime("%Y-%m-%d %H:%M:%S"),
        ],
        ["Transaction ID", transaction_id],
        ["Status", "Completed"],
    ]

    customer_table = Table(
        customer_data,
        colWidths=[140, 330],
    )

    customer_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (0, -1),
                    colors.lightgrey,
                ),
                (
                    "TEXTCOLOR",
                    (0, 0),
                    (-1, -1),
                    colors.black,
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (0, -1),
                    "Helvetica-Bold",
                ),
                (
                    "FONTNAME",
                    (1, 0),
                    (1, -1),
                    "Helvetica",
                ),
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
            ]
        )
    )

    story.append(customer_table)

    story.append(
        Spacer(1, 25)
    )

    story.append(
        Paragraph(
            "This is a sample invoice generated for "
            "the Blog Management API subscription.",
            normal_style,
        )
    )

    document.build(story)

    # Store relative path in database
    return f"/media/invoices/{invoice_filename}"


# =========================================================
# GET ALL SUBSCRIPTION PLANS
# =========================================================

@router.get(
    "/plans",
    response_model=list[SubscriptionPlanResponse],
    summary="Get available subscription plans",
)
def get_subscription_plans(
    db: Session = Depends(get_db),
):
    """
    Return all active subscription plans.
    """

    plans = (
        db.query(SubscriptionPlan)
        .filter(
            SubscriptionPlan.is_active == True
        )
        .order_by(
            SubscriptionPlan.price.asc()
        )
        .all()
    )

    return plans


# =========================================================
# SUBSCRIBE / UPGRADE PLAN
# =========================================================

@router.post(
    "/subscribe",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subscribe or upgrade subscription plan",
)
def subscribe_to_plan(
    request: SubscribeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Subscribe the authenticated user to a plan.

    A billing record, fake invoice PDF and in-app
    notification are generated for every subscription.
    """

    # -----------------------------------------------------
    # Find selected plan
    # -----------------------------------------------------

    plan = (
        db.query(SubscriptionPlan)
        .filter(
            SubscriptionPlan.id == request.plan_id,
            SubscriptionPlan.is_active == True,
        )
        .first()
    )

    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Subscription plan not found or inactive.",
        )

    # -----------------------------------------------------
    # Check existing subscription BEFORE updating it
    # -----------------------------------------------------

    had_active_subscription = (
        current_user.has_active_subscription()
    )

    same_plan_renewal = (
        had_active_subscription
        and current_user.subscription_plan_id == plan.id
    )

    # -----------------------------------------------------
    # Subscription dates
    # -----------------------------------------------------

    start_date = utc_now()

    end_date = start_date + timedelta(
        days=plan.duration_days
    )

    # -----------------------------------------------------
    # Fake transaction ID
    # -----------------------------------------------------

    transaction_id = (
        f"TXN-{uuid.uuid4().hex[:16].upper()}"
    )

    # -----------------------------------------------------
    # Generate invoice
    # -----------------------------------------------------

    invoice_path = generate_invoice_pdf(
        user=current_user,
        plan=plan,
        start_date=start_date,
        end_date=end_date,
        transaction_id=transaction_id,
    )

    # -----------------------------------------------------
    # Update user's active subscription
    # -----------------------------------------------------

    current_user.subscription_plan_id = plan.id
    current_user.subscription_start_date = start_date
    current_user.subscription_end_date = end_date

    # -----------------------------------------------------
    # Create billing history
    # -----------------------------------------------------

    billing = BillingHistory(
        user_id=current_user.id,
        plan_id=plan.id,
        price=plan.price,
        start_date=start_date,
        end_date=end_date,
        transaction_id=transaction_id,
        invoice_path=invoice_path,
        status="completed",
    )

    db.add(billing)

    # -----------------------------------------------------
    # Create In-App Subscription Notification
    # -----------------------------------------------------
    #
    # Same active plan  -> renewed
    # New/different plan -> activated
    #
    # Notification is added to the same transaction.
    # -----------------------------------------------------

    notification_action = (
        "renewed"
        if same_plan_renewal
        else "activated"
    )

    create_subscription_notification(
        db=db,
        user_id=current_user.id,
        plan_name=plan.name,
        action=notification_action,
    )

    # -----------------------------------------------------
    # Commit subscription + billing + notification
    # -----------------------------------------------------

    db.commit()

    db.refresh(current_user)
    db.refresh(billing)

    # -----------------------------------------------------
    # Return subscription information
    # -----------------------------------------------------

    return {
        "message": (
            f"Successfully subscribed to the "
            f"{plan.name} plan."
        ),
        "user_id": current_user.id,
        "plan": plan,
        "subscription_start_date": (
            current_user.subscription_start_date
        ),
        "subscription_end_date": (
            current_user.subscription_end_date
        ),
        "billing": billing,
    }


# =========================================================
# GET CURRENT USER SUBSCRIPTION
# =========================================================

@router.get(
    "/my-subscription",
    response_model=SubscriptionResponse,
    summary="Get current user's subscription",
)
def get_my_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return the currently active subscription of
    the authenticated user.
    """

    if current_user.subscription_plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "You do not have an active subscription. "
                "Please subscribe to a plan."
            ),
        )

    # -----------------------------------------------------
    # Find latest billing record
    # -----------------------------------------------------

    latest_billing = (
        db.query(BillingHistory)
        .filter(
            BillingHistory.user_id == current_user.id
        )
        .order_by(
            BillingHistory.created_at.desc()
        )
        .first()
    )

    # -----------------------------------------------------
    # Check subscription dates
    # -----------------------------------------------------

    now = utc_now()

    start_date = current_user.subscription_start_date
    end_date = current_user.subscription_end_date

    if start_date is not None and end_date is not None:

        # SQLite may return naive datetime values.
        # Compare using naive UTC values safely.
        now_naive = now.replace(tzinfo=None)

        start_naive = (
            start_date.replace(tzinfo=None)
            if start_date.tzinfo
            else start_date
        )

        end_naive = (
            end_date.replace(tzinfo=None)
            if end_date.tzinfo
            else end_date
        )

        if now_naive > end_naive:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Your subscription has expired. "
                    "Please renew or upgrade your plan."
                ),
            )

        if now_naive < start_naive:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Your subscription has not started yet."
                ),
            )

    return {
        "message": "Active subscription found.",
        "user_id": current_user.id,
        "plan": current_user.subscription_plan,
        "subscription_start_date": start_date,
        "subscription_end_date": end_date,
        "billing": latest_billing,
    }


# =========================================================
# GET BILLING HISTORY
# =========================================================

@router.get(
    "/billing-history",
    response_model=list[BillingHistoryResponse],
    summary="Get current user's billing history",
)
def get_billing_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return all billing records belonging to the
    authenticated user.
    """

    billing_records = (
        db.query(BillingHistory)
        .filter(
            BillingHistory.user_id == current_user.id
        )
        .order_by(
            BillingHistory.created_at.desc()
        )
        .all()
    )

    return billing_records