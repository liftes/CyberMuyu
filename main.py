import tkinter as tk
from PIL import Image, ImageTk, Image as PILImage
import json
import time
import os
from pynput import keyboard
from threading import Thread
from screeninfo import get_monitors
import ctypes
import sys
import threading
from pystray import Icon as TrayIcon, Menu as TrayMenu, MenuItem as TrayMenuItem

CACHE_FILE = "muyu_cache.json"

class MuyuApp:
    def __init__(self, master):
        self.master = master
        self.master.geometry("240x240+100+100")
        self.master.configure(bg="#fdf5e6")
        self.master.attributes("-topmost", True)
        self.master.overrideredirect(True)
        self.fullscreen = False
        self.info_visible = False
        self.last_geometry = self.master.geometry()

        if sys.platform == "win32":
            hwnd = ctypes.windll.user32.GetParent(self.master.winfo_id())
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_APPWINDOW = 0x00040000
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            style = style & ~WS_EX_APPWINDOW | WS_EX_TOOLWINDOW
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

        self.master.bind("<ButtonPress-1>", self.start_move)
        self.master.bind("<B1-Motion>", self.do_move)

        self.start_time = time.time()
        self.total_hits = 0
        self.total_duration = 0
        self.load_cache()

        self.original_image_idle = Image.open("muyu_idle.png")
        self.original_image_hit = Image.open("muyu_hit.png")
        init_w = 180
        self.image_idle = ImageTk.PhotoImage(self.original_image_idle.resize((init_w, init_w)))
        self.image_hit = ImageTk.PhotoImage(self.original_image_hit.resize((init_w, init_w)))

        self.container = tk.Frame(master, bg="#fdf5e6")
        self.container.pack(expand=True, fill="both")

        self.muyu_label = tk.Label(self.container, image=self.image_idle, bg="#fdf5e6", cursor="hand2")
        self.muyu_label.pack(expand=True)
        self.muyu_label.bind("<Button-1>", self.toggle_info)

        self.hit_label = tk.Label(self.container, text="", font=("微软雅黑", 12), bg="#fdf5e6")
        self.time_label = tk.Label(self.container, text="", font=("微软雅黑", 12), bg="#fdf5e6")

        self.toggle_button = tk.Button(master, text="●", font=("Arial", 10, "bold"),
                                       bg="#aaa", fg="white", bd=0,
                                       command=self.toggle_fullscreen)
        self.toggle_button.place(x=5, y=5, width=20, height=20)

        self.tray_button = tk.Button(master, text="▼", font=("Arial", 10, "bold"),
                                     bg="#aaa", fg="white", bd=0,
                                     command=self.hide_to_tray)
        self.tray_button.place(x=30, y=5, width=20, height=20)

        self.master.bind("<Configure>", self.resize_image)

        self.listener = keyboard.Listener(on_press=self.on_key_press)
        self.listener.start()

        self.update_time()
        self.periodic_save()

        self.master.protocol("WM_DELETE_WINDOW", self.on_close)
        self.tray_icon = None

    def start_move(self, event):
        self._x = event.x
        self._y = event.y

    def do_move(self, event):
        x = self.master.winfo_pointerx() - self._x
        y = self.master.winfo_pointery() - self._y
        self.master.geometry(f'+{x}+{y}')

    def toggle_fullscreen(self):
        self.fullscreen = not self.fullscreen
        if self.fullscreen:
            self.master.overrideredirect(True)
            center_x = self.master.winfo_x() + self.master.winfo_width() // 2
            center_y = self.master.winfo_y() + self.master.winfo_height() // 2
            for monitor in get_monitors():
                if (monitor.x <= center_x <= monitor.x + monitor.width and
                    monitor.y <= center_y <= monitor.y + monitor.height):
                    screen = monitor
                    break
            else:
                screen = get_monitors()[0]
            self.master.geometry(f"{screen.width}x{screen.height}+{screen.x}+{screen.y}")
        else:
            self.master.overrideredirect(False)
            self.master.geometry(self.last_geometry)

    def toggle_info(self, event=None):
        x, y = self.master.winfo_x(), self.master.winfo_y()
        w, h = self.master.winfo_width(), self.master.winfo_height()
        self.info_visible = not self.info_visible
        if self.info_visible:
            self.hit_label.pack()
            self.time_label.pack()
        else:
            self.hit_label.pack_forget()
            self.time_label.pack_forget()
        self.master.geometry(f"{w}x{h}+{x}+{y}")
        self.last_geometry = self.master.geometry()

    def resize_image(self, event=None):
        width = self.master.winfo_width()
        size = max(40, int(width * 0.8))
        self.image_idle = ImageTk.PhotoImage(self.original_image_idle.resize((size, size)))
        self.image_hit = ImageTk.PhotoImage(self.original_image_hit.resize((size, size)))
        self.muyu_label.config(image=self.image_idle)

    def update_info(self):
        elapsed = int(time.time() - self.start_time)
        self.hit_label.config(text=f"已经积攒了{self.total_hits}功德")
        self.time_label.config(text=f"当前运行时间：{elapsed} 秒")

    def update_time(self):
        if self.info_visible:
            self.update_info()
        self.master.after(1000, self.update_time)

    def on_key_press(self, key):
        self.total_hits += 1
        self.animate_hit()
        if self.info_visible:
            self.update_info()

    def periodic_save(self):
        self.save_cache()
        self.master.after(600000, self.periodic_save)  # 每600000毫秒，即10分钟调用一次

    # def animate_hit(self):
    #     self.muyu_label.config(image=self.image_hit)
    #     self.master.after(150, lambda: self.muyu_label.config(image=self.image_idle))
    def animate_hit(self):
        # 主界面木鱼图像切换
        self.muyu_label.config(image=self.image_hit)
        self.master.after(150, lambda: self.muyu_label.config(image=self.image_idle))

        # 托盘图标同步切换
        if self.tray_icon:
            try:
                # 切换为点击状态的托盘图标
                icon_image = self.original_image_hit.resize((64, 64)).convert("RGBA")
                r, g, b, a = icon_image.split()
                a = a.point(lambda x: 255 if x > 0 else 0)
                icon_image.putalpha(a)
                self.tray_icon.icon = icon_image

                # 0.15 秒后还原图标
                def reset_icon():
                    idle_img = self.original_image_idle.resize((64, 64)).convert("RGBA")
                    r, g, b, a = idle_img.split()
                    a = a.point(lambda x: 255 if x > 0 else 0)
                    idle_img.putalpha(a)
                    self.tray_icon.icon = idle_img

                self.master.after(150, reset_icon)

            except Exception as e:
                print("托盘图标动画切换失败：", e)

    def load_cache(self):
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.total_hits = data.get("total_hits", 0)
                self.total_duration = data.get("total_duration", 0)

    def save_cache(self):
        elapsed = time.time() - self.start_time
        data = {
            "total_hits": self.total_hits,
            "total_duration": self.total_duration + elapsed
        }
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def on_close(self):
        self.save_cache()
        self.hide_to_tray()

    def hide_to_tray(self):
        self.master.withdraw()
        self.setup_tray_icon()

    def show_from_tray(self, icon, item):
        self.master.deiconify()
        self.master.after(0, self.master.lift)
        self.stop_tray_icon()

    def stop_tray_icon(self, *args):
        if self.tray_icon:
            self.tray_icon.stop()
            self.tray_icon = None

    def exit_from_tray(self, icon, item):
        self.save_cache()
        self.stop_tray_icon()
        self.master.quit()

    def tray_tooltip(self):
        elapsed = int(time.time() - self.start_time)
        return f"功德：{self.total_hits} 次\n运行时间：{elapsed} 秒"

    def setup_tray_icon(self):
        try:
            icon_image = self.original_image_idle.resize((64, 64)).convert("RGBA")
            # 去除透明通道中非法值（防止 mask 错误）
            r, g, b, a = icon_image.split()
            a = a.point(lambda x: 255 if x > 0 else 0)  # 创建一个二值化的透明蒙版
            icon_image.putalpha(a)

            menu = TrayMenu(
                TrayMenuItem("显示窗口", self.show_from_tray),
                TrayMenuItem("退出", self.exit_from_tray)
            )

            self.tray_icon = TrayIcon("功德木鱼", icon_image, self.tray_tooltip(), menu)

            def update_tooltip():
                while self.tray_icon:
                    self.tray_icon.title = self.tray_tooltip()
                    time.sleep(1)

            threading.Thread(target=update_tooltip, daemon=True).start()
            threading.Thread(target=self.tray_icon.run, daemon=True).start()

        except Exception as e:
            print("托盘图标创建失败：", e)
            self.master.deiconify()


def run_gui():
    root = tk.Tk()
    root.withdraw()
    root.after(0, root.deiconify)
    app = MuyuApp(root)
    root.mainloop()


if __name__ == "__main__":
    run_gui()

# pyinstaller --noconsole --onefile main.py