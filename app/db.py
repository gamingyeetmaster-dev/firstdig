"""SQLite access and schema. One file, WAL mode, no ORM."""
import sqlite3
from contextlib import contextmanager

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY, value TEXT
);

-- One row per permit application row in the city file
CREATE TABLE IF NOT EXISTS permits (
  permit_key TEXT PRIMARY KEY,           -- PERMIT_NUM|REVISION_NUM
  permit_num TEXT, revision_num TEXT,
  permit_type TEXT, structure_type TEXT, work TEXT,
  street_num TEXT, street_name TEXT, street_type TEXT, street_dir TEXT,
  address TEXT, postal TEXT, geo_id TEXT, ward TEXT,
  application_date TEXT, issued_date TEXT, completed_date TEXT, status TEXT,
  description TEXT, current_use TEXT, proposed_use TEXT,
  units_created INTEGER, units_lost INTEGER, est_cost REAL,
  builder_name TEXT,
  lat REAL, lon REAL, neighbourhood TEXT,
  first_seen TEXT, last_seen TEXT
);
CREATE INDEX IF NOT EXISTS ix_permits_addr ON permits(address);
CREATE INDEX IF NOT EXISTS ix_permits_app ON permits(application_date);

-- Grouped residential construction projects (the Teardown Feed unit)
CREATE TABLE IF NOT EXISTS projects (
  project_id TEXT PRIMARY KEY,           -- normalized address
  address TEXT, postal TEXT, ward TEXT, neighbourhood TEXT,
  lat REAL, lon REAL,
  kind TEXT,                             -- teardown|multiplex|garden_suite|major_addition|underpinning|new_building
  stage TEXT,                            -- applied|issued|construction|completed
  headline TEXT, description TEXT,
  est_cost REAL, units_created INTEGER,
  builder_name TEXT,
  first_filed TEXT, last_activity TEXT, issued_date TEXT,
  permit_nums TEXT,                      -- comma list
  signals TEXT,                          -- comma list of permit types involved
  score INTEGER
);
CREATE INDEX IF NOT EXISTS ix_projects_filed ON projects(first_filed);
CREATE INDEX IF NOT EXISTS ix_projects_hood ON projects(neighbourhood);

-- Business licences (city file), only the categories we care about
CREATE TABLE IF NOT EXISTS licences (
  licence_no TEXT PRIMARY KEY,
  category TEXT, operating_name TEXT, client_name TEXT,
  issued TEXT, cancel_date TEXT, last_update TEXT,
  phone TEXT, address TEXT, address2 TEXT, ward TEXT,
  lat REAL, lon REAL, neighbourhood TEXT,
  first_seen TEXT
);
CREATE INDEX IF NOT EXISTS ix_lic_issued ON licences(issued);

-- AGCO liquor applications under public notice
CREATE TABLE IF NOT EXISTS liquor_apps (
  file_number TEXT PRIMARY KEY,
  city TEXT, premises_name TEXT, address TEXT, deadline TEXT,
  application_type TEXT, licence_type TEXT, areas TEXT,
  lat REAL, lon REAL, neighbourhood TEXT,
  first_seen TEXT, last_seen TEXT
);

-- Joined "opening soon" records
CREATE TABLE IF NOT EXISTS openings (
  opening_id TEXT PRIMARY KEY,           -- normalized address
  name TEXT, category TEXT, address TEXT, city TEXT, postal TEXT,
  ward TEXT, neighbourhood TEXT, lat REAL, lon REAL,
  phone TEXT, owner TEXT,
  first_signal TEXT, last_signal TEXT,
  signals TEXT,                          -- json list of {type,date,detail}
  signal_count INTEGER, score INTEGER,
  est_cost REAL, description TEXT
);
CREATE INDEX IF NOT EXISTS ix_open_first ON openings(first_signal);

CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  created TEXT, last_login TEXT,
  trial_ends TEXT,
  stripe_customer_id TEXT,
  plan TEXT,                             -- teardown|openings|bundle|NULL
  plan_status TEXT,                      -- active|past_due|canceled|NULL
  digest_teardown INTEGER DEFAULT 1,
  digest_openings INTEGER DEFAULT 1,
  areas TEXT                             -- comma list of neighbourhoods to filter digests, blank = all
);

CREATE TABLE IF NOT EXISTS magic_links (
  token TEXT PRIMARY KEY, email TEXT, expires TEXT, used INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sent_digests (
  user_id INTEGER, product TEXT, sent_date TEXT,
  PRIMARY KEY (user_id, product, sent_date)
);

CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started TEXT, finished TEXT, ok INTEGER, notes TEXT
);
"""


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH), timeout=30, check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    return con


def init_db():
    with connect() as con:
        con.executescript(SCHEMA)


@contextmanager
def db():
    con = connect()
    try:
        yield con
        con.commit()
    finally:
        con.close()


def get_meta(con, key, default=None):
    row = con.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def set_meta(con, key, value):
    con.execute("INSERT OR REPLACE INTO meta(key,value) VALUES(?,?)", (key, str(value)))
