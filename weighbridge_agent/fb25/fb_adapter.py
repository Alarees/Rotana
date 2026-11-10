"""Firebird 2.5 edition - uses the `fdb` driver (supports Firebird 2.0 - 3.0)."""
import fdb

DRIVER = 'fdb %s (Firebird 2.5 edition)' % fdb.__version__


class Source:
    def __init__(self, cfg):
        self.cfg = cfg
        self.con = None

    def connect(self):
        cfg = self.cfg
        kwargs = dict(
            database=cfg.fb_database, user=cfg.fb_user, password=cfg.fb_password, charset=cfg.fb_charset,
            isolation_level=fdb.ISOLATION_LEVEL_READ_COMMITED_RO)  # read-only transactions
        if cfg.fb_host:
            kwargs.update(host=cfg.fb_host, port=cfg.fb_port)
        if cfg.fb_client_library:
            kwargs['fb_library_name'] = cfg.fb_client_library
        self.con = fdb.connect(**kwargs)

    def query(self, sql, params=()):
        cur = self.con.cursor()
        try:
            cur.execute(sql, tuple(params))
            return cur.fetchall()
        finally:
            cur.close()
            self.con.commit()  # end the transaction so no old snapshot is kept

    def close(self):
        if self.con is not None:
            try:
                self.con.close()
            except Exception:  # noqa: BLE001
                pass
            self.con = None
