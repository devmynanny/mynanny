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

# AWS Guidance

- Prefer the AWS MCP Server for AWS interactions — it provides sandboxed
  execution, observability, and audit logging. If unavailable, use the
  AWS CLI directly.
- Before starting a task, check whether a relevant AWS skill is available.
  Load the skill with `retrieve_skill` and prefer its guidance over
  general knowledge.
- When uncertain about specific AWS details (API parameters, permissions,
  limits, error codes), verify against documentation rather than guessing.
  State uncertainty explicitly if you cannot confirm.
- When creating infrastructure, prefer infrastructure-as-code (AWS CDK or
  CloudFormation) over direct CLI commands.
- When working with infrastructure, follow AWS Well-Architected Framework
  principles.
- Do not use em dashes in AWS resource names or descriptions. Use
  hyphens instead.

## Secret Safety

- MUST load the `aws-secrets-manager` skill first for any secret,
  credential, API key, token, or password task. MUST NOT call
  `secretsmanager get-secret-value` or `batch-get-secret-value`, and MUST
  NOT hit the Secrets Manager Agent daemon directly. MUST use
  `{{resolve:secretsmanager:secret-id:SecretString:json-key}}` with
  `asm-exec` so the secret resolves at runtime without entering context.
