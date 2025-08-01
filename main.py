import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
from pdf_unlocker import batch_unlock_files, unlock_pdf
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError
from tkinter.simpledialog import askstring
from tkinterdnd2 import TkinterDnD

ACCEPTED_EXTENSIONS = {'.pdf'}

class Tooltip:
    def __init__(self, widget):
        self.widget = widget
        self.tipwindow = None
        self.id = None
        self.x = self.y = 0

    def showtip(self, text):
        if self.tipwindow or not text:
            return
        x, y, cx, cy = self.widget.bbox("active")
        x = x + self.widget.winfo_rootx() + 25
        y = y + cy + self.widget.winfo_rooty() + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hidetip(self):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()

class CrackLeafApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CrackLeaf")
        self.root.configure(bg="#fdfdfd")
        self.file_statuses = []  # List of dicts: {'path':..., 'password':..., 'icon':..., 'status':...}
        self.animating = False  # 初始化动画状态，避免首次调用异常
        self.dot_count = 0      # 初始化动画点数计数器
        self.current_drag_path = None  # 当前拖出文件路径

        self.style = ttk.Style()
        self.style.theme_use('default')
        self.style.configure('TButton', font=('Helvetica', 11), background='#f0f0f0', foreground='#333333')
        self.style.map('TButton',
                       background=[('active', '#d9d9d9')],
                       foreground=[('active', '#000000')])
        self.style.configure('Large.TButton', font=('Helvetica', 14, 'bold'), background='#4a90e2', foreground='white')
        self.style.map('Large.TButton',
                       background=[('active', '#357ABD')],
                       foreground=[('active', 'white')])

        self.create_widgets()
        self.setup_drag_and_drop()
        self.setup_file_drag_out()

        self.tooltip = Tooltip(self.file_listbox)
        self.file_listbox.bind("<Motion>", self.on_listbox_motion)
        self.file_listbox.bind("<Leave>", lambda e: self.tooltip.hidetip())

        self.drag_overlay = None

        self.update_ui_state()
        self.update_window_geometry()

    def create_widgets(self):
        self.main_frame = tk.Frame(self.root, bg="#fdfdfd")
        self.main_frame.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)

        # Welcome frame with title, hint and import button
        self.welcome_frame = tk.Frame(self.main_frame, bg="#fdfdfd")
        self.label_title = tk.Label(self.welcome_frame, text="解除PDF编辑限制", font=("Helvetica", 18, "bold"), bg="#fdfdfd")
        self.label_hint = tk.Label(self.welcome_frame, text="拖拽文件或者点击导入PDF文件", font=("Helvetica", 12), bg="#fdfdfd")
        self.import_button = ttk.Button(self.welcome_frame, text="导入PDF文件", command=self.import_file, style='Large.TButton')

        self.label_title.pack(pady=(60, 20))
        self.label_hint.pack(pady=(0, 40))
        self.import_button.pack(ipadx=14, ipady=8)

        # Single file frame (initially hidden)
        self.single_file_frame = tk.Frame(self.main_frame, bg="#fdfdfd")
        self.single_file_label = tk.Label(self.single_file_frame, text="", font=("Helvetica", 14), bg="#fdfdfd")
        self.single_unlock_button = ttk.Button(self.single_file_frame, text="🔓 解锁此文件", command=self.single_unlock_button_clicked, style='Large.TButton')
        self.single_file_label.pack(pady=(20, 10))
        self.single_unlock_button.pack(ipadx=14, ipady=8)

        # File list frame (initially hidden)
        self.file_frame = tk.Frame(self.main_frame, bg="#fdfdfd")

        scrollbar = tk.Scrollbar(self.file_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.file_listbox = tk.Listbox(self.file_frame, height=10, width=50, yscrollcommand=scrollbar.set, activestyle='none', bg="#fdfdfd", relief=tk.FLAT, selectbackground="#cce6ff", highlightthickness=0, borderwidth=0)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar.config(command=self.file_listbox.yview)

        self.unlock_button = ttk.Button(self.main_frame, text="🔓 开始解锁", command=self.start_unlock, style='Large.TButton')
        self.animation_label = tk.Label(self.main_frame, text="", font=("Helvetica", 10), bg="#fdfdfd", fg="gray")

        self.file_listbox.bind("<Button-1>", self.on_file_click)

    def update_ui_state(self):
        count = len(self.file_statuses)
        # Hide all main frames first
        self.welcome_frame.pack_forget()
        self.single_file_frame.pack_forget()
        self.file_frame.pack_forget()
        self.unlock_button.pack_forget()
        self.animation_label.pack_forget()

        if count == 0:
            # Show welcome frame
            self.welcome_frame.pack(expand=True, fill=tk.BOTH)
        elif count == 1:
            # Single file mode
            file_info = self.file_statuses[0]
            filename = os.path.basename(file_info["path"])
            self.single_file_label.config(text=f"{file_info['icon']} {filename}")
            self.single_file_frame.pack(expand=True, fill=tk.BOTH)
        else:
            # Multiple files mode
            self.file_frame.pack(expand=True, fill=tk.BOTH)
            self.unlock_button.pack(pady=(20, 15), ipadx=10, ipady=5)
            self.animation_label.pack()

        self.update_file_display()

    def update_window_geometry(self):
        self.root.update_idletasks()
        count = len(self.file_statuses)
        if count == 0:
            width = 420
            height = 300
        elif count == 1:
            width = 420
            height = 200
        else:
            width = 420
            height = 500
        self.root.geometry(f"{width}x{height}")

    def handle_files(self, filepaths):
        for path in filepaths:
            file_info = self.analyze_file(path)
            if file_info is not None:
                # Avoid duplicates
                if not any(f['path'] == path for f in self.file_statuses):
                    self.file_statuses.append(file_info)
        self.update_file_display()
        self.update_ui_state()
        self.update_window_geometry()

    def update_file_display(self):
        count = len(self.file_statuses)
        if count == 1:
            # Update single file label
            file_info = self.file_statuses[0]
            filename = os.path.basename(file_info["path"])
            self.single_file_label.config(text=f"{file_info['icon']} {filename}")
        elif count > 1:
            self.file_listbox.delete(0, tk.END)
            max_display_len = 40
            for file_info in self.file_statuses:
                icon = file_info["icon"]
                filename = os.path.basename(file_info["path"])
                # Truncate if too long
                if len(filename) > max_display_len:
                    filename = filename[:max_display_len-3] + "..."
                self.file_listbox.insert(tk.END, f"{icon} {filename}")
        # For zero files, no display update needed

    # 以下函数保持不变，无需修改：
    def start_animation(self):
        self.animating = True
        self.dot_count = 0
        self.update_animation()

    def update_animation(self):
        if self.animating:
            dots = "." * (self.dot_count % 4)
            self.animation_label.config(text=f"正在处理{dots}")
            self.dot_count += 1
            self.root.after(500, self.update_animation)

    def stop_animation(self):
        self.animating = False
        self.animation_label.config(text="")

    def import_file(self):
        filepaths = filedialog.askopenfilenames(filetypes=[("PDF files", "*.pdf")])
        self.handle_files(filepaths)

    def analyze_file(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext not in ACCEPTED_EXTENSIONS:
            messagebox.showerror("错误", f"只能处理pdf文件: {path}")
            return None
        try:
            reader = PdfReader(path)
            if reader.is_encrypted:
                # 如果加密，直接标记为加密受限，密码留空，不弹窗
                password = ""
                return {"path": path, "password": password, "icon": "🔒", "status": "加密受限"}
            else:
                password = ""
        except PdfReadError as e:
            # 如果错误信息包含 PyCryptodome，跳过提示
            if "PyCryptodome" in str(e):
                return None
            else:
                # 对于其他 PdfReadError，跳过该文件但不提示
                return None
        except Exception as e:
            messagebox.showerror("读取失败", f"{os.path.basename(path)} 无法读取: {e}")
            return None
        return {"path": path, "password": password, "icon": "🔒", "status": "未解锁"}

    def setup_drag_and_drop(self):
        # 使用 TkinterDnD.Tk() 替代 tk.Tk() 实例，实现拖拽功能
        # 注册拖拽目标，绑定拖拽事件
        self.root.drop_target_register('*')
        self.root.dnd_bind('<<DragEnter>>', self.drag_enter_event)
        self.root.dnd_bind('<<DragLeave>>', self.drag_leave_event)
        self.root.dnd_bind('<<Drop>>', self.drop_event)

    def setup_file_drag_out(self):
        # 绑定拖出事件，支持文件拖出系统
        self.file_listbox.bind('<B1-Motion>', self.on_drag_motion)
        self.file_listbox.bind('<ButtonRelease-1>', self.on_drag_release)
        self.current_drag_path = None

    def drag_enter_event(self, event):
        if self.drag_overlay is None:
            self.drag_overlay = tk.Toplevel(self.root)
            self.drag_overlay.overrideredirect(True)
            self.drag_overlay.attributes('-alpha', 0.5)
            self.drag_overlay.attributes('-topmost', True)
            self.drag_overlay.configure(bg='gray')
            x = self.root.winfo_rootx()
            y = self.root.winfo_rooty()
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            self.drag_overlay.geometry(f"{w}x{h}+{x}+{y}")
            label = tk.Label(self.drag_overlay, text="松开以导入", font=("Helvetica", 20, "bold"), fg="white", bg="gray")
            label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        return "break"

    def drag_leave_event(self, event):
        if self.drag_overlay:
            self.drag_overlay.destroy()
            self.drag_overlay = None
        return "break"

    def drop_event(self, event):
        if self.drag_overlay:
            self.drag_overlay.destroy()
            self.drag_overlay = None
        # 处理拖入的文件路径，防止非路径字符串导致异常
        data = event.data
        try:
            files = self.root.tk.splitlist(data)
        except Exception:
            files = []
        self.handle_files(files)
        return "break"

    def start_unlock(self):
        if not self.file_statuses:
            messagebox.showwarning("提示", "请先导入PDF文件")
            return

        self.start_animation()

        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        results = []
        total = len(self.file_statuses)
        for i, file_info in enumerate(self.file_statuses):
            filepath = file_info['path']
            filename = os.path.basename(filepath)
            output_path = os.path.join(downloads, os.path.splitext(filename)[0] + "_unlocked.pdf")
            password = file_info.get("password", "")
            self.unlock_button.config(text=f"解锁中 {i+1}/{total} ...")
            self.root.update()
            result = unlock_pdf(filepath, output_path, password)
            if result is None or 'success' not in result:
                result = {'success': False, 'input_path': filepath, 'reason': '未知错误'}
            else:
                if 'input_path' not in result:
                    result['input_path'] = filepath
            results.append(result)
        self.unlock_button.config(text="🔓 开始解锁")

        self.stop_animation()

        success = [os.path.basename(r.get('input_path', '未知文件')) for r in results if r.get('success')]
        failed = [os.path.basename(r.get('input_path', '未知文件')) for r in results if not r.get('success')]
        message = ""
        if success:
            message += f"以下文件解锁成功：\n" + "\n".join(success) + "\n\n"
        if failed:
            message += f"以下文件解锁失败：\n" + "\n".join(failed)
            self.log_error(results)
        messagebox.showinfo("解锁结果", message)

        for idx, r in enumerate(results):
            icon = "🔓" if r.get('success') else "❌"
            self.file_statuses[idx]["icon"] = icon
            self.file_statuses[idx]["status"] = "解锁成功" if r.get('success') else "解锁失败"
        self.update_file_display()

    def on_file_click(self, event):
        idx = self.file_listbox.nearest(event.y)
        if idx < 0 or idx >= len(self.file_statuses):
            return
        # 记录当前点击文件路径，供拖出使用
        self.current_drag_path = self.file_statuses[idx]['path']
        # Check if click is on icon area (approx first 2 chars)
        # Listbox item text like "🔒 filename"
        # We consider clicks near left side as icon clicks
        bbox = self.file_listbox.bbox(idx)
        if bbox and event.x < bbox[2] * 0.15:
            # Icon clicked, trigger single unlock
            self.single_unlock(idx)

    def on_drag_motion(self, event):
        if self.current_drag_path and os.path.exists(self.current_drag_path):
            try:
                # 调用tkdnd拖出接口，提供文件路径
                self.root.tk.call('tkdnd::drag', 'source', self.file_listbox._w, event.x_root, event.y_root, '-types', 'text/uri-list', '-data', self.current_drag_path)
            except Exception:
                pass

    def on_drag_release(self, event):
        self.current_drag_path = None

    def single_unlock(self, idx):
        file_info = self.file_statuses[idx]
        filepath = file_info['path']
        password = file_info.get("password", "")

        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        filename = os.path.basename(filepath)
        output_path = os.path.join(downloads, os.path.splitext(filename)[0] + "_unlocked.pdf")
        result = unlock_pdf(filepath, output_path, password)
        if result is None or 'success' not in result:
            result = {'success': False, 'input_path': filepath, 'reason': '未知错误'}
        else:
            if 'input_path' not in result:
                result['input_path'] = filepath

        icon = "🔓" if result.get('success') else "❌"
        file_info["icon"] = icon
        file_info["status"] = "解锁成功" if result.get('success') else "解锁失败"
        self.update_file_display()

        try:
            reader = PdfReader(filepath)
            if reader.is_encrypted:
                restriction = "加密保护（需密码）"
            elif "/P" in reader.trailer["/Root"].get("/Perms", {}):
                restriction = "编辑受限"
            else:
                restriction = "未发现限制"
        except:
            restriction = "限制未知"

        msg = f"{restriction}\n" + ("解锁成功" if result.get('success') else "解锁失败：" + result.get("reason", "未知错误"))
        messagebox.showinfo("单个文件处理", f"{filename}\n{msg}")

    def log_error(self, results):
        log_path = os.path.join(os.path.expanduser("~"), "crackleaf_unlock_errors.log")
        with open(log_path, "a", encoding="utf-8") as f:
            for r in results:
                if not r.get('success'):
                    f.write(f"{r.get('input_path', '未知文件')}: {r.get('reason', '未知错误')}\n")

    def on_listbox_motion(self, event):
        idx = self.file_listbox.nearest(event.y)
        if idx < 0 or idx >= len(self.file_statuses):
            self.tooltip.hidetip()
            return
        # Show tooltip with status
        status = self.file_statuses[idx].get("status", "")
        self.file_listbox.selection_clear(0, tk.END)
        self.file_listbox.selection_set(idx)
        self.tooltip.showtip(status)

    def single_unlock_button_clicked(self):
        if len(self.file_statuses) == 1:
            self.single_unlock(0)

if __name__ == "__main__":
    # 使用 TkinterDnD.Tk() 替代 tk.Tk()，以支持拖拽功能
    root = TkinterDnD.Tk()
    app = CrackLeafApp(root)
    root.mainloop()