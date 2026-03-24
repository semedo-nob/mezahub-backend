from marshmallow import Schema, fields


class RestaurantSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    description = fields.Str()
    address = fields.Str()
    cuisine_type = fields.Str()
    phone = fields.Str()
    is_open = fields.Bool()
    logo_image = fields.Str()
    cover_image = fields.Str()
    latitude = fields.Float()
    longitude = fields.Float()
