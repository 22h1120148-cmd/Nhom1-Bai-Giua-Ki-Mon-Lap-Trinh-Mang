# server.py
import socket
import threading
import json
import sqlite3
from datetime import datetime

DB = "booking.db"
HOST = "127.0.0.1"
PORT = 65432

# Helper DB functions
def get_db_connection():
    # allow multithreaded access
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def handle_client(conn_sock, addr):
    print(f"[+] Client connected: {addr}")
    conn = get_db_connection()
    try:
        user = None  # store authenticated user row (id, username)
        with conn_sock:
            while True:
                raw = conn_sock.recv(4096)
                if not raw:
                    break
                try:
                    req = json.loads(raw.decode())
                except json.JSONDecodeError:
                    send(conn_sock, {"status":"error","message":"Invalid JSON"})
                    continue

                action = req.get("action")
                if action == "register":
                    username = req.get("username")
                    password = req.get("password")
                    if not username or not password:
                        send(conn_sock, {"status":"error","message":"username & password required"})
                        continue
                    # Hash simple
                    import hashlib
                    pw_hash = hashlib.sha256(password.encode()).hexdigest()
                    try:
                        cur = conn.cursor()
                        cur.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, pw_hash))
                        conn.commit()
                        send(conn_sock, {"status":"ok","message":"registered"})
                    except sqlite3.IntegrityError:
                        send(conn_sock, {"status":"error","message":"username exists"})
                elif action == "login":
                    username = req.get("username")
                    password = req.get("password")
                    if not username or not password:
                        send(conn_sock, {"status":"error","message":"username & password required"})
                        continue
                    import hashlib
                    pw_hash = hashlib.sha256(password.encode()).hexdigest()
                    cur = conn.cursor()
                    cur.execute("SELECT id,username FROM users WHERE username=? AND password_hash=?", (username, pw_hash))
                    row = cur.fetchone()
                    if row:
                        user = {"id": row["id"], "username": row["username"]}
                        send(conn_sock, {"status":"ok","message":"logged_in", "user": {"id": user["id"], "username": user["username"]}})
                    else:
                        send(conn_sock, {"status":"error","message":"invalid credentials"})
                elif action == "list_movies":
                    cur = conn.cursor()
                    cur.execute("SELECT id,title,is_movie FROM movies")
                    rows = [dict(r) for r in cur.fetchall()]
                    send(conn_sock, {"status":"ok","movies": rows})
                elif action == "list_screenings":
                    movie_id = req.get("movie_id")
                    cur = conn.cursor()
                    if movie_id:
                        cur.execute("SELECT id,movie_id,start_time,price FROM screenings WHERE movie_id=?", (movie_id,))
                    else:
                        cur.execute("SELECT id,movie_id,start_time,price FROM screenings")
                    rows = [dict(r) for r in cur.fetchall()]
                    send(conn_sock, {"status":"ok","screenings": rows})
                elif action == "list_seats":
                    screening_id = req.get("screening_id")
                    if not screening_id:
                        send(conn_sock, {"status":"error","message":"screening_id required"})
                        continue
                    cur = conn.cursor()
                    cur.execute("SELECT id,seat_label,is_booked FROM seats WHERE screening_id=? ORDER BY seat_label", (screening_id,))
                    seats = [dict(r) for r in cur.fetchall()]
                    send(conn_sock, {"status":"ok","seats": seats})
                elif action == "book_seat":
                    if not user:
                        send(conn_sock, {"status":"error","message":"login required"})
                        continue
                    seat_id = req.get("seat_id")
                    if not seat_id:
                        send(conn_sock, {"status":"error","message":"seat_id required"})
                        continue
                    # Transactional booking: mark seat as booked only if not already
                    try:
                        cur = conn.cursor()
                        # Start immediate transaction to prevent race
                        cur.execute("BEGIN IMMEDIATE")
                        cur.execute("SELECT is_booked,screening_id FROM seats WHERE id=?", (seat_id,))
                        seat = cur.fetchone()
                        if not seat:
                            conn.rollback()
                            send(conn_sock, {"status":"error","message":"seat not found"})
                        elif seat["is_booked"]:
                            conn.rollback()
                            send(conn_sock, {"status":"error","message":"seat already booked"})
                        else:
                            cur.execute("UPDATE seats SET is_booked=1 WHERE id=? AND is_booked=0", (seat_id,))
                            if cur.rowcount == 1:
                                now = datetime.now().isoformat()
                                cur.execute("INSERT INTO bookings (user_id, seat_id, booked_at) VALUES (?, ?, ?)", (user["id"], seat_id, now))
                                conn.commit()
                                send(conn_sock, {"status":"ok","message":"booked", "seat_id": seat_id})
                            else:
                                conn.rollback()
                                send(conn_sock, {"status":"error","message":"failed to book (concurrency)"} )
                    except sqlite3.DatabaseError as e:
                        conn.rollback()
                        send(conn_sock, {"status":"error","message":"db error", "detail": str(e)})
                elif action == "my_bookings":
                    if not user:
                        send(conn_sock, {"status":"error","message":"login required"})
                        continue
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT b.id as booking_id, b.booked_at, s.id as seat_id, s.seat_label, sc.id as screening_id, sc.start_time, m.title
                        FROM bookings b
                        JOIN seats s ON b.seat_id = s.id
                        JOIN screenings sc ON s.screening_id = sc.id
                        JOIN movies m ON sc.movie_id = m.id
                        WHERE b.user_id = ?
                        ORDER BY b.booked_at DESC
                    """, (user["id"],))
                    rows = [dict(r) for r in cur.fetchall()]
                    send(conn_sock, {"status":"ok","bookings": rows})
                elif action == "cancel_booking":
                    if not user:
                        send(conn_sock, {"status":"error","message":"login required"})
                        continue
                    booking_id = req.get("booking_id")
                    if not booking_id:
                        send(conn_sock, {"status":"error","message":"booking_id required"})
                        continue
                    try:
                        cur = conn.cursor()
                        cur.execute("BEGIN IMMEDIATE")
                        # Check ownership
                        cur.execute("SELECT seat_id FROM bookings WHERE id=? AND user_id=?", (booking_id, user["id"]))
                        row = cur.fetchone()
                        if not row:
                            conn.rollback()
                            send(conn_sock, {"status":"error","message":"booking not found or not yours"})
                        else:
                            seat_id = row["seat_id"]
                            cur.execute("DELETE FROM bookings WHERE id=?", (booking_id,))
                            cur.execute("UPDATE seats SET is_booked=0 WHERE id=?", (seat_id,))
                            conn.commit()
                            send(conn_sock, {"status":"ok","message":"canceled"})
                    except sqlite3.DatabaseError as e:
                        conn.rollback()
                        send(conn_sock, {"status":"error","message":"db error", "detail": str(e)})
                else:
                    send(conn_sock, {"status":"error","message":"unknown action"})
    except Exception as e:
        print("Exception handling client:", e)
    finally:
        conn.close()
        print(f"[-] Client disconnected: {addr}")

def send(sock, obj):
    data = json.dumps(obj).encode()
    try:
        sock.sendall(data)
    except:
        pass

def start_server():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((HOST, PORT))
    s.listen()
    print(f"🚀 Server listening on {HOST}:{PORT}")
    try:
        while True:
            client_sock, addr = s.accept()
            t = threading.Thread(target=handle_client, args=(client_sock, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("Shutting down server...")
    finally:
        s.close()

if __name__ == "__main__":
    start_server()
