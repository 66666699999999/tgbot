import asyncio
import logging
import sys
from datetime import datetime

import pysqlite3

sys.modules["sqlite3"] = pysqlite3
from datetime import datetime, timedelta
import sqlite3
print(sqlite3.sqlite_version)
