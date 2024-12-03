from datetime import datetime, timedelta

def now():
    return int(datetime.utcnow().timestamp()) * 1000

def one_week_ago():
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    return int(week_ago.timestamp()) * 1000

def two_weeks_ago():
    now = datetime.utcnow()
    week_ago = now - timedelta(days=14)
    return int(week_ago.timestamp()) * 1000

def one_month_ago():
    now = datetime.utcnow()
    month_ago = now - timedelta(days=30)
    return int(month_ago.timestamp()) * 1000