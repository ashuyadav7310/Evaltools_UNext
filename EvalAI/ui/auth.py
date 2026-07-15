import hmac
import json
import os
from dataclasses import dataclass
from typing import Any

import streamlit as st


@dataclass(frozen=True)
class AuthUser:
    username: str
    password: str
    role: str
    name: str


def _normalize_roles(raw_roles: str | None) -> set[str]:
    roles = raw_roles or "admin,evaluator,trainer"
    return {role.strip().lower() for role in roles.split(",") if role.strip()}


def _user_from_mapping(username: str, value: Any) -> AuthUser | None:
    if isinstance(value, str):
        return AuthUser(username=username, password=value, role="evaluator", name=username)

    if not isinstance(value, dict):
        return None

    password = str(value.get("password") or "")
    if not password:
        return None

    return AuthUser(
        username=str(value.get("username") or username),
        password=password,
        role=str(value.get("role") or "evaluator"),
        name=str(value.get("name") or username),
    )


def _load_users() -> list[AuthUser]:
    users_json = (os.getenv("EVALAI_AUTH_USERS") or "").strip()
    if users_json:
        try:
            parsed = json.loads(users_json)
        except json.JSONDecodeError:
            st.error("EvalAI authentication is misconfigured.")
            return []

        if isinstance(parsed, dict):
            users = [_user_from_mapping(username, value) for username, value in parsed.items()]
            return [user for user in users if user]

        if isinstance(parsed, list):
            users = []
            for item in parsed:
                if isinstance(item, dict) and item.get("username"):
                    user = _user_from_mapping(str(item["username"]), item)
                    if user:
                        users.append(user)
            return users

    password = os.getenv("EVALAI_LOGIN_PASSWORD") or os.getenv("ADMIN_TOKEN") or "admin123"
    return [
        AuthUser(
            username=os.getenv("EVALAI_LOGIN_USERNAME", "admin"),
            password=password,
            role=os.getenv("EVALAI_LOGIN_ROLE", "admin"),
            name=os.getenv("EVALAI_LOGIN_NAME", "EvalAI Admin"),
        )
    ]


def _authenticate(username: str, password: str) -> AuthUser | None:
    allowed_roles = _normalize_roles(os.getenv("EVALAI_ALLOWED_ROLES"))
    normalized_username = username.strip().lower()

    for user in _load_users():
        if user.role.strip().lower() not in allowed_roles:
            continue
        if not hmac.compare_digest(user.username.strip().lower(), normalized_username):
            continue
        if hmac.compare_digest(user.password, password):
            return user

    return None


def _apply_login_styles() -> None:
    st.markdown(
        """
        <style>
          .stApp {
            background:
              radial-gradient(circle at 0% 0%, rgba(255, 120, 0, 0.18) 0, rgba(255, 120, 0, 0.10) 170px, rgba(255, 255, 255, 0) 380px),
              linear-gradient(135deg, rgba(255, 245, 236, 0.95) 0%, #fffaf7 34%, #ffffff 100%);
          }
          [data-testid="stHeader"] {
            background: transparent;
          }
          .evalai-login {
            max-width: 440px;
            margin: 8vh auto 1.5rem;
            padding: 1.5rem 1.5rem 1.35rem;
            border: 1px solid #f0d8c8;
            border-radius: 0.75rem;
            background: rgba(255, 255, 255, 0.92);
            box-shadow: 0 18px 60px rgba(19, 20, 25, 0.08);
          }
          .evalai-brand {
            display: inline-flex;
            align-items: center;
            gap: 0.7rem;
            margin-bottom: 1.25rem;
            color: #1f2937;
            font-weight: 700;
          }
          .evalai-mark {
            display: inline-flex;
            width: 2.4rem;
            height: 2.4rem;
            align-items: center;
            justify-content: center;
            border-radius: 0.75rem;
            background: linear-gradient(135deg, #e53d00, #ff7a00);
            color: white;
            font-weight: 800;
          }
          .evalai-title {
            margin: 0;
            color: #1f2937;
            font-size: 1.45rem;
            font-weight: 700;
            line-height: 1.2;
          }
          .evalai-copy {
            margin: 0.35rem 0 0;
            color: #667085;
            font-size: 0.94rem;
            line-height: 1.55;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def require_login() -> bool:
    if st.session_state.get("evalai_authenticated"):
        return True

    _apply_login_styles()
    st.markdown(
        """
        <div class="evalai-login">
          <div class="evalai-brand">
            <span class="evalai-mark">U</span>
            <span>U-Next</span>
          </div>
          <h1 class="evalai-title">EvalAI Login</h1>
          <p class="evalai-copy">Sign in to continue to the rubric-driven evaluation workflow.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("evalai_login_form"):
        username = st.text_input("Username", autocomplete="username")
        password = st.text_input("Password", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Login", use_container_width=True)

    if submitted:
        if not username.strip() or not password:
            st.error("Username and password are required.")
            return False

        user = _authenticate(username, password)
        if not user:
            st.error("Invalid credentials or insufficient access.")
            return False

        st.session_state.evalai_authenticated = True
        st.session_state.evalai_user = {
            "username": user.username,
            "name": user.name,
            "role": user.role,
        }
        st.rerun()

    return False


def render_user_controls() -> None:
    user = st.session_state.get("evalai_user") or {}
    with st.sidebar:
        st.caption("Signed in")
        st.write(f"**{user.get('name') or user.get('username') or 'User'}**")
        st.caption(f"Role: {user.get('role', 'evaluator')}")

        if st.button("Logout", use_container_width=True):
            for key in (
                "evalai_authenticated",
                "evalai_user",
                "job_id",
                "inputs_ready",
                "evaluation_running",
                "evaluation_done",
            ):
                st.session_state.pop(key, None)
            st.rerun()
