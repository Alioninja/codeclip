import os
import threading
import customtkinter as ctk
from PIL import Image, ImageDraw
from collections import Counter
import time

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# --- Configuration ---
IGNORED_DIRS = {".git", "__pycache__", "venv", "env",
                ".vscode", "node_modules", ".idea"}
IGNORED_FILES = {".DS_Store"}
LIGHT_NESTED_BG = "#3c3c3c"
DARK_NESTED_BG = "#303030"
INDICATOR_WIDTH = 18
NESTED_BG_PAD_X = 10
NESTED_BG_CORNER_RADIUS = 6
# Adjusted to show ~4 rows of checkboxes (approx 30px per row)
FILE_TYPE_SECTION_MAX_HEIGHT = 160
INDENT_SIZE = 20  # Width for each indentation level
# --- End Configuration ---


# Precompute lowercase ignore sets for case-insensitive checks
IGNORED_DIRS_NORMALIZED = {name.lower() for name in IGNORED_DIRS}
IGNORED_FILES_NORMALIZED = {name.lower() for name in IGNORED_FILES}


def is_ignored_dir(name):
    return name.lower() in IGNORED_DIRS_NORMALIZED


def is_ignored_file(name):
    lower_name = name.lower()
    return lower_name in IGNORED_FILES_NORMALIZED or name.startswith('.')


def path_contains_ignored_dir(path):
    normalized_path = os.path.normpath(path).lower()
    for ignored_dir in IGNORED_DIRS_NORMALIZED:
        normalized_ignored_dir = os.path.normpath(ignored_dir).lower()
        if normalized_ignored_dir in normalized_path:
            return True
    return False


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Codebase to Clipboard")
        self.geometry("800x700")
        self.minsize(500, 600)

        # Config access
        self.light_nested_bg = LIGHT_NESTED_BG
        self.dark_nested_bg = DARK_NESTED_BG
        self.indicator_width = INDICATOR_WIDTH
        self.nested_bg_pad_x = NESTED_BG_PAD_X
        self.nested_bg_corner_radius = NESTED_BG_CORNER_RADIUS
        self.indent_size = INDENT_SIZE

        self.current_dir = os.getcwd()

        self.file_extension_counts_initial = self.scan_file_extensions(
            self.current_dir)
        self.sorted_extensions = sorted(self.file_extension_counts_initial.keys(),
                                        key=lambda ext: self.file_extension_counts_initial[ext],
                                        reverse=True)

        self.folder_tree = self.build_folder_tree(self.current_dir)

        # State dictionaries
        self.folder_vars = {}
        self.folder_labels = {}
        self.file_vars = {}
        self.file_labels = {}
        self.folder_children = {}
        self.folder_parent = {}
        self.file_type_vars = {}
        self.file_type_checkboxes = {}
        self.folder_widget_refs = {}
        self.folder_states = {}  # Tracks open/closed state {folder_rel_path: bool}

        self.create_checkbox_images()

        # --- Main layout ---
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(pady=10, padx=10, fill="both", expand=True)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=0)
        main_frame.grid_rowconfigure(2, weight=0)

        # ── Folder Tree Section ─────────────────────────────────────────
        folder_section_container = ctk.CTkFrame(main_frame)
        folder_section_container.grid(
            row=0, column=0, sticky="nsew", pady=(0, 5))
        folder_section_container.grid_columnconfigure(0, weight=1)
        folder_section_container.grid_rowconfigure(1, weight=1)

        folder_header = ctk.CTkFrame(
            folder_section_container, fg_color="transparent")
        folder_header.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 2))

        folder_title = ctk.CTkLabel(
            folder_header, text="Select Folders and Files:", anchor="w")
        folder_title.pack(side="left", padx=(0, 10))

        folder_button_frame = ctk.CTkFrame(
            folder_header, fg_color="transparent")
        folder_button_frame.pack(side="right")

        folder_deselect_all_btn = ctk.CTkButton(
            folder_button_frame, text="Deselect All", width=100, height=28, command=self.deselect_all_folders)
        folder_deselect_all_btn.pack(side="right", padx=(5, 0))

        folder_select_all_btn = ctk.CTkButton(
            folder_button_frame, text="Select All", width=100, height=28, command=self.select_all_folders)
        folder_select_all_btn.pack(side="right", padx=0)

        self.folder_container = ctk.CTkScrollableFrame(
            folder_section_container)
        self.folder_container.grid(
            row=1, column=0, sticky="nsew", padx=5, pady=(0, 5))
        self.folder_container.grid_columnconfigure(0, weight=1)

        # --- Build Tree UI ---
        self.create_folder_ui(
            self.folder_tree, self.folder_container, parent_rel_path="", level=-1)

        # ── File Type Section ───────────────────────────────────────────
        type_section_container = ctk.CTkFrame(main_frame)
        type_section_container.grid(row=1, column=0, sticky="new", pady=5)
        type_section_container.grid_columnconfigure(
            0, weight=1)  # Allow column to expand horizontally
        type_section_container.grid_rowconfigure(
            0, weight=0)     # Header row, fixed
        type_section_container.grid_rowconfigure(
            1, weight=0)     # Scroll container row, fixed

        # Header
        type_header = ctk.CTkFrame(
            type_section_container, fg_color="transparent")
        type_header.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 2))

        filetype_label = ctk.CTkLabel(
            type_header, text="Select file types to include:", anchor="w")
        filetype_label.pack(side="left", padx=(0, 10))

        type_button_frame = ctk.CTkFrame(type_header, fg_color="transparent")
        type_button_frame.pack(side="right")

        filetype_deselect_all_btn = ctk.CTkButton(
            type_button_frame, text="Deselect All", width=100, height=28, command=self.deselect_all_filetypes)
        filetype_deselect_all_btn.pack(side="right", padx=(5, 0))

        filetype_select_all_btn = ctk.CTkButton(
            type_button_frame, text="Select All", width=100, height=28, command=self.select_all_filetypes)
        filetype_select_all_btn.pack(side="right", padx=0)

        # Fixed-height container for the scrollable frame
        type_scroll_container = ctk.CTkFrame(
            type_section_container, height=FILE_TYPE_SECTION_MAX_HEIGHT)
        type_scroll_container.grid(
            row=1, column=0, sticky="nsew", padx=5, pady=(0, 5))
        type_scroll_container.grid_propagate(
            False)  # Enforce the specified height
        # Allow scrollable frame to fill vertically
        type_scroll_container.grid_rowconfigure(0, weight=1)
        # Allow scrollable frame to fill horizontally
        type_scroll_container.grid_columnconfigure(0, weight=1)

        # Scrollable frame inside the fixed-height container
        filetype_scrollable_frame = ctk.CTkScrollableFrame(
            type_scroll_container, fg_color="transparent")
        filetype_scrollable_frame.grid(row=0, column=0, sticky="nsew")
        filetype_scrollable_frame.grid_columnconfigure(
            (0, 1, 2), weight=1)  # 3 columns for checkboxes

        # Populate with checkboxes (example)
        num_columns = 3
        # Assume sorted_extensions is a list
        for i, ext in enumerate(self.sorted_extensions):
            var = ctk.BooleanVar(value=True)
            self.file_type_vars[ext] = var
            count = self.file_extension_counts_initial.get(ext, 0)
            label_text = f"{ext} files ({count})"
            checkbox = ctk.CTkCheckBox(
                filetype_scrollable_frame, text=label_text, variable=var,
                command=self.update_file_type_counts
            )
            row = i // num_columns
            col = i % num_columns
            checkbox.grid(row=row, column=col, sticky="w", padx=10, pady=2)
            self.file_type_checkboxes[ext] = checkbox

        # ── Footer Section ──────────────────────────────────────────────
        footer_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        footer_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=(5, 0))
        footer_frame.grid_columnconfigure(1, weight=1)

        process_btn = ctk.CTkButton(
            footer_frame, text="Generate Text and Copy to Clipboard", height=32, command=self.process_folders)
        process_btn.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")

        self.status_label = ctk.CTkLabel(footer_frame, text="", anchor="w")
        self.status_label.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # --- Set Initial State ---
        self.select_all_folders()
        self.update_file_type_counts()
        self.after(10, self.collapse_all_folders)

    # --- Scan extensions ---
    def scan_file_extensions(self, base_path):
        if is_ignored_dir(os.path.basename(base_path)) or path_contains_ignored_dir(base_path):
            return Counter()

        normalized_base = os.path.normpath(base_path)
        extension_counts = Counter()
        for root, dirs, files in os.walk(normalized_base, topdown=True, followlinks=False):
            # Filter out ignored directories right away
            dirs[:] = [d for d in dirs if not is_ignored_dir(d)]

            if path_contains_ignored_dir(root):
                dirs[:] = []
                continue

            filtered_files = [f for f in files if not is_ignored_file(f)]
            for file in filtered_files:
                _, ext = os.path.splitext(file)
                if ext:
                    extension_counts[ext.lower()] += 1
        return extension_counts

    # --- Create checkbox images ---
    def create_checkbox_images(self):
        size = 18
        border_width = 2
        check_width = 2
        radius = 3

        try:
            fg_color = customtkinter.ThemeManager.get_color(
                ctk.ThemeManager.theme["CTkCheckBox"]["fg_color"])
            border_color_checked = customtkinter.ThemeManager.get_color(
                ctk.ThemeManager.theme["CTkCheckBox"]["border_color"])
            checkmark_color = customtkinter.ThemeManager.get_color(
                ctk.ThemeManager.theme["CTkCheckBox"]["checkmark_color"])
            border_color_unchecked = customtkinter.ThemeManager.get_color(
                ctk.ThemeManager.theme["CTkLabel"]["text_color"])
            indeterminate_color = "#F39C12"  # Orange
            indeterminate_line_color = "#FFFFFF"  # White
        except Exception as e:
            print(f"Warning: Using fallback colors due to theme error: {e}")
            fg_color = "#2ECC71"
            border_color_checked = "#2ECC71"
            checkmark_color = "#FFFFFF"
            border_color_unchecked = "#888888"
            indeterminate_color = "#F39C12"
            indeterminate_line_color = "#FFFFFF"

        # --- Unchecked ---
        unchecked = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(unchecked)
        rect_coords = [border_width // 2, border_width // 2,
                       size - border_width // 2 - 1, size - border_width // 2 - 1]
        draw.rounded_rectangle(rect_coords, radius=radius,
                               outline=border_color_unchecked, width=border_width)
        self.unchecked_image = ctk.CTkImage(
            light_image=unchecked, dark_image=unchecked, size=(size, size))

        # --- Checked ---
        checked = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw_checked = ImageDraw.Draw(checked)
        draw_checked.rounded_rectangle(
            rect_coords, radius=radius, outline=border_color_checked, fill=fg_color, width=border_width)
        p1 = (size * 0.2, size * 0.5)
        p2 = (size * 0.45, size * 0.7)
        p3 = (size * 0.75, size * 0.3)
        draw_checked.line([p1, p2, p3], fill=checkmark_color,
                          width=check_width, joint="round")
        self.checked_image = ctk.CTkImage(
            light_image=checked, dark_image=checked, size=(size, size))

        # --- Indeterminate ---
        indeterminate = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw_ind = ImageDraw.Draw(indeterminate)
        draw_ind.rounded_rectangle(
            rect_coords, radius=radius, outline=border_color_checked, fill=indeterminate_color, width=border_width)
        y_center = size // 2
        x_start = size * 0.25
        x_end = size * 0.75
        draw_ind.line([(x_start, y_center), (x_end, y_center)],
                      fill=indeterminate_line_color, width=check_width)
        self.indeterminate_image = ctk.CTkImage(
            light_image=indeterminate, dark_image=indeterminate, size=(size, size))

    # --- Build folder tree ---
    def build_folder_tree(self, base_path):
        if is_ignored_dir(os.path.basename(base_path)):
            return {"subfolders": {}, "files": []}
        tree = {"subfolders": {}, "files": []}
        if path_contains_ignored_dir(base_path):
            return tree
        try:
            dirs = []
            files_in_dir = []
            with os.scandir(base_path) as it:
                for entry in it:
                    name = entry.name
                    entry_path = entry.path
                    if path_contains_ignored_dir(entry_path) or is_ignored_dir(name):
                        continue
                    if entry.is_dir(follow_symlinks=False):
                        dirs.append(entry)
                    elif entry.is_file() and not is_ignored_file(name):
                        _, ext = os.path.splitext(name)
                        if ext and ext.lower() in self.file_extension_counts_initial:
                            files_in_dir.append(name)

            tree["files"] = sorted(files_in_dir, key=str.lower)
            dirs.sort(key=lambda e: e.name.lower())

            for entry in dirs:
                sub_tree = self.build_folder_tree(entry.path)
                if sub_tree.get("subfolders") or sub_tree.get("files"):
                    tree["subfolders"][entry.name] = sub_tree
        except OSError:
            pass
        return tree

    # --- Create UI for Each Folder/File Item ---
    def create_folder_ui(self, tree_node, parent_frame, parent_rel_path="", level=0):
        item_level = level + 1
        item_indent = item_level * self.indent_size

        if "subfolders" in tree_node:
            for folder, sub_tree_node in sorted(tree_node["subfolders"].items()):
                folder_rel_path = os.path.join(
                    parent_rel_path, folder) if parent_rel_path else folder
                has_children = bool(sub_tree_node.get(
                    "subfolders") or sub_tree_node.get("files"))

                self.folder_children.setdefault(folder_rel_path, [])
                self.folder_parent[folder_rel_path] = parent_rel_path
                self.folder_children.setdefault(
                    parent_rel_path, []).append(folder_rel_path)
                self.folder_states[folder_rel_path] = False

                folder_item_container = ctk.CTkFrame(
                    parent_frame, fg_color="transparent")
                folder_item_container.pack(fill="x", pady=0, padx=0)

                header_frame = ctk.CTkFrame(
                    folder_item_container, fg_color="transparent")
                if parent_frame is self.folder_container:
                    header_frame.pack(fill="x", pady=(1, 0), padx=0)
                else:
                    header_frame.pack(fill="x", pady=(
                        1, 0), padx=(self.indent_size, 0))

                indicator_text = "▶ " if has_children else " " * 3
                dropdown_indicator = ctk.CTkLabel(
                    header_frame, text=indicator_text, width=self.indicator_width, anchor="w", padx=0)
                dropdown_indicator.pack(side="left")

                var = ctk.IntVar(value=0)
                self.folder_vars[folder_rel_path] = var

                folder_label = ctk.CTkLabel(
                    header_frame, text=folder, image=self.unchecked_image, compound="left",
                    padx=5, anchor="w"
                )
                folder_label.pack(side="left", pady=1, fill="x", expand=True)
                self.folder_labels[folder_rel_path] = folder_label

                bg_color = self.dark_nested_bg if item_level % 2 == 0 else self.light_nested_bg
                content_bg_frame = ctk.CTkFrame(
                    folder_item_container, fg_color=bg_color,
                    corner_radius=self.nested_bg_corner_radius
                )

                contents_container = ctk.CTkFrame(
                    content_bg_frame, fg_color="transparent")
                contents_container.pack(
                    fill="both", expand=True, padx=self.nested_bg_pad_x, pady=2)

                self.folder_widget_refs[folder_rel_path] = {
                    "indicator": dropdown_indicator,
                    "content_frame": content_bg_frame,
                    "contents_container": contents_container,
                    "header_frame": header_frame,
                    "level": item_level,
                }

                folder_label.bind(
                    "<Button-1>", lambda e, frp=folder_rel_path: self.on_folder_label_click(frp))
                if has_children:
                    dropdown_indicator.bind(
                        "<Button-1>", lambda e, frp=folder_rel_path: self.toggle_folder_by_path(frp))
                    folder_label.bind(
                        "<Double-Button-1>", lambda e, frp=folder_rel_path: self.toggle_folder_by_path(frp))

                self.create_folder_ui(
                    sub_tree_node, contents_container, folder_rel_path, level=item_level)

        if "files" in tree_node and tree_node["files"]:
            self.file_vars.setdefault(parent_rel_path, {})
            self.file_labels.setdefault(parent_rel_path, {})

            for file in sorted(tree_node["files"]):
                file_var = ctk.BooleanVar(value=False)
                file_line = ctk.CTkFrame(parent_frame, fg_color="transparent")
                if parent_frame is self.folder_container:
                    file_line.pack(anchor="w", fill="x", padx=0, pady=(1, 0))
                else:
                    file_line.pack(anchor="w", fill="x", padx=(
                        self.indent_size, 0), pady=(1, 0))

                file_placeholder = ctk.CTkLabel(
                    file_line, text=" " * 3, width=self.indicator_width, anchor="w", padx=0)
                file_placeholder.pack(side="left")

                file_label = ctk.CTkLabel(
                    file_line, text=file, image=self.unchecked_image, compound="left",
                    padx=5, anchor="w"
                )
                file_label.pack(side="left", pady=1, fill="x", expand=True)

                file_label.bind("<Button-1>", lambda e, frp=parent_rel_path,
                                f=file: self.on_file_label_click(frp, f))

                self.file_vars[parent_rel_path][file] = file_var
                self.file_labels[parent_rel_path][file] = file_label

    # --- Toggle Folder ---
    def toggle_folder_by_path(self, folder_rel_path):
        refs = self.folder_widget_refs.get(folder_rel_path)
        if not refs:
            return

        content_frame = refs["content_frame"]
        header_frame = refs["header_frame"]
        indicator_label = refs["indicator"]
        item_level = refs["level"]
        is_currently_open = self.folder_states.get(folder_rel_path, False)

        if is_currently_open:
            content_frame.pack_forget()
            indicator_label.configure(text="▶ ")
            self.folder_states[folder_rel_path] = False
        else:
            content_indent = item_level * self.indent_size
            content_frame.pack(fill="x", pady=(0, 5), padx=(content_indent, 0),
                               after=header_frame)
            indicator_label.configure(text="▼ ")
            self.folder_states[folder_rel_path] = True

    # --- Collapse All Folders ---
    def collapse_all_folders(self):
        for folder_path, is_open in list(self.folder_states.items()):
            if is_open:
                refs = self.folder_widget_refs.get(folder_path)
                if refs:
                    content_frame = refs["content_frame"]
                    indicator_label = refs["indicator"]
                    content_frame.pack_forget()
                    indicator_label.configure(text="▶ ")
                    self.folder_states[folder_path] = False

    # --- Folder Selection Logic ---
    def on_folder_label_click(self, folder_rel_path):
        if folder_rel_path not in self.folder_vars:
            return
        current_value = self.folder_vars[folder_rel_path].get()
        new_value = 1 if current_value != 1 else 0
        self._propagate_folder_selection_down(folder_rel_path, new_value)
        parent_path = self.folder_parent.get(folder_rel_path)
        if parent_path is not None:
            self._update_parent_folder_state_up(parent_path)
        self.update_file_type_counts()

    def _propagate_folder_selection_down(self, folder_rel_path, target_state):
        if folder_rel_path not in self.folder_vars:
            return
        self.folder_vars[folder_rel_path].set(target_state)
        self.update_folder_image(folder_rel_path)
        is_checked = (target_state == 1)

        if folder_rel_path in self.file_vars:
            for file, file_var in self.file_vars[folder_rel_path].items():
                if file_var.get() != is_checked:
                    file_var.set(is_checked)
                    self.update_file_image(folder_rel_path, file)

        for child_path in self.folder_children.get(folder_rel_path, []):
            if child_path in self.folder_vars:
                self._propagate_folder_selection_down(child_path, target_state)

    def _update_parent_folder_state_up(self, folder_rel_path):
        if folder_rel_path == "" or folder_rel_path not in self.folder_vars:
            if folder_rel_path == "" and "" in self.file_vars:
                all_checked = True
                all_unchecked = True
                has_any_child = False
                for file_var in self.file_vars[""].values():
                    has_any_child = True
                    if file_var.get():
                        all_unchecked = False
                    else:
                        all_checked = False
                    if not all_checked and not all_unchecked:
                        break
                pass
            return

        new_state = self._recalculate_folder_state(folder_rel_path)
        current_state = self.folder_vars[folder_rel_path].get()
        if current_state != new_state:
            self.folder_vars[folder_rel_path].set(new_state)
            self.update_folder_image(folder_rel_path)
            parent = self.folder_parent.get(folder_rel_path)
            if parent is not None:
                self._update_parent_folder_state_up(parent)

    def _recalculate_folder_state(self, folder_rel_path):
        if folder_rel_path not in self.folder_vars:
            return 0

        has_any_child = False
        all_checked = True
        all_unchecked = True

        if folder_rel_path in self.file_vars:
            for file_var in self.file_vars[folder_rel_path].values():
                has_any_child = True
                if file_var.get():
                    all_unchecked = False
                else:
                    all_checked = False
                if not all_checked and not all_unchecked:
                    return 2

        for child_folder_path in self.folder_children.get(folder_rel_path, []):
            if child_folder_path in self.folder_vars:
                has_any_child = True
                child_state = self.folder_vars[child_folder_path].get()
                if child_state == 1:
                    all_unchecked = False
                elif child_state == 0:
                    all_checked = False
                elif child_state == 2:
                    all_checked = False
                    all_unchecked = False
                    return 2
                if not all_checked and not all_unchecked:
                    return 2

        if not has_any_child:
            return self.folder_vars[folder_rel_path].get()
        if all_checked:
            return 1
        if all_unchecked:
            return 0
        return 2

    def update_folder_image(self, folder_rel_path):
        if folder_rel_path not in self.folder_labels or folder_rel_path not in self.folder_vars:
            return
        label = self.folder_labels[folder_rel_path]
        state = self.folder_vars[folder_rel_path].get()
        if state == 0:
            img = self.unchecked_image
        elif state == 1:
            img = self.checked_image
        else:
            img = self.indeterminate_image
        if label.winfo_exists():
            label.configure(image=img)

    # --- File Selection Logic ---
    def on_file_label_click(self, folder_rel_path, file):
        if folder_rel_path not in self.file_vars or file not in self.file_vars[folder_rel_path]:
            return
        current_val = self.file_vars[folder_rel_path][file].get()
        self.file_vars[folder_rel_path][file].set(not current_val)
        self.update_file_image(folder_rel_path, file)
        self._update_parent_folder_state_up(folder_rel_path)
        self.update_file_type_counts()

    def update_file_image(self, folder_rel_path, file):
        if (folder_rel_path not in self.file_labels
                or file not in self.file_labels[folder_rel_path]
                or folder_rel_path not in self.file_vars
                or file not in self.file_vars[folder_rel_path]):
            return
        label = self.file_labels[folder_rel_path][file]
        var = self.file_vars[folder_rel_path][file]
        img = self.checked_image if var.get() else self.unchecked_image
        if label.winfo_exists():
            label.configure(image=img)

    # --- Buttons: Select/Deselect All ---
    def select_all_folders(self):
        if "" in self.file_vars:
            for file, file_var in self.file_vars[""].items():
                if not file_var.get():
                    file_var.set(True)
                    self.update_file_image("", file)

        for folder_rel_path in self.folder_vars:
            if self.folder_parent.get(folder_rel_path) == "":
                if self.folder_vars[folder_rel_path].get() != 1:
                    self._propagate_folder_selection_down(folder_rel_path, 1)
        self.update_file_type_counts()

    def deselect_all_folders(self):
        if "" in self.file_vars:
            for file, file_var in self.file_vars[""].items():
                if file_var.get():
                    file_var.set(False)
                    self.update_file_image("", file)

        for folder_rel_path in self.folder_vars:
            if self.folder_parent.get(folder_rel_path) == "":
                if self.folder_vars[folder_rel_path].get() != 0:
                    self._propagate_folder_selection_down(folder_rel_path, 0)
        self.update_file_type_counts()

    def select_all_filetypes(self):
        changed = False
        for var in self.file_type_vars.values():
            if not var.get():
                var.set(True)
                changed = True
        if changed:
            self.update_file_type_counts()

    def deselect_all_filetypes(self):
        changed = False
        for var in self.file_type_vars.values():
            if var.get():
                var.set(False)
                changed = True
        if changed:
            self.update_file_type_counts()

    # --- Update File Type Counts ---
    def update_file_type_counts(self):
        current_counts = Counter()
        selected_exts = {ext.lower()
                         for ext, var in self.file_type_vars.items() if var.get()}
        for folder_path, files_dict in self.file_vars.items():
            for file, var in files_dict.items():
                if var.get():
                    _, ext = os.path.splitext(file)
                    if ext and ext.lower() in selected_exts:
                        current_counts[ext.lower()] += 1

        for ext, checkbox in self.file_type_checkboxes.items():
            count = current_counts.get(ext, 0)
            label_text = f"{ext} files ({count})"
            if checkbox.winfo_exists():
                checkbox.configure(text=label_text)

    # --- Processing ---
    def process_folders(self):
        include_exts = {ext.lower()
                        for ext, var in self.file_type_vars.items() if var.get()}
        selected_files_paths = []
        q = [""]
        visited_folders = set()

        while q:
            current_folder_path = q.pop(0)
            if current_folder_path in visited_folders:
                continue
            visited_folders.add(current_folder_path)

            if current_folder_path in self.file_vars:
                for file, var in self.file_vars[current_folder_path].items():
                    if var.get():
                        _, ext = os.path.splitext(file)
                        if ext and ext.lower() in include_exts:
                            full_path = os.path.join(
                                self.current_dir, current_folder_path, file)
                            selected_files_paths.append(full_path)

            if current_folder_path in self.folder_children:
                for subfolder_path in self.folder_children[current_folder_path]:
                    if subfolder_path in self.folder_vars:
                        folder_state = self.folder_vars[subfolder_path].get()
                        if folder_state in [1, 2]:
                            q.append(subfolder_path)

        if not selected_files_paths:
            self.status_label.configure(
                text="No files selected or matching selected file types.")
            return

        self.status_label.configure(text="Processing... please wait.")
        self.update_idletasks()

        thread = threading.Thread(
            target=self._process_thread,
            args=(sorted(selected_files_paths), include_exts),
        )
        thread.daemon = True
        thread.start()

    def _process_thread(self, selected_files_paths, include_exts_set):
        start_time = time.time()
        try:
            directory_tree = get_tree_filtered_string(
                self.current_dir, allowed_extensions=tuple(include_exts_set))
            combined_text = "PROJECT DIRECTORY STRUCTURE:\n" + directory_tree + \
                "\n\n" + "=" * 20 + " FILE CONTENTS " + "=" * 20 + "\n\n"

            file_count = 0
            total_size = 0
            errors = []

            for file_path in selected_files_paths:
                try:
                    relative_path = os.path.relpath(
                        file_path, self.current_dir).replace("\\", "/")
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    combined_text += f"--- Start of {relative_path} ---\n{content}\n--- End of {relative_path} ---\n\n"
                    file_count += 1
                    total_size += len(content.encode('utf-8'))
                except Exception as e:
                    error_msg = f"Error reading {os.path.relpath(file_path, self.current_dir)}: {e}"
                    errors.append(error_msg)
                    print(error_msg)

            end_time = time.time()
            duration = end_time - start_time
            kb_size = total_size / 1024
            mb_size = kb_size / 1024
            size_str = f"{mb_size:.2f} MB" if mb_size >= 1 else f"{kb_size:.1f} KB"
            status_msg = f"Copied {file_count} files ({size_str}) in {duration:.2f}s."
            if errors:
                status_msg += f" ({len(errors)} errors occurred - check console)"

            self.after(0, lambda: self._update_after_processing(
                combined_text, status_msg))
        except Exception as e:
            import traceback
            print(f"Error during processing thread: {e}")
            traceback.print_exc()
            self.after(0, lambda: self.status_label.configure(
                text=f"Error: {e}"))

    def _update_after_processing(self, combined_text, status_msg):
        if combined_text:
            try:
                self.clipboard_clear()
                self.clipboard_append(combined_text)
                self.status_label.configure(text=status_msg)
            except Exception as e:
                error_txt = f"Error copying to clipboard: {e}. Text generated but not copied."
                print(error_txt)
                print("Length of text:", len(combined_text))
                self.status_label.configure(text=error_txt)
        else:
            self.status_label.configure(text="No content generated.")

# --- Helper get_tree_filtered_string ---


def get_tree_filtered_string(start_path, allowed_extensions=(), indent_char="    ", prefix=""):
    if path_contains_ignored_dir(start_path):
        return ""

    lines = []
    pointers = {"last": "└── ", "normal": "├── "}
    extender = {"last": indent_char, "normal": "│" + indent_char[1:]}

    try:
        with os.scandir(start_path) as it:
            entries = []
            for e in it:
                name = e.name
                entry_path = e.path
                if path_contains_ignored_dir(entry_path):
                    continue
                if e.is_file():
                    if is_ignored_file(name):
                        continue
                    _, ext = os.path.splitext(name)
                    if ext and ext.lower() in allowed_extensions:
                        entries.append(e)
                elif e.is_dir(follow_symlinks=False):
                    entries.append(e)
        entries.sort(key=lambda e: (e.is_file(), e.name.lower()))
    except OSError:
        return ""

    relevant_entries = entries  # already filtered

    for i, entry in enumerate(relevant_entries):
        is_last = (i == len(relevant_entries) - 1)
        pointer = pointers["last"] if is_last else pointers["normal"]
        extend = extender["last"] if is_last else extender["normal"]

        if entry.is_dir(follow_symlinks=False):
            subtree_str = get_tree_filtered_string(
                entry.path, allowed_extensions, indent_char, prefix + extend
            )
            if subtree_str:
                lines.append(prefix + pointer + entry.name + "/")
                lines.append(subtree_str)
        else:
            lines.append(prefix + pointer + entry.name)

    return "\n".join(lines)


if __name__ == "__main__":
    app = App()
    app.mainloop()
