from dataclasses import dataclass
from datetime import datetime


@dataclass
class TimeEntry:
    start: datetime
    stop: datetime
