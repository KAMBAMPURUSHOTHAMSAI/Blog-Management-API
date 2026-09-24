import re


# =========================================================
# AI Support Service
# =========================================================
#
# This service currently uses a lightweight FAQ-based
# response system.
#
# Later, a real AI provider such as OpenAI, Hugging Face,
# or a local LLM can be connected here without changing
# the API route or frontend.
# =========================================================


# =========================================================
# FAQ Responses
# =========================================================

FAQ_RESPONSES = {
    "create_post": (
        "To create a post, log in to your account and use the "
        "Create Post option. Enter the title and content, and "
        "you can optionally upload images. Your active "
        "subscription plan determines how many posts and "
        "images you can create."
    ),

    "edit_post": (
        "To edit a post, open your own post and use the update "
        "option. Only the owner of the post can update it. "
        "You can change the title, content, and supported image."
    ),

    "delete_post": (
        "To delete a post, use the delete option on your own "
        "post. Only the post owner can delete it. Associated "
        "post images and related records are also cleaned up."
    ),

    "subscription": (
        "The platform provides Basic, Premium, and Pro "
        "subscription plans. Each plan controls limits for "
        "posts, images, likes, and comments. The active plan "
        "determines which features you can use."
    ),

    "billing": (
        "Billing information is stored in billing history. "
        "Each subscription generates a transaction ID and a "
        "sample invoice PDF. You can check your billing history "
        "through the subscription section."
    ),

    "profile": (
        "Your profile contains your username and email details. "
        "Authentication is handled using JWT tokens. Protected "
        "features use your authenticated account identity."
    ),

    "dashboard": (
        "The dashboard shows your personal analytics, including "
        "total posts, comments made, likes received, and "
        "post-level engagement. The chart is generated "
        "dynamically using Chart.js."
    ),

    "comments": (
        "You can add comments to posts when your active "
        "subscription allows it. Comments are stored in the "
        "database and the post owner receives a notification "
        "when someone comments on their post."
    ),

    "likes": (
        "You can like posts when your subscription allows it. "
        "A user cannot like the same post twice at the same "
        "time. You can also unlike a post. The post owner "
        "receives a notification when their post is liked."
    ),

    "notifications": (
        "The Notification Center is available from the bell "
        "icon. It shows recent like, comment, and subscription "
        "notifications. You can view unread notifications and "
        "mark individual or all notifications as read."
    ),

    "images": (
        "Posts can contain supported image files. The platform "
        "validates image type and size and stores uploaded "
        "images under the media/posts directory. The number of "
        "images allowed depends on your subscription plan."
    ),

    "search": (
        "You can search blog posts using keywords from the post "
        "title or content. Search can also be combined with "
        "pagination."
    ),

    "pagination": (
        "The posts API supports page-based pagination using "
        "page and limit values. The response also provides "
        "total_count and total_pages information."
    ),

    "general": (
        "I can help you with posts, comments, likes, "
        "subscriptions, billing, profile information, "
        "dashboard analytics, notifications, images, search, "
        "and general platform usage. Try asking a specific "
        "question."
    ),
}


# =========================================================
# Keyword Groups
# =========================================================

KEYWORD_GROUPS = {
    "create_post": [
        "create post",
        "new post",
        "add post",
        "how to post",
        "publish post",
        "create a blog",
        "write a post",
    ],

    "edit_post": [
        "edit post",
        "update post",
        "modify post",
        "change post",
    ],

    "delete_post": [
        "delete post",
        "remove post",
        "erase post",
    ],

    "subscription": [
        "subscription",
        "plan",
        "premium",
        "basic plan",
        "pro plan",
        "upgrade",
        "renew",
    ],

    "billing": [
        "billing",
        "invoice",
        "transaction",
        "payment",
        "price",
        "purchase",
    ],

    "profile": [
        "profile",
        "username",
        "email",
        "account details",
        "account",
    ],

    "dashboard": [
        "dashboard",
        "analytics",
        "statistics",
        "chart",
        "likes received",
        "comments made",
        "post views",
    ],

    "comments": [
        "comment",
        "comments",
        "reply",
    ],

    "likes": [
        "like",
        "likes",
        "unlike",
        "liked",
    ],

    "notifications": [
        "notification",
        "notifications",
        "bell",
        "unread",
        "read notification",
        "mark as read",
    ],

    "images": [
        "image",
        "images",
        "photo",
        "picture",
        "upload image",
        "upload photo",
    ],

    "search": [
        "search",
        "find post",
        "find blog",
        "keyword",
    ],

    "pagination": [
        "pagination",
        "page",
        "pages",
        "limit",
        "total pages",
    ],
}


# =========================================================
# Text Normalization
# =========================================================

def normalize_message(
    message: str,
) -> str:
    """
    Convert the user's message into a simple normalized
    lowercase form for keyword matching.
    """

    normalized = message.strip().lower()

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    )

    return normalized


# =========================================================
# Intent Detection
# =========================================================

def detect_intent(
    message: str,
) -> str:
    """
    Detect the most relevant FAQ category from the
    user's message.

    Returns the FAQ key.
    """

    normalized_message = normalize_message(
        message
    )

    # Exact / phrase matching
    for intent, keywords in KEYWORD_GROUPS.items():

        for keyword in keywords:

            if keyword in normalized_message:
                return intent

    return "general"


# =========================================================
# Generate AI Support Response
# =========================================================

def generate_ai_response(
    message: str,
) -> str:
    """
    Generate a support response from the FAQ knowledge base.

    This is currently a mocked / rule-based AI response
    implementation.

    Later this function can call a real AI provider.
    """

    intent = detect_intent(
        message
    )

    return FAQ_RESPONSES.get(
        intent,
        FAQ_RESPONSES["general"],
    )