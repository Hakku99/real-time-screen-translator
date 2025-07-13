import tkinter as tk
from tkinter import messagebox, ttk
from PIL import ImageGrab, Image, ImageFilter, ImageTk
import pytesseract
import threading
import time
import ctypes
import re
import sys
from deep_translator import GoogleTranslator, exceptions

# --- DPI AWARENESS FIX FOR WINDOWS ---
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# --- IMPORTANT: UPDATE THIS PATH ---
try:
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
except Exception:
    pass

# --- Configuration ---
class Config:
    TESSERACT_CONFIG = '--psm 6'
    UPSCALE_FACTOR = 3
    SHARPNESS_FACTOR = 2.0
    BW_THRESHOLD = 200
    SOURCE_LANGUAGE = 'english'
    TARGET_LANGUAGE = 'chinese (simplified)'

class Style:
    CAPTURE_INTERVAL_MS = 800
    TRANSPARENCY = 0.95
    WINDOW_BG = '#1f2933'
    TITLE_BAR_BG = '#374151'
    TEXT_PANEL_BG = '#111827'
    TEXT_COLOR = '#e5e7eb'
    BUTTON_BG = '#2563eb'
    BUTTON_FG = '#ffffff'
    BUTTON_HOVER = '#1e40af'
    CLOSE_BUTTON_HOVER = '#b91c1c'
    FONT_FAMILY = "Segoe UI"
    FONT_NORMAL = (FONT_FAMILY, 11)
    FONT_BOLD = (FONT_FAMILY, 12, "bold")
    FONT_TITLE = (FONT_FAMILY, 16, "bold")
    FONT_UI = (FONT_FAMILY, 11)
    FONT_TRANSLATION = (FONT_FAMILY, 14)
    FONT_TOOLTIP = (FONT_FAMILY, 9)

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        x, y, _, _ = self.widget.bbox("insert") or (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        self.tooltip_window.wm_attributes("-topmost", True)

        label = tk.Label(
            self.tooltip_window,
            text=self.text,
            justify='left',
            background=Style.WINDOW_BG,
            relief='solid',
            borderwidth=1,
            font=Style.FONT_TOOLTIP,
            fg=Style.TEXT_COLOR,
            padx=8,
            pady=5
        )
        label.pack(ipadx=1)

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
        self.tooltip_window = None

class AppController:
    def __init__(self, root):
        self.root = root
        self.root.withdraw()
        self.translator_window = None
        self.setup_window = SetupWindow(self)

    def start_selection_process(self):
        if self.setup_window and self.setup_window.winfo_exists():
            self.setup_window.withdraw()
        if self.translator_window and self.translator_window.winfo_exists():
            self.translator_window.withdraw()
        SelectionCanvas(self)

    def on_area_selected(self, capture_area):
        if self.setup_window and self.setup_window.winfo_exists():
            self.setup_window.withdraw()
        if self.translator_window and self.translator_window.winfo_exists():
            self.translator_window.destroy()

        self.translator_window = TranslatorWindow(self, capture_area)
        self.translator_window.deiconify()
        self.translator_window.start_capturing()

    def on_selection_cancelled(self):
        if self.translator_window and self.translator_window.winfo_exists():
            self.translator_window.deiconify()
        elif self.setup_window and self.setup_window.winfo_exists():
            self.setup_window.deiconify()

class SetupWindow(tk.Toplevel):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.title("Screen Translator")
        self.geometry("500x250")
        self.resizable(True, True)
        self.config(bg=Style.WINDOW_BG, padx=20, pady=20)
        self.attributes('-topmost', True)

        tk.Label(
            self,
            text="Screen Translator",
            font=Style.FONT_TITLE,
            bg=Style.WINDOW_BG,
            fg=Style.TEXT_COLOR
        ).pack(pady=(0, 10))

        tk.Label(
            self,
            text="Capture and translate text from screen.",
            font=Style.FONT_NORMAL,
            bg=Style.WINDOW_BG,
            fg=Style.TEXT_COLOR
        ).pack(pady=(0, 20))

        tk.Button(
            self,
            text="Start Capture",
            command=self.controller.start_selection_process,
            bg=Style.BUTTON_BG,
            fg='white',
            relief='flat',
            font=Style.FONT_BOLD,
            pady=10,
            activebackground=Style.BUTTON_HOVER,
            activeforeground=Style.BUTTON_FG,
            bd=0
        ).pack(fill="x", pady=(0, 10))

        tk.Button(
            self,
            text="Close",
            command=self.terminate_program,
            bg='#6b7280',
            fg='white',
            relief='flat',
            font=Style.FONT_BOLD,
            pady=8,
            activebackground='#4b5563',
            activeforeground=Style.BUTTON_FG,
            bd=0
        ).pack(fill="x")

    def terminate_program(self):
        sys.exit(0)

class SelectionCanvas:
    def __init__(self, controller):
        self.controller = controller
        self.selection_window = tk.Toplevel()
        self.selection_window.attributes('-fullscreen', True)
        self.selection_window.attributes('-alpha', 0.3)
        self.selection_window.wait_visibility(self.selection_window)

        self.canvas = tk.Canvas(self.selection_window, cursor="cross", bg="gray")
        self.canvas.pack(fill="both", expand=True)

        self.rect, self.start_x, self.start_y = None, None, None
        self.canvas.bind("<ButtonPress-1>", self.on_selection_start)
        self.canvas.bind("<B1-Motion>", self.on_selection_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_selection_end)

    def on_selection_start(self, event):
        self.start_x, self.start_y = event.x, event.y
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y,
            self.start_x, self.start_y,
            outline='red',
            width=2,
            fill="white"
        )

    def on_selection_drag(self, event):
        self.canvas.coords(
            self.rect,
            self.start_x, self.start_y,
            event.x, event.y
        )

    def on_selection_end(self, event):
        x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
        x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)

        self.selection_window.destroy()

        if x2 - x1 > 10 and y2 - y1 > 10:
            self.controller.on_area_selected((x1, y1, x2, y2))
        else:
            messagebox.showwarning("Selection Error", "Selected area was too small.")
            self.controller.on_selection_cancelled()

class TranslatorWindow(tk.Toplevel):
    def __init__(self, controller, capture_area):
        super().__init__()
        self.controller = controller
        self.capture_area = capture_area

        # use native title bar
        self.title("Screen Translator")
        self.geometry("500x400+50+50")
        self.resizable(True, True)
        self.attributes('-alpha', Style.TRANSPARENCY)
        self.attributes('-topmost', True)
        self.config(bg=Style.WINDOW_BG)

        self.protocol("WM_DELETE_WINDOW", self.terminate_program)

        self.is_capturing = False
        self.is_paused = False
        self.last_translated_text = ""
        self.last_processed_image = None
        self.debug_window = None

        self.create_widgets()

    def create_widgets(self):
        # use a grid layout
        self.grid_rowconfigure(0, weight=1)  # translation text expands
        self.grid_columnconfigure(0, weight=1)

        # translation text area
        self.translation_text = tk.Text(
            self,
            wrap=tk.WORD,
            bg=Style.TEXT_PANEL_BG,
            fg=Style.TEXT_COLOR,
            font=Style.FONT_TRANSLATION,
            relief="flat",
            borderwidth=5,
            padx=10,
            pady=10,
            insertbackground=Style.TEXT_COLOR
        )
        self.translation_text.grid(row=0, column=0, sticky="nsew")

        # fixed-height bottom bar
        bottom_bar = tk.Frame(self, bg=Style.WINDOW_BG, height=60)
        bottom_bar.grid(row=1, column=0, sticky="ew")
        bottom_bar.grid_propagate(False)

        # buttons split into two rows
        button_frame1 = tk.Frame(bottom_bar, bg=Style.WINDOW_BG)
        button_frame1.pack(pady=(15,5))

        self.pause_resume_button = self.create_button(button_frame1, "Pause", self.toggle_pause_resume, '#f59e0b')
        self.new_area_button = self.create_button(button_frame1, "New Area", self.select_new_area, Style.BUTTON_BG, state="disabled")
        self.copy_button = self.create_button(button_frame1, "Copy", self.copy_translation, '#22c55e')

        button_frame2 = tk.Frame(bottom_bar, bg=Style.WINDOW_BG)
        button_frame2.pack(pady=(5, 15))

        self.debug_button = self.create_button(button_frame2, "Debug", self.show_ocr_image, '#64748b')
        self.end_button = self.create_button(button_frame2, "End", self.terminate_program, '#ef4444')

        self.add_tooltips()


    def create_button(self, parent, text, command, color, state="normal"):
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            bg=color,
            fg='white',
            relief='flat',
            font=Style.FONT_BOLD,
            width=10,
            pady=4,
            activebackground=Style.BUTTON_HOVER,
            activeforeground=Style.BUTTON_FG,
            state=state
        )
        btn.pack(side="left", padx=5)
        return btn

    def add_tooltips(self):
        ToolTip(self.pause_resume_button, "Pause or Resume screen capture")
        ToolTip(self.new_area_button, "Select a new area on the screen")
        ToolTip(self.copy_button, "Copy translation to clipboard")
        ToolTip(self.debug_button, "Show the last processed image sent to OCR")
        ToolTip(self.end_button, "Terminate the program")

    def start_capturing(self):
        try:
            pytesseract.get_tesseract_version()
        except pytesseract.TesseractNotFoundError:
            messagebox.showerror(
                "Tesseract Not Found",
                "Tesseract is not installed or the path in the script is incorrect."
            )
            self.destroy()
            return

        self.is_capturing = True
        self.capture_thread = threading.Thread(target=self.translation_loop, daemon=True)
        self.capture_thread.start()

    def select_new_area(self):
        self.is_capturing = False
        self.controller.start_selection_process()

    def toggle_pause_resume(self):
        self.is_paused = not self.is_paused
        if self.is_paused:
            self.new_area_button.config(state="normal")
            self.pause_resume_button.config(text="Resume")
        else:
            self.new_area_button.config(state="disabled")
            self.pause_resume_button.config(text="Pause")

    def translation_loop(self):
        while self.is_capturing:
            if self.is_paused:
                time.sleep(0.5)
                continue

            try:
                screenshot = ImageGrab.grab(bbox=self.capture_area)
                width, height = screenshot.size
                img_upscaled = screenshot.resize(
                    (width * Config.UPSCALE_FACTOR, height * Config.UPSCALE_FACTOR),
                    Image.Resampling.LANCZOS
                )
                img_sharpened = img_upscaled.filter(ImageFilter.SHARPEN)
                img_gray = img_sharpened.convert('L')
                img_bw = img_gray.point(lambda p: 0 if p < Config.BW_THRESHOLD else 255)
                self.last_processed_image = img_bw

                extracted_text = pytesseract.image_to_string(
                    img_bw, lang='eng', config=Config.TESSERACT_CONFIG
                ).strip()

                if extracted_text and extracted_text != self.last_translated_text and re.search('[a-zA-Z]', extracted_text):
                    # join OCR lines into one string for better translation context
                    lines = extracted_text.splitlines()

                    paragraphs = []
                    current_para = []

                    for line in lines:
                        if line.strip():
                            current_para.append(line.strip())
                        else:
                            if current_para:
                                paragraphs.append(" ".join(current_para))
                                current_para = []

                    if current_para:
                        paragraphs.append(" ".join(current_para))

                    joined_text = "\n\n".join(paragraphs)

                    self.last_translated_text = extracted_text

                    try:
                        translated_text = GoogleTranslator(
                            source=Config.SOURCE_LANGUAGE,
                            target=Config.TARGET_LANGUAGE
                        ).translate(joined_text)

                        if translated_text:
                            self.after(0, self.update_translation_text, translated_text)

                    except exceptions.NotValidPayload as e:
                        self.after(0, self.update_translation_text, f"Translation failed: {e}")

            except Exception as e:
                error_message = f"Translation Error. Retrying...\nDetails: {str(e)[:100]}"
                self.after(0, self.update_translation_text, error_message)
                time.sleep(2)

            time.sleep(Style.CAPTURE_INTERVAL_MS / 1000.0)

    def update_translation_text(self, text):
        self.translation_text.config(state='normal')
        self.translation_text.delete('1.0', tk.END)
        self.translation_text.insert('1.0', text)
        self.translation_text.config(state='disabled')

    def copy_translation(self):
        text_to_copy = self.translation_text.get('1.0', tk.END).strip()
        if text_to_copy:
            self.clipboard_clear()
            self.clipboard_append(text_to_copy)

    def show_ocr_image(self):
        if not self.last_processed_image:
            messagebox.showinfo("No Image", "No image has been processed yet.")
            return

        if self.debug_window and self.debug_window.winfo_exists():
            self.debug_window.destroy()

        self.debug_window = tk.Toplevel(self)
        self.debug_window.title("OCR Debug Image")
        self.debug_window.attributes('-topmost', True)

        img_tk = ImageTk.PhotoImage(self.last_processed_image)
        label = tk.Label(self.debug_window, image=img_tk)
        label.image = img_tk
        label.pack()

    def start_resize(self, event):
        self.resize_start_x = event.x
        self.resize_start_y = event.y

    def do_resize(self, event):
        if hasattr(self, 'resize_start_x'):
            deltax = event.x - self.resize_start_x
            deltay = event.y - self.resize_start_y
            new_width = self.winfo_width() + deltax
            new_height = self.winfo_height() + deltay
            if new_width > 350 and new_height > 200:
                self.geometry(f"{new_width}x{new_height}")
                self.translation_text.config(wraplength=new_width - 20)
            self.resize_start_x = event.x
            self.resize_start_y = event.y

    def terminate_program(self):
        sys.exit(0)

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Screen Translator")
    app = AppController(root)
    root.mainloop()
