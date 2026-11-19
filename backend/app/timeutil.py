from datetime import datetime, timedelta, timezone

BKK = timezone(timedelta(hours=7))


def now():
    return datetime.now(BKK).replace(microsecond=0)


def iso(dt=None):
    return (dt or now()).isoformat()


def parse(s):
    return datetime.fromisoformat(s)
