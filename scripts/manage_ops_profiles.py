#!/usr/bin/env python3
"""Manage Ops user profiles for Shared Airport Alerts.

This helper intentionally does not print passwords, print password hashes,
print session tokens, delete users, or reset sessions.
"""

from __future__ import annotations

import argparse
import getpass
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


VALID_OPERATOR_MODES = {"airport", "airline"}
MIN_PASSWORD_LENGTH = 8
PROFILE_FIELDS = (
    "username",
    "operator_mode",
    "airport_ident",
    "organization_name",
    "display_name",
    "is_active",
)


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def db_path_from_config(repo_root: Path, env_file: Path | None) -> str:
    if env_file is not None:
        load_env_file(env_file)
    else:
        load_env_file(repo_root / ".env")

    sys.path.insert(0, str(repo_root))
    from app.core.config import settings  # pylint: disable=import-outside-toplevel

    return settings.DB_PATH


def connect_readwrite(db_path: str) -> sqlite3.Connection:
    path = Path(db_path)
    if not path.exists():
        raise SystemExit(f"Runtime DB not found at {db_path}. Run this inside the app container or provide AIRFIELDOPS_DB_PATH.")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def require_profile_columns(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(admin_users)")}
    missing = set(PROFILE_FIELDS) - columns
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise SystemExit(f"admin_users is missing required profile column(s): {missing_list}. Confirm schema v9 migration ran.")


def parse_bool(value: str) -> int:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "active"}:
        return 1
    if normalized in {"0", "false", "no", "n", "inactive"}:
        return 0
    raise argparse.ArgumentTypeError("is_active must be true/false, yes/no, active/inactive, or 1/0.")


def normalize_airport_ident(value: str | None) -> str | None:
    if value is None:
        return None
    ident = value.strip().upper()
    if not ident:
        raise SystemExit("airport_ident cannot be blank. Omit the flag to leave it unchanged.")
    if not re.fullmatch(r"[A-Z0-9]{3,8}", ident):
        raise SystemExit("airport_ident must be an airport identifier such as KPIT.")
    return ident


def airport_exists(conn: sqlite3.Connection, airport_ident: str) -> bool:
    try:
        row = conn.execute("SELECT 1 FROM airports WHERE ident = ? LIMIT 1", (airport_ident,)).fetchone()
    except sqlite3.OperationalError as exc:
        raise SystemExit(f"Could not validate airport_ident because airports table is unavailable: {exc}") from exc
    return bool(row)


def user_exists(conn: sqlite3.Connection, username: str) -> bool:
    row = conn.execute("SELECT 1 FROM admin_users WHERE username = ? LIMIT 1", (username,)).fetchone()
    return bool(row)


def normalize_username(username: str) -> str:
    value = username.strip()
    if not value:
        raise SystemExit("username cannot be blank.")
    if not re.fullmatch(r"[A-Za-z0-9_.@-]{3,64}", value):
        raise SystemExit("username must be 3-64 characters and use only letters, numbers, dot, underscore, hyphen, or @.")
    return value


def require_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(f"password must be at least {MIN_PASSWORD_LENGTH} characters.")
    return password


def read_new_password(args: argparse.Namespace) -> str:
    if args.password and args.password_stdin:
        raise SystemExit("Use only one password input option: --password or --password-stdin.")

    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\n")
        return require_password(password)

    if args.password:
        return require_password(args.password)

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        raise SystemExit("password confirmation did not match.")
    return require_password(password)


def format_row(row: sqlite3.Row) -> list[str]:
    return [
        row["username"] or "",
        row["operator_mode"] or "",
        row["airport_ident"] or "",
        row["organization_name"] or "",
        row["display_name"] or "",
        "true" if row["is_active"] else "false",
    ]


def print_table(headers: Iterable[str], rows: list[list[str]]) -> None:
    headers = list(headers)
    widths = [len(h) for h in headers]
    for row in rows:
        for idx, value in enumerate(row):
            widths[idx] = max(widths[idx], len(value))

    fmt = "  ".join(f"{{:<{width}}}" for width in widths)
    print(fmt.format(*headers))
    print(fmt.format(*["-" * width for width in widths]))
    for row in rows:
        print(fmt.format(*row))


def list_users(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """SELECT username, operator_mode, airport_ident, organization_name,
                  display_name, is_active
           FROM admin_users
           ORDER BY LOWER(username)"""
    ).fetchall()
    if not rows:
        print("No Ops users found.")
        return
    print_table(PROFILE_FIELDS, [format_row(row) for row in rows])


def set_profile(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    username = normalize_username(args.username)
    if not user_exists(conn, username):
        raise SystemExit(f"Ops user not found: {username}")

    updates: list[str] = []
    values: list[object] = []

    if args.operator_mode is not None:
        if args.operator_mode not in VALID_OPERATOR_MODES:
            raise SystemExit("operator_mode must be airport or airline.")
        updates.append("operator_mode = ?")
        values.append(args.operator_mode)

    if args.airport_ident is not None:
        airport_ident = normalize_airport_ident(args.airport_ident)
        if airport_ident and not airport_exists(conn, airport_ident):
            raise SystemExit(f"Airport ident not found in reference data: {airport_ident}")
        updates.append("airport_ident = ?")
        values.append(airport_ident)

    if args.organization_name is not None:
        updates.append("organization_name = ?")
        values.append(args.organization_name.strip() or None)

    if args.display_name is not None:
        updates.append("display_name = ?")
        values.append(args.display_name.strip() or None)

    if args.is_active is not None:
        updates.append("is_active = ?")
        values.append(args.is_active)

    if not updates:
        raise SystemExit("No profile fields supplied. Use --operator-mode, --airport-ident, --organization-name, --display-name, or --is-active.")

    updates.append("updated_at = ?")
    values.append(datetime.now(timezone.utc).isoformat())
    values.append(username)

    conn.execute(f"UPDATE admin_users SET {', '.join(updates)} WHERE username = ?", values)
    conn.commit()
    print(f"Updated Ops profile for {username}.")


def create_user(conn: sqlite3.Connection, args: argparse.Namespace) -> None:
    username = normalize_username(args.username)
    if user_exists(conn, username):
        raise SystemExit(f"Ops user already exists: {username}. Use the set command to update profile fields.")

    operator_mode = args.operator_mode
    if operator_mode not in VALID_OPERATOR_MODES:
        raise SystemExit("operator_mode must be airport or airline.")

    airport_ident = normalize_airport_ident(args.airport_ident)
    if airport_ident and not airport_exists(conn, airport_ident):
        raise SystemExit(f"Airport ident not found in reference data: {airport_ident}")

    password = read_new_password(args)

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.services.ops_auth import hash_password  # pylint: disable=import-outside-toplevel

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO admin_users
           (username, password_hash, created_at, updated_at, operator_mode,
            airport_ident, organization_name, display_name, is_active)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            username,
            hash_password(password),
            now,
            now,
            operator_mode,
            airport_ident,
            args.organization_name.strip() if args.organization_name else None,
            args.display_name.strip() if args.display_name else None,
            args.is_active,
        ),
    )
    conn.commit()
    print(f"Created Ops user {username}.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="List, create, and update Ops user profile fields for Shared Airport Alerts.",
        epilog=(
            "Examples:\n"
            "  python3 scripts/manage_ops_profiles.py list\n"
            "  python3 scripts/manage_ops_profiles.py set meeks --operator-mode airport --airport-ident KPIT --organization-name \"Airport Ops\" --display-name \"PIT Ops\"\n"
            "  python3 scripts/manage_ops_profiles.py create-user pit-airline --operator-mode airline --airport-ident KPIT --organization-name \"Example Airline Station\" --display-name \"PIT Airline Station Ops\"\n"
            "\nShared Airport Alerts require both operator_mode and airport_ident."
            "\nThis script never prints passwords, password hashes, or session tokens."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--env-file", type=Path, default=None, help="Optional env file to load for AIRFIELDOPS_DB_PATH. Defaults to .env if present.")
    parser.add_argument("--db-path", default=None, help="Explicit SQLite runtime DB path. Overrides AIRFIELDOPS_DB_PATH.")

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List Ops users and Shared Airport Alerts profile fields.")

    set_parser = sub.add_parser("set", help="Update profile fields for an existing Ops user.")
    set_parser.add_argument("username", help="Existing Ops username to update.")
    set_parser.add_argument("--operator-mode", choices=sorted(VALID_OPERATOR_MODES), help="Ops role: airport or airline.")
    set_parser.add_argument("--airport-ident", help="Assigned airport ident. Validated against airports table and stored uppercase.")
    set_parser.add_argument("--organization-name", help="Organization/source label for this Ops profile.")
    set_parser.add_argument("--display-name", help="Display name for this Ops profile.")
    set_parser.add_argument("--is-active", type=parse_bool, help="Set active status: true/false.")

    create_parser = sub.add_parser("create-user", help="Create an Ops user with Shared Airport Alerts profile fields.")
    create_parser.add_argument("username", help="New Ops username.")
    create_parser.add_argument("--operator-mode", required=True, choices=sorted(VALID_OPERATOR_MODES), help="Ops role: airport or airline.")
    create_parser.add_argument("--airport-ident", required=True, help="Assigned airport ident. Validated against airports table and stored uppercase.")
    create_parser.add_argument("--organization-name", help="Organization/source label for this Ops profile.")
    create_parser.add_argument("--display-name", help="Display name for this Ops profile.")
    create_parser.add_argument("--is-active", type=parse_bool, default=1, help="Initial active status. Defaults to true.")
    create_parser.add_argument("--password", help="Password for non-interactive use. Prefer prompt or --password-stdin when possible.")
    create_parser.add_argument("--password-stdin", action="store_true", help="Read the password from stdin without echoing or printing it.")
    return parser


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    parser = build_parser()
    args = parser.parse_args()

    db_path = args.db_path or db_path_from_config(repo_root, args.env_file)
    with connect_readwrite(db_path) as conn:
        require_profile_columns(conn)
        if args.command == "list":
            list_users(conn)
        elif args.command == "set":
            set_profile(conn, args)
            list_users(conn)
        elif args.command == "create-user":
            create_user(conn, args)
            list_users(conn)
        else:
            parser.error("Unknown command.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
