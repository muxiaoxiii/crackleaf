import tkinter as tk
from tkinter import filedialog, messagebox
import os
from pdf_unlocker import batch_unlock_files, unlock_pdf
from PyPDF2 import PdfReader
from tkinter.simpledialog import askstring
from tkinterdnd2 import TkinterDnD

ACCEPTED_EXTENSIONS = {'.pdf'}

class CrackLeafApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CrackLeaf")
        self.root.geometry("360x420")
        self.root.configure(bg="#fdfdfd")
        self.file_statuses = []  # List of dicts: {'path':..., 'password':..., 'icon':..., 'status':...}
        self.animating = False  # 初始化动画状态，避免首次调用异常
        self.dot_count = 0      # 初始化动画点数计数器

        self.create_widgets()
        self.setup_drag_and_drop()

    def create_widgets(self):
        self.label_title = tk.Label(self.root, text="解除PDF编辑限制", font=("Helvetica", 14), bg="#fdfdfd")
        self.label_title.pack(pady=(30, 10))

        self.label_hint = tk.Label(self.root, text="拖拽文件或者点击导入PDF文件", font=("Helvetica", 10), bg="#fdfdfd")
        self.label_hint.pack(pady=(0, 20))

        self.import_button = tk.Button(self.root, text="导入PDF文件", command=self.import_file)
        self.import_button.pack(pady=(0, 20))

        frame = tk.Frame(self.root)
        frame.pack()

        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.file_listbox = tk.Listbox(frame, height=8, width=40, yscrollcommand=scrollbar.set)
        self.file_listbox.pack(side=tk.LEFT)

        scrollbar.config(command=self.file_listbox.yview)

        self.unlock_button = tk.Button(self.root, text="🔓 开始解锁", command=self.start_unlock)
        self.unlock_button.pack(pady=(20, 10))

        self.file_listbox.bind("<Button-1>", self.on_file_click)

        self.create_animation_label()

    def create_animation_label(self):
        self.animation_label = tk.Label(self.root, text="", font=("Helvetica", 10), bg="#fdfdfd", fg="gray")
        self.animation_label.pack()

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
                password = askstring("输入密码", f"{os.path.basename(path)} 受密码保护，请输入密码：", show="*")
                if not password:
                    return None
                try:
                    reader.decrypt(password)
                except Exception:
                    messagebox.showwarning("解密失败", f"{os.path.basename(path)} 密码错误，跳过此文件")
                    return None
            else:
                password = ""
        except Exception as e:
            messagebox.showerror("读取失败", f"{os.path.basename(path)} 无法读取: {e}")
            return None
        return {"path": path, "password": password, "icon": "🔒", "status": "未解锁"}

    def handle_files(self, filepaths):
        for path in filepaths:
            file_info = self.analyze_file(path)
            if file_info is not None:
                # Avoid duplicates
                if not any(f['path'] == path for f in self.file_statuses):
                    self.file_statuses.append(file_info)
        self.update_file_display()

    def update_file_display(self):
        self.file_listbox.delete(0, tk.END)
        for file_info in self.file_statuses:
            icon = file_info["icon"]
            filename = os.path.basename(file_info["path"])
            self.file_listbox.insert(tk.END, f"{icon} {filename}")

    def setup_drag_and_drop(self):
        # 使用 TkinterDnD.Tk() 替代 tk.Tk() 实例，实现拖拽功能
        # 注册拖拽目标，绑定拖拽事件
        self.root.drop_target_register('*')
        self.root.dnd_bind('<<Drop>>', self.drop_event)

    def drop_event(self, event):
        # 处理拖入的文件路径，防止非路径字符串导致异常
        data = event.data
        try:
            files = self.root.tk.splitlist(data)
        except Exception:
            files = []
        self.handle_files(files)

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
            if result is None:
                result = {'success': False, 'input_path': filepath, 'reason': '未知错误'}
            results.append(result)
        self.unlock_button.config(text="🔓 开始解锁")

        self.stop_animation()

        success = [os.path.basename(r['input_path']) for r in results if r.get('success')]
        failed = [os.path.basename(r['input_path']) for r in results if not r.get('success')]
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
        # Check if click is on icon area (approx first 2 chars)
        # Listbox item text like "🔒 filename"
        # We consider clicks near left side as icon clicks
        bbox = self.file_listbox.bbox(idx)
        if bbox and event.x < bbox[2] * 0.15:
            # Icon clicked, trigger single unlock
            self.single_unlock(idx)

    def single_unlock(self, idx):
        file_info = self.file_statuses[idx]
        filepath = file_info['path']
        password = file_info.get("password", "")

        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        filename = os.path.basename(filepath)
        output_path = os.path.join(downloads, os.path.splitext(filename)[0] + "_unlocked.pdf")
        result = unlock_pdf(filepath, output_path, password)
        if result is None:
            result = {'success': False, 'input_path': filepath, 'reason': '未知错误'}

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

if __name__ == "__main__":
    # 使用 TkinterDnD.Tk() 替代 tk.Tk()，以支持拖拽功能
    root = TkinterDnD.Tk()
    app = CrackLeafApp(root)
    root.mainloop()