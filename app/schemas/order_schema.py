from marshmallow import Schema, fields


class OrderItemSchema(Schema):
    menu_item_id = fields.Int()
    quantity = fields.Int()
    unit_price = fields.Float()
    subtotal = fields.Float()


class OrderSchema(Schema):
    id = fields.Int(dump_only=True)
    customer_id = fields.Int()
    restaurant_id = fields.Int()
    status = fields.Str()
    total_amount = fields.Float()
    delivery_address = fields.Str()
    items = fields.List(fields.Nested(OrderItemSchema))

