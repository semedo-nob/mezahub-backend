import json
from datetime import datetime, timedelta

from flask import request, Response, url_for, redirect, flash
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from markupsafe import Markup
from werkzeug.exceptions import HTTPException

from app.extensions.database import db
from app.extensions.cache import cache
from app.models import (
    User,
    Restaurant,
    Order,
    MenuItem,
    MenuCategory,
    Delivery,
    Rider,
    Payment,
    Notification,
    Review,
    Favorite,
    Cart,
)
from app.utils.media import build_media_url


class AuthException(HTTPException):
    def __init__(self, message):
        super().__init__(description=message, response=Response(
            message, 401,
            {'WWW-Authenticate': 'Basic realm="Admin Required"'}
        ))


def get_current_admin_user():
    auth = request.authorization
    if not auth or not auth.username:
        return None
    return User.find_by_login(auth.username)


DASHBOARD_CACHE_KEY = "admin:dashboard:v1"
DASHBOARD_CACHE_TTL_SECONDS = 45


def count_users_by_roles(*roles):
    return User.query.filter(User.role.in_(roles)).count()


def _image_preview(value: str | None, alt: str, height: int = 44) -> Markup:
    url = build_media_url(value)
    if not url:
        return Markup('<span class="muted-text">No image</span>')
    return Markup(
        f'<img src="{url}" alt="{alt}" '
        f'style="height:{height}px;width:{height}px;object-fit:cover;border-radius:12px;'
        f'border:1px solid rgba(148,163,184,0.2);background:rgba(255,255,255,0.08);" />'
    )

class SecureModelView(ModelView):
    list_template = 'admin/model/list.html'
    details_template = 'admin/model/details.html'
    can_view_details = True
    can_export = True
    can_set_page_size = True
    page_size = 20
    page_size_options = [20, 50, 100]
    column_display_actions = True

    def check_auth(self):
        auth = request.authorization
        if not auth or not auth.username or not auth.password:
            return False

        user = get_current_admin_user()
        if not user or user.role != "admin" or not user.check_password(auth.password):
            return False
        return True

    def is_accessible(self):
        return self.check_auth()

    def _handle_view(self, name, **kwargs):
        if not self.is_accessible():
            raise AuthException('Authentication Failed.')


def invalidate_dashboard_cache():
    client = cache.client
    if not client:
        return
    try:
        client.delete(DASHBOARD_CACHE_KEY)
    except Exception:
        pass


def _serialize_pending_restaurant(restaurant: Restaurant) -> dict:
    return {
        "id": restaurant.id,
        "name": restaurant.name,
        "phone": restaurant.phone,
        "cuisine_type": restaurant.cuisine_type,
        "logo_image_url": restaurant.logo_image_url,
        "cover_image_url": restaurant.cover_image_url,
    }


def _serialize_recent_order(order: Order) -> dict:
    return {
        "id": order.id,
        "contact_name": order.contact_name,
        "status": order.status,
        "total_amount": float(order.total_amount or 0),
    }


class UserAdminView(SecureModelView):
    details_template = 'admin/model/user_details.html'
    list_template = 'admin/model/user_list.html'
    can_create = False
    column_list = ('id', 'name', 'email', 'phone', 'role', 'is_active', 'created_at')
    column_searchable_list = ('name', 'email', 'phone', 'role')
    column_filters = ('role', 'is_active', 'created_at')
    column_sortable_list = ('id', 'name', 'email', 'role', 'is_active', 'created_at')
    column_default_sort = ('created_at', True)
    column_formatters = {
        'name': lambda v, c, m, p: Markup(
            f'<a class="admin-entity-link" href="{url_for(".details_view", id=m.id, url=url_for(".index_view"))}">{m.name}</a>'
        ),
        'email': lambda v, c, m, p: Markup(
            f'<a class="admin-entity-link" href="{url_for(".details_view", id=m.id, url=url_for(".index_view"))}">{m.email}</a>'
        ),
    }

    def render(self, template, **kwargs):
        kwargs.setdefault("current_user", get_current_admin_user())
        return super().render(template, **kwargs)

    @expose('/<int:user_id>/toggle-operations', methods=['POST'])
    def toggle_operations(self, user_id):
        if not self.check_auth():
            raise AuthException('Authentication Failed.')

        user = User.query.get_or_404(user_id)
        current_admin = get_current_admin_user()

        if current_admin and user.id == current_admin.id:
            flash('You cannot pause your own admin account.', 'warning')
            return redirect(request.form.get('return_url') or url_for('.index_view'))

        user.is_active = not user.is_active
        db.session.commit()
        invalidate_dashboard_cache()

        action = 'resumed' if user.is_active else 'paused'
        flash(f'User "{user.name}" has been {action}.', 'success')
        return redirect(request.form.get('return_url') or url_for('.details_view', id=user.id, url=url_for('.index_view')))


class RestaurantAdminView(SecureModelView):
    details_template = 'admin/model/restaurant_details.html'
    column_list = ('id', 'logo_image', 'cover_image', 'name', 'cuisine_type', 'phone', 'approved', 'is_open', 'created_at')
    column_searchable_list = ('name', 'cuisine_type', 'phone', 'address')
    column_filters = ('approved', 'is_open', 'cuisine_type', 'created_at')
    column_sortable_list = ('id', 'name', 'cuisine_type', 'approved', 'is_open', 'created_at')
    column_default_sort = ('created_at', True)
    column_formatters = {
        'logo_image': lambda v, c, m, p: _image_preview(m.logo_image, m.name),
        'cover_image': lambda v, c, m, p: _image_preview(m.cover_image, m.name),
    }
    column_formatters_detail = {
        'logo_image': lambda v, c, m, p: _image_preview(m.logo_image, m.name, height=120),
        'cover_image': lambda v, c, m, p: _image_preview(m.cover_image, m.name, height=120),
    }


class RiderAdminView(SecureModelView):
    column_list = ('id', 'user_id', 'vehicle_type', 'license_plate', 'is_available', 'max_delivery_radius', 'created_at')
    column_searchable_list = ('vehicle_type', 'license_plate')
    column_filters = ('is_available', 'vehicle_type', 'created_at')
    column_sortable_list = ('id', 'user_id', 'vehicle_type', 'license_plate', 'is_available', 'created_at')
    column_default_sort = ('created_at', True)


class OrderAdminView(SecureModelView):
    column_list = ('id', 'customer_id', 'restaurant_id', 'contact_name', 'contact_phone', 'status', 'payment_status', 'total_amount', 'created_at')
    column_searchable_list = ('contact_name', 'contact_phone', 'status', 'payment_status', 'payment_method')
    column_filters = ('status', 'payment_status', 'payment_method', 'created_at')
    column_sortable_list = ('id', 'customer_id', 'restaurant_id', 'status', 'payment_status', 'total_amount', 'created_at')
    column_default_sort = ('created_at', True)


class MenuItemAdminView(SecureModelView):
    column_list = ('id', 'image_url', 'name', 'restaurant_id', 'category_id', 'price', 'preparation_time', 'available', 'created_at')
    column_searchable_list = ('name', 'description')
    column_filters = ('available', 'restaurant_id', 'category_id', 'created_at')
    column_sortable_list = ('id', 'name', 'restaurant_id', 'category_id', 'price', 'available', 'created_at')
    column_default_sort = ('created_at', True)
    column_formatters = {
        'image_url': lambda v, c, m, p: _image_preview(m.image_url, m.name),
    }
    column_formatters_detail = {
        'image_url': lambda v, c, m, p: _image_preview(m.image_url, m.name, height=120),
    }


class MenuCategoryAdminView(SecureModelView):
    column_list = ('id', 'name', 'restaurant_id', 'display_order', 'created_at')
    column_searchable_list = ('name', 'description')
    column_filters = ('restaurant_id', 'created_at')
    column_sortable_list = ('id', 'name', 'restaurant_id', 'display_order', 'created_at')
    column_default_sort = ('created_at', True)


class DeliveryAdminView(SecureModelView):
    column_list = ('id', 'order_id', 'rider_id', 'status', 'created_at')
    column_searchable_list = ('status',)
    column_filters = ('status', 'created_at')
    column_sortable_list = ('id', 'order_id', 'rider_id', 'status', 'created_at')
    column_default_sort = ('created_at', True)


class SecureAdminIndexView(AdminIndexView):
    def check_auth(self):
        auth = request.authorization
        if not auth or not auth.username or not auth.password:
            return False

        user = get_current_admin_user()
        if not user or user.role != "admin" or not user.check_password(auth.password):
            return False
        return True

    @expose('/')
    def index(self):
        if not self.check_auth():
            raise AuthException('Authentication Failed.')

        today = datetime.utcnow()
        view_links = {
            view.endpoint: url_for(f"{view.endpoint}.index_view")
            for view in self.admin._views
            if view is not self and getattr(view, "endpoint", None)
        }

        client = cache.client
        cached_payload = client.get(DASHBOARD_CACHE_KEY) if client else None
        dashboard_data = json.loads(cached_payload) if cached_payload else None

        if dashboard_data is None:
            yesterday = today - timedelta(days=1)
            seven_days_ago = today - timedelta(days=6)

            metrics = {
                "total_users": User.query.filter_by(is_active=True).count(),
                "total_admins": count_users_by_roles('admin'),
                "total_customers": User.query.filter_by(role='customer').count(),
                "total_restaurant_owners": count_users_by_roles('restaurant', 'restaurant_owner'),
                "total_rider_accounts": count_users_by_roles('rider'),
                "total_restaurants": Restaurant.query.filter_by(approved=True).count(),
                "open_restaurants": Restaurant.query.filter_by(approved=True, is_open=True).count(),
                "total_orders": Order.query.count(),
                "total_revenue": float(db.session.query(db.func.sum(Order.total_amount)).filter(Order.status == 'delivered').scalar() or 0),
                "revenue_today": float(db.session.query(db.func.sum(Order.total_amount)).filter(
                    Order.status == 'delivered',
                    Order.created_at >= yesterday,
                ).scalar() or 0),
                "pending_restaurants": Restaurant.query.filter_by(approved=False).count(),
                "total_riders": Rider.query.count(),
                "available_riders": Rider.query.filter_by(is_available=True).count(),
                "total_menu_items": MenuItem.query.count(),
                "total_categories": MenuCategory.query.count(),
                "total_deliveries": Delivery.query.count(),
                "orders_today": Order.query.filter(Order.created_at >= yesterday).count(),
                "orders_in_flight": Order.query.filter(
                    Order.status.in_(["pending", "confirmed", "preparing", "assigned", "picked_up", "on_the_way"])
                ).count(),
                "pending_orders": Order.query.filter_by(status='pending').count(),
                "delivered_orders": Order.query.filter_by(status='delivered').count(),
                "cancelled_orders": Order.query.filter_by(status='cancelled').count(),
                "other_orders": Order.query.filter(
                    ~Order.status.in_(["pending", "confirmed", "preparing", "assigned", "picked_up", "on_the_way", "delivered", "cancelled"])
                ).count(),
                "pending_deliveries": Delivery.query.filter_by(status='pending').count(),
                "completed_deliveries": Delivery.query.filter(Delivery.status.in_(["delivered", "completed"])).count(),
                "payments_total": Payment.query.count(),
                "payments_completed": Payment.query.filter(Payment.status.in_(["completed", "paid", "successful"])).count(),
                "payments_pending": Payment.query.filter(Payment.status.in_(["pending", "processing"])).count(),
                "payments_failed": Payment.query.filter(Payment.status.in_(["failed", "cancelled"])).count(),
                "carts_total": Cart.query.count(),
                "favorites_total": Favorite.query.count(),
                "reviews_total": Review.query.count(),
                "avg_review_rating": float(db.session.query(db.func.avg(Review.rating)).scalar() or 0),
                "notifications_total": Notification.query.count(),
                "unread_notifications": Notification.query.filter_by(is_read=False).count(),
            }

            order_trend_rows = (
                db.session.query(
                    db.func.date(Order.created_at).label("day"),
                    db.func.count(Order.id).label("count"),
                    db.func.coalesce(db.func.sum(Order.total_amount), 0).label("revenue"),
                )
                .filter(Order.created_at >= seven_days_ago)
                .group_by(db.func.date(Order.created_at))
                .order_by(db.func.date(Order.created_at))
                .all()
            )

            order_trend_map = {
                row.day: {
                    "orders": int(row.count or 0),
                    "revenue": float(row.revenue or 0),
                }
                for row in order_trend_rows
            }

            trend_labels = []
            order_trend = []
            revenue_trend = []
            for offset in range(7):
                point_day = (seven_days_ago + timedelta(days=offset)).date().isoformat()
                trend_labels.append((seven_days_ago + timedelta(days=offset)).strftime("%a"))
                order_trend.append(order_trend_map.get(point_day, {}).get("orders", 0))
                revenue_trend.append(order_trend_map.get(point_day, {}).get("revenue", 0))

            pending_restaurants = [
                _serialize_pending_restaurant(restaurant)
                for restaurant in Restaurant.query.filter_by(approved=False).order_by(Restaurant.created_at.desc()).limit(10).all()
            ]
            recent_order_rows = Order.query.order_by(Order.created_at.desc()).limit(8).all()
            recent_orders = [_serialize_recent_order(order) for order in recent_order_rows]
            recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
            recent_restaurants = Restaurant.query.order_by(Restaurant.created_at.desc()).limit(5).all()
            recent_menu_items = MenuItem.query.order_by(MenuItem.created_at.desc()).limit(5).all()
            recent_categories = MenuCategory.query.order_by(MenuCategory.created_at.desc()).limit(5).all()
            recent_deliveries = Delivery.query.order_by(Delivery.created_at.desc()).limit(5).all()
            recent_riders = Rider.query.order_by(Rider.created_at.desc()).limit(5).all()

            order_statuses = [
                {"label": "Pending", "value": metrics["pending_orders"], "tone": "warning"},
                {"label": "In Flight", "value": metrics["orders_in_flight"], "tone": "info"},
                {"label": "Delivered", "value": metrics["delivered_orders"], "tone": "success"},
                {"label": "Cancelled", "value": metrics["cancelled_orders"], "tone": "danger"},
                {"label": "Other", "value": metrics["other_orders"], "tone": "muted"},
            ]

            payment_statuses = [
                {"label": "Completed Payments", "value": metrics["payments_completed"], "tone": "success"},
                {"label": "Pending Payments", "value": metrics["payments_pending"], "tone": "warning"},
                {"label": "Failed Payments", "value": metrics["payments_failed"], "tone": "danger"},
                {"label": "Unread Notifications", "value": metrics["unread_notifications"], "tone": "info"},
            ]

            platform_health = [
                {"label": "Open Restaurants", "value": metrics["open_restaurants"], "href": view_links.get("restaurants", "#")},
                {"label": "Available Riders", "value": metrics["available_riders"], "href": view_links.get("riders", "#")},
                {"label": "Active Carts", "value": metrics["carts_total"], "href": None},
                {"label": "Average Rating", "value": f'{metrics["avg_review_rating"]:.1f}', "href": None},
            ]

            dashboard_modules = [
            {
                "name": "Users",
                "endpoint": "users",
                "description": "Manage customer and admin accounts.",
                "stat": metrics["total_users"],
                "caption": "Active accounts",
            },
            {
                "name": "Restaurants",
                "endpoint": "restaurants",
                "description": "Review merchant onboarding and availability.",
                "stat": metrics["pending_restaurants"],
                "caption": "Pending approvals",
            },
            {
                "name": "Riders",
                "endpoint": "riders",
                "description": "Track rider readiness and delivery capacity.",
                "stat": metrics["available_riders"],
                "caption": "Available now",
            },
            {
                "name": "Orders",
                "endpoint": "orders",
                "description": "Monitor live order volume and fulfillment.",
                "stat": metrics["orders_in_flight"],
                "caption": "In motion",
            },
            {
                "name": "Menu Items",
                "endpoint": "menu_items",
                "description": "Update catalog items, pricing, and availability.",
                "stat": metrics["total_menu_items"],
                "caption": "Catalog items",
            },
            {
                "name": "Categories",
                "endpoint": "categories",
                "description": "Organize restaurant menus into clean sections.",
                "stat": metrics["total_categories"],
                "caption": "Menu groups",
            },
            {
                "name": "Deliveries",
                "endpoint": "deliveries",
                "description": "Manage dispatch assignments and delivery status.",
                "stat": metrics["total_deliveries"],
                "caption": "Delivery records",
            },
            ]

            for module in dashboard_modules:
                module["url"] = view_links.get(module["endpoint"], "#")

            dashboard_sections = [
            {
                "id": "section-users",
                "title": "Users",
                "eyebrow": "Accounts",
                "description": "Review the latest user activity, role mix, and support-sensitive account states.",
                "url": view_links.get("users", "#"),
                "primary_value": metrics["total_users"],
                "primary_label": "Active users",
                "stats": [
                    {"label": "Customers", "value": metrics["total_customers"]},
                    {"label": "Restaurant owners", "value": metrics["total_restaurant_owners"]},
                    {"label": "Admins", "value": metrics["total_admins"]},
                    {"label": "Rider accounts", "value": metrics["total_rider_accounts"]},
                ],
                "records": [
                    {
                        "title": user.name,
                        "meta": user.role.replace("_", " ").title(),
                        "aux": user.email,
                        "href": url_for("users.details_view", id=user.id, url=view_links.get("users", "#")),
                    }
                    for user in recent_users
                ],
            },
            {
                "id": "section-restaurants",
                "title": "Restaurants",
                "eyebrow": "Merchants",
                "description": "Keep merchant onboarding, brand quality, and store availability moving in one sequence.",
                "url": view_links.get("restaurants", "#"),
                "primary_value": metrics["total_restaurants"],
                "primary_label": "Approved restaurants",
                "stats": [
                    {"label": "Pending approvals", "value": metrics["pending_restaurants"]},
                    {"label": "Open restaurants", "value": metrics["open_restaurants"]},
                    {"label": "Menu items", "value": metrics["total_menu_items"]},
                    {"label": "Categories", "value": metrics["total_categories"]},
                ],
                "records": [
                    {
                        "title": restaurant.name,
                        "meta": restaurant.cuisine_type or "Cuisine not set",
                        "aux": "Approved" if restaurant.approved else "Pending approval",
                        "href": url_for("restaurants.details_view", id=restaurant.id, url=view_links.get("restaurants", "#")),
                    }
                    for restaurant in recent_restaurants
                ],
            },
            {
                "id": "section-orders",
                "title": "Orders",
                "eyebrow": "Flow",
                "description": "Stay on top of active fulfillment, exceptions, and the last few orders moving through the system.",
                "url": view_links.get("orders", "#"),
                "primary_value": metrics["total_orders"],
                "primary_label": "Total orders",
                "stats": [
                    {"label": "In flight", "value": metrics["orders_in_flight"]},
                    {"label": "Pending", "value": metrics["pending_orders"]},
                    {"label": "Delivered", "value": metrics["delivered_orders"]},
                    {"label": "Cancelled", "value": metrics["cancelled_orders"]},
                ],
                "records": [
                    {
                        "title": f"Order #{order.id}",
                        "meta": order.contact_name or "Unknown customer",
                        "aux": order.status.replace("_", " ").title(),
                        "href": url_for("orders.details_view", id=order.id, url=view_links.get("orders", "#")),
                    }
                    for order in recent_order_rows[:5]
                ],
            },
            {
                "id": "section-menu-items",
                "title": "Menu Items",
                "eyebrow": "Catalog",
                "description": "Track the freshest items added to the catalog and jump into menu management without leaving the dashboard.",
                "url": view_links.get("menu_items", "#"),
                "primary_value": metrics["total_menu_items"],
                "primary_label": "Catalog items",
                "stats": [
                    {"label": "Categories", "value": metrics["total_categories"]},
                    {"label": "Approved restaurants", "value": metrics["total_restaurants"]},
                    {"label": "Orders today", "value": metrics["orders_today"]},
                    {"label": "Favorites", "value": metrics["favorites_total"]},
                ],
                "records": [
                    {
                        "title": item.name,
                        "meta": item.restaurant.name if item.restaurant else "Unknown restaurant",
                        "aux": f"${float(item.price):.2f}",
                        "href": url_for("menu_items.details_view", id=item.id, url=view_links.get("menu_items", "#")),
                    }
                    for item in recent_menu_items
                ],
            },
            {
                "id": "section-categories",
                "title": "Categories",
                "eyebrow": "Structure",
                "description": "Keep the menu structure organized so restaurants and customers see a cleaner catalog.",
                "url": view_links.get("categories", "#"),
                "primary_value": metrics["total_categories"],
                "primary_label": "Menu categories",
                "stats": [
                    {"label": "Menu items", "value": metrics["total_menu_items"]},
                    {"label": "Restaurants", "value": metrics["total_restaurants"]},
                    {"label": "Pending approvals", "value": metrics["pending_restaurants"]},
                    {"label": "Reviews", "value": metrics["reviews_total"]},
                ],
                "records": [
                    {
                        "title": category.name,
                        "meta": category.restaurant.name if category.restaurant else "Unknown restaurant",
                        "aux": f"Display order {category.display_order}",
                        "href": url_for("categories.details_view", id=category.id, url=view_links.get("categories", "#")),
                    }
                    for category in recent_categories
                ],
            },
            {
                "id": "section-deliveries",
                "title": "Deliveries",
                "eyebrow": "Dispatch",
                "description": "Watch delivery readiness, rider assignments, and the latest delivery records in motion.",
                "url": view_links.get("deliveries", "#"),
                "primary_value": metrics["total_deliveries"],
                "primary_label": "Delivery records",
                "stats": [
                    {"label": "Pending", "value": metrics["pending_deliveries"]},
                    {"label": "Completed", "value": metrics["completed_deliveries"]},
                    {"label": "Available riders", "value": metrics["available_riders"]},
                    {"label": "Orders in flight", "value": metrics["orders_in_flight"]},
                ],
                "records": [
                    {
                        "title": f"Delivery #{delivery.id}",
                        "meta": delivery.status.replace("_", " ").title(),
                        "aux": f"Order #{delivery.order_id}",
                        "href": url_for("deliveries.details_view", id=delivery.id, url=view_links.get("deliveries", "#")),
                    }
                    for delivery in recent_deliveries
                ],
            },
            {
                "id": "section-riders",
                "title": "Riders",
                "eyebrow": "Fleet",
                "description": "Keep fleet readiness visible, from available riders to the latest onboarding records.",
                "url": view_links.get("riders", "#"),
                "primary_value": metrics["total_riders"],
                "primary_label": "Rider profiles",
                "stats": [
                    {"label": "Available now", "value": metrics["available_riders"]},
                    {"label": "Rider accounts", "value": metrics["total_rider_accounts"]},
                    {"label": "Deliveries", "value": metrics["total_deliveries"]},
                    {"label": "Orders in motion", "value": metrics["orders_in_flight"]},
                ],
                "records": [
                    {
                        "title": rider.vehicle_type or "Vehicle not set",
                        "meta": rider.license_plate or "No plate",
                        "aux": "Available" if rider.is_available else "Unavailable",
                        "href": url_for("riders.details_view", id=rider.id, url=view_links.get("riders", "#")),
                    }
                    for rider in recent_riders
                ],
            },
            ]

            dashboard_anchor_map = {
                view_links.get("users"): "#section-users",
                view_links.get("restaurants"): "#section-restaurants",
                view_links.get("orders"): "#section-orders",
                view_links.get("menu_items"): "#section-menu-items",
                view_links.get("categories"): "#section-categories",
                view_links.get("deliveries"): "#section-deliveries",
                view_links.get("riders"): "#section-riders",
            }

            dashboard_data = {
                "metrics": metrics,
                "dashboard_modules": dashboard_modules,
                "dashboard_sections": dashboard_sections,
                "dashboard_anchor_map": dashboard_anchor_map,
                "order_statuses": order_statuses,
                "payment_statuses": payment_statuses,
                "platform_health": platform_health,
                "trend_labels": trend_labels,
                "order_trend": order_trend,
                "revenue_trend": revenue_trend,
                "pending_restaurants": pending_restaurants,
                "recent_orders": recent_orders,
            }

            if client:
                try:
                    client.setex(DASHBOARD_CACHE_KEY, DASHBOARD_CACHE_TTL_SECONDS, json.dumps(dashboard_data))
                except Exception:
                    pass

        return self.render('admin/index.html',
                           metrics=dashboard_data["metrics"],
                           generated_at=today,
                           dashboard_modules=dashboard_data["dashboard_modules"],
                           dashboard_sections=dashboard_data["dashboard_sections"],
                           dashboard_anchor_map=dashboard_data["dashboard_anchor_map"],
                           view_links=view_links,
                           order_statuses=dashboard_data["order_statuses"],
                           payment_statuses=dashboard_data["payment_statuses"],
                           platform_health=dashboard_data["platform_health"],
                           trend_labels=dashboard_data["trend_labels"],
                           order_trend=dashboard_data["order_trend"],
                           revenue_trend=dashboard_data["revenue_trend"],
                           pending_restaurants=dashboard_data["pending_restaurants"],
                           recent_orders=dashboard_data["recent_orders"],
                           admin_profile_url=url_for('.profile'))

    @expose('/profile')
    def profile(self):
        if not self.check_auth():
            raise AuthException('Authentication Failed.')

        admin_user = get_current_admin_user()
        return self.render('admin/profile.html',
                           model=admin_user,
                           admin_profile_url=url_for('.profile'))

    @expose('/approve_restaurant/<int:restaurant_id>', methods=['POST'])
    def approve_restaurant(self, restaurant_id):
        if not self.check_auth():
            raise AuthException('Authentication Failed.')
        from flask import redirect, url_for, flash
        rest = Restaurant.query.get_or_404(restaurant_id)
        rest.approved = True
        db.session.commit()
        invalidate_dashboard_cache()
        flash(f'Restaurant "{rest.name}" has been approved!', 'success')
        return redirect(url_for('.index'))


def init_admin_panel(app):
    admin = Admin(
        app,
        name='Mezahub Admin Panel',
        index_view=SecureAdminIndexView(),
        template_mode='bootstrap4',
    )

    admin.add_view(UserAdminView(User, db.session, name='Users', endpoint='users'))
    admin.add_view(RestaurantAdminView(Restaurant, db.session, name='Restaurants', endpoint='restaurants'))
    admin.add_view(OrderAdminView(Order, db.session, name='Orders', endpoint='orders'))
    admin.add_view(MenuItemAdminView(MenuItem, db.session, name='Menu Items', endpoint='menu_items'))
    admin.add_view(MenuCategoryAdminView(MenuCategory, db.session, name='Categories', endpoint='categories'))
    admin.add_view(DeliveryAdminView(Delivery, db.session, name='Deliveries', endpoint='deliveries'))
    admin.add_view(RiderAdminView(Rider, db.session, name='Riders', endpoint='riders'))
