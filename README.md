# mezahub-backend

Production-ready Flask backend scaffold for MEZAHUB.

## Run locally

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# copy env
cp .env.example .env

# migrations
export FLASK_APP="app:create_app"
flask db init
flask db migrate -m "init"
flask db upgrade

python run.py
```

The server listens on `0.0.0.0:5000`, so it is reachable from other devices on the same network. For the **restaurant app** or **customer app** on a physical device, set the API base URL to `http://YOUR_PC_IP:5000/api/v1` (use your computer’s LAN IP; same WiFi as the phone).

## API docs

- Swagger UI: `http://localhost:5000/api/v1/docs/`
- Health: `http://localhost:5000/health`

## M-Pesa setup

The backend now includes:

- `POST /api/v1/payments/mpesa/stk-push`
- `POST /api/v1/payments/mpesa/callback`
- `GET /api/v1/payments/mpesa/query/<checkout_request_id>`
- `POST /api/v1/payments/mpesa/rider-payout`

Before using them:

```bash
flask db upgrade
```

Only put your private credentials in these places:

- `.env`
- Render environment variables

Do not hardcode real values in source files.

Sensitive values you must provide yourself:

- `MPESA_CONSUMER_KEY`
- `MPESA_CONSUMER_SECRET`
- `MPESA_PASSKEY`
- `MPESA_INITIATOR_NAME`
- `MPESA_B2C_SECURITY_CREDENTIAL`
- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `DATABASE_URL` or `DB_PASSWORD`

Public/non-secret but deployment-specific values:

- `MPESA_CALLBACK_BASE_URL` or `MPESA_STK_CALLBACK_URL`
- `MPESA_B2C_RESULT_URL`
- `MPESA_B2C_TIMEOUT_URL`
- `MPESA_SHORTCODE`
- `MPESA_ENV`

The template for these lives in [.env.example](/home/nelson/mezahub-backend/.env.example).

## Troubleshooting

### SQLAlchemy OperationalError when logging in (e.g. restaurant app)

This usually means the **database is not reachable**.

- **If using PostgreSQL** (`.env` has `DATABASE_URL`): start PostgreSQL, then run migrations:
  ```bash
  sudo systemctl start postgresql   # or: pg_ctlcluster 15 main start
  flask db upgrade
  ```
- **To use SQLite instead** (no PostgreSQL needed): in `.env`, comment out or remove `DATABASE_URL`. The app will use `sqlite:///mezahub.db`. Then run:
  ```bash
  flask db upgrade
  python run.py
  ```
