# Mezahub Deployment

## Recommended stack

- Backend hosting: Render
- Database: PostgreSQL (Render managed PostgreSQL or external provider)
- Redis: Render Redis or external Redis provider

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

1. Create a new Render web service from this repo.
2. Use the existing `render.yaml` manifest and set the service environment to Python.
3. Add the required environment variables above in Render.
4. Deploy the service.
5. Run migrations from the Render shell or locally:
   - `flask db upgrade`
6. Confirm health:
   - `GET /health`
   - `GET /admin`
   - `GET /api/v1/restaurants`

## Render manifest

This repo now includes `render.yaml` for Render service configuration.

### Render start command

If you need to enter the command manually, use:

```bash
sh -c 'gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 -b 0.0.0.0:$PORT wsgi:app'
```

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
