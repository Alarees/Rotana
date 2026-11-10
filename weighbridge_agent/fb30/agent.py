"""Rotana weighbridge agent - command line.

  python agent.py check                 test Firebird + Odoo access and print the Firebird version
  python agent.py once --dry-run        show what would be sent, send nothing
  python agent.py once                  one synchronisation cycle
  python agent.py full                  re-send every ticket (initial import / after changing station)
  python agent.py run                   run forever (this is what the scheduled task starts)
"""
import argparse
import os
import sys

import core
from fb_adapter import DRIVER, Source


def main():
    parser = argparse.ArgumentParser(description='Rotana weighbridge agent')
    parser.add_argument('command', choices=['check', 'once', 'full', 'run'])
    parser.add_argument('--config', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini'))
    parser.add_argument('--dry-run', action='store_true', help='read and report only, never call Odoo')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()

    cfg = core.Config(args.config)
    core.setup_logging(cfg, args.verbose)
    cfg.validate(need_odoo=(args.command != 'check' and not args.dry_run))

    if args.command == 'check':
        sys.exit(0 if core.run_check(cfg, Source, DRIVER) else 1)
    if args.command == 'run':
        core.run_forever(cfg, Source)
        return

    state = core.State(cfg.state_dir)
    if args.command == 'full' and not args.dry_run:
        state.clear()  # forget what was sent so every ticket is sent again
    src = Source(cfg)
    src.connect()
    try:
        summary = core.run_cycle(cfg, src, state, full=(args.command == 'full'), dry_run=args.dry_run)
    except (core.AuthError, core.TransientError) as exc:
        core.LOG.error('%s', exc)
        sys.exit(2)
    finally:
        src.close()
        state.close()
    core.LOG.info('done: %s', summary)


if __name__ == '__main__':
    main()
