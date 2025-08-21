# db_init.py
import sqlite3
import hashlib
from datetime import datetime, timedelta

DB = "booking.db"

def hash_pass(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def init_db():
    conn = sqlite3.connect(DB)
    c = conn.cursor()

    # Tạo bảng
    c.executescript("""
    PRAGMA foreign_keys = ON;

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        is_movie INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS screenings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        movie_id INTEGER NOT NULL,
        start_time TEXT NOT NULL,
        price REAL NOT NULL,
        FOREIGN KEY(movie_id) REFERENCES movies(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS seats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        screening_id INTEGER NOT NULL,
        seat_label TEXT NOT NULL,
        is_booked INTEGER DEFAULT 0,
        FOREIGN KEY(screening_id) REFERENCES screenings(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        seat_id INTEGER NOT NULL,
        booked_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(seat_id) REFERENCES seats(id)
    );
    """)

    conn.commit()

    # Thêm dữ liệu mẫu nếu chưa có
    c.execute("SELECT COUNT(*) FROM movies")
    if c.fetchone()[0] == 0:
        # Thêm vài "phim" (cũng có thể là chuyến xe nếu is_movie=0)
        movies = [("Avengers: Endgame",1), ("Spider-Man: No Way Home",1), ("Xe Saigon-Hanoi",0)]
        c.executemany("INSERT INTO movies (title, is_movie) VALUES (?, ?)", movies)
        conn.commit()

        # Thêm screenings (3 screenings)
        now = datetime.now()
        screenings = []
        for i, (title, _) in enumerate(movies):
            for s in range(1,3):  # 2 suất mỗi mục
                t = (now + timedelta(hours=2*(i+1) + s)).isoformat()
                price = 50.0 + 10*i + 5*s
                screenings.append((i+1, t, price))
        c.executemany("INSERT INTO screenings (movie_id, start_time, price) VALUES (?, ?, ?)", screenings)
        conn.commit()

        # Thêm seats: mỗi screening 10 ghế (A1..A5, B1..B5)
        c.execute("SELECT id FROM screenings")
        screening_ids = [row[0] for row in c.fetchall()]
        seats = []
        labels = [f"A{i}" for i in range(1,6)] + [f"B{i}" for i in range(1,6)]
        for sid in screening_ids:
            for lbl in labels:
                seats.append((sid, lbl))
        c.executemany("INSERT INTO seats (screening_id, seat_label) VALUES (?, ?)", seats)
        conn.commit()

        # Thêm 1 user test
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", ("testuser", hash_pass("password")))
        conn.commit()

    conn.close()
    print("✅ DB initialized (booking.db) with sample data.")

if __name__ == "__main__":
    init_db()
