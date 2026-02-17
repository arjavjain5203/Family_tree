# Family Tree WhatsApp Chatbot

A backend API for a WhatsApp chatbot that allows users to create and manage their family tree.

## Features

- **Manage Family Tree**: Create, View, Delete trees.
- **Member Management**: Add, Edit members with details (Name, DOB, Gender, Relation).
- **Relationships**: Automatically tracks lineage (Parent/Child).
- **Access Control**: Owner, Editor, Viewer roles.
- **Sharing**: Share your tree with other users via phone number.
- **Ownership Transfer**: Transfer ownership to another user.
- [x] Concurrency Control: Locking mechanism when editing members.

## Documentation

For detailed information, please refer to the `docs/` folder:

-   [Project Overview](docs/overview.md)
-   [Project Structure](docs/structure.md)
-   [Service Architecture](docs/services.md)
-   [API Reference](docs/api.md)

## Tech Stack

- Python 3.11
- FastAPI
- PostgreSQL + SQLAlchemy (Async)
- Alembic (Migrations)
- Twilio API (WhatsApp)

## Webhook Configuration

1.  Deploy the application (e.g., on Render).
2.  Configure your Twilio Sandbox or WhatsApp Sender.
3.  Set the **When a message comes in** webhook URL to: `https://your-app-url.onrender.com/webhook`
4.  Set the HTTP method to `POST`.

## Environment Variables

See `.env.example` for required variables.

- `DATABASE_URL`: PostgreSQL connection string.
- `TWILIO_ACCOUNT_SID`: Your Twilio Account SID.
- `TWILIO_AUTH_TOKEN`: Your Twilio Auth Token.
- `TWILIO_PHONE_NUMBER`: Your Twilio WhatsApp Number.

## Local Development

1.  Clone the repository.
2.  Install dependencies: `pip install -r requirements.txt`.
3.  Run migrations: `alembic upgrade head`.
4.  Start server: `uvicorn app.main:app --reload`.
5.  Use `ngrok` to expose your local server for Twilio testing: `ngrok http 8000`.

## Deployment

This project includes a `render.yaml` for easy deployment on Render.
1.  Connect your repo to Render.
2.  Select "Blueprints".
3.  Render will automatically configure the web service and database.
# Family_tree
# whatsapp_family_tree
# whatsapp_family_tree
