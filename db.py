import pymysql
import os
from dotenv import load_dotenv

load_dotenv("apikey.env")
def get_conn():
    return pymysql.connect(
        host=os.getenv("DATABASE_URL"),
        user=os.getenv("DATABASE_USER"),
        password=os.getenv("DATABASE_PASSWORD"),
        db=os.getenv("DATABASE_NAME"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor
    )
