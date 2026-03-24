# Mezahub Deployment

## Recommended stack

- Backend hosting: Railway
- Database: Neon PostgreSQL
- Redis: Railway Redis or Upstash

## Required backend environment variables

- `FLASK_ENV=production`
- `DATABASE_URL=...`
- `SECRET_KEY=...`
- `JWT_SECRET_KEY=...`
- `REDIS_URL=...`
- `CORS_ORIGINS=https://your-admin-domain,https://your-customer-origin`
- `PUBLIC_API_BASE_URL=https://your-backend-domain`
- `LOG_TO_STDOUT=true`

## Deploy flow

1. Create a new Railway project from this repo.
2. Add the environment variables above.
3. Attach Redis or provide an external `REDIS_URL`.
4. Deploy the service.
5. Run migrations:
   - `flask db upgrade`
6. Confirm health:
   - `GET /health`
   - `GET /admin`
   - `GET /api/v1/restaurants`

## Flutter apps

Each Flutter app should be built with:

```bash
flutter run --dart-define=MEZAHUB_API_BASE_URL=https://your-backend-domain/api/v1
```

For release builds, use the same `--dart-define`.

## Notes

- Uploaded images are currently stored on the backend filesystem under `app/static/uploads`.
- This is acceptable for early deployment, but persistent cloud storage like Cloudinary or S3 is recommended for production.
- Rotate any previously exposed Neon credentials before deployment.
