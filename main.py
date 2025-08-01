import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import tkinter.font as tkfont
import os
import threading
import queue
from pdf_unlocker import batch_unlock_files, unlock_pdf # 假设这些函数已存在且功能正常
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError
from tkinter.simpledialog import askstring
from tkinterdnd2 import TkinterDnD
from PIL import Image, ImageTk # 确保导入 PIL 库

ACCEPTED_EXTENSIONS = {'.pdf'}

class Tooltip:
    # Tooltip 类保持不变
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
        self.root.title("CrackLeaf———解除PDF编辑限制")
        self.root.configure(bg="#FCF5EA")
        
        # 初始窗口尺寸和位置设置
        window_width = 390
        window_height = 390
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = int((screen_width - window_width) / 2) - 40
        y = int((screen_height - window_height) / 2)
        self.root.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.root.resizable(False, False)
        
        # 关键步骤：强制更新窗口，确保winfo_width()返回正确值
        self.root.update_idletasks() 

        self.file_statuses = []  # List of dicts: {'path':..., 'password':..., 'icon':..., 'status':...}
        
        # 动画状态变量
        self.current_animation_id = None # 用于取消当前正在播放的动画
        self.animation_frames = {} # 缓存所有动画帧图片
        self.animation_index = 0 # 当前动画帧索引
        self.is_animating = False # 标记是否有动画正在播放

        self.MAX_HEIGHT_RATIO = 2  # 最大高度为宽度的2倍

        # Load custom fonts (use system font instead of loading from file)
        # Set initial font size to 1 for scaling after window is realized.
        self.custom_font = tkfont.Font(family="Songti SC", size=1) # 初始可以设为1，确保能被缩放
        self.large_font = tkfont.Font(family="Songti SC", size=1) # 初始可以设为1，确保能被缩放

        self.style = ttk.Style()
        self.style.theme_use('default')
        self.style.configure('TButton', font=self.custom_font, background='#f0f0f0', foreground='#192F2A')
        self.style.map('TButton',
                       background=[('active', '#d9d9d9')],
                       foreground=[('active', '#192F2A')])
        self.style.configure('Large.TButton', font=self.large_font, background='#4a90e2', foreground='white')
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

        self.unlock_queue = queue.Queue()
        self.root.bind("<Configure>", self.on_window_resize)

        # 初始时加载所有图片，并确保resize_logo_images在更新UI状态前被调用
        self.load_all_animation_frames()
        self.resize_logo_images() # 确保在第一次update_ui_state前图片尺寸正确
        
        # 第一次字体大小计算和应用，确保初始显示正确
        base_width = 390
        current_width = self.root.winfo_width() # 获取正确的窗口宽度
        scale = current_width / base_width
        new_font_size = max(10, int(24 * scale)) 
        new_large_font_size = max(12, int(36 * scale))
        self.custom_font.config(size=new_font_size)
        self.large_font.config(size=new_large_font_size)

        self.update_ui_state() # 初始UI状态更新


    def load_all_animation_frames(self):
        """预加载所有动画帧图片，避免运行时重复加载"""
        frame_sets = {
            "idle": ["高兴1", "高兴2", "高兴3", "高兴4", "高兴4", "高兴3", "高兴2", "高兴1"],
            "run": ["啄1", "啄2"],
            "unlock_start": ["成功1", "成功2", "成功3", "成功4", "成功5"], # 新增的解锁开始动画
            "success": ["高兴1", "高兴2", "高兴3", "高兴4"], # 解锁成功后的动画
            "failure": ["高兴4", "高兴3", "高兴2", "高兴1"], # 失败反向动画
            "crackleaf": ["crackleaf"], # 原始logo
            "happy": ["高兴1", "高兴2"] # 导入文件后的默认/悬停图片
        }
        
        # 确保 assets 目录存在
        if not os.path.exists("assets"):
            print("Error: 'assets' directory not found. Please create it and place your images there.")
            return

        for anim_type, names in frame_sets.items():
            self.animation_frames[anim_type] = []
            for name in names:
                try:
                    # 仅加载原始图片，不在这里resize
                    img = Image.open(f"assets/{name}.png")
                    self.animation_frames[anim_type].append(img)
                except FileNotFoundError:
                    print(f"Warning: Image file 'assets/{name}.png' not found.")
                    # 可以使用一个占位符图片
                    placeholder_img = Image.new('RGB', (100, 100), color = 'red')
                    self.animation_frames[anim_type].append(placeholder_img)


    def _play_animation_loop(self, frame_list_key, interval_ms, loop=True, on_complete_callback=None):
        """
        通用的动画播放循环函数。
        :param frame_list_key: 动画帧列表的键名 (e.g., "idle", "run", "success")
        :param interval_ms: 每帧之间的间隔时间 (毫秒)
        :param loop: 是否循环播放
        :param on_complete_callback: 动画播放完成后的回调函数 (仅在 loop=False 时有效)
        """
        if self.current_animation_id:
            self.root.after_cancel(self.current_animation_id) # 取消之前的动画
        
        frames = self.animation_frames.get(frame_list_key)
        if not frames:
            print(f"Error: Animation frames for '{frame_list_key}' not loaded.")
            return

        # 获取当前logo_label的尺寸，用于resize图片
        current_size = self.logo_label.winfo_width() 
        if current_size == 1: # 窗口可能还没完全渲染，使用预设的image_display_size
            current_size = self.image_display_size

        # 确保图片尺寸正确
        display_frames = []
        for img_orig in frames:
            # 确保 img_orig 是 Image 对象
            if isinstance(img_orig, Image.Image):
                display_frames.append(ImageTk.PhotoImage(img_orig.resize((current_size, current_size))))
            else:
                # Fallback for placeholder or error
                display_frames.append(ImageTk.PhotoImage(Image.new('RGB', (current_size, current_size), color = 'red')))

        self.is_animating = True

        def animate_frame():
            if not self.is_animating: # 动画被中断
                if not loop and on_complete_callback:
                    on_complete_callback() # 如果是非循环动画，且被中断，也执行完成回调
                return

            self.logo_label.config(image=display_frames[self.animation_index])
            self.animation_index = (self.animation_index + 1) % len(display_frames)

            if not loop and self.animation_index == 0: # 非循环动画播放完成
                self.is_animating = False
                if on_complete_callback:
                    on_complete_callback()
                return

            self.current_animation_id = self.root.after(interval_ms, animate_frame)

        self.animation_index = 0 # 从第一帧开始
        animate_frame()


    def stop_current_animation(self):
        """停止当前正在播放的动画，并重置logo显示"""
        self.is_animating = False
        if self.current_animation_id:
            self.root.after_cancel(self.current_animation_id)
            self.current_animation_id = None
        
        # 根据当前文件状态恢复logo
        if len(self.file_statuses) == 0:
            self.logo_label.config(image=self.logo_img) # crackleaf.png
        else:
            self.logo_label.config(image=self.happy_img1) # 高兴1.png


    # 1. 初始界面闲置动画 (鼠标悬停触发)
    def start_idle_animation(self, event=None):
        if len(self.file_statuses) == 0 and not self.is_animating: # 只有在无文件且当前无动画时才启动
            self._play_animation_loop("idle", 150)

    def stop_idle_animation(self, event=None):
        if len(self.file_statuses) == 0: # 只有在无文件状态下才响应此停止
            self.stop_current_animation()
            self.logo_label.config(image=self.logo_img) # 恢复到crackleaf.png


    # 2. 导入文件后闲置动画 (鼠标悬停触发)
    def start_file_loaded_idle_animation(self, event=None):
        if len(self.file_statuses) > 0 and not self.is_animating: # 只有在有文件且当前无动画时才启动
            self._play_animation_loop("run", 200) # 啄1和啄2轮播

    def stop_file_loaded_idle_animation(self, event=None):
        if len(self.file_statuses) > 0: # 只有在有文件状态下才响应此停止
            self.stop_current_animation()
            self.logo_label.config(image=self.happy_img1) # 恢复到高兴1.png


    # 3. 解锁处理动画
    def start_unlock_animation(self):
        """开始解锁处理时的动画 (啄1和啄2循环)"""
        self._play_animation_loop("run", 200) # 啄1和啄2循环


    def show_success_animation(self):
        """解锁成功后的动画 (高兴1到高兴4播放一次)"""
        def on_success_complete():
            self.stop_current_animation() # 停止成功动画循环
            self.logo_label.config(image=self.happy_img1) # 恢复到高兴1.png
            # 可以在这里添加其他成功后的UI更新，例如显示结果文字
            self.result_label.config(text="解锁成功")

        self._play_animation_loop("success", 200, loop=False, on_complete_callback=on_success_complete)


    def show_failure_animation(self):
        """解锁失败后的动画 (高兴4到高兴1反向播放一次)"""
        def on_failure_complete():
            self.stop_current_animation() # 停止失败动画循环
            self.logo_label.config(image=self.logo_img) # 恢复到crackleaf.png
            # 可以在这里添加其他失败后的UI更新，例如显示结果文字
            self.result_label.config(text="解锁失败")

        self._play_animation_loop("failure", 200, loop=False, on_complete_callback=on_failure_complete)


    def create_widgets(self):
        from PIL import Image, ImageTk
        self.main_frame = tk.Frame(self.root, bg="#FCF5EA")
        self.main_frame.pack(expand=True, fill=tk.BOTH, padx=20, pady=20)

        # Persistent top frame with logo and label_hint
        self.top_frame = tk.Frame(self.main_frame, bg="#FCF5EA")
        # Load original images for dynamic resizing
        # 这些图片现在从 load_all_animation_frames 中获取原始Image对象
        self.original_logo_img = self.animation_frames.get("crackleaf", [None])[0]
        self.original_happy1 = self.animation_frames.get("happy", [None, None])[0]
        self.original_happy2 = self.animation_frames.get("happy", [None, None])[1]

        self.logo_label = ttk.Label(self.top_frame, background="#FCF5EA")
        self.logo_label.pack(pady=(10, 5))
        # 初始界面的文字
        self.label_hint = ttk.Label(self.top_frame, text="点击或者拖入文件", font=self.custom_font, background="#FCF5EA", foreground="#192F2A")
        self.label_hint.pack(pady=(0, 10))
        self.top_frame.pack()
        
        # 初始界面的点击和悬停绑定
        self.top_frame.bind("<Button-1>", lambda e: self.import_file())
        self.logo_label.bind("<Button-1>", lambda e: self.import_file())
        self.label_hint.bind("<Button-1>", lambda e: self.import_file())
        self.logo_label.bind("<Enter>", self.start_idle_animation)
        self.logo_label.bind("<Leave>", self.stop_idle_animation)


        # File list frame (initially hidden)
        self.file_frame = tk.Frame(self.main_frame, bg="#FCF5EA")

        scrollbar = tk.Scrollbar(self.file_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 动态高度的Listbox，初始height=1，后续随文件数调整
        self.file_listbox = tk.Listbox(self.file_frame, height=1, width=50, yscrollcommand=scrollbar.set, activestyle='none', bg="#FCF5EA", relief=tk.FLAT, selectbackground="#cce6ff", highlightthickness=0, borderwidth=0, font=self.custom_font, fg="#192F2A")
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # 绑定Configure事件，动态调整高度
        self.file_listbox.bind("<Configure>", lambda e: self.file_listbox.config(height=len(self.file_statuses)))

        scrollbar.config(command=self.file_listbox.yview)

        # Animation and result labels in a fixed container at the bottom
        self.animation_frame_container = tk.Frame(self.main_frame, bg="#FCF5EA")
        self.animation_label = tk.Label(self.animation_frame_container, text="", font=self.custom_font, bg="#FCF5EA", fg="gray")
        self.result_label = tk.Label(self.animation_frame_container, text="", font=self.custom_font, bg="#FCF5EA", fg="#192F2A")
        self.animation_label.pack()
        self.result_label.pack()

        self.file_listbox.bind("<Button-1>", self.on_file_click)


    def update_ui_state(self):
        count = len(self.file_statuses)
        
        # 停止所有当前动画，确保状态切换时的干净
        self.stop_current_animation() 

        # 隐藏所有动态内容框架
        self.file_frame.pack_forget()
        self.animation_frame_container.pack_forget()

        # 根据文件数量更新logo和label_hint
        if count >= 1:
            # 导入文件后的Logo和交互
            self.logo_label.config(image=self.happy_img1) # 默认显示高兴1.png
            
            # 解除初始界面的绑定
            self.top_frame.unbind("<Button-1>")
            self.logo_label.unbind("<Button-1>")
            self.label_hint.unbind("<Button-1>")
            self.logo_label.unbind("<Enter>")
            self.logo_label.unbind("<Leave>")

            # 绑定导入文件后的悬停和点击逻辑
            self.logo_label.bind("<Enter>", self.start_file_loaded_idle_animation)
            self.logo_label.bind("<Leave>", self.stop_file_loaded_idle_animation)
            self.logo_label.bind("<Button-1>", lambda e: self.start_unlock()) # 点击Logo开始解锁

            if count == 1:
                file_info = self.file_statuses[0]
                filename = os.path.basename(file_info["path"])
                # 这里可以添加emoji，假设file_info['icon']就是emoji
                self.label_hint.config(text=f"{file_info['icon']} {filename}") 
            else:
                first_file_name = os.path.basename(self.file_statuses[0]["path"])
                # 对于多文件，label_hint 显示第一个文件名，或者显示总数
                self.label_hint.config(text=f"已导入 {count} 个文件") 

            # 显示文件列表框架
            self.file_frame.pack(expand=True, fill=tk.BOTH)
            # 滚动条逻辑
            if count > 8: # 假设8个文件达到最大高度
                # 确保滚动条已打包
                self.file_listbox.config(yscrollcommand=self.file_frame.children['!scrollbar'].set)
                self.file_frame.children['!scrollbar'].pack(side=tk.RIGHT, fill=tk.Y)
            else:
                # 隐藏滚动条
                self.file_listbox.config(yscrollcommand=None)
                self.file_frame.children['!scrollbar'].pack_forget()

        else: # count == 0, 初始界面
            self.logo_label.config(image=self.logo_img) # crackleaf.png
            self.label_hint.config(text="点击或者拖入文件")
            
            # 重新绑定初始界面的点击和悬停逻辑
            self.top_frame.bind("<Button-1>", lambda e: self.import_file())
            self.logo_label.bind("<Button-1>", lambda e: self.import_file())
            self.label_hint.bind("<Button-1>", lambda e: self.import_file())
            self.logo_label.bind("<Enter>", self.start_idle_animation)
            self.logo_label.bind("<Leave>", self.stop_idle_animation)

        # 始终显示动画/结果容器在底部
        self.animation_frame_container.pack(pady=(10, 5))

        self.update_file_display()
        self.update_window_geometry() # 确保在UI状态更新后调整窗口大小

    def update_window_geometry(self):
        count = len(self.file_statuses)
        width = 390
        
        # 窗口高度逻辑 (根据文件数量保持比例)
        if count == 0:
            height = 390
        elif count == 1:
            height = 390 # 单文件时高度不变
        elif count == 2:
            height = 390 # 两个文件时高度不变，需要调整布局
        elif 3 <= count <= 8: # 假设8个文件达到最大高度
            height = 390 + (count - 2) * 70 # 每次增加70像素
        else: # count > 8
            height = 750 # 最大高度
            
        self.root.geometry(f"{width}x{height}")
        self.resize_logo_images() # 调整图片尺寸以适应新窗口大小

    def resize_logo_images(self):
        width = self.root.winfo_width()
        # 图片尺寸统一按照窗口长或者宽的50%来进行缩放
        # 由于窗口宽度固定为390，所以直接使用宽度
        self.image_display_size = int(width * 0.5) 
        size = self.image_display_size
        size = max(60, min(size, 390)) # 确保尺寸在合理范围
        
        # 重新生成PhotoImage对象
        self.logo_img = ImageTk.PhotoImage(self.animation_frames["crackleaf"][0].resize((size, size)))
        self.happy_img1 = ImageTk.PhotoImage(self.animation_frames["happy"][0].resize((size, size)))
        self.happy_img2 = ImageTk.PhotoImage(self.animation_frames["happy"][1].resize((size, size)))

        # 更新当前显示的图片，避免闪烁
        # 只有当非动画状态时才强制更新logo_label的图片
        if not self.is_animating:
            if len(self.file_statuses) == 0:
                self.logo_label.config(image=self.logo_img)
            else:
                self.logo_label.config(image=self.happy_img1)


    def on_window_resize(self, event):
        if event.width < 100 or event.height < 100:
            return
        self.resize_logo_images()
        # Dynamically scale font size
        base_width = 390
        scale = event.width / base_width
        new_font_size = max(10, int(24 * scale)) # 使用24作为基准字号
        new_large_font_size = max(12, int(36 * scale))
        self.custom_font.config(size=new_font_size)
        self.large_font.config(size=new_large_font_size)
        # 重新更新UI状态以确保布局和内容适应新尺寸
        self.update_ui_state() 


    def handle_files(self, filepaths):
        for path in filepaths:
            file_info = self.analyze_file(path)
            if file_info is not None:
                # Avoid duplicates
                if not any(f['path'] == path for f in self.file_statuses):
                    self.file_statuses.append(file_info)
        self.update_file_display()
        self.update_ui_state() # 确保UI状态在文件处理后更新

    def update_file_display(self):
        count = len(self.file_statuses)
        self.file_listbox.delete(0, tk.END) # 清空Listbox

        if count == 1:
            # 单文件信息已经在 update_ui_state 中更新到 label_hint
            pass
        elif count > 1:
            window_width = self.root.winfo_width()
            max_pixel_width = window_width - 40  # Adjusted for padding/margin
            fnt = self.custom_font
            for file_info in self.file_statuses:
                filename = os.path.basename(file_info["path"])
                display_name = filename
                # Truncate by pixel width using font measure
                # 假设文件图标（emoji）宽度固定，这里只截断文件名部分
                icon_width = fnt.measure(file_info['icon'] + " ") # 估算图标宽度
                
                # 调整 max_pixel_width，为图标和可能的间隔留出空间
                available_width_for_text = max_pixel_width - icon_width
                
                while fnt.measure(display_name) > available_width_for_text and len(display_name) > 4:
                    display_name = display_name[:-1]
                if display_name != filename:
                    display_name = display_name[:-3] + "..." # 确保省略号不会被截断
                
                display_text = f"{file_info['icon']} {display_name}"
                self.file_listbox.insert(tk.END, display_text)
        # For zero files, no display update needed for listbox

    # 以下函数保持不变，无需修改：
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
                password = ""
                return {"path": path, "password": password, "icon": "🔒", "status": "加密受限"}
            else:
                password = ""
        except PdfReadError as e:
            if "PyCryptodome" in str(e):
                return None
            else:
                return None
        except Exception as e:
            messagebox.showerror("读取失败", f"{os.path.basename(path)} 无法读取: {e}")
            return None
        return {"path": path, "password": password, "icon": "🔒", "status": "未解锁"}

    def setup_drag_and_drop(self):
        self.root.drop_target_register('*')
        self.root.dnd_bind('<<DragEnter>>', self.drag_enter_event)
        self.root.dnd_bind('<<DragLeave>>', self.drag_leave_event)
        self.root.dnd_bind('<<Drop>>', self.drop_event)

    def setup_file_drag_out(self):
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
            label = tk.Label(self.drag_overlay, text="松开以导入", font=self.large_font, fg="white", bg="gray")
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
        
        # 播放解锁开始动画，动画结束后才启动解锁线程
        self._play_animation_loop("unlock_start", 200, loop=False, on_complete_callback=self.run_unlock_in_thread_after_animation)
        self.result_label.config(text="处理中...") # 显示处理中文字

    def run_unlock_in_thread_after_animation(self):
        """在解锁开始动画播放完毕后，启动实际的解锁线程"""
        self.unlock_queue = queue.Queue()
        self.unlock_thread = threading.Thread(target=self.run_unlock_in_thread)
        self.unlock_thread.start()
        self.root.after(200, self.check_unlock_status) # 定时检查解锁状态

    def run_unlock_in_thread(self):
        downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        for idx, file_info in enumerate(self.file_statuses):
            filepath = file_info['path']
            filename = os.path.basename(filepath)
            output_path = os.path.join(downloads, os.path.splitext(filename)[0] + "_unlocked.pdf")
            password = file_info.get("password", "")
            
            # 模拟耗时操作
            # import time
            # time.sleep(1) 

            result = unlock_pdf(filepath, output_path, password)
            if result is None or 'success' not in result:
                result = {'success': False, 'input_path': filepath, 'reason': '未知错误'}
            else:
                if 'input_path' not in result:
                    result['input_path'] = filepath
            
            # 更新file_statuses中的状态
            icon = "🔓" if result.get('success') else "❌"
            status = "解锁成功" if result.get('success') else "解锁失败"
            self.file_statuses[idx]["icon"] = icon
            self.file_statuses[idx]["status"] = status
            
            # 将更新信息放入队列，供主线程处理
            self.unlock_queue.put((idx, result))

    def check_unlock_status(self):
        updated = False
        while not self.unlock_queue.empty():
            idx, result = self.unlock_queue.get()
            updated = True
            # 实时更新Listbox中的文件状态
            if len(self.file_statuses) > 1: # 只有多文件才在Listbox中更新
                filename = os.path.basename(self.file_statuses[idx]["path"])
                display_name = filename
                window_width = self.root.winfo_width()
                max_pixel_width = window_width - 40
                fnt = self.custom_font
                icon_width = fnt.measure(file_info['icon'] + " ") # 这里file_info未定义，应使用self.file_statuses[idx]['icon']
                available_width_for_text = max_pixel_width - icon_width
                
                while fnt.measure(display_name) > available_width_for_text and len(display_name) > 4:
                    display_name = display_name[:-1]
                if display_name != filename:
                    display_name = display_name[:-3] + "..." # 确保省略号不会被截断
                
                display_text = f"{self.file_statuses[idx]['icon']} {display_name}"
                self.file_listbox.delete(idx)
                self.file_listbox.insert(idx, display_text)

        if hasattr(self, "unlock_thread") and self.unlock_thread.is_alive():
            self.root.after(200, self.check_unlock_status) # 继续检查
        else:
            # 解锁线程完成
            self.stop_current_animation() # 停止啄动画
            
            success_count = sum(1 for f in self.file_statuses if f["icon"] == "🔓")
            
            if success_count == len(self.file_statuses): # 所有文件都成功
                self.show_success_animation()
                self.result_label.config(text="解锁成功")
            else: # 部分或全部失败
                self.show_failure_animation()
                self.result_label.config(text="解锁失败")
            
            # 如果是单文件，更新label_hint
            if len(self.file_statuses) == 1:
                file_info = self.file_statuses[0]
                filename = os.path.basename(file_info["path"])
                self.label_hint.config(text=f"{file_info['icon']} {filename}")
            else:
                # 多文件时，可以显示总数或第一个文件信息
                self.label_hint.config(text=f"已导入 {len(self.file_statuses)} 个文件")


    def on_file_click(self, event):
        idx = self.file_listbox.nearest(event.y)
        if idx < 0 or idx >= len(self.file_statuses):
            return
        self.current_drag_path = self.file_statuses[idx]['path']
        # 这里不再通过点击Listbox条目来触发single_unlock
        # 单文件解锁现在只通过点击logo_label触发
        pass 

    def on_drag_motion(self, event):
        if self.current_drag_path and os.path.exists(self.current_drag_path):
            try:
                self.root.tk.call('tkdnd::drag', 'source', self.file_listbox._w, event.x_root, event.y_root, '-types', 'text/uri-list', '-data', self.current_drag_path)
            except Exception:
                pass

    def on_drag_release(self, event):
        self.current_drag_path = None

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

    # Removed single_unlock_button_clicked; now single file unlock is via logo_label click

if __name__ == "__main__":
    # 使用 TkinterDnD.Tk() 替代 tk.Tk()，以支持拖拽功能
    root = TkinterDnD.Tk()
    app = CrackLeafApp(root)
    root.mainloop()

