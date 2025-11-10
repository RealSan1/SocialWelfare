import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData, Table, Column, String, Text, Integer, ForeignKey

# 개발 시
load_dotenv("apikey.env")
DB_USER = os.getenv("DATABASE_USER")
DB_PASS = os.getenv("DATABASE_PASSWORD")
DB_HOST = os.getenv("DATABASE_URL")
DB_NAME = os.getenv("DATABASE_NAME")

# 배포 시
# DB_USER = os.environ.get("DATABASE_USER", "root")
# DB_PASS = os.environ.get("DATABASE_PASSWORD", "")
# DB_HOST = os.environ.get("DATABASE_URL", "localhost")
# DB_NAME = os.environ.get("DATABASE_NAME", "welfare")


engine = create_engine(
    f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_HOST}/{DB_NAME}?charset=utf8mb4",
    echo=False
)

metadata = MetaData()

# -------------------------
# 테이블 정의
# -------------------------
복지서비스 = Table(
    "복지서비스", metadata,
    Column("서비스ID", String(20), primary_key=True),
    Column("정책명", Text),
    Column("링크", Text),
    Column("지원대상", Text),
    Column("참고사항", Text),
    Column("상세내용", Text)
)

카테고리 = Table(
    "카테고리", metadata,
    Column("카테고리ID", Integer, primary_key=True, autoincrement=True),
    Column("서비스ID", String(20), ForeignKey("복지서비스.서비스ID", onupdate="CASCADE", ondelete="CASCADE")),
    Column("카테고리", String(50))
)
