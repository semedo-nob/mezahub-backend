#!/usr/bin/env python
"""
Database seeding script for MEZAHUB.

Run:
  python scripts/seed_db.py --force
  python scripts/seed_db.py --clear-only --force
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import time

from sqlalchemy.exc import IntegrityError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app  # noqa: E402
from app.extensions.database import db  # noqa: E402
from app.models import (  # noqa: E402
    Cart,
    CartItem,
    Delivery,
    Favorite,
    MenuCategory,
    MenuItem,
    MenuItemOption,
    Notification,
    Order,
    OrderItem,
    OrderStatusHistory,
    Payment,
    Restaurant,
    Review,
    Rider,
    User,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("seed_db")

PLACEHOLDER_IMAGES = {
    "restaurant": "https://placehold.co/600x400/FF6B6B/white?text=Restaurant",
    "pizza": "https://placehold.co/600x400/F9A826/white?text=Pizza",
    "burger": "https://placehold.co/600x400/4ECDC4/white?text=Burger",
    "drink": "https://placehold.co/600x400/45B7D1/white?text=Drink",
    "user": "https://placehold.co/200x200/95A5A6/white?text=User",
    "rider": "https://placehold.co/200x200/3498DB/white?text=Rider",
}


def safe_commit() -> None:
    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        raise RuntimeError(f"Integrity error: {e}") from e
    except Exception as e:
        db.session.rollback()
        raise


def get_or_create(model, defaults=None, **kwargs):
    instance = model.query.filter_by(**kwargs).first()
    if instance:
        return instance, False
    params = dict(kwargs)
    if defaults:
        params.update(defaults)
    instance = model(**params)
    db.session.add(instance)
    return instance, True


def clear_tables(force: bool) -> None:
    if not force:
        confirm = input("⚠️  This will DELETE ALL DATA. Type 'yes' to continue: ")
        if confirm.strip().lower() != "yes":
            logger.info("Cancelled.")
            raise SystemExit(1)

    logger.info("🗑️  Clearing database...")
    tables_to_clear = [
        OrderStatusHistory,
        OrderItem,
        CartItem,
        MenuItemOption,
        Review,
        Favorite,
        Notification,
        Payment,
        Delivery,
        Order,
        Cart,
        MenuItem,
        MenuCategory,
        Rider,
        Restaurant,
        User,
    ]

    for table in tables_to_clear:
        deleted = table.query.delete()
        logger.info("   Cleared %s rows from %s", deleted, table.__tablename__)

    safe_commit()
    logger.info("✅ Database cleared")


def seed_database(force: bool, clear_only: bool) -> None:
    app = create_app(os.getenv("FLASK_ENV", "development"))

    with app.app_context():
        if force or clear_only:
            clear_tables(force=force)
            if clear_only:
                return

        logger.info("🌱 Seeding database...")

        users_data = [
            {
                "name": "John Customer",
                "email": "customer@test.com",
                "phone": "+254712345678",
                "password": "customer123",
                "role": "customer",
                "profile_image": PLACEHOLDER_IMAGES["user"],
            },
            {
                "name": "Sarah Restaurant Owner",
                "email": "owner@test.com",
                "phone": "+254723456789",
                "password": "owner1234",
                "role": "restaurant",
                "profile_image": PLACEHOLDER_IMAGES["restaurant"],
            },
            {
                "name": "Mike Rider",
                "email": "rider@test.com",
                "phone": "+254734567890",
                "password": "rider1234",
                "role": "rider",
                "profile_image": PLACEHOLDER_IMAGES["rider"],
            },
            {
                "name": "Admin User",
                "email": "admin@test.com",
                "phone": "+254700000000",
                "password": "admin1234",
                "role": "admin",
                "profile_image": PLACEHOLDER_IMAGES["user"],
            },
            {
                "name": "Pizza Hut Owner",
                "email": "pizzahut@test.com",
                "phone": "+254767890123",
                "password": "pizza1234",
                "role": "restaurant",
                "profile_image": PLACEHOLDER_IMAGES["restaurant"],
            },
            {
                "name": "Burger King Owner",
                "email": "burgerking@test.com",
                "phone": "+254778901234",
                "password": "burger1234",
                "role": "restaurant",
                "profile_image": PLACEHOLDER_IMAGES["restaurant"],
            },
            {
                "name": "Jane Rider",
                "email": "jane.rider@test.com",
                "phone": "+254789012345",
                "password": "jane12345",
                "role": "rider",
                "profile_image": PLACEHOLDER_IMAGES["rider"],
            },
        ]

        for u in users_data:
            existing = User.find_by_email(u["email"])
            if existing:
                logger.info("   ⏩ User exists: %s", existing.email)
                continue
            user = User(
                name=u["name"],
                email=u["email"],
                phone=u.get("phone", ""),
                role=u["role"],
                profile_image=u.get("profile_image"),
                is_active=True,
            )
            user.set_password(u["password"])
            db.session.add(user)
            logger.info("   ✅ Created user: %s", user.email)

        safe_commit()

        owner1 = User.find_by_email("owner@test.com")
        owner2 = User.find_by_email("pizzahut@test.com")
        owner3 = User.find_by_email("burgerking@test.com")
        if not owner1 or not owner2 or not owner3:
            raise RuntimeError("Missing restaurant owners; seed users step failed.")

        restaurants_data = [
            {
                "owner_id": owner1.id,
                "name": "Pizza Paradise",
                "description": "Best Italian pizza in town with fresh ingredients",
                "address": "123 Kenyatta Avenue, Nairobi",
                "cuisine_type": "Italian",
                "opening_time": time(9, 0),
                "closing_time": time(22, 0),
                "delivery_fee": 2.99,
                "minimum_order": 10.00,
                "approved": True,
                "is_open": True,
                "cover_image": PLACEHOLDER_IMAGES["pizza"],
                "latitude": -1.286389,
                "longitude": 36.817223,
                "phone": "+254700111222",
            },
            {
                "owner_id": owner2.id,
                "name": "Pizza Hut Express",
                "description": "Fast delivery pizza",
                "address": "456 Moi Avenue, Mombasa",
                "cuisine_type": "Fast Food",
                "opening_time": time(10, 0),
                "closing_time": time(23, 0),
                "delivery_fee": 1.99,
                "minimum_order": 8.00,
                "approved": True,
                "is_open": True,
                "cover_image": PLACEHOLDER_IMAGES["pizza"],
                "latitude": -4.043477,
                "longitude": 39.668205,
                "phone": "+254700333444",
            },
            {
                "owner_id": owner3.id,
                "name": "Burger King",
                "description": "Flame-grilled burgers",
                "address": "789 Uhuru Highway, Kisumu",
                "cuisine_type": "American",
                "opening_time": time(8, 0),
                "closing_time": time(21, 0),
                "delivery_fee": 3.50,
                "minimum_order": 12.00,
                "approved": True,
                "is_open": True,
                "cover_image": PLACEHOLDER_IMAGES["burger"],
                "latitude": -0.102210,
                "longitude": 34.761711,
                "phone": "+254700555666",
            },
        ]

        created_restaurants = []
        for r in restaurants_data:
            restaurant, created = get_or_create(
                Restaurant,
                owner_id=r["owner_id"],
                name=r["name"],
                defaults={k: v for k, v in r.items() if k not in {"owner_id", "name"}},
            )
            if created:
                created_restaurants.append(restaurant)
                logger.info("   ✅ Created restaurant: %s", restaurant.name)
            else:
                logger.info("   ⏩ Restaurant exists: %s", restaurant.name)

        safe_commit()

        for restaurant in Restaurant.query.all():
            categories_data = [
                {"name": "Pizzas", "display_order": 1, "description": "Delicious pizzas"},
                {"name": "Drinks", "display_order": 2, "description": "Cold beverages"},
                {"name": "Sides", "display_order": 3, "description": "Perfect accompaniments"},
            ]
            if "Burger" in restaurant.name:
                categories_data = [
                    {"name": "Burgers", "display_order": 1, "description": "Signature burgers"},
                    {"name": "Fries", "display_order": 2, "description": "Crispy fries"},
                    {"name": "Drinks", "display_order": 3, "description": "Beverages"},
                ]

            for cat in categories_data:
                get_or_create(
                    MenuCategory,
                    restaurant_id=restaurant.id,
                    name=cat["name"],
                    defaults={"display_order": cat["display_order"], "description": cat["description"]},
                )

        safe_commit()

        for restaurant in Restaurant.query.all():
            pizza_cat = MenuCategory.query.filter_by(restaurant_id=restaurant.id, name="Pizzas").first()
            drinks_cat = MenuCategory.query.filter_by(restaurant_id=restaurant.id, name="Drinks").first()
            burgers_cat = MenuCategory.query.filter_by(restaurant_id=restaurant.id, name="Burgers").first()

            if pizza_cat:
                for item_data in [
                    {
                        "name": "Margherita",
                        "description": "Tomato sauce, fresh mozzarella, basil",
                        "price": 12.99,
                        "image_url": PLACEHOLDER_IMAGES["pizza"],
                        "preparation_time": 15,
                        "calories": 800,
                    },
                    {
                        "name": "Pepperoni",
                        "description": "Tomato sauce, mozzarella, double pepperoni",
                        "price": 14.99,
                        "image_url": PLACEHOLDER_IMAGES["pizza"],
                        "preparation_time": 15,
                        "calories": 950,
                    },
                ]:
                    item, created = get_or_create(
                        MenuItem,
                        restaurant_id=restaurant.id,
                        category_id=pizza_cat.id,
                        name=item_data["name"],
                        defaults={k: v for k, v in item_data.items() if k != "name"},
                    )
                    if created:
                        # Ensure item.id exists before adding options.
                        db.session.flush()
                        for opt in [
                            {"name": "Extra Cheese", "price_adjustment": 1.50},
                            {"name": "Gluten Free Crust", "price_adjustment": 2.50},
                        ]:
                            db.session.add(
                                MenuItemOption(
                                    menu_item_id=item.id,
                                    name=opt["name"],
                                    price_adjustment=opt["price_adjustment"],
                                )
                            )

            if burgers_cat:
                for item_data in [
                    {
                        "name": "Whopper",
                        "description": "Flame-grilled beef patty, lettuce, tomato, mayo",
                        "price": 8.99,
                        "image_url": PLACEHOLDER_IMAGES["burger"],
                        "preparation_time": 10,
                        "calories": 1100,
                    }
                ]:
                    get_or_create(
                        MenuItem,
                        restaurant_id=restaurant.id,
                        category_id=burgers_cat.id,
                        name=item_data["name"],
                        defaults={k: v for k, v in item_data.items() if k != "name"},
                    )

            if drinks_cat:
                for item_data in [
                    {
                        "name": "Coca Cola",
                        "description": "Chilled 500ml",
                        "price": 2.50,
                        "image_url": PLACEHOLDER_IMAGES["drink"],
                        "preparation_time": 1,
                        "calories": 210,
                    }
                ]:
                    get_or_create(
                        MenuItem,
                        restaurant_id=restaurant.id,
                        category_id=drinks_cat.id,
                        name=item_data["name"],
                        defaults={k: v for k, v in item_data.items() if k != "name"},
                    )

        safe_commit()

        # ------------------------------------------------------------------
        # Extra mock data aligned with customer app categories/menu_items
        # ------------------------------------------------------------------
        first_restaurant = Restaurant.query.first()
        if first_restaurant:
            mock_categories = [
                ("specials", "Specials"),
                ("appetizers", "Appetizers"),
                ("mains", "Main Courses"),
                ("desserts", "Desserts"),
                ("drinks", "Beverages"),
            ]
            cat_map: dict[str, MenuCategory] = {}
            order_idx = 10
            for cid, cname in mock_categories:
                cat, _ = get_or_create(
                    MenuCategory,
                    restaurant_id=first_restaurant.id,
                    name=cname,
                    defaults={"display_order": order_idx, "description": ""},
                )
                cat_map[cid] = cat
                order_idx += 1

            mock_items = [
                # specials
                {
                    "external_id": "s1",
                    "category_key": "specials",
                    "name": "Rack of Lamb with Vegetables",
                    "description": "Tender rack of lamb served with seasonal roasted vegetables and mint sauce",
                    "price": 38.0,
                    "image_url": "https://images.pexels.com/photos/323682/pexels-photo-323682.jpeg",
                    "preparation_time": 30,
                },
                {
                    "external_id": "s2",
                    "category_key": "specials",
                    "name": "Grilled Steak with Vegetables",
                    "description": "Premium grilled steak with herb butter and fresh seasonal vegetables",
                    "price": 32.0,
                    "image_url": "https://images.pexels.com/photos/769289/pexels-photo-769289.jpeg",
                    "preparation_time": 25,
                },
                # appetizers
                {
                    "external_id": "a1",
                    "category_key": "appetizers",
                    "name": "Chicken Wings with Dipping Sauce",
                    "description": "Crispy chicken wings with your choice of signature dipping sauces",
                    "price": 14.0,
                    "image_url": "https://images.pexels.com/photos/1893561/pexels-photo-1893561.jpeg",
                    "preparation_time": 15,
                },
                {
                    "external_id": "a2",
                    "category_key": "appetizers",
                    "name": "Bruschetta with Tomatoes and Basil",
                    "description": "Toasted bread topped with fresh tomatoes, basil, and olive oil",
                    "price": 12.0,
                    "image_url": "https://images.pexels.com/photos/434283/pexels-photo-434283.jpeg",
                    "preparation_time": 10,
                },
                # mains
                {
                    "external_id": "m1",
                    "category_key": "mains",
                    "name": "Beef Burger with Fries",
                    "description": "Juicy beef burger with cheese, lettuce, and crispy fries",
                    "price": 16.0,
                    "image_url": "https://images.pexels.com/photos/725992/pexels-photo-725992.jpeg",
                    "preparation_time": 12,
                },
                {
                    "external_id": "m2",
                    "category_key": "mains",
                    "name": "Seafood Paella",
                    "description": "Traditional Spanish paella with mixed seafood and saffron rice",
                    "price": 32.0,
                    "image_url": "https://images.pexels.com/photos/34501903/pexels-photo-34501903.jpeg",
                    "preparation_time": 35,
                },
                # desserts
                {
                    "external_id": "d1",
                    "category_key": "desserts",
                    "name": "Chocolate Cake Slice",
                    "description": "Rich chocolate cake with chocolate ganache and berries",
                    "price": 9.0,
                    "image_url": "https://images.pexels.com/photos/45202/chocolate-dark-coffee-confiserie-45202.jpeg",
                    "preparation_time": 5,
                },
                # drinks
                {
                    "external_id": "dr1",
                    "category_key": "drinks",
                    "name": "Fresh Orange Juice",
                    "description": "Freshly squeezed orange juice",
                    "price": 4.5,
                    "image_url": "https://images.pexels.com/photos/96974/pexels-photo-96974.jpeg",
                    "preparation_time": 2,
                },
            ]

            for mi in mock_items:
                cat = cat_map.get(mi["category_key"])
                if not cat:
                    continue
                get_or_create(
                    MenuItem,
                    restaurant_id=first_restaurant.id,
                    category_id=cat.id,
                    name=mi["name"],
                    defaults={
                        "description": mi["description"],
                        "price": mi["price"],
                        "image_url": mi["image_url"],
                        "preparation_time": mi["preparation_time"],
                        "available": True,
                    },
                )

            safe_commit()

        rider_users = User.query.filter_by(role="rider").all()
        for i, user in enumerate(rider_users):
            get_or_create(
                Rider,
                user_id=user.id,
                defaults={
                    "vehicle_type": ["Motorbike", "Bicycle", "Scooter"][i % 3],
                    "license_plate": f"KAA{i:03d}",
                    "is_available": True,
                    "max_delivery_radius": 10.0,
                },
            )
        safe_commit()

        customer = User.find_by_email("customer@test.com")
        restaurant = Restaurant.query.filter_by(name="Pizza Paradise").first()
        if customer and restaurant:
            cart, created = get_or_create(Cart, customer_id=customer.id, restaurant_id=restaurant.id)
            if created:
                db.session.flush()
                items = MenuItem.query.filter_by(restaurant_id=restaurant.id).limit(2).all()
                for item in items:
                    db.session.add(
                        CartItem(
                            cart_id=cart.id,
                            menu_item_id=item.id,
                            quantity=2,
                            special_instructions="Extra sauce please",
                            selected_options={},
                        )
                    )
                safe_commit()

        logger.info("🎉 Seeding complete.")
        logger.info("Users=%s Restaurants=%s Categories=%s Items=%s Riders=%s", User.query.count(), Restaurant.query.count(), MenuCategory.query.count(), MenuItem.query.count(), Rider.query.count())


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed MEZAHUB database")
    parser.add_argument("--force", "-f", action="store_true", help="Force clear without prompt")
    parser.add_argument("--clear-only", "-c", action="store_true", help="Only clear, don't seed")
    args = parser.parse_args()

    seed_database(force=args.force, clear_only=args.clear_only)


if __name__ == "__main__":
    main()

