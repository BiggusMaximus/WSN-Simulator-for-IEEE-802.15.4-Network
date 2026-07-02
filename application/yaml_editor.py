import customtkinter as ctk
import yaml
from tkinter import messagebox, BooleanVar


# ─────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────

def _cast(original, new_str):
    """Preserve original type when converting a string back."""
    if isinstance(original, bool):
        return new_str.strip().lower() in ("true", "1", "yes")
    if isinstance(original, int):
        try:
            return int(new_str)
        except ValueError:
            pass
    if isinstance(original, float):
        try:
            return float(new_str)
        except ValueError:
            pass
    return new_str


def _set_nested(data, keys, value):
    """Walk *keys* path in *data* and write *value* at the leaf."""
    for k in keys[:-1]:
        data = data[k]
    data[keys[-1]] = value


def _get_nested(data, keys):
    """Read a value from *data* at the path described by *keys*."""
    for k in keys:
        data = data[k]
    return data


def _is_flat_list(val):
    return isinstance(val, list) and all(
        isinstance(i, (int, float, str, bool)) for i in val
    )


# ─────────────────────────────────────────────
#  Core builder
# ─────────────────────────────────────────────

def build_yaml_editor(parent_frame, data: dict, yaml_path: str):
    """
    Fill *parent_frame* with a collapsible, editable YAML tree.

    Key behaviour:
    • Sections that have both 'name' and 'params' show ONLY:
        – a combobox to pick the active model
        – the parameters of the currently selected model
      The 'params' block itself is never shown as a raw collapsible.
    • bool values   → CTkCheckBox
    • 'name' keys   → CTkComboBox
    • everything else → CTkEntry
    """

    # path → {"widget", "kind": entry|combo|check, "original", "var"?}
    registry: dict[tuple, dict] = {}

    # ── Save ─────────────────────────────────────────────────────
    def save():
        errors = []
        for path, info in list(registry.items()):
            kind, widget, original = info["kind"], info["widget"], info["original"]
            try:
                if kind == "check":
                    val = info["var"].get()
                elif kind == "combo":
                    val = widget.get().strip()
                else:
                    val = _cast(original, widget.get().strip())
                _set_nested(data, list(path), val)
            except Exception as e:
                errors.append(f"{' > '.join(str(p) for p in path)}: {e}")

        if errors:
            messagebox.showerror("Save error", "\n".join(errors))
            return

        with open(yaml_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        messagebox.showinfo("Saved", "simulation.yaml updated ✓")

    # ── Top bar ───────────────────────────────────────────────────
    top_bar = ctk.CTkFrame(parent_frame, fg_color="transparent")
    top_bar.pack(fill="x", padx=8, pady=(6, 2))
    ctk.CTkLabel(top_bar, text="Simulation Config",
                 font=("Helvetica", 15, "bold"), text_color="#1a1a2e").pack(side="left")
    ctk.CTkButton(top_bar, text="💾 Save", width=80, height=28,
                  fg_color="#2563eb", hover_color="#1d4ed8",
                  font=("Helvetica", 12, "bold"), command=save).pack(side="right")

    # ── Scrollable tree ───────────────────────────────────────────
    scroll = ctk.CTkScrollableFrame(
        parent_frame, fg_color="#f8fafc",
        scrollbar_button_color="#cbd5e1",
        scrollbar_button_hover_color="#94a3b8"
    )
    scroll.pack(fill="both", expand=True, padx=4, pady=4)

    INDENT_PX = 14

    # ── Low-level widget factories ────────────────────────────────

    def make_entry(row, path, val):
        e = ctk.CTkEntry(row, height=24, font=("Helvetica", 11))
        e.insert(0, "" if val is None else str(val))
        e.pack(side="left", fill="x", expand=True, padx=(0, 6))
        registry[path] = {"widget": e, "kind": "entry", "original": val}

    def make_check(row, path, val):
        var = BooleanVar(value=bool(val))
        chk = ctk.CTkCheckBox(row, text="", variable=var,
                               width=24, height=24,
                               checkbox_width=18, checkbox_height=18,
                               fg_color="#2563eb", hover_color="#1d4ed8",
                               border_color="#94a3b8")
        chk.pack(side="left", padx=(0, 6))
        registry[path] = {"widget": chk, "kind": "check", "original": val, "var": var}

    # ── Leaf row (single key → widget) ───────────────────────────

    def make_leaf_row(container, key, val, path, depth):
        row = ctk.CTkFrame(container, fg_color="transparent")
        row.pack(fill="x", pady=1)
        ctk.CTkFrame(row, width=depth * INDENT_PX + 8, height=1,
                     fg_color="transparent").pack(side="left")
        ctk.CTkLabel(row, text=f"{key}:", width=130, anchor="w",
                     font=("Helvetica", 11), text_color="#475569").pack(side="left")

        if isinstance(val, bool):
            make_check(row, path, val)
        elif _is_flat_list(val):
            make_entry(row, path, val)
        else:
            make_entry(row, path, val)

    # ── Smart "model selector" section ───────────────────────────
    #
    # Called when a dict has BOTH a 'name' key AND a 'params' key.
    # Renders:
    #   Model: [ ComboBox ▼ ]          ← picks the active model
    #   param_a: [entry]               ← params of selected model only
    #   param_b: [checkbox]
    #   ...
    #
    # When the combo changes → wipe the params frame, re-render for new model.

    def make_model_section(container, section_key, section_dict, section_path, depth):
        """Render a name+params section with reactive param display."""

        params_dict = section_dict.get("params", {})
        current_name = section_dict.get("name", "")
        model_names = list(params_dict.keys()) if params_dict else [str(current_name)]

        # ── collapsible wrapper ───────────────────────────────────
        wrapper = ctk.CTkFrame(container, fg_color="transparent")
        wrapper.pack(fill="x", pady=1)

        header = ctk.CTkFrame(wrapper, fg_color="transparent")
        header.pack(fill="x")
        ctk.CTkFrame(header, width=depth * INDENT_PX, height=1,
                     fg_color="transparent").pack(side="left")

        toggle_btn = ctk.CTkButton(
            header, text=f"▶  {section_key}", anchor="w",
            font=("Helvetica", 12, "bold"), text_color="#1e3a5f",
            fg_color="#dbeafe" if depth == 0 else "#e0f2fe",
            hover_color="#bfdbfe", height=26, corner_radius=4, border_width=0,
        )
        toggle_btn.pack(side="left", fill="x", expand=True, pady=1)

        body = ctk.CTkFrame(wrapper, fg_color="transparent")
        # body starts hidden; built lazily on first expand

        expanded = [False]
        built    = [False]

        def build_body():
            # ── name row with combobox ────────────────────────────
            name_row = ctk.CTkFrame(body, fg_color="transparent")
            name_row.pack(fill="x", pady=1)
            ctk.CTkFrame(name_row, width=(depth + 1) * INDENT_PX + 8,
                         height=1, fg_color="transparent").pack(side="left")
            ctk.CTkLabel(name_row, text="Model:", width=130, anchor="w",
                         font=("Helvetica", 11, "bold"),
                         text_color="#021d41").pack(side="left")

            combo = ctk.CTkComboBox(
                name_row, values=model_names, height=24,
                font=("Helvetica", 11),
                fg_color="black", button_color="#2563eb",
                button_hover_color="#1d4ed8",
                dropdown_fg_color="white", dropdown_text_color="#1e293b",
                width=160,
            )
            combo.set(str(current_name))
            combo.pack(side="left", fill="x", expand=True, padx=(0, 6))

            name_path = section_path + ("name",)
            registry[name_path] = {"widget": combo, "kind": "combo",
                                    "original": current_name}

            # ── params frame (swapped on combo change) ────────────
            params_frame = ctk.CTkFrame(body, fg_color="transparent")
            params_frame.pack(fill="x")

            # remove registry entries that belong to this params frame
            def clear_params_registry(model):
                prefix = section_path + ("params", model)
                for p in list(registry.keys()):
                    if len(p) > len(prefix) and p[:len(prefix)] == prefix:
                        del registry[p]

            def render_params(model_name):
                # destroy old widgets
                for w in params_frame.winfo_children():
                    w.destroy()

                model_params = params_dict.get(model_name, {})
                if not isinstance(model_params, dict):
                    return

                for pk, pv in model_params.items():
                    p_path = section_path + ("params", model_name, pk)
                    if isinstance(pv, dict) or (isinstance(pv, list) and not _is_flat_list(pv)):
                        # nested sub-dict inside params — render as collapsible
                        render_collapsible(params_frame, pk, pv, p_path, depth + 2)
                    else:
                        make_leaf_row(params_frame, pk, pv, p_path, depth + 2)

            render_params(str(current_name))

            def on_model_change(new_name):
                clear_params_registry(combo.get())   # clear previous selection
                render_params(new_name)

            combo.configure(command=on_model_change)

        def toggle():
            if expanded[0]:
                body.pack_forget()
                toggle_btn.configure(text=toggle_btn.cget("text").replace("▼", "▶"))
            else:
                if not built[0]:
                    build_body()
                    built[0] = True
                body.pack(fill="x")
                toggle_btn.configure(text=toggle_btn.cget("text").replace("▶", "▼"))
            expanded[0] = not expanded[0]

        toggle_btn.configure(command=toggle)

    # ── Generic collapsible (for dicts without name+params) ───────

    def render_collapsible(container, key, val, path, depth):
        section = ctk.CTkFrame(container, fg_color="transparent")
        section.pack(fill="x", pady=1)

        header = ctk.CTkFrame(section, fg_color="transparent")
        header.pack(fill="x")
        ctk.CTkFrame(header, width=depth * INDENT_PX, height=1,
                     fg_color="transparent").pack(side="left")

        toggle_btn = ctk.CTkButton(
            header, text=f"▶  {key}", anchor="w",
            font=("Helvetica", 12, "bold"), text_color="#1e3a5f",
            fg_color="#dbeafe" if depth == 0 else "#e0f2fe",
            hover_color="#bfdbfe", height=26, corner_radius=4, border_width=0,
        )
        toggle_btn.pack(side="left", fill="x", expand=True, pady=1)

        body = ctk.CTkFrame(section, fg_color="transparent")
        expanded = [False]
        built    = [False]

        def make_toggle(btn, bd, nv, p, d, exp, blt):
            def toggle():
                if exp[0]:
                    bd.pack_forget()
                    btn.configure(text=btn.cget("text").replace("▼", "▶"))
                else:
                    if not blt[0]:
                        render_node(bd, nv, p, d + 1)
                        blt[0] = True
                    bd.pack(fill="x")
                    btn.configure(text=btn.cget("text").replace("▶", "▼"))
                exp[0] = not exp[0]
            return toggle

        toggle_btn.configure(command=make_toggle(
            toggle_btn, body, val, path, depth, expanded, built))

    # ── Recursive renderer ────────────────────────────────────────

    def render_node(container, node, path: tuple, depth: int):
        if isinstance(node, dict):
            for key, val in node.items():
                key_path = path + (key,)

                # ── smart model section: has name + params ────────
                if (isinstance(val, dict)
                        and "name" in val
                        and "params" in val
                        and isinstance(val["params"], dict)):
                    make_model_section(container, key, val, key_path, depth)

                # ── generic collapsible ───────────────────────────
                elif isinstance(val, dict) or (
                    isinstance(val, list) and not _is_flat_list(val)
                ):
                    render_collapsible(container, key, val, key_path, depth)

                # ── leaf ──────────────────────────────────────────
                else:
                    make_leaf_row(container, key, val, key_path, depth)

        elif isinstance(node, list):
            for i, item in enumerate(node):
                render_node(container, item, path + (i,), depth)

    render_node(scroll, data, (), 0)
    return registry