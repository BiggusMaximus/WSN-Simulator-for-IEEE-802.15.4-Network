"""
pages/homepage.py
=================
Landing page shown when the app starts.
Provides navigation cards to the two simulation pages.
"""

import customtkinter as ctk

CLR_BG      = "#1e1e2e"
CLR_PANEL   = "#2a2a3e"
CLR_ACCENT  = "#7c3aed"
CLR_ACCENT2 = "#06b6d4"
CLR_SUCCESS = "#10b981"
CLR_TEXT    = "#e2e8f0"
CLR_SUBTEXT = "#94a3b8"
CLR_BORDER  = "#3f3f5a"
CLR_CARD    = "#252540"


def draw(parent: ctk.CTkFrame, project_root: str, show_page_callback):
    """Populate *parent* with the home page layout."""

    parent.configure(fg_color=CLR_BG)

    # ── hero section ──────────────────────────────────────────────────────────
    hero = ctk.CTkFrame(parent, fg_color=CLR_ACCENT, corner_radius=0, height=130)
    hero.pack(fill="x")
    hero.pack_propagate(False)

    ctk.CTkLabel(
        hero,
        text="⚡  WSN Simulator",
        font=ctk.CTkFont(family="Segoe UI", size=30, weight="bold"),
        text_color="#ffffff",
    ).pack(pady=(24, 2))
    ctk.CTkLabel(
        hero,
        text="IEEE 802.15.4 Network Simulation Platform",
        font=ctk.CTkFont(family="Segoe UI", size=13),
        text_color="#c4b5fd",
    ).pack()

    # ── body ──────────────────────────────────────────────────────────────────
    body = ctk.CTkFrame(parent, fg_color=CLR_BG)
    body.pack(fill="both", expand=True, padx=40, pady=30)

    ctk.CTkLabel(
        body,
        text="Select a simulation mode to get started",
        font=ctk.CTkFont(family="Segoe UI", size=14),
        text_color=CLR_SUBTEXT,
    ).pack(pady=(0, 24))

    # ── card row ──────────────────────────────────────────────────────────────
    card_row = ctk.CTkFrame(body, fg_color="transparent")
    card_row.pack()

    # helper to make a navigation card
    def make_card(parent_frame, icon, title, desc, page_id, accent):
        card = ctk.CTkFrame(parent_frame, fg_color=CLR_CARD,
                             corner_radius=16, width=320, height=260)
        card.pack(side="left", padx=16)
        card.pack_propagate(False)

        ctk.CTkLabel(card, text=icon,
                     font=ctk.CTkFont(size=44)).pack(pady=(28, 4))
        ctk.CTkLabel(card, text=title,
                     font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
                     text_color=CLR_TEXT).pack()
        ctk.CTkLabel(card, text=desc,
                     font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=CLR_SUBTEXT,
                     wraplength=270).pack(padx=16, pady=8)

        ctk.CTkButton(
            card,
            text=f"Open  →",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            fg_color=accent,
            hover_color="#5b21b6" if accent == CLR_ACCENT else "#0e7490",
            corner_radius=8,
            height=36,
            command=lambda: show_page_callback(page_id),
        ).pack(pady=(4, 20), ipadx=20)

    make_card(
        card_row,
        icon="📊",
        title="Parametric Study",
        desc=(
            "Sweep node counts and area dimensions.\n"
            "Visualise energy, latency, PDR, packets\n"
            "and collisions as 3-D contour plots."
        ),
        page_id="parametric_study_page",
        accent=CLR_ACCENT,
    )

    make_card(
        card_row,
        icon="📡",
        title="Routing Simulation",
        desc=(
            "Run a full multi-round simulation until\n"
            "all nodes die. View per-round metrics:\n"
            "lifetime, PDR, energy, packets, collisions."
        ),
        page_id="routing_page",
        accent=CLR_ACCENT2,
    )

    # ── info strip ────────────────────────────────────────────────────────────
    info = ctk.CTkFrame(body, fg_color=CLR_PANEL, corner_radius=10)
    info.pack(fill="x", pady=(32, 0))

    info_items = [
        ("🔧", "Protocol",   "DirectUnslottedCSMA / LEACH / HEED"),
        ("📡", "RF Model",   "IEEE 802.15.4 CSMA/CA with ACK"),
        ("⚡", "Energy",     "MCU + RF + Sensor + Memory tracking"),
        ("🗺", "Deployment", "Random / Poisson / User-input"),
    ]
    for icon_t, key_t, val_t in info_items:
        row = ctk.CTkFrame(info, fg_color="transparent")
        row.pack(side="left", expand=True, padx=10, pady=12)
        ctk.CTkLabel(row, text=f"{icon_t} {key_t}",
                     font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                     text_color=CLR_TEXT).pack()
        ctk.CTkLabel(row, text=val_t,
                     font=ctk.CTkFont(family="Segoe UI", size=10),
                     text_color=CLR_SUBTEXT).pack()
