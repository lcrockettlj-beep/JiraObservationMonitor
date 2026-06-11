import os

from jira_client import safe_jira_get


USER_PAGE_SIZE = int(os.getenv("JOM_USER_PAGE_SIZE", "100"))


def _extract_application_role_products(application_roles_payload):
    if not isinstance(application_roles_payload, list):
        return []

    products = []

    for role in application_roles_payload:
        if not isinstance(role, dict):
            continue

        products.append({
            "key": role.get("key"),
            "name": role.get("name"),
            "user_count": role.get("userCount"),
            "number_of_seats": role.get("numberOfSeats"),
            "remaining_seats": role.get("remainingSeats"),
            "has_unlimited_seats": role.get("hasUnlimitedSeats"),
            "selected_by_default": role.get("selectedByDefault"),
            "defined": role.get("defined")
        })

    return products


def _estimate_licensed_users_from_roles(products):
    """
    Conservative estimate:
    - take the maximum visible product userCount where present
    - avoids double-counting across multiple app roles
    """
    counts = []

    for product in products:
        user_count = product.get("user_count")
        if isinstance(user_count, int):
            counts.append(user_count)

    if not counts:
        return None

    return max(counts)


def _fetch_all_users(access_token, cloud_id):
    """
    Uses Jira Cloud users/search endpoint in pages.
    Note: Jira user search/list resources only return users found within the first 1000 users.
    """
    users = []
    start_at = 0
    max_results = USER_PAGE_SIZE

    while True:
        result = safe_jira_get(
            access_token=access_token,
            cloud_id=cloud_id,
            endpoint="users/search",
            params={
                "startAt": start_at,
                "maxResults": max_results
            }
        )

        if not result.get("ok"):
            return {
                "ok": False,
                "users": [],
                "error": result.get("error"),
                "error_category": result.get("error_category"),
                "status_code": result.get("status_code"),
                "url": result.get("url")
            }

        payload = result.get("data")
        if not isinstance(payload, list):
            payload = []

        users.extend(payload)

        if len(payload) < max_results:
            break

        start_at += max_results

        if start_at >= 1000:
            break

    return {
        "ok": True,
        "users": users,
        "error": None,
        "error_category": None,
        "status_code": 200,
        "url": None
    }


def _summarise_users(users):
    total_users = 0
    active_users = 0
    inactive_users = 0

    for user in users:
        if not isinstance(user, dict):
            continue

        total_users += 1

        if user.get("active") is True:
            active_users += 1
        elif user.get("active") is False:
            inactive_users += 1

    return {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": inactive_users
    }


def collect_user_and_licence_data(access_token, cloud_id, application_roles_payload=None):
    products = _extract_application_role_products(application_roles_payload)
    licensed_users_estimate = _estimate_licensed_users_from_roles(products)

    user_fetch = _fetch_all_users(access_token, cloud_id)

    if user_fetch["ok"]:
        user_summary = _summarise_users(user_fetch["users"])
    else:
        user_summary = {
            "total_users": None,
            "active_users": None,
            "inactive_users": None
        }

    return {
        "user_summary": user_summary,
        "user_fetch_status": {
            "ok": user_fetch["ok"],
            "error": user_fetch["error"],
            "error_category": user_fetch["error_category"],
            "status_code": user_fetch["status_code"],
            "url": user_fetch["url"]
        },
        "licence_summary": {
            "licensed_users_estimate": licensed_users_estimate,
            "products": products
        }
    }