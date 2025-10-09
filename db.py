import pymysql
import os
from dotenv import load_dotenv


# load_dotenv("apikey.env")
# def get_conn():
#     return pymysql.connect(
#         host=os.getenv("DATABASE_URL"),
#         user=os.getenv("DATABASE_USER"),
#         password=os.getenv("DATABASE_PASSWORD"),
#         db=os.getenv("DATABASE_NAME"),
#         charset="utf8mb4",
#         cursorclass=pymysql.cursors.DictCursor
#     )

# 배포 시
def get_conn():
    return pymysql.connect(
        host=os.environ.get("DATABASE_URL"),
        user=os.environ.get("DATABASE_USER"),
        password=os.environ.get("DATABASE_PASSWORD"),
        db=os.environ.get("DATABASE_NAME"),
        cursorclass=pymysql.cursors.DictCursor
    )