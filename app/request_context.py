from contextvars import ContextVar
from typing import Optional

act_as_user_id_ctx: ContextVar[Optional[str]] = ContextVar("act_as_user_id", default=None)
auth_token_ctx: ContextVar[Optional[str]] = ContextVar("auth_token", default=None)
