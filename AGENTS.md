# AGENTS.md

## Project
This is the My Nanny app.

## Stack
Backend: FastAPI
Frontend: Static HTML/CSS/JavaScript (no SPA framework currently)
Database: SQLite today (`nanny_app.db`), planned migration path to Postgres for production
Payments: Paystack first, later international support
Country focus: South Africa first

## Rules
Always explain proposed changes briefly before making large edits.
Do not rename files unless necessary.
Keep code simple and production-minded.
Preserve existing API patterns and folder structure.
Prefer small safe changes over big rewrites.
Do not remove backward compatibility unless explicitly requested.
For auth/security/payment changes, include a quick risk note before implementation.

## Commands
Run backend with:
`uvicorn app.main:app --reload`

Install dependencies with:
`pip install -r requirements.txt`

## Coding Preferences
Use clear function names.
Add comments only where needed.
Validate inputs properly.
Avoid breaking existing routes.
Prefer explicit error messages and consistent HTTP status codes.
When touching existing endpoints, keep request/response shapes stable unless instructed otherwise.
