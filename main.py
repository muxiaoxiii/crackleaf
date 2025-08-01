import tkinter as tk
from tkinter import filedialog, messagebox
import os
from pdf_unlocker import batch_unlock_files, unlock_pdf
from PyPDF2 import PdfReader
from tkinter.simpledialog import askstring

ACCEPTED_EXTENSIONS = {'.pdf'}

class CrackLeafApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CrackLeaf")
        self.root.geometry("360x420")
        self.root.configure(bg="#fdfdfd")
        self.file_list = []
        self.file_statuses = []

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

        self.unlock_button = tk.Button(self.root, text="开始解锁", command=self.start_unlock)
        self.unlock_button.pack(pady=(20, 10))

        self.file_listbox.bind("<Double-Button-1>", self.on_file_select)
        self.file_listbox.bind("<B1-Motion>", self.on_drag_file)

    def import_file(self):
        filepaths = filedialog.askopenfilenames(filetypes=[("PDF files", "*.pdf")])
        self.handle_files(filepaths)

    def handle_files(self, filepaths):
        self.file_list = []
        self.file_statuses = []

        for path in filepaths:
            ext = os.path.splitext(path)[1].lower()
            if ext not in ACCEPTED_EXTENSIONS:
                messagebox.showerror("错误", f"只能处理pdf文件: {path}")
                continue

            try:
                reader = PdfReader(path)
                if reader.is_encrypted:
                    password = askstring("输入密码", f"{os.path.basename(path)} 受密码保护，请输入密码：", show="*")
                    if not password:
                        continue
                    try:
                        reader.decrypt(password)
                    except Exception:
                        messagebox.showwarning("解密失败", f"{os.path.basename(path)} 密码错误，跳过此文件")
                        continue
                else:
                    password = ""
            except Exception as e:
                messagebox.showerror("读取失败", f"{os.path.basename(path)} 无法读取: {e}")
                continue

            self.file_list.append(path)
            self.file_statuses.append({"password": password, "icon": "🔒"})

        self.update_file_display()

    def update_file_display(self):
        self.file_listbox.delete(0, tk.END)
        for i, path in enumerate(self.file_list):
            icon = self.file_statuses[i]["icon"]
            self.file_listbox.insert(tk.END, f"{icon} {os.path.basename(path)}")

    def setup_drag_and_drop(self):
        self.root.bind("<Button-1>", lambda e: self.import_file())

    def start_unlock(self):
        if not self.file_list:
            messagebox.showwarning("提示", "请先导入PDF文件")
            return

        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        results = []
        for i, filepath in enumerate(self.file_list):
            filename = os.path.basename(filepath)
            output_path = os.path.join(downloads, os.path.splitext(filename)[0] + "_unlocked.pdf")
            password = self.file_statuses[i].get("password", "")
            result = unlock_pdf(filepath, output_path, password)
            results.append(result)

        success = [os.path.basename(r['input_path']) for r in results if r['success']]
        failed = [os.path.basename(r['input_path']) for r in results if not r['success']]
        message = ""
        if success:
            message += f"以下文件解锁成功：\n" + "\n".join(success) + "\n\n"
        if failed:
            message += f"以下文件解锁失败：\n" + "\n".join(failed)
        messagebox.showinfo("解锁结果", message)

        for idx, r in enumerate(results):
            icon = "🔓" if r['success'] else "❌"
            filename = os.path.basename(r['input_path'])
            self.file_statuses[idx]["icon"] = icon
        self.update_file_display()

    def on_file_select(self, event):
        selection = self.file_listbox.curselection()
        if not selection:
            return
        idx = selection[0]
        filepath = self.file_list[idx]
        password = self.file_statuses[idx]["password"]

        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        filename = os.path.basename(filepath)
        output_path = os.path.join(downloads, os.path.splitext(filename)[0] + "_unlocked.pdf")
        result = unlock_pdf(filepath, output_path, password)

        icon = "🔓" if result['success'] else "❌"
        self.file_statuses[idx]["icon"] = icon
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

        msg = f"{restriction}\n" + ("解锁成功" if result['success'] else "解锁失败：" + result.get("reason", "未知错误"))
        messagebox.showinfo("单个文件处理", f"{filename}\n{msg}")

    def on_drag_file(self, event):
        idx = self.file_listbox.nearest(event.y)
        if idx < 0 or idx >= len(self.file_list):
            return

        filepath = self.file_list[idx]
        filename = os.path.basename(filepath)
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        unlocked_path = os.path.join(downloads, os.path.splitext(filename)[0] + "_unlocked.pdf")

        if not os.path.exists(unlocked_path):
            return

        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(unlocked_path)
            self.root.update()
        except Exception:
            pass

if __name__ == "__main__":
    root = tk.Tk()
    app = CrackLeafApp(root)
    root.mainloop()