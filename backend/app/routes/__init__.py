from __future__ import annotations

from .account_pages import register_account_page_routes
from .auth import register_auth_routes
from .cmn import register_cmn_routes
from .commerce import register_commerce_routes
from .deps import RouteDeps
from .messages import register_messages_routes
from .profile import register_profile_routes
from .session import register_session_routes
from .system import register_system_routes
from .transfer import register_transfer_routes

__all__ = [
    "RouteDeps",
    "register_account_page_routes",
    "register_auth_routes",
    "register_cmn_routes",
    "register_commerce_routes",
    "register_messages_routes",
    "register_profile_routes",
    "register_session_routes",
    "register_system_routes",
    "register_transfer_routes",
]
