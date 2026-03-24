# MEZAHUB – Breaking Points Assessment

Assessment of breaking points across the **customer Flutter app** and **Flask backend**, with fixes applied where noted.

---

## 1. Orders cannot be placed (PRIMARY – ADDRESSED)

### Cause
- Backend `POST /api/v1/orders` requires **JWT** and **role `customer`** (`@jwt_required()`, `@roles_required("customer")`).
- The app allowed checkout from Discover → Cart without requiring **backend** login, so requests were sent with no token or an invalid one → **401/403** and a generic “Order failed” message.

### Fixes applied
1. **Login required for backend orders**  
   In checkout, when the cart has a `restaurantId` (items from Discover), the app now checks `UserProvider.isLoggedIn`. If not logged in, it shows “Please log in to place an order” and navigates to `/login`.
2. **Clear error messages**  
   When order creation fails, the app now parses the backend response and shows a specific message (e.g. “Please log in to place an order”, “Menu item X not found”, “Forbidden”) instead of a generic “Check connection and try again”.
3. **BackendOrderService**  
   - Stores the last error in `BackendOrderService.lastOrderError`.  
   - Uses a small parser to pull `error` / `message` / `msg` from JSON or map 401/403 to a user-friendly line.

### Other possible order failures
- **Invalid or missing menu item IDs**  
  Backend returns 400 `"Menu item &lt;id&gt; not found"` if a `menu_item_id` does not exist. Cart item IDs are set from the restaurant menu API (`id` from each item); ensure the same backend and DB are used so IDs match.
- **Expired JWT**  
  No refresh flow in the app yet. If the access token is expired, orders will get 401 until the user logs in again.

---

## 2. Auth / token

| Issue | Impact | Recommendation |
|-------|--------|----------------|
| No token refresh | Expired access token → 401 on orders, profile, etc. | Use backend refresh endpoint and refresh before critical calls or on 401. |
| Guest vs backend user | Anonymous Firebase user is not a backend customer; no JWT. | Keep current behaviour: backend orders require login; fallback path for “no restaurant” cart stays as-is. |
| Multiple AuthService instances (historical) | Was a risk for inconsistent auth state. | Already addressed by making AuthService a singleton. |

---

## 3. Profile and orders list

- **Profile**  
  `GET/PUT /auth/profile` and `BackendApi.getProfile()` / `updateProfile()` require a valid JWT. If the user is not logged in or token is expired, these will fail (handled by existing UI/error handling).
- **Orders list**  
  `GET /orders` is JWT + role-scoped. Customers see only their orders. Same token/refresh considerations as above.

---

## 4. Live tracking

- **Track order**  
  `GET /orders/:id/track` requires JWT and that the order belongs to the current user (or rider/restaurant/admin). Works as long as the user is logged in and token is valid.

---

## 5. Backend robustness (for reference)

- **Orders**  
  - Create: validates `restaurant_id`, `delivery_address`, `payment_method`, `items` (each with `menu_item_id`, `quantity`).  
  - Looks up each `menu_item_id`; returns 400 if any not found.  
- **Auth**  
  - Register: email/password/role; JWT includes `role`.  
  - Login: same; required for all order and profile endpoints.

---

## 6. Flutter app – other risks

| Area | Risk | Mitigation |
|------|------|------------|
| Favorites | Stored in-memory only (FavoritesProvider). | Consider persisting (e.g. backend or local) if needed. |
| Cart | In-memory; no backend cart. | Acceptable for current flow; cart is cleared after order. |
| Network/errors | Generic messages on failure. | Order creation errors are now more specific; same pattern can be used elsewhere. |
| Base URL | Hardcoded or config (e.g. `api_config.dart`). | Ensure device and backend are on same network and URL is correct for the environment. |

---

## Summary

- **Main fix:** Orders from Discover now require the user to be **logged in** (backend JWT). If not, the app prompts to log in and navigates to the login screen. Order creation errors are surfaced in a user-friendly way.
- **Remaining:** Add token refresh and consistent 401 handling (e.g. redirect to login) for orders, profile, and orders list to avoid “silent” failures when the token expires.
