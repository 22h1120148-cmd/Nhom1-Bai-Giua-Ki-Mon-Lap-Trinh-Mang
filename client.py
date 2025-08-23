import tkinter as tk
from tkinter import messagebox
import socket, json
HOST = "127.0.0.1"
PORT = 65432
class BookingClient:
    def __init__(self, master):
        self.master = master
        self.master.title("Hệ thống đặt vé")
        self.username = None
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((HOST, PORT))
        self.login_screen()

    def send(self, action, **params):
        req = {"action": action}
        req.update(params)
        self.sock.sendall(json.dumps(req).encode())
        return json.loads(self.sock.recv(8192).decode())

    # --- Login / Register -
    def login_screen(self):
        for w in self.master.winfo_children(): w.destroy()
        tk.Label(self.master, text="Tên đăng nhập").pack()
        user_entry = tk.Entry(self.master); user_entry.pack()
        tk.Label(self.master, text="Mật khẩu").pack()
        pass_entry = tk.Entry(self.master, show="*"); pass_entry.pack()

        def login():
            res = self.send("login", username=user_entry.get(), password=pass_entry.get())
            if res["status"] == "ok":
                self.username = user_entry.get()
                self.main_menu()
            else:
                messagebox.showerror("Lỗi", res["message"])

        def register():
            res = self.send("register", username=user_entry.get(), password=pass_entry.get())
            messagebox.showinfo("Thông báo", res["message"])

        tk.Button(self.master, text="Đăng nhập", command=login).pack()
        tk.Button(self.master, text="Đăng ký", command=register).pack()

    # --- Main Menu ---
    def main_menu(self):
        for w in self.master.winfo_children(): w.destroy()
        tk.Label(self.master, text=f"Xin chào {self.username}", font=("Arial", 14)).pack()
        tk.Button(self.master, text="Xem phim", command=self.show_movies).pack(pady=5)
        tk.Button(self.master, text="Vé của tôi", command=self.my_bookings).pack(pady=5)
        tk.Button(self.master, text="Đăng xuất", command=self.login_screen).pack(pady=5)

    # --- Movies ---
    def show_movies(self):
        for w in self.master.winfo_children(): w.destroy()
        res = self.send("list_movies")
        tk.Label(self.master, text="Danh sách phim", font=("Arial", 14)).pack()
        for movie in res.get("movies", []):
            tk.Button(self.master, text=movie["title"],
                      command=lambda m=movie: self.show_screenings(m["id"], m["title"])).pack(pady=2)
        tk.Button(self.master, text="⬅ Quay lại", command=self.main_menu).pack()

    # --- Screenings ---
    def show_screenings(self, movie_id, title):
        for w in self.master.winfo_children(): w.destroy()
        res = self.send("list_screenings", movie_id=movie_id)
        tk.Label(self.master, text=f"Suất chiếu - {title}", font=("Arial", 14)).pack()
        for sc in res.get("screenings", []):
            text = f"{sc['start_time']} - {sc['price']} VNĐ"
            tk.Button(self.master, text=text,
                      command=lambda s=sc: self.show_seats(s["id"])).pack(pady=2)
        tk.Button(self.master, text="⬅ Quay lại", command=self.show_movies).pack()

    # --- Seats ---
    def show_seats(self, screening_id):
        for w in self.master.winfo_children(): w.destroy()
        res = self.send("list_seats", screening_id=screening_id)
        tk.Label(self.master, text="Chọn ghế", font=("Arial", 14)).pack()
        frame = tk.Frame(self.master); frame.pack()
        for i, seat in enumerate(res.get("seats", [])):
            color = "red" if seat["is_booked"] else "green"
            b = tk.Button(frame, text=seat["seat_label"], bg=color, width=4,
                          command=lambda s=seat: self.book_seat(s["id"]))
            b.grid(row=i//8, column=i%8, padx=2, pady=2)
        tk.Button(self.master, text="⬅ Quay lại", command=self.show_movies).pack()

    def book_seat(self, seat_id):
        res = self.send("book_seat", username=self.username, seat_id=seat_id)
        messagebox.showinfo("Kết quả", res["message"])
        self.show_movies()

    # --- My Bookings ---
    def my_bookings(self):
        for w in self.master.winfo_children(): w.destroy()
        res = self.send("my_bookings", username=self.username)
        tk.Label(self.master, text="Vé đã đặt", font=("Arial", 14)).pack()
        for b in res.get("bookings", []):
            tk.Label(self.master, text=f"{b['seat_label']} - {b['start_time']}").pack()
        tk.Button(self.master, text="⬅ Quay lại", command=self.main_menu).pack()

# --- Run ---
root = tk.Tk()
app = BookingClient(root)
root.mainloop()


