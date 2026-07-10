import string
import random
from datetime import datetime, timezone, timedelta  #v2upgrades

_IST = timezone(timedelta(hours=5, minutes=30))  #v2upgrades

def to_ist_str(dt: datetime) -> str:  #v2upgrades
    """Convert a UTC datetime to India Standard Time (IST, UTC+5:30) formatted string."""  #v2upgrades
    if dt is None:  #v2upgrades
        return None  #v2upgrades
    if dt.tzinfo is None:  #v2upgrades
        dt = dt.replace(tzinfo=timezone.utc)  #v2upgrades
    return dt.astimezone(_IST).strftime("%d %b %Y, %I:%M %p IST")  #v2upgrades

def generate_random_string(length=8):
    """Generate random alphanumeric string"""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def format_percentage(value):
    """Format float as percentage"""
    return f"{value:.2f}%"

def validate_email(email):
    """Basic email validation"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None