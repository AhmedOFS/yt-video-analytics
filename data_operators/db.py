import os
import sqlite3
import pandas as pd
from deltalake import DeltaTable


class DB:

    def __init__(self, db_path="yt.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                video_id TEXT PRIMARY KEY,
                published_at TEXT,
                channel_id TEXT,
                title TEXT,
                description TEXT,
                category_id TEXT,
                view_count INTEGER,
                like_count INTEGER,
                dislike_count INTEGER,
                comment_count INTEGER,
                privacy_status TEXT,
                channel TEXT,
                fetched_comments_count INTEGER
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                comment_id TEXT PRIMARY KEY,
                video_id TEXT REFERENCES videos(video_id),
                thread_id TEXT,
                text_display TEXT,
                author_display_name TEXT,
                author_channel_id TEXT,
                like_count INTEGER,
                published_at TEXT
            )
        """)
        # migrate existing db where thread_id was the primary key
        info = cur.execute("PRAGMA table_info(comments)").fetchall()
        pk_cols = [col[1] for col in info if col[5] == 1]
        if pk_cols == ["thread_id"]:
            cur.execute("PRAGMA foreign_keys = OFF")
            cur.execute("BEGIN TRANSACTION")
            cur.execute("ALTER TABLE comments RENAME TO comments_old")
            cur.execute("""
                CREATE TABLE comments (
                    comment_id TEXT PRIMARY KEY,
                    video_id TEXT REFERENCES videos(video_id),
                    thread_id TEXT,
                    text_display TEXT,
                    author_display_name TEXT,
                    author_channel_id TEXT,
                    like_count INTEGER,
                    published_at TEXT
                )
            """)
            cur.execute("""
                INSERT INTO comments (comment_id, video_id, thread_id, text_display,
                                       author_display_name, author_channel_id,
                                       like_count, published_at)
                SELECT comment_id, video_id, thread_id, text_display,
                       author_display_name, author_channel_id,
                       like_count, published_at
                FROM comments_old
            """)
            cur.execute("DROP TABLE comments_old")
            cur.execute("COMMIT")
            cur.execute("PRAGMA foreign_keys = ON")
        conn.commit()
        conn.close()

    def _ensure_db(self):
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"Database {self.db_path} not found.")
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('videos', 'comments')")
        tables = {row[0] for row in cur.fetchall()}
        conn.close()
        if tables != {"videos", "comments"}:
            raise RuntimeError("Database is missing required tables.")

    def load_from_L2(self):
        self._ensure_db()

        videos = DeltaTable("L2/Video_Details").to_pandas()
        comments = DeltaTable("L2/Comments").to_pandas()

        videos["published_at"] = pd.to_datetime(videos["published_at"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
        if "published_at" in comments.columns:
            comments["published_at"] = pd.to_datetime(comments["published_at"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.execute("DELETE FROM comments")
        cur.execute("DELETE FROM videos")
        videos.to_sql("videos", conn, if_exists="append", index=False)
        comments.to_sql("comments", conn, if_exists="append", index=False)
        conn.commit()
        conn.close()

        print(f"Loaded {len(videos)} videos and {len(comments)} comments into {self.db_path}.")
