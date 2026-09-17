from datetime import timedelta

from sqlalchemy.orm import Session

from app.database import engine
from app.models import SubscriptionPlan, User, utc_now


def activate_basic_for_existing_users():
    with Session(engine) as db:

        basic_plan = (
            db.query(SubscriptionPlan)
            .filter(
                SubscriptionPlan.name == "Basic",
                SubscriptionPlan.is_active == True
            )
            .first()
        )

        if basic_plan is None:
            print("ERROR: Basic subscription plan not found.")
            return

        users = (
            db.query(User)
            .filter(User.subscription_plan_id.is_(None))
            .all()
        )

        if not users:
            print("All users already have a subscription.")
            return

        now = utc_now()
        end_date = now + timedelta(days=basic_plan.duration_days)

        updated_count = 0

        for user in users:
            user.subscription_plan_id = basic_plan.id
            user.subscription_start_date = now
            user.subscription_end_date = end_date

            updated_count += 1

            print(f"Activated Basic plan for: {user.username}")

        db.commit()

        print(
            f"Successfully activated Basic plan for "
            f"{updated_count} user(s)."
        )


if __name__ == "__main__":
    activate_basic_for_existing_users()