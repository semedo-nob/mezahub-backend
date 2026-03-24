from flask import request, current_app
from flask_restx import Namespace, Resource, fields
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_
from sqlalchemy.exc import OperationalError

from app.extensions.database import db
from app.models import Restaurant, User, MenuCategory, MenuItem
from app.schemas.restaurant_schema import RestaurantSchema
from app.utils.media import build_media_url, save_uploaded_image
from app.utils.decorators import roles_required

restaurants_ns = Namespace("restaurants", description="Restaurant operations")

restaurant_model = restaurants_ns.model(
    "Restaurant",
    {
        "id": fields.Integer(readonly=True),
        "name": fields.String(required=True),
        "description": fields.String,
        "address": fields.String,
        "cuisine_type": fields.String,
        "phone": fields.String,
        "is_open": fields.Boolean,
        "logo_image": fields.String(description="Restaurant logo URL"),
        "cover_image": fields.String(description="Restaurant photo URL (Discover & profile)"),
        "latitude": fields.Float(description="Restaurant location for tracking"),
        "longitude": fields.Float(description="Restaurant location for tracking"),
    },
)

restaurant_schema = RestaurantSchema()
restaurant_list_schema = RestaurantSchema(many=True)


def _serialize_restaurant(restaurant: Restaurant) -> dict:
    return {
        "id": restaurant.id,
        "name": restaurant.name,
        "description": restaurant.description,
        "address": restaurant.address,
        "cuisine_type": restaurant.cuisine_type,
        "phone": restaurant.phone,
        "is_open": restaurant.is_open,
        "logo_image": build_media_url(restaurant.logo_image),
        "cover_image": build_media_url(restaurant.cover_image),
        "latitude": restaurant.latitude,
        "longitude": restaurant.longitude,
    }


@restaurants_ns.route("")
class RestaurantList(Resource):
    @restaurants_ns.marshal_list_with(restaurant_model)
    @restaurants_ns.doc(security="Bearer Auth (optional for public list; required for ?mine=1)")
    @jwt_required(optional=True)
    def get(self):
        """Public list of restaurants with basic pagination. Use ?mine=1 with JWT for current user's restaurants."""
        try:
            mine = request.args.get("mine", "").lower() in ("1", "true", "yes")
            if mine:
                current_user_id = get_jwt_identity()
                if not current_user_id:
                    return []
                uid = int(current_user_id)
                restaurants = Restaurant.query.filter_by(owner_id=uid).order_by(Restaurant.id).all()
                return [_serialize_restaurant(restaurant) for restaurant in restaurants]
        except OperationalError as e:
            current_app.logger.exception("Database error listing my restaurants: %s", e)
            return {
                "error": "Database schema may be out of date. Run: flask db upgrade",
                "detail": str(e) if current_app.debug else None,
            }, 503
        page = int(request.args.get("page", 1))
        per_page = min(int(request.args.get("per_page", 20)), 100)
        category_name = (request.args.get("category") or "").strip()
        # Show approved restaurants that have at least one dish (menu item); is_open True or None (for testing)
        query = (
            Restaurant.query.filter(Restaurant.approved.is_(True))
            .filter(or_(Restaurant.is_open.is_(True), Restaurant.is_open.is_(None)))
            .join(MenuItem, Restaurant.id == MenuItem.restaurant_id)
            .distinct()
        )
        if category_name:
            # Filter by menu category name (harmonised with discover chips and upload-dish categories)
            subq = (
                MenuCategory.query.filter(MenuCategory.name.ilike(category_name))
                .with_entities(MenuCategory.restaurant_id)
                .distinct()
            )
            query = query.filter(Restaurant.id.in_(subq))
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        return [_serialize_restaurant(restaurant) for restaurant in pagination.items]

    @restaurants_ns.expect(restaurant_model, validate=True)
    @restaurants_ns.marshal_with(restaurant_model, code=201)
    @restaurants_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("restaurant", "admin")
    def post(self):
        """Create a restaurant (restaurant owner or admin)."""
        data = request.get_json() or {}
        current_user_id = int(get_jwt_identity())
        owner = User.query.get_or_404(current_user_id)

        # For testing: new restaurants appear without admin approval. Tighten when admin app exists.
        lat = data.get("latitude")
        lng = data.get("longitude")
        restaurant = Restaurant(
            owner_id=owner.id,
            name=data["name"],
            description=data.get("description") or "",
            address=data.get("address") or "",
            cuisine_type=data.get("cuisine_type") or "",
            phone=data.get("phone") or owner.phone,
            is_open=data.get("is_open", True),
            approved=True if owner.role == "admin" else False,
            logo_image=data.get("logo_image") or None,
            cover_image=data.get("cover_image") or None,
            latitude=float(lat) if lat is not None else None,
            longitude=float(lng) if lng is not None else None,
        )
        db.session.add(restaurant)
        db.session.commit()
        return _serialize_restaurant(restaurant), 201


@restaurants_ns.route("/<int:restaurant_id>")
@restaurants_ns.response(404, "Restaurant not found")
class RestaurantDetail(Resource):
    @restaurants_ns.marshal_with(restaurant_model)
    def get(self, restaurant_id: int):
        """Get a single restaurant by ID."""
        restaurant = Restaurant.query.get_or_404(restaurant_id)
        return _serialize_restaurant(restaurant)

    @restaurants_ns.expect(restaurant_model, validate=False)
    @restaurants_ns.marshal_with(restaurant_model)
    @restaurants_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("restaurant", "admin")
    def put(self, restaurant_id: int):
        """Update a restaurant (owner or admin)."""
        restaurant = Restaurant.query.get_or_404(restaurant_id)
        current_user_id = int(get_jwt_identity())
        current_user = User.query.get_or_404(current_user_id)

        if current_user.role != "admin" and restaurant.owner_id != current_user.id:
            return {"error": "Forbidden"}, 403

        data = request.get_json() or {}
        for field in ["name", "description", "address", "cuisine_type", "phone", "is_open", "logo_image", "cover_image"]:
            if field in data:
                setattr(restaurant, field, data[field] if data[field] is not None else None)
        if "latitude" in data:
            restaurant.latitude = float(data["latitude"]) if data["latitude"] is not None else None
        if "longitude" in data:
            restaurant.longitude = float(data["longitude"]) if data["longitude"] is not None else None

        db.session.commit()
        return _serialize_restaurant(restaurant)

    @restaurants_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("restaurant", "admin")
    def delete(self, restaurant_id: int):
        """Delete a restaurant (owner or admin)."""
        restaurant = Restaurant.query.get_or_404(restaurant_id)
        current_user_id = int(get_jwt_identity())
        current_user = User.query.get_or_404(current_user_id)
        if current_user.role != "admin" and restaurant.owner_id != current_user.id:
            return {"error": "Forbidden"}, 403
        db.session.delete(restaurant)
        db.session.commit()
        return "", 204


@restaurants_ns.route("/<int:restaurant_id>/cover-image")
@restaurants_ns.response(404, "Restaurant not found")
@restaurants_ns.response(403, "Forbidden")
class RestaurantCoverImageUpload(Resource):
    @restaurants_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("restaurant", "admin")
    def post(self, restaurant_id: int):
        restaurant = Restaurant.query.get_or_404(restaurant_id)
        current_user_id = int(get_jwt_identity())
        current_user = User.query.get_or_404(current_user_id)
        if current_user.role != "admin" and restaurant.owner_id != current_user.id:
            return {"error": "Forbidden"}, 403

        image = request.files.get("image")
        if image is None:
            return {"error": "Image file is required"}, 400

        try:
            restaurant.cover_image = save_uploaded_image(image, "restaurants")
            db.session.commit()
            return _serialize_restaurant(restaurant)
        except ValueError as exc:
            db.session.rollback()
            return {"error": str(exc)}, 400


@restaurants_ns.route("/<int:restaurant_id>/logo-image")
@restaurants_ns.response(404, "Restaurant not found")
@restaurants_ns.response(403, "Forbidden")
class RestaurantLogoImageUpload(Resource):
    @restaurants_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("restaurant", "admin")
    def post(self, restaurant_id: int):
        restaurant = Restaurant.query.get_or_404(restaurant_id)
        current_user_id = int(get_jwt_identity())
        current_user = User.query.get_or_404(current_user_id)
        if current_user.role != "admin" and restaurant.owner_id != current_user.id:
            return {"error": "Forbidden"}, 403

        image = request.files.get("image")
        if image is None:
            return {"error": "Image file is required"}, 400

        try:
            restaurant.logo_image = save_uploaded_image(image, "restaurant-logos")
            db.session.commit()
            return _serialize_restaurant(restaurant)
        except ValueError as exc:
            db.session.rollback()
            return {"error": str(exc)}, 400


@restaurants_ns.route("/<int:restaurant_id>/menu")
@restaurants_ns.response(404, "Restaurant not found")
class RestaurantMenu(Resource):
    def get(self, restaurant_id: int):
        """Get a restaurant's menu grouped by category."""
        restaurant = Restaurant.query.get_or_404(restaurant_id)
        categories = (
            MenuCategory.query.filter_by(restaurant_id=restaurant.id)
            .order_by(MenuCategory.display_order)
            .all()
        )
        result = []
        for cat in categories:
            items = (
                MenuItem.query.filter_by(restaurant_id=restaurant.id, category_id=cat.id, available=True)
                .order_by(MenuItem.id)
                .all()
            )
            result.append(
                {
                    "id": cat.id,
                    "name": cat.name,
                    "description": cat.description,
                    "items": [
                        {
                            "id": item.id,
                            "name": item.name,
                            "description": item.description,
                            "price": float(item.price),
                            "image_url": build_media_url(item.image_url),
                        }
                        for item in items
                    ],
                }
            )
        return {"categories": result}


category_create_model = restaurants_ns.model(
    "CreateMenuCategory",
    {
        "name": fields.String(required=True),
        "description": fields.String,
        "display_order": fields.Integer,
    },
)

item_create_model = restaurants_ns.model(
    "CreateMenuItem",
    {
        "category_id": fields.Integer(required=True),
        "name": fields.String(required=True),
        "description": fields.String,
        "price": fields.Float(required=True),
        "image_url": fields.String,
        "preparation_time": fields.Integer,
        "available": fields.Boolean,
    },
)


@restaurants_ns.route("/<int:restaurant_id>/menu/categories")
@restaurants_ns.response(404, "Restaurant not found")
@restaurants_ns.response(403, "Forbidden")
class RestaurantMenuCategories(Resource):
    @restaurants_ns.expect(category_create_model, validate=True)
    @restaurants_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("restaurant", "admin")
    def post(self, restaurant_id: int):
        """Create a menu category (restaurant owner or admin)."""
        restaurant = Restaurant.query.get_or_404(restaurant_id)
        current_user_id = int(get_jwt_identity())
        current_user = User.query.get_or_404(current_user_id)
        if current_user.role != "admin" and restaurant.owner_id != current_user.id:
            return {"error": "Forbidden"}, 403
        data = request.get_json() or {}
        display_order = data.get("display_order")
        if display_order is None:
            last = (
                MenuCategory.query.filter_by(restaurant_id=restaurant_id)
                .order_by(MenuCategory.display_order.desc())
                .first()
            )
            display_order = (last.display_order + 1) if last else 0
        category = MenuCategory(
            restaurant_id=restaurant_id,
            name=data["name"],
            description=data.get("description") or "",
            display_order=int(display_order),
        )
        db.session.add(category)
        if not (restaurant.cuisine_type and restaurant.cuisine_type.strip()):
            restaurant.cuisine_type = category.name
        db.session.commit()
        return {
            "id": category.id,
            "restaurant_id": category.restaurant_id,
            "name": category.name,
            "description": category.description,
            "display_order": category.display_order,
        }, 201


@restaurants_ns.route("/<int:restaurant_id>/menu/items")
@restaurants_ns.response(404, "Restaurant or category not found")
@restaurants_ns.response(403, "Forbidden")
class RestaurantMenuItems(Resource):
    @restaurants_ns.expect(item_create_model, validate=True)
    @restaurants_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("restaurant", "admin")
    def post(self, restaurant_id: int):
        """Create a menu item (restaurant owner or admin)."""
        restaurant = Restaurant.query.get_or_404(restaurant_id)
        current_user_id = int(get_jwt_identity())
        current_user = User.query.get_or_404(current_user_id)
        if current_user.role != "admin" and restaurant.owner_id != current_user.id:
            return {"error": "Forbidden"}, 403
        data = request.get_json() or {}
        category_id = int(data["category_id"])
        category = MenuCategory.query.filter_by(
            id=category_id, restaurant_id=restaurant_id
        ).first()
        if not category:
            return {"error": "Category not found"}, 404
        item = MenuItem(
            restaurant_id=restaurant_id,
            category_id=category_id,
            name=data["name"],
            description=data.get("description") or "",
            price=float(data["price"]),
            image_url=data.get("image_url"),
            preparation_time=int(data["preparation_time"]) if data.get("preparation_time") is not None else 10,
            available=data.get("available", True),
        )
        db.session.add(item)
        db.session.commit()
        return {
            "id": item.id,
            "restaurant_id": item.restaurant_id,
            "category_id": item.category_id,
            "name": item.name,
            "description": item.description,
            "price": float(item.price),
            "image_url": build_media_url(item.image_url),
            "preparation_time": item.preparation_time,
            "available": item.available,
        }, 201


@restaurants_ns.route("/<int:restaurant_id>/menu/items/<int:item_id>/image")
@restaurants_ns.response(404, "Restaurant or menu item not found")
@restaurants_ns.response(403, "Forbidden")
class RestaurantMenuItemImageUpload(Resource):
    @restaurants_ns.doc(security="Bearer Auth")
    @jwt_required()
    @roles_required("restaurant", "admin")
    def post(self, restaurant_id: int, item_id: int):
        restaurant = Restaurant.query.get_or_404(restaurant_id)
        current_user_id = int(get_jwt_identity())
        current_user = User.query.get_or_404(current_user_id)
        if current_user.role != "admin" and restaurant.owner_id != current_user.id:
            return {"error": "Forbidden"}, 403

        item = MenuItem.query.filter_by(id=item_id, restaurant_id=restaurant_id).first()
        if not item:
            return {"error": "Menu item not found"}, 404

        image = request.files.get("image")
        if image is None:
            return {"error": "Image file is required"}, 400

        try:
            item.image_url = save_uploaded_image(image, "menu-items")
            db.session.commit()
            return {
                "id": item.id,
                "restaurant_id": item.restaurant_id,
                "category_id": item.category_id,
                "name": item.name,
                "description": item.description,
                "price": float(item.price),
                "image_url": build_media_url(item.image_url),
                "preparation_time": item.preparation_time,
                "available": item.available,
            }
        except ValueError as exc:
            db.session.rollback()
            return {"error": str(exc)}, 400
