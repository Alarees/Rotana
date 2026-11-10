"""Firebird 3.0 edition - uses the `firebird-driver` package (Firebird 3.0, 4.0, 5.0)."""
from firebird.driver import Isolation, TraAccessMode, connect, driver_config, tpb

try:
    from importlib.metadata import version as _version
    DRIVER = 'firebird-driver %s (Firebird 3.0 edition)' % _version('firebird-driver')
except Exception:  # noqa: BLE001
    DRIVER = 'firebird-driver (Firebird 3.0 edition)'


class Source:
    def __init__(self, cfg):
        self.cfg = cfg
        self.con = None
        self.tm = None

    def connect(self):
        cfg = self.cfg
        if cfg.fb_client_library:
            driver_config.fb_client_library.value = cfg.fb_client_library
        target = '%s/%s:%s' % (cfg.fb_host, cfg.fb_port, cfg.fb_database) if cfg.fb_host else cfg.fb_database
        self.con = connect(target, user=cfg.fb_user, password=cfg.fb_password, charset=cfg.fb_charset)
        # every query runs in a READ-ONLY transaction
        self.tm = self.con.transaction_manager(
            tpb(Isolation.READ_COMMITTED_RECORD_VERSION, access_mode=TraAccessMode.READ))

    def query(self, sql, params=()):
        self.tm.begin()
        try:
            cur = self.tm.cursor()
            try:
                cur.execute(sql, list(params))
                return cur.fetchall()
            finally:
                cur.close()
        finally:
            self.tm.commit()

    def close(self):
        if self.con is not None:
            try:
                self.con.close()
            except Exception:  # noqa: BLE001
                pass
            self.con = None
            self.tm = None
