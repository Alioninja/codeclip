import os
import threading
import customtkinter as ctk
from PIL import Image, ImageDraw

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Codebase to Clipboard")
        self.geometry("800x700")
        self.minsize(400, 500)

        self.current_dir = os.getcwd()
        self.allowed_exts = (".py", ".json", ".ipynb", ".txt", ".yml", ".sql")

        # Build folder tree (only for directories)
        self.folder_tree = self.build_folder_tree(self.current_dir)

        # Root files (files directly in current_dir)
        self.root_files = [
            f for f in os.listdir(self.current_dir)
            if os.path.isfile(os.path.join(self.current_dir, f))
            and not f.startswith(".")
            and f.endswith(self.allowed_exts)
        ]

        # State dictionaries
        self.folder_vars = {}
        self.folder_labels = {}
        # BooleanVars for files; keys are folder names (or "__root__")
        self.file_vars = {}
        self.file_labels = {}   # File label widgets, structured the same as file_vars
        self.folder_children = {}
        self.folder_parent = {}

        # Create custom checkbox images
        self.create_checkbox_images()

        # Main layout
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(pady=5, padx=5, fill="both", expand=True)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        content_frame = ctk.CTkFrame(main_frame)
        content_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        content_frame.grid_rowconfigure(0, weight=3)
        content_frame.grid_rowconfigure(1, weight=1)
        content_frame.grid_rowconfigure(2, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)

        # ── Folder Tree Section ─────────────────────────────────────────
        folder_section = ctk.CTkFrame(content_frame)
        folder_section.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        folder_header = ctk.CTkFrame(folder_section)
        folder_header.pack(fill="x", padx=2, pady=2)

        folder_title = ctk.CTkLabel(
            folder_header, text="Select Folders and Files:", anchor="w")
        folder_title.pack(side="left", padx=2, pady=2)

        folder_select_all_btn = ctk.CTkButton(
            folder_header, text="Select All", width=80, height=25,
            fg_color="grey", hover_color="#555555", command=self.select_all_folders
        )
        folder_select_all_btn.pack(side="right", padx=2, pady=2)

        folder_deselect_all_btn = ctk.CTkButton(
            folder_header, text="Deselect All", width=80, height=25,
            fg_color="grey", hover_color="#555555", command=self.deselect_all_folders
        )
        folder_deselect_all_btn.pack(side="right", padx=2, pady=2)

        self.folder_container = ctk.CTkScrollableFrame(folder_section)
        self.folder_container.pack(fill="both", expand=True, padx=2, pady=2)

        # ── Add Root Files (integrated into Folder Tree) ───────────────────
        if self.root_files:
            # Adjusted from 20 to 15
            root_files_frame = ctk.CTkFrame(self.folder_container)
            root_files_frame.pack(fill="x", padx=15, pady=2)

            self.file_vars["__root__"] = {}
            self.file_labels["__root__"] = {}
            for file in self.root_files:
                var = ctk.BooleanVar(value=False)

                file_line = ctk.CTkFrame(root_files_frame)
                file_line.pack(anchor="w", fill="x")

                file_placeholder = ctk.CTkLabel(file_line, text="", width=20)
                file_placeholder.pack(side="left", padx=(2, 5))

                file_label = ctk.CTkLabel(
                    file_line, text=file, image=self.unchecked_image,
                    compound="left", padx=5
                )
                file_label.pack(side="left", padx=2, pady=1)

                file_label.bind("<Button-1>", lambda event, folder="__root__",
                                f=file: self.on_file_label_click(folder, f))
                self.file_vars["__root__"][file] = var
                self.file_labels["__root__"][file] = file_label

        # Create folder UI for nested directories
        self.create_folder_ui(self.folder_tree, self.folder_container)

        # ── File Type Section ───────────────────────────────────────────
        type_section = ctk.CTkFrame(content_frame)
        type_section.grid(row=2, column=0, sticky="nsew", padx=5, pady=5)

        type_header = ctk.CTkFrame(type_section)
        type_header.pack(fill="x", padx=2, pady=2)

        filetype_label = ctk.CTkLabel(
            type_header, text="Select file types to include:", anchor="w")
        filetype_label.pack(side="left", padx=2, pady=2)

        filetype_select_all_btn = ctk.CTkButton(
            type_header, text="Select All", width=80, height=25,
            fg_color="grey", hover_color="#555555", command=self.select_all_filetypes
        )
        filetype_select_all_btn.pack(side="right", padx=2, pady=2)

        filetype_deselect_all_btn = ctk.CTkButton(
            type_header, text="Deselect All", width=80, height=25,
            fg_color="grey", hover_color="#555555", command=self.deselect_all_filetypes
        )
        filetype_deselect_all_btn.pack(side="right", padx=2, pady=2)

        filetype_container = ctk.CTkFrame(type_section, fg_color="transparent")
        filetype_container.pack(fill="x", expand=True, padx=2, pady=2)
        filetype_container.grid_columnconfigure(0, weight=1)
        filetype_container.grid_columnconfigure(1, weight=1)
        filetype_container.grid_columnconfigure(2, weight=1)

        self.include_py = ctk.BooleanVar(value=True)
        self.include_json = ctk.BooleanVar(value=True)
        self.include_ipynb = ctk.BooleanVar(value=True)
        self.include_txt = ctk.BooleanVar(value=True)
        self.include_yml = ctk.BooleanVar(value=True)
        self.include_sql = ctk.BooleanVar(value=True)

        py_check = ctk.CTkCheckBox(
            filetype_container, text=".py files", variable=self.include_py)
        py_check.grid(row=0, column=0, sticky="w", padx=2, pady=2)
        json_check = ctk.CTkCheckBox(
            filetype_container, text=".json files", variable=self.include_json)
        json_check.grid(row=0, column=1, sticky="w", padx=2, pady=2)
        ipynb_check = ctk.CTkCheckBox(
            filetype_container, text=".ipynb files", variable=self.include_ipynb)
        ipynb_check.grid(row=0, column=2, sticky="w", padx=2, pady=2)
        txt_check = ctk.CTkCheckBox(
            filetype_container, text=".txt files", variable=self.include_txt)
        txt_check.grid(row=1, column=0, sticky="w", padx=2, pady=2)
        yml_check = ctk.CTkCheckBox(
            filetype_container, text=".yml files", variable=self.include_yml)
        yml_check.grid(row=1, column=1, sticky="w", padx=2, pady=2)
        sql_check = ctk.CTkCheckBox(
            filetype_container, text=".sql files", variable=self.include_sql)
        sql_check.grid(row=1, column=2, sticky="w", padx=2, pady=2)

        # ── Footer Section ───────────────────────────────────────────────
        footer_frame = ctk.CTkFrame(main_frame)
        footer_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=5)
        footer_frame.grid_columnconfigure(0, weight=0)
        footer_frame.grid_columnconfigure(1, weight=1)

        process_btn = ctk.CTkButton(
            footer_frame,
            text="Generate Text and Copy to Clipboard",
            command=self.process_folders
        )
        process_btn.grid(row=0, column=0, padx=5, pady=5, sticky="w")

        self.status_label = ctk.CTkLabel(footer_frame, text="")
        self.status_label.grid(row=0, column=1, padx=5, pady=5, sticky="w")

    # ── Create Checkbox Images ─────────────────────────────────────────
    def create_checkbox_images(self):
        size = 20
        unchecked = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(unchecked)
        draw.rounded_rectangle([2, 2, size - 2, size - 2],
                               radius=4, outline="#CCCCCC", width=2)

        checked = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw_checked = ImageDraw.Draw(checked)
        draw_checked.rounded_rectangle(
            [2, 2, size - 2, size - 2], radius=4, outline="#CCCCCC", width=2)
        draw_checked.line(
            [(4, size // 2), (size // 2, size - 4)], fill="#4CAF50", width=2)
        draw_checked.line(
            [(size // 2, size - 4), (size - 4, 4)], fill="#4CAF50", width=2)

        indeterminate = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw_ind = ImageDraw.Draw(indeterminate)
        draw_ind.rounded_rectangle(
            [2, 2, size - 2, size - 2], radius=4, outline="#CCCCCC", width=2)
        draw_ind.line([(4, size // 2), (size - 4, size // 2)],
                      fill="#FFA500", width=2)

        self.unchecked_image = ctk.CTkImage(unchecked, size=(size, size))
        self.checked_image = ctk.CTkImage(checked, size=(size, size))
        self.indeterminate_image = ctk.CTkImage(
            indeterminate, size=(size, size))

    # ── Build Folder Tree ──────────────────────────────────────────────
    def build_folder_tree(self, base_path):
        tree = {}
        for entry in os.scandir(base_path):
            if entry.is_dir() and not entry.name.startswith(".") and entry.name.lower() != "venv":
                subfolder = os.path.join(base_path, entry.name)
                sub_tree = self.build_folder_tree(subfolder)
                files = [
                    f for f in os.listdir(subfolder)
                    if os.path.isfile(os.path.join(subfolder, f))
                    and f.endswith(self.allowed_exts)
                    and not f.startswith(".")
                ]
                if files or sub_tree:
                    tree[entry.name] = {"files": sorted(
                        files), "subfolders": sub_tree}
        return tree

    # ── Create UI for Each Folder ──────────────────────────────────────
    def create_folder_ui(self, tree, parent_frame, parent_rel_path=""):
        for folder, content in tree.items():
            folder_rel_path = os.path.join(
                parent_rel_path, folder) if parent_rel_path else folder

            # Record parent/children
            self.folder_children[folder_rel_path] = []
            if parent_rel_path:
                self.folder_parent[folder_rel_path] = parent_rel_path
                self.folder_children[parent_rel_path].append(folder_rel_path)
            else:
                self.folder_parent[folder_rel_path] = None

            # Outer frame for folder
            folder_frame = ctk.CTkFrame(parent_frame)
            folder_frame.pack(fill="x", padx=10, pady=2)

            # Header row: arrow/placeholder + folder checkbox label
            header_frame = ctk.CTkFrame(folder_frame)
            header_frame.pack(fill="x", padx=0, pady=0)

            has_children = bool(content["subfolders"] or content["files"])
            if has_children:
                dropdown_btn = ctk.CTkButton(
                    header_frame, text="▶", width=20, fg_color="transparent",
                    command=lambda ff=folder_frame: self.toggle_folder_contents(
                        ff)
                )
                dropdown_btn.pack(side="left", padx=(2, 5))
            else:
                placeholder = ctk.CTkLabel(header_frame, text="", width=20)
                placeholder.pack(side="left", padx=(2, 5))

            var = ctk.IntVar(value=0)
            self.folder_vars[folder_rel_path] = var

            folder_label = ctk.CTkLabel(
                header_frame, text=folder, image=self.unchecked_image,
                compound="left", padx=5
            )
            folder_label.pack(side="left", padx=2, pady=2)
            folder_label.bind("<Button-1>", lambda event,
                              frp=folder_rel_path: self.on_folder_label_click(frp))
            self.folder_labels[folder_rel_path] = folder_label

            # Contents container (files + subfolders), starts collapsed
            contents_container = ctk.CTkFrame(folder_frame)
            contents_container.pack(fill="x", padx=10, pady=2)
            contents_container.pack_forget()

            # Create file checkboxes for files in this folder
            if content["files"]:
                # Adjusted from 20 to 15 for additional indentation
                files_frame = ctk.CTkFrame(contents_container)
                files_frame.pack(fill="x", pady=2, padx=15)

                self.file_vars[folder_rel_path] = {}
                self.file_labels[folder_rel_path] = {}
                for file in content["files"]:
                    file_var = ctk.BooleanVar(value=False)
                    file_line = ctk.CTkFrame(files_frame)
                    file_line.pack(anchor="w", fill="x")

                    file_placeholder = ctk.CTkLabel(
                        file_line, text="", width=20)
                    file_placeholder.pack(side="left", padx=(2, 5))

                    file_label = ctk.CTkLabel(
                        file_line, text=file, image=self.unchecked_image,
                        compound="left", padx=5
                    )
                    file_label.pack(side="left", padx=2, pady=1)

                    file_label.bind("<Button-1>", lambda event, frp=folder_rel_path,
                                    f=file: self.on_file_label_click(frp, f))
                    self.file_vars[folder_rel_path][file] = file_var
                    self.file_labels[folder_rel_path][file] = file_label

            # Recursively create subfolders
            if content["subfolders"]:
                self.create_folder_ui(
                    content["subfolders"], contents_container, folder_rel_path)

    def toggle_folder_contents(self, folder_frame):
        contents = folder_frame.winfo_children()[1]
        dropdown_btn = folder_frame.winfo_children()[0].winfo_children()[0]
        if contents.winfo_ismapped():
            contents.pack_forget()
            dropdown_btn.configure(text="▶")
        else:
            contents.pack(fill="x", padx=10, pady=2)
            dropdown_btn.configure(text="▼")

    # ── Folder Selection Logic ─────────────────────────────────────────
    def on_folder_label_click(self, folder_rel_path):
        current_value = self.folder_vars[folder_rel_path].get()
        new_value = 1 if current_value != 1 else 0
        self.propagate_folder_selection(folder_rel_path, new_value)
        self.update_folder_image(folder_rel_path)
        self.update_parent_folder_state(folder_rel_path)

    def propagate_folder_selection(self, folder_rel_path, new_value):
        self.folder_vars[folder_rel_path].set(new_value)
        if folder_rel_path in self.file_vars:
            for file in self.file_vars[folder_rel_path]:
                self.file_vars[folder_rel_path][file].set(
                    True if new_value == 1 else False)
                self.update_file_image(folder_rel_path, file)
        for child in self.folder_children.get(folder_rel_path, []):
            self.propagate_folder_selection(child, new_value)
            self.update_folder_image(child)

    def update_parent_folder_state(self, folder_rel_path):
        parent = self.folder_parent.get(folder_rel_path)
        if parent is not None:
            new_state = self.recalc_folder_state(parent)
            self.folder_vars[parent].set(new_state)
            self.update_folder_image(parent)
            self.update_parent_folder_state(parent)

    def recalc_folder_state(self, folder_rel_path):
        states = []
        if folder_rel_path in self.file_vars:
            for var in self.file_vars[folder_rel_path].values():
                states.append(1 if var.get() else 0)
        for child in self.folder_children.get(folder_rel_path, []):
            states.append(self.folder_vars[child].get())

        if not states:
            return self.folder_vars.get(folder_rel_path, 0)
        if all(s == 1 for s in states):
            return 1
        if all(s == 0 for s in states):
            return 0
        return 2

    def update_folder_image(self, folder_rel_path):
        var = self.folder_vars[folder_rel_path]
        label = self.folder_labels[folder_rel_path]
        if var.get() == 0:
            label.configure(image=self.unchecked_image)
        elif var.get() == 1:
            label.configure(image=self.checked_image)
        else:
            label.configure(image=self.indeterminate_image)

    # ── File Selection Logic (for two-state checkboxes) ──────────────────
    def on_file_label_click(self, folder, file):
        current = self.file_vars[folder][file].get()
        new_value = not current
        self.file_vars[folder][file].set(new_value)
        self.update_file_image(folder, file)
        if folder != "__root__":
            self.on_file_change(folder)

    def update_file_image(self, folder, file):
        val = self.file_vars[folder][file].get()
        label = self.file_labels[folder][file]
        if val:
            label.configure(image=self.checked_image)
        else:
            label.configure(image=self.unchecked_image)

    def on_file_change(self, folder_rel_path):
        new_state = self.recalc_folder_state(folder_rel_path)
        if folder_rel_path in self.folder_vars:
            self.folder_vars[folder_rel_path].set(new_state)
            self.update_folder_image(folder_rel_path)
            self.update_parent_folder_state(folder_rel_path)

    # ── Buttons: Select/Deselect All ───────────────────────────────────
    def select_all_folders(self):
        for folder in self.folder_vars:
            self.propagate_folder_selection(folder, 1)
            self.update_folder_image(folder)
        # Also update root files if present
        if "__root__" in self.file_vars:
            for file in self.file_vars["__root__"]:
                self.file_vars["__root__"][file].set(True)
                self.update_file_image("__root__", file)

    def deselect_all_folders(self):
        for folder in self.folder_vars:
            self.propagate_folder_selection(folder, 0)
            self.update_folder_image(folder)
        # Also update root files if present
        if "__root__" in self.file_vars:
            for file in self.file_vars["__root__"]:
                self.file_vars["__root__"][file].set(False)
                self.update_file_image("__root__", file)

    def select_all_filetypes(self):
        self.include_py.set(True)
        self.include_json.set(True)
        self.include_ipynb.set(True)
        self.include_txt.set(True)
        self.include_yml.set(True)
        self.include_sql.set(True)

    def deselect_all_filetypes(self):
        self.include_py.set(False)
        self.include_json.set(False)
        self.include_ipynb.set(False)
        self.include_txt.set(False)
        self.include_yml.set(False)
        self.include_sql.set(False)

    # ── Processing ─────────────────────────────────────────────────────
    def process_folders(self):
        folder_selections = {f: var.get()
                             for f, var in self.folder_vars.items()}
        file_selections = {
            folder: {file: var.get() for file, var in files.items()}
            for folder, files in self.file_vars.items()
        }

        include_exts = []
        if self.include_py.get():
            include_exts.append(".py")
        if self.include_json.get():
            include_exts.append(".json")
        if self.include_ipynb.get():
            include_exts.append(".ipynb")
        if self.include_txt.get():
            include_exts.append(".txt")
        if self.include_yml.get():
            include_exts.append(".yml")
        if self.include_sql.get():
            include_exts.append(".sql")

        self.status_label.configure(text="Processing... please wait.")
        thread = threading.Thread(
            target=self._process_thread,
            args=(folder_selections, file_selections, include_exts)
        )
        thread.daemon = True
        thread.start()

    def _process_thread(self, folder_selections, file_selections, include_exts):
        directory_tree = get_tree_filtered_string(
            self.current_dir, allowed_extensions=tuple(include_exts)
        )

        combined_text = ""
        file_count = 0

        combined_text += "PROJECT DIRECTORY STRUCTURE:\n"
        combined_text += directory_tree + "\n\n"

        for folder, files in file_selections.items():
            for file, selected in files.items():
                if selected and any(file.endswith(ext) for ext in include_exts):
                    if folder == "__root__":
                        file_path = os.path.join(self.current_dir, file)
                        display_name = file
                    else:
                        file_path = os.path.join(
                            self.current_dir, folder, file)
                        display_name = os.path.join(folder, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        combined_text += f"----- {display_name} -----\n{content}\n\n"
                        file_count += 1
                    except Exception as e:
                        print(f"Error reading {file_path}: {e}")

        self.after(0, lambda: self._update_after_processing(
            combined_text, file_count))

    def _update_after_processing(self, combined_text, file_count):
        if combined_text:
            self.clipboard_clear()
            self.clipboard_append(combined_text)
            self.status_label.configure(
                text=f"Copied content from {file_count} file(s) to clipboard.")
        else:
            self.status_label.configure(text="No matching files found.")


def get_tree_filtered_string(path, allowed_extensions=(".py", ".ipynb", ".json"), indent=0):
    """
    Recursively build a string representing the directory tree,
    skipping .git and .codebase-to-text.py, and including only
    certain allowed file extensions.
    """
    lines = []
    for item in sorted(os.listdir(path)):
        if item in (".git", ".codebase-to-text.py"):
            continue

        item_path = os.path.join(path, item)
        prefix = "    " * indent + "|-- "

        if os.path.isdir(item_path):
            lines.append(prefix + item)
            subtree = get_tree_filtered_string(
                item_path, allowed_extensions, indent + 1)
            if subtree:
                lines.append(subtree)
        else:
            if item.endswith(allowed_extensions):
                lines.append(prefix + item)
    return "\n".join(lines)


if __name__ == "__main__":
    app = App()
    app.mainloop()
