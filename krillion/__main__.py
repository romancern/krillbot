import argparse
import os
import re
import sys
import time
from .store import Store


def room_code(value):
    value = value.strip().upper()
    if not re.fullmatch(r'[A-Z]{4}', value):
        raise argparse.ArgumentTypeError('room code must contain four letters')
    return value


def main():
    from dotenv import load_dotenv
    load_dotenv()
    p = argparse.ArgumentParser(description='Assisted Puffer Party evidence tracker')
    p.add_argument('--db', default=os.environ.get('KRILLION_DB', 'krillion.sqlite3'))
    sub = p.add_subparsers(dest='command', required=True)
    find = sub.add_parser('suggest', help='Find previously recorded answers for an exact question')
    find.add_argument('question')
    find.add_argument('--mode', default='puffer-party')
    find.add_argument('--used', action='append', default=[], help='Exclude an answer already used this round; repeat as needed')
    rec = sub.add_parser('record', help='Record a result or an unverified answer')
    rec.add_argument('question')
    rec.add_argument('answer')
    rec.add_argument('--status', required=True, choices=['accepted', 'rejected', 'observed', 'suggested', 'inferred'])
    rec.add_argument('--source', required=True, help='Where this specific evidence came from')
    rec.add_argument('--mode', default='puffer-party')
    rec.add_argument('--score', type=float)
    rec.add_argument('--rarity')
    live = sub.add_parser('live', help='Open a Playwright browser and play your turns')
    mode = live.add_mutually_exclusive_group(required=True)
    mode.add_argument('-b', '--bot', action='store_true', help='Automatically submit answers')
    mode.add_argument('-o', '--overlay', action='store_true', help='Show hints in a floating window')
    live.add_argument('--name', dest='join_name', metavar='NAME', help='Join the room using this display name')
    live.add_argument('--observe', action='store_true', help='Watch and log without a model key or sending answers')
    destination = live.add_mutually_exclusive_group()
    destination.add_argument('--code', type=room_code, help='Four-letter room code; omit to open the lobby')
    destination.add_argument('--ranked', action='store_true', help='Join ranked matchmaking')
    destination.add_argument('--new', action='store_true', help='Host a new private room')
    live.add_argument('--table-size', choices=['1v1', '3s', '4-6', '8-10'], default='4-6', help='Ranked table size (default: 4-6)')
    live.add_argument('--model', default=os.environ.get('KRILLION_MODEL', 'gpt-6-luna'))
    live.add_argument('--model-timeout', type=float, default=8.0)
    live.add_argument('--poll', type=float, default=0.15)
    args = p.parse_args()
    if args.command == 'live':
        if args.overlay and args.observe:
            p.error('--overlay generates hints; it cannot be combined with --observe')
        import asyncio
        from .live import run
        try:
            if args.overlay:
                from .overlay import run_overlay
                run_overlay(args)
            else:
                asyncio.run(run(args))
        except KeyboardInterrupt:
            print('\nStopped.')
        except (RuntimeError, ImportError) as exc:
            p.error(str(exc))
        return
    start = time.perf_counter()
    try:
        store = Store(args.db)
        if args.command == 'record':
            store.record(args.question, args.mode, args.answer, args.status, args.source, args.score, args.rarity)
            print('Recorded.')
        else:
            groups = store.lookup(args.question, args.mode, args.used)
            if not groups:
                print('No matching recorded answers. Enter a candidate manually and record its outcome.')
            for group in groups:
                decisive = next((r for r in group if r['status'] in ('accepted', 'rejected')), group[0])
                print(f"{decisive['answer']} | {decisive['status']} | score={decisive['score']} | rarity={decisive['rarity']} | source={decisive['source']} | {decisive['timestamp']}")
            print(f'Lookup: {(time.perf_counter()-start)*1000:.1f} ms', file=sys.stderr)
    except (ValueError, OSError) as exc:
        p.error(str(exc))

def cli():
    # The command's default action is live; named subcommands remain available.
    if len(sys.argv) > 1 and sys.argv[1].startswith('-') and sys.argv[1] not in ('-h', '--help'):
        sys.argv.insert(1, 'live')
    main()

if __name__ == '__main__':
    main()
