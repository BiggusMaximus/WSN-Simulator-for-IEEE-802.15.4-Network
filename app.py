"""
app.py
======
Main entry-point for the WSN Simulator GUI.

Run from inside the WSN project folder:
    python app.py

The app uses customtkinter for the outer shell and imports page modules
from pages/. Each page module must expose a `draw(parent, project_root)` function
that populates the given CTkFrame and returns nothing.
"""

import os
import sys
from pathlib import Path

import customtkinter as ctk

# ── resolve project root ───────────────────────────────────────────────────────
PROJECT_ROOT = str(Path(__file__).resolve().parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ── import page modules ────────────────────────────────────────────────────────
from pages import homepage
from pages import parametric_study_page
from pages import routing_page

# ── appearance ────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

# ── palette ───────────────────────────────────────────────────────────────────
CLR_BG      = "#1e1e2e"
CLR_SIDEBAR = "#16213e"
CLR_ACCENT  = "#7c3aed"
CLR_ACCENT2 = "#06b6d4"
CLR_TEXT    = "#e2e8f0"
CLR_SUBTEXT = "#94a3b8"
CLR_SUCCESS = "#10b981"
CLR_BORDER  = "#3f3f5a"


# ─────────────────────────────────────────────────────────────────────────────
class WSNApp(ctk.CTk):
    """Root application window."""

    PAGE_NAMES = [
        "home",
        "parametric_study_page",
        "routing_page",
    ]
    PAGE_MODULES = {
        "home":                  homepage,
        "parametric_study_page": parametric_study_page,
        "routing_page":          routing_page,
    }
    PAGE_TITLES = {
        "home":                  "🏠  Home",
        "parametric_study_page": "📊  Parametric Study",
        "routing_page":          "📡  Routing Simulation",
    }

    def __init__(self):
        super().__init__()
        self.title("WSN Simulator — IEEE 802.15.4")
        self.geometry("1400x860")
        self.minsize(1100, 700)
        self.configure(fg_color=CLR_BG)

        # tracks which CTkFrame is currently drawn
        self._current_page: str = ""
        self._page_frames: dict[str, ctk.CTkFrame] = {}

        self._build_layout()
        # Show the home page on startup
        self.show_page("home")

    # ── layout ────────────────────────────────────────────────────────────────
    def _build_layout(self):
        # ── sidebar ──────────────────────────────────────────────────────────
        self._sidebar = ctk.CTkFrame(
            self, width=220, fg_color=CLR_SIDEBAR, corner_radius=0)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        # logo / title area
        logo_frame = ctk.CTkFrame(self._sidebar, fg_color=CLR_ACCENT,
                                   corner_radius=0, height=64)
        logo_frame.pack(fill="x")
        logo_frame.pack_propagate(False)
        ctk.CTkLabel(
            logo_frame,
            text="⚡ WSN Simulator",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color=CLR_TEXT,
        ).pack(expand=True)

        ctk.CTkLabel(
            self._sidebar,
            text="IEEE 802.15.4 Network",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=CLR_SUBTEXT,
        ).pack(pady=(10, 4))

        # nav separator
        ctk.CTkFrame(self._sidebar, height=1, fg_color=CLR_BORDER,
                     corner_radius=0).pack(fill="x", padx=10, pady=4)

        # nav buttons
        self._nav_btns: dict[str, ctk.CTkButton] = {}
        for page_id in self.PAGE_NAMES:
            btn = ctk.CTkButton(
                self._sidebar,
                text=self.PAGE_TITLES[page_id],
                font=ctk.CTkFont(family="Segoe UI", size=12),
                anchor="w",
                fg_color="transparent",
                text_color=CLR_SUBTEXT,
                hover_color=CLR_BORDER,
                corner_radius=8,
                height=42,
                command=lambda pid=page_id: self.show_page(pid),
            )
            btn.pack(fill="x", padx=10, pady=2)
            self._nav_btns[page_id] = btn

        # bottom: version label
        ctk.CTkLabel(
            self._sidebar,
            text="v1.0  •  Python " + sys.version.split()[0],
            font=ctk.CTkFont(family="Segoe UI", size=9),
            text_color=CLR_SUBTEXT,
        ).pack(side="bottom", pady=12)

        # ── main content area ─────────────────────────────────────────────────
        self._content = ctk.CTkFrame(self, fg_color=CLR_BG, corner_radius=0)
        self._content.pack(side="left", fill="both", expand=True)

    # ── page switching ────────────────────────────────────────────────────────
    def show_page(self, page_id: str):
        """
        Public method; called by the homepage and sidebar buttons.
        Hides the current page, creates (or reveals) the target page.
        """
        if page_id == self._current_page:
            return

        # hide current
        if self._current_page and self._current_page in self._page_frames:
            self._page_frames[self._current_page].pack_forget()

        # update nav button highlights
        for pid, btn in self._nav_btns.items():
            if pid == page_id:
                btn.configure(fg_color=CLR_ACCENT, text_color=CLR_TEXT)
            else:
                btn.configure(fg_color="transparent", text_color=CLR_SUBTEXT)

        # build the frame if it does not yet exist
        self.switch_pages(page_id)
        self._current_page = page_id

    def switch_pages(self, page_id: str):
        """
        Instantiate the page frame if needed, then pack it into _content.
        Each page module must expose:
            draw(parent: CTkFrame, project_root: str, show_page_callback: callable)
        """
        if page_id not in self._page_frames:
            frame = ctk.CTkFrame(self._content, fg_color=CLR_BG, corner_radius=0)
            module = self.PAGE_MODULES[page_id]
            # every page module receives the frame, the project root, and
            # a callback so it can trigger navigation from within the page
            module.draw(
                frame,
                PROJECT_ROOT,
                self.show_page,          # show_page_callback
            )
            self._page_frames[page_id] = frame

        self._page_frames[page_id].pack(fill="both", expand=True)


# ── entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = WSNApp()
    app.mainloop()
