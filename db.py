import sqlite3
import os
from flask import g, current_app

DB_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), "career_portal.db")
SCHEMA_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), "schema.sql")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, "r") as f:
        db.executescript(f.read())
    db.commit()
    db.close()


def query_db(query, args=(), one=False):
    cur = get_db().execute(query, args)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows


def execute_db(query, args=()):
    db = get_db()
    cur = db.execute(query, args)
    db.commit()
    last_id = cur.lastrowid
    cur.close()
    return last_id


def init_app(app):
    app.teardown_appcontext(close_db)
