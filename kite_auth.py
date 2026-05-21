"""
Zerodha Kite Connect — OAuth authentication helper.

Run this script ONCE PER DAY before using the Kite API.
It opens the Zerodha login page, captures your request_token,
exchanges it for an access_token, and saves it to your .env file.

Usage:
    python3 kite_auth.py
"""

import os
import sys
import webbrowser
from dotenv import load_dotenv, set_key

# .env file lives next to this script
ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")


def main():
    load_dotenv(ENV_PATH)

    # ── pre-flight checks ──────────────────────────────────────────────────
    try:
        from kiteconnect import KiteConnect
    except ImportError:
        print("ERROR: kiteconnect not installed.\nRun: pip install kiteconnect")
        sys.exit(1)

    api_key    = os.getenv("KITE_API_KEY", "").strip()
    api_secret = os.getenv("KITE_API_SECRET", "").strip()

    if not api_key or api_key == "your_api_key_here":
        print(
            "ERROR: KITE_API_KEY not set.\n"
            "1. Copy .env.template → .env\n"
            "2. Fill in your API key and secret from https://developers.kite.trade/"
        )
        sys.exit(1)

    if not api_secret or api_secret == "your_api_secret_here":
        print("ERROR: KITE_API_SECRET not set in .env")
        sys.exit(1)

    # ── step 1: open login URL ─────────────────────────────────────────────
    kite      = KiteConnect(api_key=api_key)
    login_url = kite.login_url()

    print("\n" + "─" * 55)
    print("  Kite Connect Authentication")
    print("─" * 55)
    print(f"\nStep 1  Opening Zerodha login in your browser …")
    print(f"        {login_url}\n")
    webbrowser.open(login_url)

    # ── step 2: capture request_token ─────────────────────────────────────
    print("Step 2  After you log in and authorise the app,")
    print("        you'll land on your redirect URL, e.g.:")
    print("        https://127.0.0.1/?request_token=XXXXXX&status=success\n")
    print("        Copy ONLY the request_token value and paste below.")
    print("        (It looks like a 32-character random string)\n")

    request_token = input("        request_token → ").strip()

    if not request_token:
        print("No token entered. Exiting.")
        sys.exit(1)

    # ── step 3: exchange for access_token ─────────────────────────────────
    try:
        session_data = kite.generate_session(request_token, api_secret=api_secret)
    except Exception as exc:
        print(f"\nERROR generating session: {exc}")
        print("Common causes:")
        print("  • request_token was already used (each token is one-time)")
        print("  • API secret is wrong in .env")
        print("  • Token expired (must be used within a few minutes of login)")
        sys.exit(1)

    access_token = session_data["access_token"]
    user_name    = session_data.get("user_name", "—")
    user_id      = session_data.get("user_id", "—")

    # ── step 4: save to .env ───────────────────────────────────────────────
    # Create .env from template if it doesn't exist yet
    if not os.path.exists(ENV_PATH):
        template = os.path.join(os.path.dirname(__file__), ".env.template")
        if os.path.exists(template):
            import shutil
            shutil.copy(template, ENV_PATH)

    set_key(ENV_PATH, "KITE_ACCESS_TOKEN", access_token)

    print("\n" + "─" * 55)
    print(f"  Logged in as : {user_name} ({user_id})")
    print(f"  Access token : {access_token[:8]}… (saved to .env)")
    print("─" * 55)
    print("\n  IMPORTANT: This token expires at midnight IST.")
    print("  Re-run this script each trading day before your strategy.\n")

    # Quick connectivity test
    kite.set_access_token(access_token)
    try:
        profile = kite.profile()
        print(f"  Connected OK  ·  Exchange: {', '.join(profile.get('exchanges', []))}")
    except Exception:
        print("  (Could not verify connection — token saved anyway)")

    print()


if __name__ == "__main__":
    main()
