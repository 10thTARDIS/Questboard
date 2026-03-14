"""Management CLI for Quest Board.

Usage (from the project root):
    docker compose exec backend python -m app.cli set_admin --email user@example.com
    docker compose exec backend python -m app.cli set_admin --oidc-sub <sub> --oidc-issuer <issuer>

Or via make:
    make set-admin EMAIL=user@example.com
"""

import argparse
import asyncio
import sys


async def _set_admin_by_email(email: str) -> None:
    from sqlalchemy import select, update
    from app.database import AsyncSessionLocal
    from app.models.user import User

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        if user is None:
            print(f"ERROR: No user found with email '{email}'", file=sys.stderr)
            sys.exit(1)
        user.is_admin = True
        await db.commit()
        print(
            f"✅ {user.effective_display_name} ({email}) is now an admin."
        )


async def _set_admin_by_oidc(oidc_sub: str, oidc_issuer: str) -> None:
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.user import User

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(
                User.oidc_sub == oidc_sub,
                User.oidc_issuer == oidc_issuer,
            )
        )
        user = result.scalar_one_or_none()
        if user is None:
            print(
                f"ERROR: No user found with oidc_sub='{oidc_sub}' oidc_issuer='{oidc_issuer}'",
                file=sys.stderr,
            )
            sys.exit(1)
        user.is_admin = True
        await db.commit()
        print(
            f"✅ {user.effective_display_name} is now an admin."
        )


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    set_admin_parser = subparsers.add_parser(
        "set_admin", help="Grant admin status to a user"
    )
    set_admin_parser.add_argument("--email", help="User's email address")
    set_admin_parser.add_argument("--oidc-sub", help="User's OIDC subject claim")
    set_admin_parser.add_argument(
        "--oidc-issuer", help="OIDC issuer URL (required with --oidc-sub)"
    )

    args = parser.parse_args()

    if args.command == "set_admin":
        if args.email:
            asyncio.run(_set_admin_by_email(args.email))
        elif args.oidc_sub and args.oidc_issuer:
            asyncio.run(_set_admin_by_oidc(args.oidc_sub, args.oidc_issuer))
        else:
            print(
                "ERROR: Provide either --email or both --oidc-sub and --oidc-issuer",
                file=sys.stderr,
            )
            sys.exit(1)


if __name__ == "__main__":
    main()
