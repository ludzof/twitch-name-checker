"""
CLI Interface for Twitch Username Checker.
Allows running scans, checking individual names, and exporting results directly from the terminal.
"""

import sys
import argparse
import asyncio
import time
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from backend.config import BASE_DIR
from backend.database import init_db, get_statistics, export_usernames
from backend.checker_engine import CheckerEngine
from backend.generators import (
    generate_3char_letters,
    generate_3char_alphanumeric,
    generate_4char_letters,
    generate_4char_alphanumeric,
    load_dictionary_words,
    generate_pronounceable,
    generate_aesthetic_patterns,
    generate_by_pattern,
    load_custom_wordlist
)

def print_banner():
    banner = r"""
  _____         _ _       _       _   _                         ____        _                 
 |_   _|_      _(_) |_ ___| |__   | \ | | __ _ _ __ ___   ___  / ___| _ __ (_)_ __   ___ _ __ 
   | | \ \ /\ / / | __/ __| '_ \  |  \| |/ _` | '_ ` _ \ / _ \ \___ \| '_ \| | '_ \ / _ \ '__|
   | |  \ V  V /| | || (__| | | | | |\  | (_| | | | | | |  __/  ___) | | | | | |_) |  __/ |   
   |_|   \_/\_/ |_|\__\___|_| |_| |_| \_|\__,_|_| |_| |_|\___| |____/|_| |_|_| .__/ \___|_|   
                                                                              |_|              
    """
    print(banner)

async def check_single(username: str):
    init_db()
    engine = CheckerEngine()
    print(f"\n🔍 Checking availability for: '{username}'...")
    res = await engine.check_single_username(username)
    
    status = res.get("status", "unknown").upper()
    if status == "AVAILABLE":
        print(f"\n✅ [AVAILABLE] The username '{username}' is 100% free!")
        print(f"👉 Claim here: https://www.twitch.tv/settings/profile")
    elif status == "TAKEN":
        print(f"\n❌ [TAKEN] '{username}' is owned by an active Twitch user.")
        print(f"   Display Name: {res.get('display_name')}")
        print(f"   Channel ID:   {res.get('channel_id')}")
        print(f"   Profile:      https://twitch.tv/{username}")
    elif status == "LOCKED":
        print(f"\n🔒 [LOCKED/BANNED] '{username}' is held/reserved by Twitch.")
        print(f"   (Suspended, deactivated, or legacy Justin.tv account)")
    else:
        print(f"\n⚠️  [INVALID] '{username}': {res.get('reason')}")

async def run_scan(names, speed="normal", skip_checked=True, outfile=None):
    init_db()
    engine = CheckerEngine()
    
    total = len(names)
    print(f"\n🚀 Starting scan of {total:,} usernames (Speed: {speed}, Skip already checked: {skip_checked})...")
    print("Press Ctrl+C to stop scan at any time.\n")
    
    found_avail = []
    
    def on_update(st):
        pct = st["progress_percent"]
        spd = st["speed"]
        chk = st["checked"]
        avl = st["available"]
        eta = f"{st['eta_seconds']}s" if st["eta_seconds"] > 0 else "done"
        sys.stdout.write(f"\r  ⏳ Progress: {chk:,}/{st['total']:,} ({pct}%) | Speed: {spd:.1f}/s | Free: {avl} | ETA: {eta}   ")
        sys.stdout.flush()

    engine.on_update_callback = on_update
    success, msg = engine.start_scan(names, speed_mode=speed, skip_already_checked=skip_checked)
    if not success:
        print(f"Error: {msg}")
        return

    try:
        while engine.state in ("RUNNING", "PAUSED"):
            await asyncio.sleep(0.5)
            # Print newly found available names in terminal
            while engine.newly_found:
                item = engine.newly_found.pop(0)
                found_avail.append(item["username"])
                print(f"\n  🎯 FREE FOUND: {item['username']} ({item['length']} chars)")
    except KeyboardInterrupt:
        print("\n\nStopping scan gracefully...")
        engine.stop_scan()
        await asyncio.sleep(1)

    print("\n\n" + "=" * 55)
    print(" Scan Finished Summary")
    print("=" * 55)
    stats = get_statistics()
    print(f"  Total Checked:    {stats['total']:,}")
    print(f"  Available (Free): {stats['available']:,}")
    print(f"  Taken:            {stats['taken']:,}")
    print(f"  Locked/Banned:    {stats['locked']:,}")
    print("=" * 55)

    if outfile:
        export_usernames("available", filepath=Path(outfile))
        print(f"\n📁 Saved available usernames to: {outfile}")

def main():
    print_banner()
    parser = argparse.ArgumentParser(description="Twitch Username Sniper & Checker")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Command: check
    check_p = subparsers.add_parser("check", help="Check a single username")
    check_p.add_argument("username", type=str, help="Username to check")

    # Command: scan
    scan_p = subparsers.add_parser("scan", help="Scan a range or list of usernames")
    scan_p.add_argument("--mode", type=str, default="3char_letters",
                       choices=["3char_letters", "3char_alphanumeric", "3char_words", "4char_words",
                                "5char_words", "4char_letters", "pronounceable_4", "aesthetic_4",
                                "pattern", "file"],
                       help="Preset generator mode")
    scan_p.add_argument("--pattern", type=str, default="z***", help="Pattern for wildcard mode (e.g. z***)")
    scan_p.add_argument("--file", type=str, help="Custom wordlist text file path")
    scan_p.add_argument("--speed", type=str, default="normal", choices=["safe", "normal", "turbo"], help="Scan speed")
    scan_p.add_argument("--no-skip", action="store_true", help="Do not skip previously checked names")
    scan_p.add_argument("--out", type=str, default="available_usernames.txt", help="Output text file for free names")

    # Command: stats
    subparsers.add_parser("stats", help="Display current database statistics")

    # Command: export
    export_p = subparsers.add_parser("export", help="Export available names to file")
    export_p.add_argument("--out", type=str, default="available_usernames.txt", help="Output file path")
    export_p.add_argument("--status", type=str, default="available", choices=["available", "locked", "taken"])

    args = parser.parse_args()

    if args.command == "check":
        asyncio.run(check_single(args.username))
    elif args.command == "scan":
        mode = args.mode
        names = []
        if mode == "3char_letters":
            names = list(generate_3char_letters())
        elif mode == "3char_alphanumeric":
            names = list(generate_3char_alphanumeric())
        elif mode == "3char_words":
            names = load_dictionary_words(3)
        elif mode == "4char_words":
            names = load_dictionary_words(4)
        elif mode == "5char_words":
            names = load_dictionary_words(5)
        elif mode == "4char_letters":
            names = list(generate_4char_letters())
        elif mode == "pronounceable_4":
            names = list(generate_pronounceable(4))
        elif mode == "aesthetic_4":
            names = list(generate_aesthetic_patterns(4))
        elif mode == "pattern":
            names = list(generate_by_pattern(args.pattern))
        elif mode == "file":
            if not args.file:
                print("Error: --file argument required when --mode file is chosen")
                return
            names = load_custom_wordlist(args.file)

        asyncio.run(run_scan(names, speed=args.speed, skip_checked=not args.no_skip, outfile=args.out))
    elif args.command == "stats":
        init_db()
        st = get_statistics()
        print("\n📊 Database Statistics:")
        print(f"  Total Checked:    {st['total']:,}")
        print(f"  Available (Free): {st['available']:,}")
        print(f"  Taken:            {st['taken']:,}")
        print(f"  Locked/Banned:    {st['locked']:,}")
        print(f"  Invalid Syntax:   {st['invalid']:,}")
    elif args.command == "export":
        init_db()
        names = export_usernames(status=args.status, filepath=Path(args.out))
        print(f"Exported {len(names)} '{args.status}' usernames to {args.out}")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
