# Reminder for next session (resolved)

- **Image upload in dish** – Done: dish images use Firebase → backend `image_url`; customer app shows them with `CachedNetworkImage` (restaurant detail + menu items) for reliable loading.
- **Tracking from exact location passed by restaurant** – Done: backend `/orders/<id>/track` returns `restaurant_latitude` and `restaurant_longitude` from the restaurant’s saved location; customer app live tracking screen uses them for the restaurant marker on the map.
- **Restaurant app: faster loading when order placed by customer** – Done: Orders tab auto-refreshes every 15 seconds so new customer orders appear without manual pull.
