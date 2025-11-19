from pathlib import Path
import threading
import time
from collections import Counter
import subprocess
import platform
import os
import json

from textual.app import App, ComposeResult
from textual.reactive import reactive
from textual.widgets import Header, Footer, Tree, Checkbox, Button, Static, Input
from textual.containers import Vertical, Horizontal
from textual.binding import Binding

# --- Configuration ---
IGNORED_DIRS = {"__pycache__", "venv", "env", "node_modules"}
IGNORED_FILES = {}
# Characters that files/directories starting with should be ignored
# Examples:
#   ['.', '_'] - ignores .git, .vscode, _temp, __pycache__ (if not in IGNORED_DIRS)
#   ['.', '_', '~'] - also ignores ~backup files
#   ['#'] - ignores files starting with # (like #temp.py)
# Directories starting with these characters will be ignored
IGNORED_DIR_PREFIXES = ['.', '_']
# Files starting with these characters will be ignored
IGNORED_FILE_PREFIXES = ['.']
# File tree display limits
MAX_FILES_TO_SHOW_ALL = 25  # Show all files if count is <= this number
TREE_SHOW_FIRST_FILES = 10  # Number of first files to show when truncating
TREE_SHOW_LAST_FILES = 3   # Number of last files to show when truncating
# Performance limits
# Max files to scan per directory to avoid performance issues
MAX_FILES_PER_DIR_SCAN = 100
MAX_INITIAL_SCAN_DEPTH = 2    # Max depth for initial extension scanning
LARGE_DIR_THRESHOLD = 50     # Directories with more files are considered "large"
# --- End Configuration ---

STATE_FILE = Path.home() / ".codeclip_state.json"


# Precompute lowercase ignore sets for case-insensitive checks
def _normalized_parts(value):
    """Return normalized, case-insensitive path parts."""
    normalized = str(Path(value)).lower()
    # Remove empty entries that can appear from leading/trailing separators.
    return tuple(part for part in Path(normalized).parts if part)


IGNORED_DIRS_COMPONENTS = [_normalized_parts(name) for name in IGNORED_DIRS]
IGNORED_DIRS_BASENAMES = {parts[0]
                          for parts in IGNORED_DIRS_COMPONENTS if len(parts) == 1}
IGNORED_FILES_NORMALIZED = {name.lower() for name in IGNORED_FILES}


# --- Native Clipboard Implementation ---
def copy_to_clipboard(text: str) -> tuple[bool, str]:
    """Copy text to clipboard using native OS mechanisms (no external dependencies).
    
    Supports:
    - Linux: xclip, xsel, wl-copy (Wayland), file fallback
    - macOS: pbcopy
    - Windows: PowerShell, file fallback
    - Universal fallback: ~/.codeclip_clipboard
    
    Args:
        text: Text to copy to clipboard
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    system = platform.system()
    
    try:
        if system == "Linux":
            # Try xclip first (most common)
            try:
                process = subprocess.Popen(
                    ['xclip', '-selection', 'clipboard'],
                    stdin=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                process.communicate(text.encode('utf-8'), timeout=2)
                if process.returncode == 0:
                    return True, "✓ Copied to clipboard (xclip)"
            except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
                pass
            
            # Try xsel as fallback
            try:
                process = subprocess.Popen(
                    ['xsel', '--clipboard', '--input'],
                    stdin=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                process.communicate(text.encode('utf-8'), timeout=2)
                if process.returncode == 0:
                    return True, "✓ Copied to clipboard (xsel)"
            except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
                pass
            
            # Try wl-copy for Wayland
            try:
                process = subprocess.Popen(
                    ['wl-copy'],
                    stdin=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                process.communicate(text.encode('utf-8'), timeout=2)
                if process.returncode == 0:
                    return True, "✓ Copied to clipboard (wl-copy)"
            except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
                pass
        
        elif system == "Darwin":  # macOS
            try:
                process = subprocess.Popen(
                    ['pbcopy'],
                    stdin=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                process.communicate(text.encode('utf-8'), timeout=2)
                if process.returncode == 0:
                    return True, "✓ Copied to clipboard (pbcopy)"
            except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
                pass
        
        elif system == "Windows":
            try:
                # PowerShell is more reliable than clip.exe
                process = subprocess.Popen(
                    ['powershell', '-Command', 'Set-Clipboard -Value $input'],
                    stdin=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                process.communicate(text.encode('utf-8'), timeout=2)
                if process.returncode == 0:
                    return True, "✓ Copied to clipboard (PowerShell)"
            except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
                pass
    
    except Exception as e:
        pass
    
    # Universal fallback: save to file
    try:
        clipboard_file = Path.home() / ".codeclip_clipboard"
        with open(clipboard_file, 'w', encoding='utf-8') as f:
            f.write(text)
        return True, f"✓ Saved to {clipboard_file} (clipboard tools unavailable)"
    except Exception as e:
        return False, f"✗ Failed to copy: {str(e)}"
# --- End Native Clipboard Implementation ---


def is_ignored_dir(name):
    # Don't ignore the current directory marker
    if name == '.' or name == '..':
        return False
    # Check exact name matches first
    if name.lower() in IGNORED_DIRS_BASENAMES:
        return True
    # Check if name starts with any ignored prefix
    return any(name.startswith(prefix) for prefix in IGNORED_DIR_PREFIXES)


def is_ignored_file(name):
    lower_name = name.lower()
    # Check exact name matches first
    if lower_name in IGNORED_FILES_NORMALIZED:
        return True
    # Check if name starts with any ignored prefix
    return any(name.startswith(prefix) for prefix in IGNORED_FILE_PREFIXES)


def path_contains_ignored_dir(path):
    path_parts = _normalized_parts(path)
    if not path_parts:
        return False

    for ignored_parts in IGNORED_DIRS_COMPONENTS:
        if not ignored_parts:
            continue

        if len(ignored_parts) == 1:
            if ignored_parts[0] in path_parts:
                return True
            continue

        parts_range = len(path_parts) - len(ignored_parts) + 1
        if parts_range < 1:
            continue

        for index in range(parts_range):
            if path_parts[index:index + len(ignored_parts)] == ignored_parts:
                return True

    return False

# --- Scan extensions ---
def scan_file_extensions(base_path):
    base_path = Path(base_path)
    if is_ignored_dir(base_path.name) or path_contains_ignored_dir(str(base_path)):
        return Counter()

    extension_counts = Counter()
    limited_extensions = set()

    def scan_directory(directory_path, current_depth=0):
        """Recursively scan directory using pathlib"""
        if current_depth > MAX_INITIAL_SCAN_DEPTH:
            return

        if path_contains_ignored_dir(str(directory_path)):
            return

        try:
            # Get all files and subdirectories
            all_files = []
            subdirs = []

            for item in directory_path.iterdir():
                if item.is_file() and not is_ignored_file(item.name):
                    all_files.append(item.name)
                elif item.is_dir() and not is_ignored_dir(item.name):
                    subdirs.append(item)

            # Process files in current directory
            if len(all_files) > MAX_FILES_PER_DIR_SCAN:
                # For very large directories, sample files to estimate extensions
                sampled_files = all_files[:MAX_FILES_PER_DIR_SCAN //
                                          2] + all_files[-MAX_FILES_PER_DIR_SCAN//2:]
                multiplier = len(all_files) / len(sampled_files)
                # Mark that we hit a limit in this directory
                for file in sampled_files:
                    ext = Path(file).suffix
                    if ext:
                        limited_extensions.add(ext.lower())
            else:
                sampled_files = all_files
                multiplier = 1

            for file in sampled_files:
                ext = Path(file).suffix
                if ext:
                    extension_counts[ext.lower()] += int(multiplier)

            # Recursively scan subdirectories
            for subdir in subdirs:
                scan_directory(subdir, current_depth + 1)

        except (OSError, PermissionError):
            pass

    scan_directory(base_path)
    return extension_counts, limited_extensions

def _get_language_from_extension(ext):
    """Map file extensions to language identifiers for markdown code blocks."""
    ext = ext.lower()

    # Programming languages
    language_map = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'tsx',
        '.jsx': 'jsx',
        '.java': 'java',
        '.c': 'c',
        '.cpp': 'cpp',
        '.cc': 'cpp',
        '.cxx': 'cpp',
        '.h': 'c',
        '.hpp': 'cpp',
        '.cs': 'csharp',
        '.php': 'php',
        '.rb': 'ruby',
        '.go': 'go',
        '.rs': 'rust',
        '.swift': 'swift',
        '.kt': 'kotlin',
        '.scala': 'scala',
        '.sh': 'bash',
        '.bash': 'bash',
        '.zsh': 'zsh',
        '.fish': 'fish',
        '.ps1': 'powershell',
        '.bat': 'batch',
        '.cmd': 'batch',

        # Web technologies
        '.html': 'html',
        '.htm': 'html',
        '.xml': 'xml',
        '.css': 'css',
        '.scss': 'scss',
        '.sass': 'sass',
        '.less': 'less',

        # Data formats
        '.json': 'json',
        '.yaml': 'yaml',
        '.yml': 'yaml',
        '.toml': 'toml',
        '.ini': 'ini',
        '.cfg': 'ini',
        '.conf': 'conf',

        # Documentation
        '.md': 'markdown',
        '.markdown': 'markdown',
        '.rst': 'rst',
        '.txt': 'text',

        # Database
        '.sql': 'sql',

        # Other
        '.dockerfile': 'dockerfile',
        '.gitignore': 'gitignore',
        '.env': 'bash',
        '.r': 'r',
        '.m': 'matlab',
        '.pl': 'perl',
        '.lua': 'lua',
        '.vim': 'vim',
        '.asm': 'assembly',
        '.s': 'assembly',
    }

    return language_map.get(ext, '')

# --- Build folder tree ---
def build_folder_tree(base_path, max_depth=None, current_depth=0):
    base_path = Path(base_path)
    if is_ignored_dir(base_path.name):
        return {"subfolders": {}, "files": [], "is_large": False}
    tree = {"subfolders": {}, "files": [], "is_large": False}
    if path_contains_ignored_dir(str(base_path)):
        return tree

    # Stop recursion if we've reached max depth (for performance)
    if max_depth is not None and current_depth >= max_depth:
        tree["lazy_load"] = True
        return tree

    try:
        dirs = []
        files_in_dir = []
        file_count = 0

        for entry in base_path.iterdir():
            name = entry.name
            if path_contains_ignored_dir(str(entry)) or is_ignored_dir(name):
                continue
            if entry.is_dir():
                dirs.append(entry)
            elif entry.is_file() and not is_ignored_file(name):
                file_count += 1
                # For performance, limit the number of files we process
                if file_count <= MAX_FILES_PER_DIR_SCAN:
                    # Include ALL non-ignored files, not just those with known extensions
                    # This ensures __init__.py and other files are always shown
                    files_in_dir.append(name)
                elif file_count == MAX_FILES_PER_DIR_SCAN + 1:
                    # Mark as large directory
                    tree["is_large"] = True

        tree["files"] = sorted(files_in_dir, key=str.lower)
        dirs.sort(key=lambda e: e.name.lower())

        # For performance, limit recursion depth for initial build
        next_max_depth = 3 if max_depth is None else max_depth  # Initial build depth limit

        for entry in dirs:
            sub_tree = build_folder_tree(
                entry, next_max_depth, current_depth + 1)
            # Always include directories, even if empty
            tree["subfolders"][entry.name] = sub_tree
    except OSError:
        pass
    return tree

# --- Helper get_tree_filtered_string ---
def get_tree_filtered_string(start_path, allowed_extensions=(), indent_char="    ", prefix=""):
    start_path = Path(start_path)
    if path_contains_ignored_dir(str(start_path)):
        return ""

    lines = []
    pointers = {"last": "└── ", "normal": "├── "}
    extender = {"last": indent_char, "normal": "│" + indent_char[1:]}

    try:
        dirs = []
        files = []
        file_count = 0
        too_many_files = False

        for entry in start_path.iterdir():
            name = entry.name
            if path_contains_ignored_dir(str(entry)):
                continue
            if entry.is_file():
                if is_ignored_file(name):
                    continue
                file_count += 1

                # For performance, limit scanning in very large directories
                if file_count > MAX_FILES_PER_DIR_SCAN:
                    too_many_files = True
                    continue

                # If allowed_extensions is None, show all files; otherwise filter by extension
                if allowed_extensions is None:
                    files.append(entry)
                else:
                    ext = entry.suffix
                    if ext and ext.lower() in allowed_extensions:
                        files.append(entry)
            elif entry.is_dir():
                if not is_ignored_dir(name):
                    dirs.append(entry)

        # Sort directories and files separately
        dirs.sort(key=lambda e: e.name.lower())
        files.sort(key=lambda e: e.name.lower())

        # Apply file truncation if there are too many files
        files_to_show = files
        omitted_count = 0
        performance_limit_msg = ""

        if too_many_files:
            # We hit the performance limit, but still apply truncation for display
            if len(files) > MAX_FILES_TO_SHOW_ALL:
                # Apply normal truncation even with performance limits
                first_files = files[:TREE_SHOW_FIRST_FILES]
                last_files = files[-TREE_SHOW_LAST_FILES:]
                files_to_show = first_files + last_files
                omitted_count = len(files) - len(files_to_show)
                performance_limit_msg = f"... (directory too large, showing first {TREE_SHOW_FIRST_FILES} and last {TREE_SHOW_LAST_FILES} of {file_count}+ files) ..."
            else:
                # Performance limit hit but not enough files to require truncation
                performance_limit_msg = f"... (directory too large, showing first {len(files)} of {file_count}+ files) ..."
        elif len(files) > MAX_FILES_TO_SHOW_ALL:
            # Normal file truncation without performance limits
            first_files = files[:TREE_SHOW_FIRST_FILES]
            last_files = files[-TREE_SHOW_LAST_FILES:]
            files_to_show = first_files + last_files
            omitted_count = len(files) - len(files_to_show)

        # Combine directories first, then files
        all_entries = dirs + files_to_show

        # Insert performance limit message at the beginning of files section if needed
        if performance_limit_msg and len(dirs) < len(all_entries):
            lines.append(prefix + pointers["normal"] + performance_limit_msg)

        # Process entries
        for i, entry in enumerate(all_entries):
            is_last_entry = (i == len(all_entries) - 1)

            # Check if we need to insert the omitted files indicator
            if (omitted_count > 0 and
                entry in files and
                    i == len(dirs) + TREE_SHOW_FIRST_FILES):
                # Insert the omitted files indicator before the last files
                omitted_pointer = pointers["normal"]
                lines.append(prefix + omitted_pointer +
                             f"... ({omitted_count} files omitted) ...")

            pointer = pointers["last"] if is_last_entry else pointers["normal"]
            extend = extender["last"] if is_last_entry else extender["normal"]

            if entry.is_dir():
                lines.append(prefix + pointer + entry.name + "/")
                subtree_str = get_tree_filtered_string(
                    entry, allowed_extensions, indent_char, prefix + extend
                )
                if subtree_str:
                    lines.append(subtree_str)
            else:
                lines.append(prefix + pointer + entry.name)

    except OSError:
        return ""

    return "\n".join(lines)


def collect_selected_files_from_tree(tree, include_exts, current_dir):
    """Collect selected file paths from a textual Tree-like object.

    Args:
        tree: object with either a root node (Textual Tree) or walk_children method (test tree)
        include_exts: set of extension strings (e.g. '.py') to include; when empty, include everything
        current_dir: Path for base join

    Returns:
        list of Path objects
    """
    selected_files_paths = []
    # When no filters are selected, include all extensions
    filter_all = not include_exts
    
    # Support both Textual Tree (with root) and test trees (with walk_children)
    if hasattr(tree, 'root'):
        def walk_nodes(node):
            """Manually walk the tree starting from a node."""
            for child in node.children:
                yield child
                yield from walk_nodes(child)
        nodes = walk_nodes(tree.root)
    else:
        nodes = tree.walk_children()
    
    for node in nodes:
        if not node.data.get("is_dir", False) and node.data.get("selected") is True:
            rel_path = node_relative_path(node)
            if not rel_path:
                continue
            ext = rel_path.suffix
            if filter_all or (ext and ext.lower() in include_exts):
                selected_files_paths.append(Path(current_dir) / rel_path)
    return selected_files_paths


def node_relative_path(node):
    parts = []
    current = node
    while current and getattr(current, "data", None):
        parent = current.parent
        if parent is None:
            break
        part = current.data.get("path", "")
        if part:
            parts.append(part)
        current = parent
    if not parts:
        return Path()
    return Path(*reversed(parts))


def walk_tree(root_node):
    """Manually walk all descendants of a tree node (since Tree.walk_children() doesn't work)."""
    def _walk(node):
        for child in node.children:
            yield child
            yield from _walk(child)
    return _walk(root_node)



class ChangeDirectoryPrompt(Static):
    """Simple modal for entering a directory path."""

    def __init__(self) -> None:
        super().__init__()
        self.id = "change-dir-prompt"

    def compose(self) -> ComposeResult:
        yield Static("Change Directory", classes="header")
        yield Static("Enter the path to your project directory:", classes="prompt-text")
        yield Input(placeholder="/path/to/project", id="change-dir-input")
        with Horizontal(classes="change-dir-buttons"):
            yield Button("Cancel", id="change-dir-cancel")
            yield Button("Change", id="change-dir-confirm", variant="primary")

class CodebaseToTextApp(App):
    """A Textual app to select files and copy their content to the clipboard."""

    CSS_PATH = "terminal_app.css"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("h", "toggle_help", "Help"),
        ("space", "toggle_select", "Toggle selection"),
        ("a", "select_all", "Select all"),
        ("A", "select_all_inverse", "Deselect all"),
    ]

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield Footer()
        with Horizontal(id="main-container"):
            with Vertical(id="left-pane"):
                yield Static("File Tree", classes="header")
                yield Tree("Root", id="file-tree")
            with Vertical(id="right-pane"):
                yield Static("File Types", classes="header")
                yield Vertical(id="file-types")
                yield Static("Controls", classes="header")
                yield Button("Generate and Copy", id="generate-copy", variant="primary")
                yield Button("Select All", id="select-all")
                yield Button("Deselect All", id="deselect-all")
                yield Button("Change Directory", id="change-dir")
                # A small status bar to mimic btop's bottom info
                yield Static("Ready", id="status")
                # Help overlay (hidden by default)
                yield Static("Keys: q=Quit h=Help space=Toggle selection a=Select all A=Deselect all", id="help-overlay")


    def on_mount(self) -> None:
        """Called when the app is mounted."""
        self._state = self._load_state()
        last_dir = Path(self._state.get("last_dir", Path.cwd()))
        if not last_dir.is_dir():
            last_dir = Path.cwd()
        self.current_dir = last_dir
        self.title = f"Codebase to Clipboard - {self.current_dir.name}"
        self.sub_title = str(self.current_dir)
        self._change_dir_prompt = None
        self.load_directory()
        self._hide_help_overlay()

    def load_directory(self):
        """Load the directory tree and file types."""
        tree = self.query_one(Tree)
        tree.clear()
        folder_tree = build_folder_tree(self.current_dir)
        # Ensure root has data so it can be walked
        tree.root.data = {"path": "", "is_dir": True, "selected": True}
        self.add_nodes(tree.root, folder_tree)
        tree.root.expand()

        file_types_container = self.query_one("#file-types")
        for child in file_types_container.children:
            child.remove()
            
        extension_counts, _ = scan_file_extensions(self.current_dir)
        sorted_extensions = sorted(extension_counts.keys(),
                                   key=lambda ext: extension_counts[ext],
                                   reverse=True)
        for ext in sorted_extensions:
            count = extension_counts.get(ext, 0)
            checkbox = Checkbox(f"{ext} ({count})", id=f"ext-{ext.replace('.', '_')}", value=True)
            # keep the original extension on the widget for easy matching
            checkbox.ext = ext.lower()
            file_types_container.mount(checkbox)
        saved_exts = set(self._state.get("selected_exts", [])) if self._state else set()
        if saved_exts:
            for cb in file_types_container.query(Checkbox):
                ext = getattr(cb, "ext", None)
                if ext:
                    cb.value = ext in saved_exts
        self._apply_saved_selection(tree)
        self.update_status()
        self._persist_state()

    def _hide_help_overlay(self):
        try:
            help_overlay = self.query_one("#help-overlay")
            help_overlay.styles.display = "none"
            help_overlay.refresh()
        except Exception:
            pass

    def _format_node_label(self, name: str, selected: bool, is_dir: bool) -> str:
        icon = "[bright_green]●[/bright_green]" if selected else "[dim]○[/dim]"
        suffix = "/" if is_dir else ""
        return f"{icon} {name}{suffix}"

    def _refresh_node_label(self, node):
        if not node or not node.data:
            return
        node.set_label(
            self._format_node_label(
                node.data.get("path", ""),
                node.data.get("selected", False),
                node.data.get("is_dir", False),
            )
        )

    def _refresh_directory_selection_states(self):
        tree = self.query_one(Tree)
        for node in walk_tree(tree.root):
            if not node.data:
                continue
            if not node.data.get("is_dir", False):
                continue
            has_selected = any(
                child.data.get("selected", False)
                for child in node.children
                if child.data
            )
            node.data["selected"] = has_selected
            self._refresh_node_label(node)

    def _apply_saved_selection(self, tree):
        saved_files = {
            Path(p) for p in self._state.get("selected_files", [])
            if p
        }
        has_saved = bool(saved_files)
        for node in walk_tree(tree.root):
            if not node.data:
                continue
            if node.data.get("is_dir", False):
                continue
            rel_path = node_relative_path(node)
            # If we have saved state, use it; otherwise default to True (all selected)
            if has_saved:
                node.data["selected"] = rel_path in saved_files
            else:
                node.data["selected"] = True
            self._refresh_node_label(node)
        self._refresh_directory_selection_states()

    def _persist_state(self):
        try:
            tree = self.query_one(Tree)
        except Exception:
            return
        selected_files = []
        for node in walk_tree(tree.root):
            if not node.data:
                continue
            if node.data.get("is_dir", False):
                continue
            # Only save files that are explicitly marked as selected (not using default)
            if node.data.get("selected") is True:
                rel_path = node_relative_path(node)
                if rel_path:
                    selected_files.append(rel_path.as_posix())
        selected_exts = []
        for cb in self.query(Checkbox):
            if cb.id and cb.id.startswith("ext-") and cb.value:
                ext = getattr(cb, "ext", None)
                if ext:
                    selected_exts.append(ext)
        state = {
            "last_dir": str(self.current_dir),
            "selected_files": selected_files,
            "selected_exts": selected_exts,
        }
        self._state = state
        try:
            STATE_FILE.write_text(json.dumps(state, indent=2))
        except Exception:
            pass

    def _load_state(self):
        try:
            raw = STATE_FILE.read_text()
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    def add_nodes(self, tree_node, folder_tree):
        """Recursively add nodes to the tree."""
        for folder, sub_tree in folder_tree["subfolders"].items():
            label = self._format_node_label(folder, True, is_dir=True)
            child_node = tree_node.add(label, data={"path": folder, "is_dir": True, "selected": True})
            self.add_nodes(child_node, sub_tree)
        for file in folder_tree["files"]:
            label = self._format_node_label(file, True, is_dir=False)
            tree_node.add_leaf(label, data={"path": file, "is_dir": False, "selected": True})

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Called when a checkbox is changed."""
        if event.checkbox.id and event.checkbox.id.startswith("ext-"):
            self._persist_state()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Called when a button is pressed."""
        if event.button.id == "generate-copy":
            self.process_folders()
        elif event.button.id == "select-all":
            self.select_all(True)
        elif event.button.id == "deselect-all":
            self.select_all(False)
        elif event.button.id == "change-dir":
            self.open_change_directory_prompt()
        elif event.button.id == "change-dir-confirm":
            if self._change_dir_prompt is None:
                return
            input_widget = self._change_dir_prompt.query_one("#change-dir-input", Input)
            self._handle_change_directory_value(input_widget.value)
        elif event.button.id == "change-dir-cancel":
            if self._change_dir_prompt:
                self._change_dir_prompt.remove()
                self._change_dir_prompt = None

    def open_change_directory_prompt(self) -> None:
        if self._change_dir_prompt:
            return
        prompt = ChangeDirectoryPrompt()
        self._change_dir_prompt = prompt
        self.mount(prompt)
        input_widget = prompt.query_one("#change-dir-input", Input)
        input_widget.value = str(self.current_dir)
        self.set_focus(input_widget)

    def _handle_change_directory_value(self, raw_value: str) -> None:
        value = raw_value.strip()
        if not value:
            self.notify("Please enter a directory path.", title="Change Directory", severity="warning")
            return
        target = Path(value).expanduser()
        if not target.is_dir():
            self.notify(f"Directory not found: {target}", title="Change Directory", severity="warning")
            return
        if self._change_dir_prompt:
            self._change_dir_prompt.remove()
            self._change_dir_prompt = None
        self._set_directory(target)

    def _set_directory(self, target: Path) -> None:
        self.current_dir = target
        self.title = f"Codebase to Clipboard - {self.current_dir.name}"
        self.sub_title = str(self.current_dir)
        self.load_directory()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "change-dir-input":
            self._handle_change_directory_value(event.value)

    def select_all(self, value: bool):
        """Select or deselect all files and folders."""
        tree = self.query_one(Tree)
        for node in walk_tree(tree.root):
            if not node.data or node.data.get("is_dir", False):
                continue
            node.data["selected"] = value
            self._refresh_node_label(node)
        self._refresh_directory_selection_states()
        self.update_status()
        self._persist_state()

    def process_folders(self):
        """Process the selected folders and files."""
        include_exts = set()
        for cb in self.query(Checkbox):
            if cb.id and cb.id.startswith("ext-") and cb.value:
                ext = getattr(cb, "ext", None)
                if ext:
                    include_exts.add(ext.lower())
        
        tree = self.query_one(Tree)
        selected_files_paths = collect_selected_files_from_tree(tree, include_exts, self.current_dir)

        if not selected_files_paths:
            self.notify("No files selected or matching selected file types.", title="Warning", severity="warning")
            return

        self.notify("Processing... please wait.", title="Processing")

        thread = threading.Thread(
            target=self._process_thread,
            args=(sorted(selected_files_paths),),
        )
        thread.daemon = True
        thread.start()

    def _process_thread(self, selected_files_paths):
        start_time = time.time()
        try:
            directory_tree = get_tree_filtered_string(self.current_dir)
            combined_text = "PROJECT DIRECTORY STRUCTURE:\n" + directory_tree + \
                "\n\n" + "=" * 20 + " FILE CONTENTS " + "=" * 20 + "\n\n"

            file_count = 0
            total_size = 0
            errors = []

            for file_path in selected_files_paths:
                try:
                    file_path_obj = Path(file_path)
                    relative_path = str(file_path_obj.relative_to(
                        self.current_dir)).replace("\\", "/")
                    with file_path_obj.open("r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    ext = file_path_obj.suffix
                    language = _get_language_from_extension(ext)

                    combined_text += f"## {relative_path}\n\n```{language}\n{content}\n```\n\n"
                    file_count += 1
                    total_size += len(content.encode('utf-8'))
                except Exception as e:
                    error_msg = f"Error reading {Path(file_path).relative_to(self.current_dir)}: {e}"
                    errors.append(error_msg)

            end_time = time.time()
            duration = end_time - start_time
            kb_size = total_size / 1024
            mb_size = kb_size / 1024
            size_str = f"{mb_size:.2f} MB" if mb_size >= 1 else f"{kb_size:.1f} KB"
            status_msg = f"Copied {file_count} files ({size_str}) in {duration:.2f}s."
            if errors:
                status_msg += f" ({len(errors)} errors occurred)"

            success, clip_message = copy_to_clipboard(combined_text)
            if not success:
                status_msg = f"Generated {file_count} files but copy failed: {clip_message}"
            
            self.call_from_thread(self.notify, status_msg, title="Success")
            # Ensure we also update status from thread
            self.call_from_thread(self.update_status)

        except Exception as e:
            self.call_from_thread(self.notify, f"Error: {e}", title="Error", severity="error")


    def action_toggle_help(self) -> None:
        """Toggle the help overlay (mimics btop help)."""
        try:
            help_overlay = self.query_one("#help-overlay")
            current = getattr(help_overlay, "styles", None)
            if current is not None and getattr(current, "display", None) == "none":
                help_overlay.styles.display = ""
            else:
                help_overlay.styles.display = "none"
            help_overlay.refresh()
        except Exception:
            pass

    def action_toggle_select(self) -> None:
        """Toggle the selection for the currently focused tree node."""
        try:
            tree = self.query_one(Tree)
            node = getattr(tree, "cursor_node", None) or getattr(tree, "focused_node", None)
            if node and node.data:
                node.data["selected"] = not node.data.get("selected", True)
                self._refresh_node_label(node)
                self._refresh_directory_selection_states()
                self.update_status()
                self._persist_state()
        except Exception:
            pass

    def on_tree_node_selected(self, event) -> None:
        """Called when a tree node is selected (clicked). Toggle selected state so users can click to choose files."""
        try:
            node = getattr(event, "node", None) or getattr(event, "target", None)
            if node and getattr(node, "data", None):
                node.data["selected"] = not node.data.get("selected", True)
                self._refresh_node_label(node)
                self._refresh_directory_selection_states()
                self.update_status()
                self._persist_state()
        except Exception:
            pass

    def action_select_all(self) -> None:
        self.select_all(True)

    def action_select_all_inverse(self) -> None:
        self.select_all(False)

    def update_status(self):
        """Update status bar with file and selection counts."""
        tree = self.query_one(Tree)
        total_files = 0
        selected_files = 0
        for node in walk_tree(tree.root):
            if node.data and not node.data.get("is_dir", False):
                total_files += 1
                if node.data.get("selected") is True:
                    selected_files += 1
        status = self.query_one("#status")
        status.update(f"Files: {selected_files}/{total_files}  |  Directory: {self.current_dir}")



if __name__ == "__main__":
    app = CodebaseToTextApp()
    app.run()
