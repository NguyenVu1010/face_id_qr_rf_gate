"""Event tail subcommand."""
from __future__ import annotations


def tail(db, n: int = 20) -> None:
    rows = db.recent_events(limit=n)
    if not rows:
        print("(no events)")
        return
    for r in rows:
        ev_id, ts, method, _uid, name, granted, detail, clip = r
        ok = "OK" if granted else "DENY"
        name = name or "-"
        clip = clip or "-"
        print(f"#{ev_id:>5} {ts}  {method:<14} {name:<20} {ok:<4} {clip}")
