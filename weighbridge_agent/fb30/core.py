"""Rotana weighbridge agent - shared core (Python 3.8+, standard library only).

Reads SmartBridge tickets from the Firebird database (read-only) and pushes them to the
Odoo module `rotana_weighbridge`. The Firebird database itself is the durable queue: a ticket is
only marked as "sent" after Odoo acknowledged it, so anything not acknowledged is retried.
"""
import calendar
import configparser
import hashlib
import json
import logging
import logging.handlers
import os
import sqlite3
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

VERSION = '1.0.0'
LOG = logging.getLogger('wbagent')
_LAST_BLOCK = {'count': None, 'time': 0.0}  # avoids repeating the same warning every cycle


class AuthError(Exception):
    """Odoo rejected the token (HTTP 401)."""


class TransientError(Exception):
    """Network / server problem: retry later."""


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
class Config:
    def __init__(self, path):
        cp = configparser.ConfigParser(interpolation=None)
        if not cp.read(path, encoding='utf-8-sig'):
            raise SystemExit('Config file not found or empty: %s' % path)
        self.path = os.path.abspath(path)
        base = os.path.dirname(self.path)

        def get(section, key, default=''):
            return cp.get(section, key, fallback=default).strip()

        self.fb_host = get('firebird', 'host', 'localhost')
        self.fb_port = int(get('firebird', 'port', '3050') or 3050)
        self.fb_database = get('firebird', 'database')
        self.fb_user = os.environ.get('WB_FB_USER') or get('firebird', 'user')
        self.fb_password = os.environ.get('WB_FB_PASSWORD') or get('firebird', 'password')
        self.fb_charset = get('firebird', 'charset', 'UTF8') or 'UTF8'
        self.fb_client_library = get('firebird', 'client_library')

        self.odoo_url = get('odoo', 'url').rstrip('/')
        self.odoo_db = get('odoo', 'db')
        self.odoo_token = os.environ.get('WB_ODOO_TOKEN') or get('odoo', 'token')
        self.station = get('odoo', 'station', 'main') or 'main'
        self.timeout = int(get('odoo', 'timeout_seconds', '30') or 30)

        self.poll_seconds = max(10, int(get('agent', 'poll_seconds', '60') or 60))
        self.lookback_days = max(1, int(get('agent', 'lookback_days', '30') or 30))
        self.batch_size = max(1, min(500, int(get('agent', 'batch_size', '200') or 200)))
        self.max_deletes = max(0, int(get('agent', 'max_deletes_per_cycle', '20') or 20))
        # Sudan is UTC+2 all year (no DST). Weighbridge PC clock is local time.
        self.utc_offset_minutes = int(get('agent', 'utc_offset_minutes', '120') or 120)
        self.state_dir = os.path.join(base, get('agent', 'state_dir', 'state'))
        self.log_dir = os.path.join(base, get('agent', 'log_dir', 'logs'))

    def validate(self, need_odoo=True):
        missing = []
        if not self.fb_database:
            missing.append('[firebird] database')
        if not self.fb_user:
            missing.append('[firebird] user')
        if need_odoo and not self.odoo_url:
            missing.append('[odoo] url')
        if need_odoo and not self.odoo_token:
            missing.append('[odoo] token')
        if missing:
            raise SystemExit('Missing settings in %s: %s' % (self.path, ', '.join(missing)))


def setup_logging(cfg, verbose=False):
    os.makedirs(cfg.log_dir, exist_ok=True)
    fmt = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    root = logging.getLogger('wbagent')
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(cfg.log_dir, 'agent.log'), maxBytes=1000000, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(fmt)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    root.handlers[:] = [file_handler, console]


# --------------------------------------------------------------------------
# Firebird queries (compatible with Firebird 2.5 and 3.0)
# --------------------------------------------------------------------------
TICKET_SELECT = """
SELECT w.TICKETNUMBER, w.FIRSTWEIGHT, w.FIRSTWEIGHTDATETIME, w.SECONDWEIGHT, w.SECONDWEIGHTDATETIME,
       w.UNIT, w.TRUCKHASTRAILER, w.TRAILERFIRSTWEIGHT, w.TRAILERSECONDWEIGHT, w.TOTALNETWEIGHT,
       w.NOTES, t.TRKPLATE, d.NAME, c.NAME, f.FIELDVALUE
FROM TBLWEIGHTS w
LEFT JOIN TBLTRUCKS t ON t.TRKID = w.TRKID
LEFT JOIN TBLDRIVERS d ON d.DRVID = w.DRVID
LEFT JOIN TBLCOMPANIES c ON c.CMPID = w.CMPID
LEFT JOIN TBLCUSTOMFIELD1 f ON f.CF1ID = w.CF1ID
"""
WINDOW = (" WHERE (w.FIRSTWEIGHTDATETIME >= ? OR w.SECONDWEIGHTDATETIME >= ?"
          " OR w.SECONDWEIGHT IS NULL OR w.FIRSTWEIGHTDATETIME IS NULL)")
ORDER_BY = " ORDER BY w.TICKETNUMBER"


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _text(value):
    return '' if value is None else str(value).strip()


def _num(value):
    try:
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def local_to_utc(value, offset_minutes):
    return value - timedelta(minutes=offset_minutes) if value else None


def fmt_dt(value):
    return value.strftime('%Y-%m-%d %H:%M:%S') if value else None


def epoch(utc_dt):
    return calendar.timegm(utc_dt.timetuple())


def row_to_payload(row, cfg):
    """Firebird row -> (payload for Odoo, timestamp used by the 'recent window' bookkeeping)."""
    (number, w1, t1, w2, t2, unit, has_trailer, tw1, tw2, total,
     notes, plate, driver, customer, destination) = row
    t1_utc = local_to_utc(t1, cfg.utc_offset_minutes)
    t2_utc = local_to_utc(t2, cfg.utc_offset_minutes)
    payload = {
        'ticket_number': int(number),
        'plate': _text(plate),
        'first_weight': _num(w1),
        'first_weight_datetime': fmt_dt(t1_utc),
        'second_weight': _num(w2),
        'second_weight_datetime': fmt_dt(t2_utc),
        'has_trailer': bool(has_trailer),
        'trailer_first_weight': _num(tw1),
        'trailer_second_weight': _num(tw2),
        'total_net_weight': abs(_num(total)),
        'unit': _text(unit),
        'driver': _text(driver),
        'customer': _text(customer),
        'destination': _text(destination),
        'notes': _text(notes),
    }
    stamps = [d for d in (t1_utc, t2_utc) if d]
    ts = epoch(max(stamps)) if stamps else epoch(utcnow())
    return payload, ts


def payload_hash(payload):
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode('utf-8')
    return hashlib.sha1(raw).hexdigest()


# --------------------------------------------------------------------------
# Local state: which ticket version Odoo already acknowledged
# --------------------------------------------------------------------------
class State:
    def __init__(self, directory):
        os.makedirs(directory, exist_ok=True)
        self.path = os.path.join(directory, 'agent_state.db')
        self.db = sqlite3.connect(self.path)
        self.db.execute('CREATE TABLE IF NOT EXISTS sent ('
                        'ticket_number INTEGER PRIMARY KEY, hash TEXT NOT NULL, ts REAL NOT NULL)')
        self.db.commit()

    def is_empty(self):
        return self.db.execute('SELECT 1 FROM sent LIMIT 1').fetchone() is None

    def hashes(self):
        return dict(self.db.execute('SELECT ticket_number, hash FROM sent'))

    def mark_sent(self, items):
        self.db.executemany('INSERT OR REPLACE INTO sent (ticket_number, hash, ts) VALUES (?, ?, ?)', items)
        self.db.commit()

    def recent_numbers(self, since_ts):
        return [r[0] for r in self.db.execute('SELECT ticket_number FROM sent WHERE ts >= ?', (since_ts,))]

    def remove(self, numbers):
        self.db.executemany('DELETE FROM sent WHERE ticket_number = ?', [(n,) for n in numbers])
        self.db.commit()

    def clear(self):
        self.db.execute('DELETE FROM sent')
        self.db.commit()

    def count(self):
        return self.db.execute('SELECT COUNT(*) FROM sent').fetchone()[0]

    def close(self):
        self.db.close()


# --------------------------------------------------------------------------
# Odoo HTTP
# --------------------------------------------------------------------------
def _url(cfg, path):
    url = cfg.odoo_url + path
    if cfg.odoo_db:
        url += '?db=' + urllib.parse.quote(cfg.odoo_db)
    return url


def _request(cfg, path, payload=None):
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload is not None else None
    req = urllib.request.Request(
        _url(cfg, path), data=data, method='POST' if data is not None else 'GET',
        headers={'Content-Type': 'application/json; charset=utf-8', 'X-Weighbridge-Token': cfg.odoo_token})
    try:
        with urllib.request.urlopen(req, timeout=cfg.timeout) as response:
            status, body = response.status, response.read()
    except urllib.error.HTTPError as exc:
        status, body = exc.code, exc.read()
    except (urllib.error.URLError, OSError) as exc:
        raise TransientError('cannot reach Odoo: %s' % exc)
    try:
        parsed = json.loads(body.decode('utf-8') or '{}')
    except ValueError:
        parsed = {}
    if status == 401:
        raise AuthError('Odoo rejected the token (check rotana_weighbridge.api_token)')
    if status != 200:
        raise TransientError('Odoo answered HTTP %s: %s' % (status, str(parsed)[:200]))
    return parsed


def odoo_ping(cfg):
    return _request(cfg, '/rotana/weighbridge/ping')


def odoo_sync(cfg, tickets=None, deleted=None):
    return _request(cfg, '/rotana/weighbridge/sync', {
        'station': cfg.station, 'tickets': tickets or [], 'deleted': deleted or []})


# --------------------------------------------------------------------------
# One synchronisation cycle
# --------------------------------------------------------------------------
def fetch_rows(src, cfg, since_local, full):
    if full:
        return src.query(TICKET_SELECT + ORDER_BY)
    return src.query(TICKET_SELECT + WINDOW + ORDER_BY, (since_local, since_local))


def detect_deleted(src, state, since_ts):
    recent = state.recent_numbers(since_ts)
    if not recent:
        return []
    floor = min(recent)
    present = {int(r[0]) for r in src.query('SELECT TICKETNUMBER FROM TBLWEIGHTS WHERE TICKETNUMBER >= ?', (floor,))}
    return sorted(n for n in recent if n not in present)


def run_cycle(cfg, src, state, full=False, dry_run=False):
    now = utcnow()
    since_local = now + timedelta(minutes=cfg.utc_offset_minutes) - timedelta(days=cfg.lookback_days)
    since_ts = epoch(now - timedelta(days=cfg.lookback_days))
    full = full or state.is_empty()

    rows = fetch_rows(src, cfg, since_local, full)
    known = state.hashes()
    changed = []
    for row in rows:
        payload, ts = row_to_payload(row, cfg)
        digest = payload_hash(payload)
        if known.get(payload['ticket_number']) != digest:
            changed.append((payload, digest, ts))

    summary = {'read': len(rows), 'changed': len(changed), 'created': 0, 'updated': 0,
               'cancelled': 0, 'failed': 0, 'delete_blocked': 0, 'mode': 'full' if full else 'window'}

    if dry_run:
        LOG.info('DRY RUN: %s tickets read, %s would be sent', len(rows), len(changed))
        for payload, _, _ in changed[:3]:
            LOG.info('sample: %s', json.dumps(payload, ensure_ascii=False))
        return summary

    for start in range(0, len(changed), cfg.batch_size):
        batch = changed[start:start + cfg.batch_size]
        result = odoo_sync(cfg, tickets=[p for p, _, _ in batch])
        failed = set()
        for err in result.get('errors') or []:
            try:
                failed.add(int(err.get('ticket_number')))
            except (TypeError, ValueError):
                pass
            LOG.warning('Odoo could not store ticket %s: %s', err.get('ticket_number'), err.get('error'))
        ok = [(p['ticket_number'], h, ts) for p, h, ts in batch if p['ticket_number'] not in failed]
        state.mark_sent(ok)
        summary['created'] += result.get('created', 0)
        summary['updated'] += result.get('updated', 0)
        summary['failed'] += len(failed)

    if not full:
        deleted = detect_deleted(src, state, since_ts)
        if deleted and len(deleted) > cfg.max_deletes:
            repeat = _LAST_BLOCK['count'] == len(deleted) and time.time() - _LAST_BLOCK['time'] < 3600
            _LAST_BLOCK.update(count=len(deleted), time=time.time() if not repeat else _LAST_BLOCK['time'])
            (LOG.debug if repeat else LOG.error)('%s tickets vanished from the weighbridge database (limit %s): NOT cancelling them in Odoo. '
                      'Possible archive / numbering reset - check the station setting and run "full" if intended.',
                      len(deleted), cfg.max_deletes)
            summary['delete_blocked'] = len(deleted)
        elif deleted:
            result = odoo_sync(cfg, deleted=deleted)
            state.remove(deleted)
            summary['cancelled'] = result.get('cancelled', 0)
    return summary


def write_heartbeat(cfg):
    try:
        with open(os.path.join(cfg.state_dir, 'heartbeat.txt'), 'w', encoding='utf-8') as fh:
            fh.write(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    except OSError:
        pass


def run_forever(cfg, source_class):
    state = State(cfg.state_dir)
    failures = 0
    last_alive = 0.0
    LOG.info('Agent %s started (station=%s, every %ss, lookback %s days)',
             VERSION, cfg.station, cfg.poll_seconds, cfg.lookback_days)
    while True:
        try:
            src = source_class(cfg)
            src.connect()
            try:
                summary = run_cycle(cfg, src, state)
            finally:
                src.close()
            failures = 0
            write_heartbeat(cfg)
            busy = any(summary[k] for k in ('created', 'updated', 'cancelled', 'failed', 'delete_blocked'))
            if busy or time.time() - last_alive > 600:
                LOG.info('cycle ok: %s', summary)
                last_alive = time.time()
        except AuthError as exc:
            failures += 1
            LOG.error('%s', exc)
        except TransientError as exc:
            failures += 1
            LOG.warning('%s - will retry', exc)
        except KeyboardInterrupt:
            LOG.info('Stopped by user')
            return
        except Exception as exc:  # noqa: BLE001 - keep the agent alive whatever happens
            failures += 1
            LOG.exception('cycle failed: %s', exc)
        time.sleep(min(300, cfg.poll_seconds * (2 ** min(failures, 3)) if failures else cfg.poll_seconds))


# --------------------------------------------------------------------------
# Environment check
# --------------------------------------------------------------------------
def run_check(cfg, source_class, driver_name):
    ok = True
    print('Agent %s | Python %s %s-bit | %s' % (VERSION, sys.version.split()[0], struct.calcsize('P') * 8, sys.platform))
    print('Driver: %s' % driver_name)
    try:
        src = source_class(cfg)
        src.connect()
    except Exception as exc:  # noqa: BLE001
        print('[FAIL] Firebird connection: %s' % exc)
        print('       (a "cannot load fbclient" error usually means Python and Firebird differ in 32/64-bit)')
        return False
    try:
        version = src.query("SELECT RDB$GET_CONTEXT('SYSTEM', 'ENGINE_VERSION'), CURRENT_USER FROM RDB$DATABASE")[0]
        print('[ OK ] Firebird server version %s, connected as %s' % (version[0], str(version[1]).strip()))
        if str(version[1]).strip().upper() == 'SYSDBA':
            print('[WARN] Connected as SYSDBA - use a dedicated read-only user (see grant_reader.sql).')
        count, highest, duplicates = None, None, None
        row = src.query('SELECT COUNT(*), MAX(TICKETNUMBER), COUNT(*) - COUNT(DISTINCT TICKETNUMBER) FROM TBLWEIGHTS')[0]
        count, highest, duplicates = row
        print('[ OK ] TBLWEIGHTS: %s tickets, highest number %s' % (count, highest))
        if duplicates:
            print('[WARN] %s duplicated ticket numbers: Odoo keeps one record per number.' % duplicates)
            ok = False
        src.query(TICKET_SELECT + ' WHERE w.TBLID < 0')
        print('[ OK ] Reader can read all tables needed by the agent')
    except Exception as exc:  # noqa: BLE001
        print('[FAIL] Firebird query: %s' % exc)
        ok = False
    finally:
        src.close()
    if cfg.odoo_url and cfg.odoo_token:
        try:
            odoo_ping(cfg)
            print('[ OK ] Odoo reachable and token accepted (%s)' % cfg.odoo_url)
        except (AuthError, TransientError) as exc:
            print('[FAIL] Odoo: %s' % exc)
            ok = False
    else:
        print('[SKIP] Odoo url/token not set')
    return ok
