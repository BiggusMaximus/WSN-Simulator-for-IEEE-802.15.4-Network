import customtkinter as ctk
from tkinter import Canvas, messagebox
from PIL import Image, ImageTk

class ResponsiveImageApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("WSN Simulator")
        self.attributes('-fullscreen', False)

        self.screen_width = self.winfo_screenwidth()
        self.screen_height = self.winfo_screenheight()

        self.canvas = Canvas(
            self, width=self.screen_width, height=self.screen_height,
            highlightthickness=0, bg="black"
        )
        self.canvas.pack(fill="both", expand=True)

        self.current_page = "main"
        self.canvas.bind("<Configure>", self.on_resize)

        try:
            self.original_image = Image.open("./assets/image.png")
        except FileNotFoundError:
            self.original_image = None
        
        self.bind("<Escape>", lambda e: self.confirm_quit())
        
    def on_resize(self, event):
        if self.current_page == "main":
            self.main_page(event)
        elif self.current_page == "page1":
            self.page_one(event)
        elif self.current_page == "page2":
            self.page_two(event)

    def show_page(self, page_name):
        self.current_page = page_name
        # Trigger a redraw with current size
        self.on_resize(
            type("Event", (object,), {
                "width": self.canvas.winfo_width(),
                "height": self.canvas.winfo_height()
            })
        )

    def main_page(self, event):
        self.canvas.delete("all")
        width, height = event.width, event.height

        # Image background
        if self.original_image:
            resized = self.original_image.resize((width, height), Image.Resampling.LANCZOS)
            self.bg_photo = ImageTk.PhotoImage(resized)
            self.canvas.create_image(0, 0, anchor="nw", image=self.bg_photo)
            self.canvas.image = self.bg_photo

        description = "WSN Simulator for IEEE 802.15.4 \n Beaconless Network"
        developer = "Annastya Bagas Dewantara"

        self.canvas.create_text(
            width * 0.75, height // 2 - 60,
            text=description, font=("Helvetica", 32, "bold"), fill="black", justify="center"
        )
        self.canvas.create_text(
            width * 0.75, height // 2 + 20,
            text=developer, font=("Helvetica", 22), fill="gray"
        )

        # ----- Buttons -----
        btn_y = height // 2 + 80
        btn1_x = width * 0.75 - 110
        btn2_x = width * 0.75 + 110

        button_style = {
            "fg_color": "#1f538d", "hover_color": "#14375e",
            "text_color": "white", "corner_radius": 8,
            "width": 200, "height": 40
        }

        self.btn_page1 = ctk.CTkButton(
            self, text="📊 Page 1",
            command=lambda: self.show_page("page1"),
            **button_style
        )
        self.btn_page2 = ctk.CTkButton(
            self, text="📈 Page 2",
            command=lambda: self.show_page("page2"),
            **button_style
        )
        self.canvas.create_window(btn1_x, btn_y, window=self.btn_page1)
        self.canvas.create_window(btn2_x, btn_y, window=self.btn_page2)

        # ----- Citation box (moved lower to avoid overlap) -----
        center_x = width * 0.75
        center_y = height // 2 + 50
        rect_y1 = center_y + 140          # original +80 offset
        rect_width, rect_height = 650, 200
        rect_x1 = center_x - rect_width // 2
        rect_x2 = center_x + rect_width // 2
        rect_y2 = rect_y1 + rect_height

        self.canvas.create_rectangle(
            rect_x1, rect_y1, rect_x2, rect_y2,
            fill="white", outline="black", width=1
        )
        self.canvas.create_text(
            center_x, rect_y1 - 12,
            text="📄 Cite this work", font=("Helvetica", 14, "bold"), fill="black", anchor="s"
        )
        bibtex_text = (
            "@article{yourname2024simulation,\n"
            "  author    = {Your Name and Co-author Name},\n"
            "  title     = {A Novel Simulation Framework for X},\n"
            "  journal   = {Journal of Computational Physics},\n"
            "  year      = {2024},\n"
            "  volume    = {500},\n"
            "  pages     = {123--145},\n"
            "  doi       = {10.1234/jcp.2024.12345}\n"
            "}"
        )
        self.canvas.create_text(
            center_x, rect_y1 + rect_height // 2,
            text=bibtex_text, font=("Courier", 12), fill="black",
            justify="left", anchor="center"
        )

    def page_one(self, event):
        self.canvas.delete("all")
        width, height = event.width, event.height
        self.canvas.create_rectangle(0, 0, width, height, fill="#2b2b2b", outline="")
        self.canvas.create_text(
            width//2, height//2 - 50,
            text="📊 Page 1 – Simulation Results",
            font=("Helvetica", 28, "bold"), fill="white"
        )
        back_btn = ctk.CTkButton(
            self, text="⬅ Back to Main",
            command=lambda: self.show_page("main"),
            fg_color="#555", hover_color="#333",
            corner_radius=8, width=160, height=40
        )
        self.canvas.create_window(width//2, height//2 + 50, window=back_btn)

    def page_two(self, event):
        self.canvas.delete("all")
        width, height = event.width, event.height
        self.canvas.create_rectangle(0, 0, width, height, fill="#1e1e1e", outline="")
        self.canvas.create_text(
            width//2, height//2 - 50,
            text="📈 Page 2 – Network Statistics",
            font=("Helvetica", 28, "bold"), fill="white"
        )
        back_btn = ctk.CTkButton(
            self, text="⬅ Back to Main",
            command=lambda: self.show_page("main"),
            fg_color="#555", hover_color="#333",
            corner_radius=8, width=160, height=40
        )
        self.canvas.create_window(width//2, height//2 + 50, window=back_btn)

    def confirm_quit(self):
        if messagebox.askyesno("Quit", "Are you sure you want to quit?"):
            self.destroy()

if __name__ == "__main__":
    app = ResponsiveImageApp()
    app.mainloop()