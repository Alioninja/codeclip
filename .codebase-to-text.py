import os
import sys
import argparse
import fnmatch # For more powerful exclusion patterns in CLI/shared scan
from collections import Counter
import time
import threading # For GUI background processing

# --- Optional GUI Imports (handle potential ImportError if CLI-only use is desired without GUI deps) ---
try:
    import customtkinter as ctk
    from PIL import Image, ImageDraw
    GUI_ENABLED = True
except ImportError:
    GUI_ENABLED = False
    # Define dummy classes/functions if needed for type hinting or minimal structure
    # class CTk: pass
    # class CTkFrame: pass
    # etc. - Or just rely on the GUI_ENABLED check

# --- Shared Configuration ---
DEFAULT_IGNORED_DIRS = {".git", "__pycache__", "venv", ".venv",
                        ".vscode", "node_modules", ".idea", "build", "dist"}
DEFAULT_IGNORED_FILES = {".DS_Store"}
DEFAULT_ENCODING = "utf-8"

# --- GUI Specific Configuration (only used if GUI_ENABLED) ---
if GUI_ENABLED:
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    LIGHT_NESTED_BG = "#3c3c3c"
    DARK_NESTED_BG = "#303030"
    INDICATOR_WIDTH = 18
    NESTED_BG_PAD_X = 10
    NESTED_BG_CORNER_RADIUS = 6
    FILE_TYPE_SECTION_MAX_HEIGHT = 160
    INDENT_SIZE = 20

# =============================================================================
# >>> SHARED CORE LOGIC <<<
# =============================================================================

def scan_and_filter_files(start_path, include_exts=None, exclude_patterns=None, ignore_dirs=None, ignore_files=None, verbose=False):
    """
    Scans the directory, filters files based on extensions and exclusion patterns.
    (Adapted from CLI version for more robust filtering)

    Args:
        start_path (str): The root directory to scan.
        include_exts (set): Set of lowercase extensions to include (e.g., {'.py', '.js'}). If None, include all.
        exclude_patterns (list): List of patterns (like 'node_modules/', '*.log') to exclude.
        ignore_dirs (set): Set of directory names to always ignore.
        ignore_files (set): Set of file names to always ignore.
        verbose (bool): If True, print scanning/exclusion info to stderr.


    Returns:
        list: A sorted list of absolute file paths to include.
        Counter: Counts of all found extensions (before filtering by include_exts).
    """
    selected_files = []
    all_extension_counts = Counter() # Count all extensions found, before include/exclude
    abs_start_path = os.path.abspath(start_path)
    exclude_patterns = exclude_patterns or []
    ignore_dirs = ignore_dirs or DEFAULT_IGNORED_DIRS
    ignore_files = ignore_files or DEFAULT_IGNORED_FILES

    # Normalize exclude patterns to be relative to start_path if they aren't absolute
    normalized_excludes = []
    for pattern in exclude_patterns:
        if not os.path.isabs(pattern):
            # Treat patterns like 'node_modules' or '*.log' relative to start_path
            normalized_excludes.append(os.path.join(abs_start_path, pattern))
        else:
            normalized_excludes.append(pattern)
        # Add directory exclude patterns (e.g., 'node_modules' should match 'node_modules/')
        # Be careful not to add os.path.sep if pattern already includes wildcards for files
        base = os.path.basename(pattern)
        if not pattern.endswith(os.path.sep) and '*' not in base and '?' not in base and '.' not in base:
             normalized_excludes.append(os.path.join(abs_start_path, pattern) + os.path.sep)

    if verbose:
        print(f"Scanning directory: {abs_start_path}", file=sys.stderr)
        print(f"Ignoring dirs: {ignore_dirs}", file=sys.stderr)
        print(f"Ignoring files: {ignore_files}", file=sys.stderr)
        print(f"Excluding patterns: {exclude_patterns}", file=sys.stderr)
        print(f"Normalized exclude patterns: {normalized_excludes}", file=sys.stderr)
        print(f"Including extensions: {'All' if include_exts is None else include_exts}", file=sys.stderr)


    for root, dirs, files in os.walk(abs_start_path, topdown=True):
        rel_root = os.path.relpath(root, abs_start_path)
        if rel_root == '.':
            rel_root = '' # Avoid './' prefix for root level matching

        # --- Filter Directories ---
        original_dirs = list(dirs) # Keep original list for exclude pattern matching
        dirs[:] = [d for d in dirs if d not in ignore_dirs and not d.startswith('.')]

        dirs_to_remove_by_pattern = set()
        for d in original_dirs: # Check original names against patterns
             dir_path_abs = os.path.join(root, d)
             dir_path_rel_unix = os.path.join(rel_root, d).replace(os.path.sep, '/')

             for pattern in normalized_excludes:
                 pattern_unix = pattern.replace(os.path.sep, '/')
                 # Check absolute path and relative path (unix-style)
                 # Need to match the directory itself or the directory path ending with /
                 if fnmatch.fnmatch(dir_path_abs, pattern) or \
                    fnmatch.fnmatch(dir_path_abs + os.path.sep, pattern) or \
                    fnmatch.fnmatch(dir_path_rel_unix, pattern_unix) or \
                    fnmatch.fnmatch(dir_path_rel_unix + '/', pattern_unix):
                     if verbose: print(f"Excluding dir by pattern: {dir_path_abs} (matched {pattern})", file=sys.stderr)
                     if d in dirs: # Check if not already removed by ignore_dirs
                         dirs_to_remove_by_pattern.add(d)
                     break # Stop checking patterns for this dir

        dirs[:] = [d for d in dirs if d not in dirs_to_remove_by_pattern]


        # --- Filter and Process Files ---
        for file in files:
            if file in ignore_files or file.startswith('.'):
                continue

            file_path_abs = os.path.join(root, file)
            file_path_rel_unix = os.path.join(rel_root, file).replace(os.path.sep, '/')

            # Count all extensions first
            _, ext = os.path.splitext(file)
            if ext:
                all_extension_counts[ext.lower()] += 1

            # Check against exclude patterns
            excluded_by_pattern = False
            for pattern in normalized_excludes:
                pattern_unix = pattern.replace(os.path.sep, '/')
                if fnmatch.fnmatch(file_path_abs, pattern) or fnmatch.fnmatch(file_path_rel_unix, pattern_unix):
                    if verbose: print(f"Excluding file by pattern: {file_path_abs} (matched {pattern})", file=sys.stderr)
                    excluded_by_pattern = True
                    break
            if excluded_by_pattern:
                continue

            # Check if extension is included (if include_exts is specified)
            if include_exts is None or (ext and ext.lower() in include_exts):
                selected_files.append(file_path_abs)

    return sorted(selected_files), all_extension_counts


def get_tree_string_for_selected(start_path, selected_files, indent_char="    "):
    """
    Generates a tree string showing only selected files and their necessary parent directories.
    (Adapted from CLI version)
    """
    lines = []
    abs_start_path = os.path.abspath(start_path)
    structure = {} # {dirpath: {'dirs': set(), 'files': set()}}

    # Build the structure needed based *only* on selected files
    for file_path in selected_files:
        # Ensure the file is within the start_path before processing
        if not file_path.startswith(abs_start_path):
            print(f"Warning: Skipping file outside start path for tree: {file_path}", file=sys.stderr)
            continue
        rel_path = os.path.relpath(file_path, abs_start_path)
        parts = rel_path.split(os.path.sep)
        current_path_abs = abs_start_path
        for i, part in enumerate(parts):
            parent_path_abs = current_path_abs
            current_path_abs = os.path.join(current_path_abs, part)
            if parent_path_abs not in structure:
                 structure[parent_path_abs] = {'dirs': set(), 'files': set()}

            if i < len(parts) - 1: # It's a directory
                structure[parent_path_abs]['dirs'].add(part)
            else: # It's the file
                structure[parent_path_abs]['files'].add(part)

    # Recursive function to build the string from the structure
    def build_lines(current_dir_abs, current_prefix=""):
        if current_dir_abs not in structure:
            return []

        # Sort dirs and files alphabetically
        dir_entries = sorted(list(structure[current_dir_abs]['dirs']), key=str.lower)
        file_entries = sorted(list(structure[current_dir_abs]['files']), key=str.lower)
        entries = dir_entries + file_entries # Dirs first, then files

        local_lines = []
        pointers = {"last": "└── ", "normal": "├── "}
        extender = {"last": "    ", "normal": "│   "} # Standard tree extenders

        for i, entry_name in enumerate(entries):
            is_last = (i == len(entries) - 1)
            pointer = pointers["last"] if is_last else pointers["normal"]
            extend = extender["last"] if is_last else extender["normal"]
            entry_path_abs = os.path.join(current_dir_abs, entry_name)

            # Check if it's a directory we recorded
            is_dir = entry_name in structure[current_dir_abs]['dirs']

            if is_dir:
                 local_lines.append(current_prefix + pointer + entry_name + "/")
                 # Important: Recurse with the *absolute* path
                 local_lines.extend(build_lines(entry_path_abs, current_prefix + extend))
            else: # It must be a file
                 local_lines.append(current_prefix + pointer + entry_name)
        return local_lines

    # Start building from the root absolute path
    tree_root_name = os.path.basename(abs_start_path)
    lines = [f"{tree_root_name}/"]
    lines.extend(build_lines(abs_start_path))
    return "\n".join(lines)


def read_files_and_combine(selected_files, start_path, encoding=DEFAULT_ENCODING):
    """Reads content of selected files and combines them with delimiters."""
    combined_parts = []
    file_count = 0
    total_size = 0
    errors = []
    abs_start_path = os.path.abspath(start_path)

    for file_path in selected_files:
        try:
            # Use relative path from the *original* start_path for clarity
            relative_path = os.path.relpath(file_path, abs_start_path).replace(os.path.sep, "/")
            with open(file_path, "r", encoding=encoding, errors="ignore") as f:
                content = f.read()
            combined_parts.append(f"--- Start of {relative_path} ---")
            combined_parts.append(content)
            combined_parts.append(f"--- End of {relative_path} ---\n")
            file_count += 1
            # Estimate size using specified encoding
            total_size += len(content.encode(encoding, errors='ignore'))
        except Exception as e:
            error_msg = f"Error reading {os.path.relpath(file_path, abs_start_path)}: {e}"
            errors.append(error_msg)
            print(error_msg, file=sys.stderr) # Also print error immediately

    return "\n".join(combined_parts), file_count, total_size, errors

# =============================================================================
# >>> GUI IMPLEMENTATION <<<
# =============================================================================

if GUI_ENABLED:
    class App(ctk.CTk):
        def __init__(self):
            super().__init__()
            self.title("Codebase to Text")
            self.geometry("800x700")
            self.minsize(500, 600)

            # Config access (using constants defined above)
            self.light_nested_bg = LIGHT_NESTED_BG
            self.dark_nested_bg = DARK_NESTED_BG
            self.indicator_width = INDICATOR_WIDTH
            self.nested_bg_pad_x = NESTED_BG_PAD_X
            self.nested_bg_corner_radius = NESTED_BG_CORNER_RADIUS
            self.indent_size = INDENT_SIZE

            self.current_dir = os.getcwd()

            # --- Initial Simple Scan for UI population ---
            # This scan is faster and only for populating the initial UI checkboxes.
            # The final processing will use the more robust scan if needed, or just the selected files.
            self.file_extension_counts_initial = self.scan_file_extensions_simple(
                self.current_dir)
            self.sorted_extensions = sorted(self.file_extension_counts_initial.keys(),
                                            key=lambda ext: self.file_extension_counts_initial[ext],
                                            reverse=True)

            self.folder_tree = self.build_folder_tree(self.current_dir)

            # State dictionaries (remain GUI specific)
            self.folder_vars = {}
            self.folder_labels = {}
            self.file_vars = {}
            self.file_labels = {}
            self.folder_children = {}
            self.folder_parent = {}
            self.file_type_vars = {}
            self.file_type_checkboxes = {}
            self.folder_widget_refs = {}
            self.folder_states = {}

            self.create_checkbox_images()

            # --- Main layout ---
            main_frame = ctk.CTkFrame(self, fg_color="transparent")
            main_frame.pack(pady=10, padx=10, fill="both", expand=True)
            main_frame.grid_rowconfigure(0, weight=1)
            main_frame.grid_columnconfigure(0, weight=1)
            main_frame.grid_rowconfigure(1, weight=0) # File types (fixed height)
            main_frame.grid_rowconfigure(2, weight=0) # Footer

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
            type_section_container.grid_columnconfigure(0, weight=1)
            type_section_container.grid_rowconfigure(1, weight=0) # Fixed height scroll container

            type_header = ctk.CTkFrame(
                type_section_container, fg_color="transparent")
            type_header.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 2))

            filetype_label = ctk.CTkLabel(
                type_header, text="Include files of type:", anchor="w")
            filetype_label.pack(side="left", padx=(0, 10))

            type_button_frame = ctk.CTkFrame(type_header, fg_color="transparent")
            type_button_frame.pack(side="right")

            filetype_deselect_all_btn = ctk.CTkButton(
                type_button_frame, text="Deselect All", width=100, height=28, command=self.deselect_all_filetypes)
            filetype_deselect_all_btn.pack(side="right", padx=(5, 0))

            filetype_select_all_btn = ctk.CTkButton(
                type_button_frame, text="Select All", width=100, height=28, command=self.select_all_filetypes)
            filetype_select_all_btn.pack(side="right", padx=0)

            type_scroll_container = ctk.CTkFrame(
                type_section_container, height=FILE_TYPE_SECTION_MAX_HEIGHT)
            type_scroll_container.grid(
                row=1, column=0, sticky="nsew", padx=5, pady=(0, 5))
            type_scroll_container.grid_propagate(False)
            type_scroll_container.grid_rowconfigure(0, weight=1)
            type_scroll_container.grid_columnconfigure(0, weight=1)

            filetype_scrollable_frame = ctk.CTkScrollableFrame(
                type_scroll_container, fg_color="transparent")
            filetype_scrollable_frame.grid(row=0, column=0, sticky="nsew")
            filetype_scrollable_frame.grid_columnconfigure((0, 1, 2), weight=1)

            num_columns = 3
            for i, ext in enumerate(self.sorted_extensions):
                var = ctk.BooleanVar(value=True)
                self.file_type_vars[ext] = var
                count = self.file_extension_counts_initial.get(ext, 0)
                label_text = f"{ext} ({count})" # Shortened label
                checkbox = ctk.CTkCheckBox(
                    filetype_scrollable_frame, text=label_text, variable=var,
                    command=self.update_file_type_counts # Update counts on change
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
                footer_frame, text="Generate & Copy", height=32, command=self.process_folders)
            process_btn.grid(row=0, column=0, padx=(0, 10), pady=5, sticky="w")

            self.status_label = ctk.CTkLabel(footer_frame, text="", anchor="w")
            self.status_label.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

            # --- Set Initial State ---
            self.select_all_folders() # Select all folders/files initially
            self.update_file_type_counts() # Update counts based on initial selection
            self.after(10, self.collapse_all_folders) # Collapse folders after UI setup


        # --- GUI Specific Methods (Simplified or adapted from original GUI code) ---

        def scan_file_extensions_simple(self, base_path):
            """A simplified scan just for populating the UI checkboxes quickly."""
            extension_counts = Counter()
            try:
                for root, dirs, files in os.walk(base_path, topdown=True):
                    # Use shared ignore lists
                    dirs[:] = [d for d in dirs if d not in DEFAULT_IGNORED_DIRS and not d.startswith(".")]
                    files[:] = [f for f in files if f not in DEFAULT_IGNORED_FILES and not f.startswith(".")]

                    for file in files:
                        _, ext = os.path.splitext(file)
                        if ext:
                            extension_counts[ext.lower()] += 1
            except OSError as e:
                print(f"Error during initial scan: {e}", file=sys.stderr)
            return extension_counts

        def create_checkbox_images(self):
            # This method remains largely the same as in the original GUI code
            # It depends on customtkinter ThemeManager
            size = 18
            border_width = 2
            check_width = 2
            radius = 3
            try:
                # Corrected access using customtkinter directly
                theme_data = ctk.ThemeManager.theme
                fg_color = theme_data["CTkCheckBox"]["fg_color"][1] # Index 1 for dark mode usually
                border_color_checked = theme_data["CTkCheckBox"]["border_color"][1]
                checkmark_color = theme_data["CTkCheckBox"]["checkmark_color"][1]
                # Validate checkmark_color: if it's invalid, use a fallback hex code
                try:
                    from PIL import ImageColor
                    ImageColor.getrgb(checkmark_color)
                except ValueError:
                    checkmark_color = "#FFFFFF"
                # Use a default text color for unchecked border if Label text color isn't reliable
                border_color_unchecked = theme_data.get("CTkLabel", {}).get("text_color", ["#000000", "#DCE4EE"])[1]
                indeterminate_color = "#E67E22" # Slightly different orange
                indeterminate_line_color = "#FFFFFF" # White line (indeterminate)
            except Exception as e:
                 print(f"Warning: Using fallback checkbox colors due to theme error: {e}")
                 # Fallback colors (ensure these contrast with your theme)
                 fg_color = "#2ECC71" # Green check fill
                 border_color_checked = "#2ECC71" # Green border (checked)
                 checkmark_color = "#FFFFFF" # White checkmark
                 border_color_unchecked = "#888888" # Grey border (unchecked)
                 indeterminate_color = "#E67E22" # Orange fill (indeterminate)
                 indeterminate_line_color = "#FFFFFF" # White line (indeterminate)

            # --- Unchecked ---
            unchecked = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(unchecked)
            rect_coords = [border_width // 2, border_width // 2,
                           size - border_width // 2 - 1, size - border_width // 2 - 1]
            draw.rounded_rectangle(rect_coords, radius=radius,
                                   outline=border_color_unchecked, width=border_width)
            self.unchecked_image = ctk.CTkImage(light_image=unchecked, dark_image=unchecked, size=(size, size))

            # --- Checked ---
            checked = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            draw_checked = ImageDraw.Draw(checked)
            draw_checked.rounded_rectangle(
                rect_coords, radius=radius, outline=border_color_checked, fill=fg_color, width=border_width)
            p1 = (size * 0.2, size * 0.5)
            p2 = (size * 0.45, size * 0.7)
            p3 = (size * 0.75, size * 0.3)
            draw_checked.line([p1, p2, p3], fill=checkmark_color, width=check_width, joint="round")
            self.checked_image = ctk.CTkImage(light_image=checked, dark_image=checked, size=(size, size))

            # --- Indeterminate ---
            indeterminate = Image.new("RGBA", (size, size), (0, 0, 0, 0))
            draw_ind = ImageDraw.Draw(indeterminate)
            draw_ind.rounded_rectangle(
                rect_coords, radius=radius, outline=border_color_checked, fill=indeterminate_color, width=border_width)
            y_center = size // 2
            x_start = size * 0.25
            x_end = size * 0.75
            draw_ind.line([(x_start, y_center), (x_end, y_center)], fill=indeterminate_line_color, width=check_width)
            self.indeterminate_image = ctk.CTkImage(light_image=indeterminate, dark_image=indeterminate, size=(size, size))


        def build_folder_tree(self, base_path):
            # This method builds the *internal* representation used by the GUI tree UI
            # It should respect the ignore lists.
            tree = {"subfolders": {}, "files": []}
            try:
                dirs = []
                files_in_dir = []
                for entry in os.scandir(base_path):
                    if entry.name in DEFAULT_IGNORED_DIRS or entry.name.startswith("."):
                        continue
                    if entry.is_dir():
                        dirs.append(entry)
                    elif entry.is_file() and entry.name not in DEFAULT_IGNORED_FILES:
                         # Check if the file extension was found in the initial scan
                        _, ext = os.path.splitext(entry.name)
                        if ext and ext.lower() in self.file_extension_counts_initial:
                             files_in_dir.append(entry.name)

                tree["files"] = sorted(files_in_dir, key=str.lower)
                dirs.sort(key=lambda e: e.name.lower())

                for entry in dirs:
                    sub_tree = self.build_folder_tree(entry.path)
                    # Only add subfolders if they contain relevant files or subfolders
                    if sub_tree.get("subfolders") or sub_tree.get("files"):
                        tree["subfolders"][entry.name] = sub_tree
            except OSError:
                pass # Ignore permission errors etc. for UI building
            return tree


        def create_folder_ui(self, tree_node, parent_frame, parent_rel_path="", level=0):
            # This method builds the actual customtkinter widgets for the tree view.
            # It remains largely the same as in the original GUI code.
            item_level = level + 1

            if "subfolders" in tree_node:
                for folder, sub_tree_node in sorted(tree_node["subfolders"].items()):
                    folder_rel_path = os.path.join(parent_rel_path, folder) if parent_rel_path else folder
                    has_children = bool(sub_tree_node.get("subfolders") or sub_tree_node.get("files"))

                    self.folder_children.setdefault(folder_rel_path, [])
                    self.folder_parent[folder_rel_path] = parent_rel_path
                    if parent_rel_path is not None: # Root ('') needs this check
                        self.folder_children.setdefault(parent_rel_path, []).append(folder_rel_path)
                    self.folder_states[folder_rel_path] = False # Default closed

                    folder_item_container = ctk.CTkFrame(parent_frame, fg_color="transparent")
                    folder_item_container.pack(fill="x", pady=0, padx=0)

                    # Frame for Header (Indicator + Label)
                    header_frame = ctk.CTkFrame(folder_item_container, fg_color="transparent")
                    # Apply indent to the header frame itself for structure
                    header_indent = item_level * self.indent_size if parent_frame != self.folder_container else 0
                    header_frame.pack(fill="x", pady=(1, 0), padx=(header_indent, 0))


                    indicator_text = "▶ " if has_children else "   " # More padding if no children
                    dropdown_indicator = ctk.CTkLabel(header_frame, text=indicator_text, width=self.indicator_width, anchor="w", padx=0)
                    dropdown_indicator.pack(side="left")

                    var = ctk.IntVar(value=0) # 0=unchecked, 1=checked, 2=indeterminate
                    self.folder_vars[folder_rel_path] = var

                    folder_label = ctk.CTkLabel(
                        header_frame, text=folder, image=self.unchecked_image, compound="left",
                        padx=5, anchor="w"
                    )
                    folder_label.pack(side="left", pady=1, fill="x", expand=True)
                    self.folder_labels[folder_rel_path] = folder_label

                    # Frame for nested content (indented and with background)
                    bg_color = self.dark_nested_bg if item_level % 2 != 0 else self.light_nested_bg # Alternate bg
                    content_bg_frame = ctk.CTkFrame(
                         folder_item_container, fg_color=bg_color,
                         corner_radius=self.nested_bg_corner_radius
                    )
                    # Content frame will be packed/unpacked by toggle, initially hidden

                    contents_container = ctk.CTkFrame(content_bg_frame, fg_color="transparent")
                    contents_container.pack(fill="both", expand=True, padx=self.nested_bg_pad_x, pady=(2,5)) # Padding inside bg


                    self.folder_widget_refs[folder_rel_path] = {
                        "indicator": dropdown_indicator,
                        "content_frame": content_bg_frame, # The one with the background
                        "contents_container": contents_container, # The one inside for children
                        "header_frame": header_frame,
                        "level": item_level,
                    }

                    # Bindings
                    folder_label.bind("<Button-1>", lambda e, frp=folder_rel_path: self.on_folder_label_click(frp))
                    if has_children:
                        dropdown_indicator.bind("<Button-1>", lambda e, frp=folder_rel_path: self.toggle_folder_by_path(frp))
                        # Allow double-click on label to toggle too
                        folder_label.bind("<Double-Button-1>", lambda e, frp=folder_rel_path: self.toggle_folder_by_path(frp))

                    # Recursively create UI for children inside the 'contents_container'
                    self.create_folder_ui(sub_tree_node, contents_container, folder_rel_path, level=item_level)

            # Create UI for files within the current level
            if "files" in tree_node and tree_node["files"]:
                self.file_vars.setdefault(parent_rel_path, {})
                self.file_labels.setdefault(parent_rel_path, {})

                for file in sorted(tree_node["files"]):
                    file_var = ctk.BooleanVar(value=False) # Files start unchecked unless Select All is used

                    file_line = ctk.CTkFrame(parent_frame, fg_color="transparent")
                     # Apply indent to the file line frame
                    file_indent = (item_level + 1) * self.indent_size if parent_frame != self.folder_container else self.indent_size
                    file_line.pack(anchor="w", fill="x", padx=(file_indent, 0), pady=(1, 0))


                    # Placeholder for alignment with folder indicators
                    file_placeholder = ctk.CTkLabel(file_line, text="   ", width=self.indicator_width, anchor="w", padx=0)
                    file_placeholder.pack(side="left")

                    file_label = ctk.CTkLabel(
                        file_line, text=file, image=self.unchecked_image, compound="left",
                        padx=5, anchor="w"
                    )
                    file_label.pack(side="left", pady=1, fill="x", expand=True)

                    file_label.bind("<Button-1>", lambda e, frp=parent_rel_path, f=file: self.on_file_label_click(frp, f))

                    self.file_vars[parent_rel_path][file] = file_var
                    self.file_labels[parent_rel_path][file] = file_label

        # --- Event Handlers and Logic (Mostly from original GUI code) ---

        def toggle_folder_by_path(self, folder_rel_path):
            refs = self.folder_widget_refs.get(folder_rel_path)
            if not refs: return

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
                # Indent the background frame relative to its container
                content_indent = item_level * self.indent_size
                content_frame.pack(fill="x", pady=(0, 5), padx=(content_indent, 0), after=header_frame)
                indicator_label.configure(text="▼ ")
                self.folder_states[folder_rel_path] = True

        def collapse_all_folders(self):
             for folder_path, is_open in list(self.folder_states.items()):
                 if is_open:
                      self.toggle_folder_by_path(folder_path) # Reuse toggle logic


        def on_folder_label_click(self, folder_rel_path):
            # Folder state propagation logic (remains GUI specific)
            if folder_rel_path not in self.folder_vars: return
            current_value = self.folder_vars[folder_rel_path].get()
            new_value = 1 if current_value != 1 else 0 # Toggle between checked/unchecked
            self._propagate_folder_selection_down(folder_rel_path, new_value)
            parent_path = self.folder_parent.get(folder_rel_path)
            if parent_path is not None: # Need to check for None, not just falsy
                 self._update_parent_folder_state_up(parent_path)
            self.update_file_type_counts() # Recalculate counts

        def _propagate_folder_selection_down(self, folder_rel_path, target_state):
            # Folder state propagation logic (remains GUI specific)
            if folder_rel_path not in self.folder_vars: return

            self.folder_vars[folder_rel_path].set(target_state)
            self.update_folder_image(folder_rel_path)
            is_checked = (target_state == 1)

            # Propagate to child files
            if folder_rel_path in self.file_vars:
                for file, file_var in self.file_vars[folder_rel_path].items():
                    if file_var.get() != is_checked:
                        file_var.set(is_checked)
                        self.update_file_image(folder_rel_path, file)

            # Propagate to child folders
            for child_path in self.folder_children.get(folder_rel_path, []):
                if child_path in self.folder_vars: # Check if child folder exists in UI
                    self._propagate_folder_selection_down(child_path, target_state)


        def _update_parent_folder_state_up(self, folder_rel_path):
            # Folder state propagation logic (remains GUI specific)
            # Handle the root case correctly (parent_rel_path can be "")
            if folder_rel_path is None: return # Reached top

            if folder_rel_path == "" or folder_rel_path in self.folder_vars:
                new_state = self._recalculate_folder_state(folder_rel_path)

                # Handle root ('') state update - it doesn't have its own var/label
                if folder_rel_path == "":
                     # If root state changed (implicitly), update its parent (None) - stop condition
                     parent = self.folder_parent.get(folder_rel_path) # Should be None
                     if parent is not None: # This check might be redundant here
                          self._update_parent_folder_state_up(parent)
                     return # Stop recursion for root

                # For non-root folders with vars
                current_state = self.folder_vars[folder_rel_path].get()
                if current_state != new_state:
                    self.folder_vars[folder_rel_path].set(new_state)
                    self.update_folder_image(folder_rel_path)
                    parent = self.folder_parent.get(folder_rel_path)
                    # Check parent is not None before recursing
                    if parent is not None:
                         self._update_parent_folder_state_up(parent)

        def _recalculate_folder_state(self, folder_rel_path):
            # Folder state propagation logic (remains GUI specific)
            # Determines if a folder should be checked, unchecked, or indeterminate

            has_any_child = False
            all_checked = True
            all_unchecked = True

            # Check state of files directly within this folder
            if folder_rel_path in self.file_vars:
                for file_var in self.file_vars[folder_rel_path].values():
                    has_any_child = True
                    if file_var.get(): # Checked
                        all_unchecked = False
                    else: # Unchecked
                        all_checked = False
                    if not all_checked and not all_unchecked:
                         # If we have both checked and unchecked files, state is indeterminate
                        return 2

            # Check state of subfolders
            for child_folder_path in self.folder_children.get(folder_rel_path, []):
                if child_folder_path in self.folder_vars: # Ensure child folder exists
                    has_any_child = True
                    child_state = self.folder_vars[child_folder_path].get()
                    if child_state == 1: # Child fully checked
                        all_unchecked = False
                    elif child_state == 0: # Child fully unchecked
                        all_checked = False
                    elif child_state == 2: # Child indeterminate
                        # If any child is indeterminate, parent must be indeterminate
                        return 2
                    # Check if state became indeterminate from children mix
                    if not all_checked and not all_unchecked:
                         return 2

            if not has_any_child:
                 # If it's an empty folder displayed in the UI, reflect its own var state
                 # This case might be rare if empty folders are pre-filtered by build_folder_tree
                 if folder_rel_path in self.folder_vars:
                     return self.folder_vars[folder_rel_path].get()
                 else:
                     return 0 # Default to unchecked if somehow it has no var

            # Determine final state based on children
            if all_checked: return 1
            if all_unchecked: return 0
            return 2 # Otherwise indeterminate

        def update_folder_image(self, folder_rel_path):
             # Updates the visual state of a folder label's checkbox image
            if folder_rel_path not in self.folder_labels or folder_rel_path not in self.folder_vars: return
            label = self.folder_labels[folder_rel_path]
            state = self.folder_vars[folder_rel_path].get()
            img = self.unchecked_image
            if state == 1: img = self.checked_image
            elif state == 2: img = self.indeterminate_image

            if label.winfo_exists(): # Check widget exists before configuring
                label.configure(image=img)


        def on_file_label_click(self, folder_rel_path, file):
             # Handles clicking on a file label
            if folder_rel_path not in self.file_vars or file not in self.file_vars[folder_rel_path]: return

            current_val = self.file_vars[folder_rel_path][file].get()
            self.file_vars[folder_rel_path][file].set(not current_val) # Toggle state
            self.update_file_image(folder_rel_path, file)
            # Update parent folder states upwards
            self._update_parent_folder_state_up(folder_rel_path)
            self.update_file_type_counts() # Recalculate counts

        def update_file_image(self, folder_rel_path, file):
            # Updates the visual state of a file label's checkbox image
            if (folder_rel_path not in self.file_labels or
                    file not in self.file_labels[folder_rel_path] or
                    folder_rel_path not in self.file_vars or
                    file not in self.file_vars[folder_rel_path]):
                return

            label = self.file_labels[folder_rel_path][file]
            var = self.file_vars[folder_rel_path][file]
            img = self.checked_image if var.get() else self.unchecked_image
            if label.winfo_exists():
                label.configure(image=img)


        def select_all_folders(self):
            # Selects all folders and files displayed in the tree
            # Handle root-level files first
            if "" in self.file_vars:
                 for file, file_var in self.file_vars[""].items():
                      if not file_var.get():
                           file_var.set(True)
                           self.update_file_image("", file)

            # Propagate 'checked' state down from top-level folders
            for folder_rel_path in self.folder_vars:
                 # Only start propagation from folders directly under the root ('')
                 if self.folder_parent.get(folder_rel_path) == "":
                     if self.folder_vars[folder_rel_path].get() != 1:
                         self._propagate_folder_selection_down(folder_rel_path, 1) # 1 = checked

            # Explicitly update root parents if they exist (though root itself has no UI var)
            # This might not be strictly necessary if propagation handles all cases
            # self._update_parent_folder_state_up("") # Redundant?

            self.update_file_type_counts()


        def deselect_all_folders(self):
            # Deselects all folders and files displayed in the tree
            # Handle root-level files first
            if "" in self.file_vars:
                 for file, file_var in self.file_vars[""].items():
                      if file_var.get():
                           file_var.set(False)
                           self.update_file_image("", file)

            # Propagate 'unchecked' state down from top-level folders
            for folder_rel_path in self.folder_vars:
                 if self.folder_parent.get(folder_rel_path) == "":
                      if self.folder_vars[folder_rel_path].get() != 0:
                          self._propagate_folder_selection_down(folder_rel_path, 0) # 0 = unchecked

            # self._update_parent_folder_state_up("") # Redundant?

            self.update_file_type_counts()


        def select_all_filetypes(self):
             # Checks all file type checkboxes
            changed = False
            for var in self.file_type_vars.values():
                if not var.get():
                    var.set(True)
                    changed = True
            if changed:
                 self.update_file_type_counts()

        def deselect_all_filetypes(self):
            # Unchecks all file type checkboxes
            changed = False
            for var in self.file_type_vars.values():
                if var.get():
                    var.set(False)
                    changed = True
            if changed:
                 self.update_file_type_counts()


        def update_file_type_counts(self):
             # Updates the counts displayed next to file type checkboxes based on current *selection* in the tree
            current_counts = Counter()
            selected_exts_types = {ext.lower() for ext, var in self.file_type_vars.items() if var.get()}

            # Iterate through all selected files in the tree view state
            # Check root files first
            if "" in self.file_vars:
                 for file, var in self.file_vars[""].items():
                      if var.get():
                           _, ext = os.path.splitext(file)
                           if ext and ext.lower() in selected_exts_types:
                                current_counts[ext.lower()] += 1

            # Check files within selected/indeterminate folders
            q = list(self.folder_children.get("", [])) # Start with top-level folders
            visited_folders = set()

            while q:
                folder_path = q.pop(0)
                if folder_path in visited_folders or folder_path not in self.folder_vars:
                     continue
                visited_folders.add(folder_path)

                folder_state = self.folder_vars[folder_path].get()

                # Only count files if the folder is checked (1) or indeterminate (2)
                if folder_state in [1, 2]:
                    # Count files directly in this folder
                    if folder_path in self.file_vars:
                        for file, var in self.file_vars[folder_path].items():
                            if var.get(): # Double-check file var is checked
                                _, ext = os.path.splitext(file)
                                if ext and ext.lower() in selected_exts_types:
                                    current_counts[ext.lower()] += 1
                    # Add children to queue if folder is checked or indeterminate
                    for subfolder_path in self.folder_children.get(folder_path, []):
                        if subfolder_path not in visited_folders:
                             q.append(subfolder_path)


            # Update the checkbox labels
            for ext, checkbox in self.file_type_checkboxes.items():
                count = current_counts.get(ext, 0)
                # Find the original total count for display consistency
                total_count = self.file_extension_counts_initial.get(ext, 0)
                label_text = f"{ext} ({count}/{total_count})" # Show selected/total
                if checkbox.winfo_exists():
                    checkbox.configure(text=label_text)

        # --- Processing (uses shared core functions) ---

        def process_folders(self):
            """Initiates the process of collecting selected files and generating output."""
            selected_exts_to_include = {ext.lower()
                                    for ext, var in self.file_type_vars.items() if var.get()}
            selected_files_paths = [] # Store absolute paths

            # Collect selected files based on tree state
            abs_current_dir = os.path.abspath(self.current_dir)

            # Check root files
            if "" in self.file_vars:
                 for file, var in self.file_vars[""].items():
                     if var.get():
                          _, ext = os.path.splitext(file)
                          if ext and ext.lower() in selected_exts_to_include:
                               full_path = os.path.join(abs_current_dir, file)
                               selected_files_paths.append(full_path)

            # Check files within folders using the state vars
            q = list(self.folder_children.get("", [])) # Start with top-level folders
            visited_folders = set()

            while q:
                folder_rel_path = q.pop(0)
                if folder_rel_path in visited_folders or folder_rel_path not in self.folder_vars:
                     continue
                visited_folders.add(folder_rel_path)

                folder_state = self.folder_vars[folder_rel_path].get()

                # Only process folder if checked(1) or indeterminate(2)
                if folder_state in [1, 2]:
                     # Add files directly within this folder
                     if folder_rel_path in self.file_vars:
                          for file, var in self.file_vars[folder_rel_path].items():
                               if var.get(): # Ensure file itself is checked
                                    _, ext = os.path.splitext(file)
                                    if ext and ext.lower() in selected_exts_to_include:
                                         full_path = os.path.join(abs_current_dir, folder_rel_path, file)
                                         selected_files_paths.append(full_path)

                     # Add subfolders to the queue regardless of their own state if parent is checked/indeterminate
                     # The check will happen when the subfolder itself is processed
                     for subfolder_path in self.folder_children.get(folder_rel_path, []):
                          if subfolder_path not in visited_folders:
                              q.append(subfolder_path)

            if not selected_files_paths:
                self.status_label.configure(text="No files selected or matching included types.")
                return

            # Sort the final list for consistent output
            selected_files_paths.sort()

            self.status_label.configure(text="Processing... please wait.")
            self.update_idletasks() # Ensure UI updates before blocking thread starts

            # Run processing in background thread
            thread = threading.Thread(
                target=self._process_thread,
                args=(selected_files_paths,),
                daemon=True
            )
            thread.start()

        def _process_thread(self, selected_files_paths):
            """Background thread for generating tree and content."""
            start_time = time.time()
            try:
                # Generate tree using the SHARED function based on FINAL selected files
                tree_string = get_tree_string_for_selected(self.current_dir, selected_files_paths)

                # Read and combine content using the SHARED function
                combined_content, file_count, total_size, errors = read_files_and_combine(
                    selected_files_paths, self.current_dir, encoding=DEFAULT_ENCODING
                )

                # Assemble final output
                final_text = (
                    f"PROJECT DIRECTORY STRUCTURE ({os.path.basename(os.path.abspath(self.current_dir))}):\n"
                    f"{tree_string}\n\n"
                    f"{'=' * 20} FILE CONTENTS {'=' * 20}\n\n"
                    f"{combined_content}"
                )

                end_time = time.time()
                duration = end_time - start_time
                kb_size = total_size / 1024
                mb_size = kb_size / 1024
                size_str = f"{mb_size:.2f} MB" if mb_size >= 0.1 else f"{kb_size:.1f} KB"
                status_msg = f"Copied {file_count} files ({size_str}) in {duration:.2f}s."
                if errors:
                    status_msg += f" ({len(errors)} errors - see console)"

                # Schedule UI update back on the main thread
                self.after(0, self._update_gui_after_processing, final_text, status_msg)

            except Exception as e:
                import traceback
                error_trace = traceback.format_exc()
                print(f"Error during processing thread:\n{error_trace}", file=sys.stderr)
                # Schedule error message update on main thread
                self.after(0, lambda: self.status_label.configure(text=f"Error: {e}"))

        def _update_gui_after_processing(self, final_text, status_msg):
            """Updates GUI elements after background processing is complete."""
            if final_text:
                try:
                    self.clipboard_clear()
                    self.clipboard_append(final_text)
                    self.status_label.configure(text=status_msg)
                except Exception as e:
                    # Handle potential clipboard errors (e.g., size limits)
                    error_txt = f"Error copying: {e}. Content generated."
                    print(f"{error_txt}\nText length: {len(final_text)}", file=sys.stderr)
                    self.status_label.configure(text=error_txt)
            else:
                self.status_label.configure(text="No content generated.")

# =============================================================================
# >>> CLI IMPLEMENTATION <<<
# =============================================================================

def run_cli(args):
    """Executes the Command Line Interface logic."""
    start_path = args.directory
    if not os.path.isdir(start_path):
        print(f"Error: Directory not found: {start_path}", file=sys.stderr)
        sys.exit(1)

    # Prepare filters for the core scanning function
    include_extensions = None
    if args.include_ext:
        include_extensions = set(ext.lower() if ext.startswith('.') else '.' + ext.lower() for ext in args.include_ext)

    exclude_patterns = args.exclude or []

    # --- Scan using shared function ---
    # Pass verbose=True for CLI to show scan details
    selected_files, all_extensions = scan_and_filter_files(
        start_path, include_extensions, exclude_patterns, DEFAULT_IGNORED_DIRS, DEFAULT_IGNORED_FILES, verbose=True
    )

    # --- Handle --list-exts ---
    if args.list_exts:
        print("\nFound file extensions (before filtering by --include-ext):")
        if not all_extensions:
            print("  (No files with extensions found)")
        else:
            sorted_exts = sorted(all_extensions.items(), key=lambda item: (-item[1], item[0]))
            for ext, count in sorted_exts:
                print(f"  {ext:<10} : {count}")
        sys.exit(0) # Exit after listing

    # --- Prepare Output ---
    start_time = time.time()
    combined_output_parts = []
    final_text = ""

    # --- Generate Tree (if not disabled) ---
    if not args.no_tree:
        if selected_files: # Only generate tree if there are files to show
            print("Generating directory tree...", file=sys.stderr)
            # Use shared tree function with the final list of selected files
            tree_string = get_tree_string_for_selected(start_path, selected_files)
            combined_output_parts.append(f"PROJECT DIRECTORY STRUCTURE ({os.path.basename(os.path.abspath(start_path))}):")
            combined_output_parts.append(tree_string)
            combined_output_parts.append("\n" + "=" * 20 + " FILE CONTENTS " + "=" * 20 + "\n")
        else:
             combined_output_parts.append("No files selected matching criteria. Tree not generated.")


    # --- Generate Content (if not disabled) ---
    file_count = 0
    total_size = 0
    errors = []
    if not args.no_content:
        if selected_files:
            print(f"Reading {len(selected_files)} selected files...", file=sys.stderr)
            # Use shared content reading function
            content_part, file_count, total_size, errors = read_files_and_combine(
                selected_files, start_path, encoding=args.encoding
            )
            combined_output_parts.append(content_part)
        else:
             combined_output_parts.append("\nNo files selected matching criteria. Content not generated.\n")


    # --- Final Output Assembly ---
    final_text = "\n".join(combined_output_parts)
    end_time = time.time()
    duration = end_time - start_time

    # --- Write to File or Stdout ---
    output_target = args.output or sys.stdout

    try:
        if args.output:
            # Write to file
            with open(args.output, "w", encoding=args.encoding, errors="ignore") as f:
                f.write(final_text)
            print(f"\nOutput successfully written to: {args.output}", file=sys.stderr)
        else:
            # Write to stdout
            print(final_text)

    except Exception as e:
        print(f"\nError writing output: {e}", file=sys.stderr)
        if not args.output: # If stdout failed, maybe print summary to stderr
             print("\n--- Output Summary ---", file=sys.stderr)
             print(final_text[:1000] + ("..." if len(final_text) > 1000 else ""), file=sys.stderr)
             print("--- End Summary ---", file=sys.stderr)


    # --- Final Status Message (always to stderr) ---
    kb_size = total_size / 1024
    mb_size = kb_size / 1024
    size_str = f"{mb_size:.2f} MB" if mb_size >= 0.1 else f"{kb_size:.1f} KB"
    status_msg = f"Processed {file_count} files ({size_str}) in {duration:.2f}s."
    if errors:
        status_msg += f" ({len(errors)} errors occurred)"
    print(f"\n{status_msg}", file=sys.stderr)


def setup_cli_parser():
    """Sets up the argparse parser for CLI mode."""
    parser = argparse.ArgumentParser(
        description="Scan a directory, filter files, and combine their content. Run without arguments for GUI mode.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        prog="codebase-to-text" # Set program name
    )
    parser.add_argument(
        "directory",
        nargs="?", # Make directory optional for CLI too, defaults to '.'
        default=".",
        help="The root directory to scan (default: current directory)."
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Force run in Command Line Interface mode (used internally by the script logic)."
    )
    parser.add_argument(
        "-i", "--include-ext",
        metavar="EXT",
        nargs="+",
        help="File extensions to include (e.g., .py .js .txt). If not specified, includes all allowed files."
    )
    parser.add_argument(
        "-e", "--exclude",
        metavar="PATTERN",
        nargs="+",
        help="fnmatch patterns for files or directories to exclude (e.g., 'node_modules/' 'build/' '*.log' 'temp.txt'). Applied relative to start path unless absolute."
    )
    parser.add_argument(
        "--list-exts",
        action="store_true",
        help="Scan the directory, list all found file extensions (before filtering) and counts, then exit."
    )
    parser.add_argument(
        "-o", "--output",
        metavar="FILE",
        help="Write the combined output to a file instead of stdout."
    )
    parser.add_argument(
        "--no-tree",
        action="store_true",
        help="Do not include the directory tree structure in the output."
    )
    parser.add_argument(
        "--no-content",
        action="store_true",
        help="Do not include the file contents in the output (only shows tree/headers)."
    )
    parser.add_argument(
        "--encoding",
        default=DEFAULT_ENCODING,
        help=f"Encoding to use when reading files (default: {DEFAULT_ENCODING})."
    )
    return parser

# =============================================================================
# >>> MAIN EXECUTION LOGIC <<<
# =============================================================================

if __name__ == "__main__":
    # Check if running in CLI mode explicitly or if any arguments other than the script name are provided
    # Note: A simple check like `len(sys.argv) > 1` is often sufficient if the GUI takes no args.
    # Using a specific flag like `--cli` is more robust.
    run_as_cli = "--cli" in sys.argv

    if run_as_cli:
        # Remove --cli argument itself so argparse doesn't complain
        # Be careful if it's the only argument
        try:
            sys.argv.remove("--cli")
        except ValueError:
             pass # Should not happen if found earlier, but safe check

        # Setup and parse arguments specifically for CLI
        cli_parser = setup_cli_parser()
        cli_args = cli_parser.parse_args() # Parses the modified sys.argv
        run_cli(cli_args)
    elif len(sys.argv) > 1 and not run_as_cli:
         # If arguments are given but not '--cli', show help assuming CLI was intended
         print("Arguments detected. Assuming CLI mode was intended. Use --cli flag explicitly, or run without arguments for GUI.", file=sys.stderr)
         # Show CLI help message
         cli_parser = setup_cli_parser()
         cli_parser.print_help()
         sys.exit(1)

    else:
        # --- Run GUI Mode ---
        if not GUI_ENABLED:
            print("Error: GUI mode requires customtkinter and Pillow (PIL) to be installed.", file=sys.stderr)
            print("Install them with: pip install customtkinter Pillow", file=sys.stderr)
            # Optionally, fall back to CLI help or basic CLI execution?
            # For now, just exit.
            # cli_parser = setup_cli_parser()
            # cli_parser.print_help()
            sys.exit(1)
        else:
            # Launch the GUI Application
            app = App()
            app.mainloop()
