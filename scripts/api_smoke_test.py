#!/usr/bin/env python
"""
Simple end-to-end API smoke test against the running server.

Assumes:
- Server running on http://127.0.0.1:5000
- Seed data created via scripts/seed_db.py --force
"""
import json

import requests

BASE = "http://127.0.0.1:5000"
API = f"{BASE}/api/v1"


def pretty(obj):
    return json.dumps(obj, indent=2, sort_keys=True, default=str)


def main() -> None:
    print("=== Health ===")
    r = requests.get(f"{BASE}/health")
    print(r.status_code, r.json())

    # Login as seeded users
    print("\n=== Auth: login customer ===")
    cust = requests.post(
        f"{API}/auth/login",
        json={"email": "customer@test.com", "password": "customer123"},
    )
    print(cust.status_code)
    cust_data = cust.json()
    print(pretty({"user": cust_data.get("user"), "have_tokens": "access_token" in cust_data}))
    cust_token = cust_data.get("access_token")

    print("\n=== Auth: login restaurant owner ===")
    owner = requests.post(
        f"{API}/auth/login",
        json={"email": "owner@test.com", "password": "owner1234"},
    )
    print(owner.status_code)
    owner_data = owner.json()
    print(pretty({"user": owner_data.get("user"), "have_tokens": "access_token" in owner_data}))
    owner_token = owner_data.get("access_token")

    print("\n=== Auth: login rider ===")
    rider = requests.post(
        f"{API}/auth/login",
        json={"email": "rider@test.com", "password": "rider1234"},
    )
    print(rider.status_code)
    rider_data = rider.json()
    print(pretty({"user": rider_data.get("user"), "have_tokens": "access_token" in rider_data}))
    rider_token = rider_data.get("access_token")

    print("\n=== Auth: login admin ===")
    admin = requests.post(
        f"{API}/auth/login",
        json={"email": "admin@test.com", "password": "admin1234"},
    )
    print(admin.status_code)
    admin_data = admin.json()
    print(pretty({"user": admin_data.get("user"), "have_tokens": "access_token" in admin_data}))
    admin_token = admin_data.get("access_token")

    # List restaurants (customer)
    print("\n=== GET /restaurants as customer ===")
    r = requests.get(
        f"{API}/restaurants",
        headers={"Authorization": f"Bearer {cust_token}"},
    )
    print(r.status_code)
    restaurants = r.json()
    print(pretty(restaurants[:2]))
    first_restaurant_id = restaurants[0]["id"] if restaurants else None

    # Create order for first restaurant
    print("\n=== POST /orders as customer ===")
    if first_restaurant_id:
        # pick one menu item from that restaurant
        menu = requests.get(f"{API}/restaurants/{first_restaurant_id}/menu")
        menu_json = menu.json()
        print("Menu status:", menu.status_code)
        # choose first item from first category
        first_item_id = None
        for cat in menu_json.get("categories", []):
            if cat.get("items"):
                first_item_id = cat["items"][0]["id"]
                break
        if not first_item_id:
            print("No menu items found; skipping order creation.")
        else:
            order_req = {
                "restaurant_id": first_restaurant_id,
                "delivery_address": "Test street 123, Nairobi",
                "payment_method": "cash",
                "items": [{"menu_item_id": first_item_id, "quantity": 1}],
            }
            r = requests.post(
                f"{API}/orders",
                json=order_req,
                headers={"Authorization": f"Bearer {cust_token}"},
            )
            print(r.status_code)
            order_data = r.json()
            print(pretty(order_data))
            order_id = order_data.get("id")
    else:
        print("No restaurants; skipping order creation.")
        order_id = None

    # Assign rider using admin
    if order_id:
        print("\n=== POST /orders/{id}/assign-rider as admin ===")
        assign = requests.post(
            f"{API}/orders/{order_id}/assign-rider",
            json={"rider_id": 1},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        print(assign.status_code)
        print(pretty(assign.json()))

        # Rider assignments
        print("\n=== GET /riders/me/assignments as rider ===")
        ass = requests.get(
            f"{API}/riders/me/assignments",
            headers={"Authorization": f"Bearer {rider_token}"},
        )
        print(ass.status_code)
        print(pretty(ass.json()))

        # Customer tracking
        print("\n=== GET /orders/{id}/track as customer ===")
        track = requests.get(
            f"{API}/orders/{order_id}/track",
            headers={"Authorization": f"Bearer {cust_token}"},
        )
        print(track.status_code)
        print(pretty(track.json()))


if __name__ == "__main__":
    main()

