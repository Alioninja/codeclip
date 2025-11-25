#!/usr/bin/env python3
"""CodeClip TUI - A btop-inspired terminal app to copy codebase to clipboard."""

from pathlib import Path
import threading
import time
from collections import Counter
import subprocess
import platform
import json
import os

from textual.app import App, ComposeResult
from textual.widgets import Header, Tree, Checkbox, Button, Static, Input, DirectoryTree
from textual.widget import Widget
from textual.containers import Vertical, Horizontal, VerticalScroll, Container
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.suggester import Suggester
from textual.reactive import reactive
from textual.message import Message

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
IGNORED_DIRS = {"__pycache__", "venv", "env", "node_modules", ".git", ".svn"}
IGNORED_FILES = set()
IGNORED_DIR_PREFIXES = ['.', '_']
IGNORED_FILE_PREFIXES = ['.']

# Performance limits
MAX_FILES_PER_DIR_SCAN = 100
MAX_INITIAL_SCAN_DEPTH = 3
LARGE_DIR_THRESHOLD = 50

# State file
STATE_FILE = Path.home() / ".codeclip_state.json"

# Output formats
OUTPUT_FORMATS = ["markdown", "xml", "plain"]

# ═══════════════════════════════════════════════════════════════════════════════
# IGNORE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _normalized_parts(value):
    """Return normalized, case-insensitive path parts."""
    normalized = str(Path(value)).lower()
    return tuple(part for part in Path(normalized).parts if part)


IGNORED_DIRS_COMPONENTS = [_normalized_parts(name) for name in IGNORED_DIRS]
IGNORED_DIRS_BASENAMES = {parts[0] for parts in IGNORED_DIRS_COMPONENTS if len(parts) == 1}
IGNORED_FILES_NORMALIZED = {name.lower() for name in IGNORED_FILES}


def is_ignored_dir(name):
    """Check if directory should be ignored."""
    if name in ('.', '..'):
        return False
    if name.lower() in IGNORED_DIRS_BASENAMES:
        return True
    return any(name.startswith(prefix) for prefix in IGNORED_DIR_PREFIXES)


def is_ignored_file(name):
    """Check if file should be ignored."""
    if name.lower() in IGNORED_FILES_NORMALIZED:
        return True
    return any(name.startswith(prefix) for prefix in IGNORED_FILE_PREFIXES)


def path_contains_ignored_dir(path):
    """Check if path contains any ignored directory."""
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


# ═══════════════════════════════════════════════════════════════════════════════
# CLIPBOARD
# ═══════════════════════════════════════════════════════════════════════════════

def copy_to_clipboard(text: str) -> tuple[bool, str]:
    """Copy text to clipboard using native OS mechanisms."""
    system = platform.system()
    
    try:
        if system == "Linux":
            for cmd in [['xclip', '-selection', 'clipboard'],
                        ['xsel', '--clipboard', '--input'],
                        ['wl-copy']]:
                try:
                    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
                    process.communicate(text.encode('utf-8'), timeout=2)
                    if process.returncode == 0:
                        return True, f"✓ Copied ({cmd[0]})"
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue
        
        elif system == "Darwin":
            process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            process.communicate(text.encode('utf-8'), timeout=2)
            if process.returncode == 0:
                return True, "✓ Copied (pbcopy)"
        
        elif system == "Windows":
            process = subprocess.Popen(
                ['powershell', '-Command', 'Set-Clipboard -Value $input'],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE
            )
            process.communicate(text.encode('utf-8'), timeout=2)
            if process.returncode == 0:
                return True, "✓ Copied (PowerShell)"
    except Exception:
        pass
    
    # Fallback: save to file
    try:
        clipboard_file = Path.home() / ".codeclip_clipboard"
        clipboard_file.write_text(text, encoding='utf-8')
        return True, f"✓ Saved to {clipboard_file}"
    except Exception as e:
        return False, f"✗ Failed: {e}"


# ═══════════════════════════════════════════════════════════════════════════════
# FILE SCANNING
# ═══════════════════════════════════════════════════════════════════════════════

def scan_file_extensions(base_path):
    """Scan directory for file extensions."""
    base_path = Path(base_path)
    if is_ignored_dir(base_path.name) or path_contains_ignored_dir(str(base_path)):
        return Counter(), set()

    extension_counts = Counter()
    limited_extensions = set()

    def scan_directory(directory_path, current_depth=0):
        if current_depth > MAX_INITIAL_SCAN_DEPTH:
            return
        if path_contains_ignored_dir(str(directory_path)):
            return
        try:
            all_files = []
            subdirs = []
            for item in directory_path.iterdir():
                if item.is_file() and not is_ignored_file(item.name):
                    all_files.append(item.name)
                elif item.is_dir() and not is_ignored_dir(item.name):
                    subdirs.append(item)
            
            if len(all_files) > MAX_FILES_PER_DIR_SCAN:
                sampled = all_files[:MAX_FILES_PER_DIR_SCAN//2] + all_files[-MAX_FILES_PER_DIR_SCAN//2:]
                multiplier = len(all_files) / len(sampled)
                for f in sampled:
                    ext = Path(f).suffix
                    if ext:
                        limited_extensions.add(ext.lower())
            else:
                sampled = all_files
                multiplier = 1
            
            for f in sampled:
                ext = Path(f).suffix
                if ext:
                    extension_counts[ext.lower()] += int(multiplier)
            
            for subdir in subdirs:
                scan_directory(subdir, current_depth + 1)
        except (OSError, PermissionError):
            pass

    scan_directory(base_path)
    return extension_counts, limited_extensions


def build_folder_tree(base_path, max_depth=None, current_depth=0):
    """Build a folder tree structure."""
    base_path = Path(base_path)
    if is_ignored_dir(base_path.name):
        return {"subfolders": {}, "files": [], "is_large": False}
    
    tree = {"subfolders": {}, "files": [], "is_large": False}
    if path_contains_ignored_dir(str(base_path)):
        return tree

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
                if file_count <= MAX_FILES_PER_DIR_SCAN:
                    files_in_dir.append(name)
                elif file_count == MAX_FILES_PER_DIR_SCAN + 1:
                    tree["is_large"] = True

        tree["files"] = sorted(files_in_dir, key=str.lower)
        dirs.sort(key=lambda e: e.name.lower())

        next_max_depth = 4 if max_depth is None else max_depth

        for entry in dirs:
            sub_tree = build_folder_tree(entry, next_max_depth, current_depth + 1)
            tree["subfolders"][entry.name] = sub_tree
    except OSError:
        pass
    return tree


def get_tree_string(start_path, allowed_extensions=None):
    """Generate a string representation of the directory tree."""
    start_path = Path(start_path)
    if path_contains_ignored_dir(str(start_path)):
        return ""

    lines = []
    
    def walk(path, prefix=""):
        try:
            entries = list(path.iterdir())
            dirs = sorted([e for e in entries if e.is_dir() and not is_ignored_dir(e.name)], key=lambda e: e.name.lower())
            files = sorted([e for e in entries if e.is_file() and not is_ignored_file(e.name)], key=lambda e: e.name.lower())
            
            if allowed_extensions:
                files = [f for f in files if f.suffix.lower() in allowed_extensions]
            
            all_entries = dirs + files
            for i, entry in enumerate(all_entries):
                is_last = i == len(all_entries) - 1
                pointer = "└── " if is_last else "├── "
                
                if entry.is_dir():
                    lines.append(f"{prefix}{pointer}{entry.name}/")
                    extension = "    " if is_last else "│   "
                    if not path_contains_ignored_dir(str(entry)):
                        walk(entry, prefix + extension)
                else:
                    lines.append(f"{prefix}{pointer}{entry.name}")
        except OSError:
            pass

    walk(start_path)
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# LANGUAGE MAPPING
# ═══════════════════════════════════════════════════════════════════════════════

LANGUAGE_MAP = {
    '.py': 'python', '.js': 'javascript', '.ts': 'typescript', '.tsx': 'tsx',
    '.jsx': 'jsx', '.java': 'java', '.c': 'c', '.cpp': 'cpp', '.cc': 'cpp',
    '.cxx': 'cpp', '.h': 'c', '.hpp': 'cpp', '.cs': 'csharp', '.php': 'php',
    '.rb': 'ruby', '.go': 'go', '.rs': 'rust', '.swift': 'swift', '.kt': 'kotlin',
    '.scala': 'scala', '.sh': 'bash', '.bash': 'bash', '.zsh': 'zsh',
    '.fish': 'fish', '.ps1': 'powershell', '.bat': 'batch', '.cmd': 'batch',
    '.html': 'html', '.htm': 'html', '.xml': 'xml', '.css': 'css',
    '.scss': 'scss', '.sass': 'sass', '.less': 'less', '.json': 'json',
    '.yaml': 'yaml', '.yml': 'yaml', '.toml': 'toml', '.ini': 'ini',
    '.cfg': 'ini', '.conf': 'conf', '.md': 'markdown', '.markdown': 'markdown',
    '.rst': 'rst', '.txt': 'text', '.sql': 'sql', '.dockerfile': 'dockerfile',
    '.gitignore': 'gitignore', '.env': 'bash', '.r': 'r', '.m': 'matlab',
    '.pl': 'perl', '.lua': 'lua', '.vim': 'vim', '.asm': 'assembly', '.s': 'assembly',
}


def get_language(ext):
    """Get language identifier for a file extension."""
    return LANGUAGE_MAP.get(ext.lower(), '')


# ═══════════════════════════════════════════════════════════════════════════════
# TREE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def walk_tree(root_node):
    """Walk all descendants of a tree node."""
    def _walk(node):
        for child in node.children:
            yield child
            yield from _walk(child)
    return _walk(root_node)


def node_relative_path(node):
    """Get the relative path of a tree node."""
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


def collect_selected_files(tree, include_exts, current_dir):
    """Collect selected file paths from the tree."""
    selected = []
    filter_all = not include_exts
    
    for node in walk_tree(tree.root):
        if not node.data.get("is_dir", False) and node.data.get("selected"):
            rel_path = node_relative_path(node)
            if not rel_path:
                continue
            ext = rel_path.suffix
            if filter_all or (ext and ext.lower() in include_exts):
                selected.append(Path(current_dir) / rel_path)
    return selected


# ═══════════════════════════════════════════════════════════════════════════════
# OUTPUT FORMATTERS
# ═══════════════════════════════════════════════════════════════════════════════

def format_output_markdown(project_name, tree_string, files_content):
    """Format output as Markdown."""
    output = f"# Project: {project_name}\n\n"
    output += "## Directory Structure\n\n```\n"
    output += f"{project_name}/\n{tree_string}\n```\n\n"
    output += "## File Contents\n\n"
    
    for rel_path, content, lang in files_content:
        output += f"### {rel_path}\n\n```{lang}\n{content}\n```\n\n"
    
    return output


def format_output_xml(project_name, tree_string, files_content):
    """Format output as XML."""
    output = '<?xml version="1.0" encoding="UTF-8"?>\n'
    output += f'<project name="{project_name}">\n'
    output += '  <structure>\n'
    output += f'    <![CDATA[\n{project_name}/\n{tree_string}\n]]>\n'
    output += '  </structure>\n'
    output += '  <files>\n'
    
    for rel_path, content, lang in files_content:
        # Escape CDATA end sequences in content
        safe_content = content.replace(']]>', ']]]]><![CDATA[>')
        output += f'    <file path="{rel_path}" language="{lang}">\n'
        output += f'      <![CDATA[{safe_content}]]>\n'
        output += '    </file>\n'
    
    output += '  </files>\n'
    output += '</project>\n'
    
    return output


def format_output_plain(project_name, tree_string, files_content):
    """Format output as plain text."""
    output = f"PROJECT: {project_name}\n"
    output += "=" * 60 + "\n\n"
    output += "DIRECTORY STRUCTURE:\n"
    output += "-" * 40 + "\n"
    output += f"{project_name}/\n{tree_string}\n\n"
    output += "=" * 60 + "\n"
    output += "FILE CONTENTS\n"
    output += "=" * 60 + "\n\n"
    
    for rel_path, content, lang in files_content:
        output += f">>> {rel_path} ({lang if lang else 'text'})\n"
        output += "-" * 40 + "\n"
        output += f"{content}\n"
        output += "-" * 40 + "\n\n"
    
    return output


# ═══════════════════════════════════════════════════════════════════════════════
# PATH SUGGESTER & FOLDER TREE
# ═══════════════════════════════════════════════════════════════════════════════

class PathSuggester(Suggester):
    """Suggester for directory paths with autocomplete."""
    
    async def get_suggestion(self, value: str) -> str | None:
        """Get path suggestion based on current input."""
        if not value:
            return None
        
        try:
            path = Path(value).expanduser()
            
            # If the path exists and is a directory, suggest first child dir
            if path.is_dir():
                if not value.endswith(os.sep):
                    return value + os.sep
                # List child directories
                try:
                    dirs = sorted([
                        d.name for d in path.iterdir() 
                        if d.is_dir() and not d.name.startswith('.')
                    ])
                    if dirs:
                        return value + dirs[0]
                except (PermissionError, OSError):
                    pass
                return None
            
            # If parent exists, suggest matching child directories
            parent = path.parent
            partial = path.name.lower()
            
            if parent.is_dir():
                try:
                    dirs = sorted([
                        d.name for d in parent.iterdir()
                        if d.is_dir() and d.name.lower().startswith(partial)
                        and not d.name.startswith('.')
                    ])
                    if dirs:
                        return str(parent / dirs[0])
                except (PermissionError, OSError):
                    pass
        except Exception:
            pass
        
        return None


class FolderOnlyTree(DirectoryTree):
    """DirectoryTree that only shows folders, not files."""
    
    def filter_paths(self, paths):
        """Filter to show only directories."""
        try:
            return [p for p in paths if p.is_dir() and not p.name.startswith('.')]
        except (OSError, PermissionError):
            return []
    
    def on_mount(self):
        """Handle mount errors gracefully."""
        try:
            self.reload()
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOM WIDGETS
# ═══════════════════════════════════════════════════════════════════════════════

class FormatSelector(Widget):
    """Format selector with arrow key navigation."""
    
    FORMATS = [("markdown", "MD"), ("xml", "XML"), ("plain", "TXT")]
    
    can_focus = True
    
    DEFAULT_CSS = """
    FormatSelector {
        height: 2;
        layout: horizontal;
        align: center middle;
        padding: 0;
    }
    FormatSelector:focus {
        border: round #7f9825;
    }
    FormatSelector .format-btn {
        width: 1fr;
        height: 1;
        min-width: 5;
        background: #1a1a1a;
        color: #606060;
        border: none;
        margin: 0 1 0 0;
        padding: 0;
    }
    FormatSelector .format-btn:hover {
        background: #252525;
        color: #909090;
    }
    FormatSelector .format-btn.format-active {
        background: #7f9825;
        color: #0a0a0a;
        text-style: bold;
    }
    """
    
    current_format = reactive("markdown")
    
    class FormatChanged(Message):
        """Posted when format changes."""
        def __init__(self, format: str):
            self.format = format
            super().__init__()
    
    def __init__(self, initial_format: str = "markdown", **kwargs):
        super().__init__(**kwargs)
        self.current_format = initial_format
    
    def compose(self) -> ComposeResult:
        for fmt, label in self.FORMATS:
            classes = "format-btn format-active" if fmt == self.current_format else "format-btn"
            yield Button(label, id=f"fmt-{fmt}", classes=classes)
    
    def _update_buttons(self):
        """Update button active states."""
        for fmt, _ in self.FORMATS:
            try:
                btn = self.query_one(f"#fmt-{fmt}", Button)
                if fmt == self.current_format:
                    btn.add_class("format-active")
                else:
                    btn.remove_class("format-active")
            except Exception:
                pass
    
    def watch_current_format(self, new_format: str):
        """React to format changes."""
        self._update_buttons()
        self.post_message(self.FormatChanged(new_format))
    
    def on_button_pressed(self, event: Button.Pressed):
        """Handle button clicks."""
        btn_id = event.button.id
        if btn_id and btn_id.startswith("fmt-"):
            new_fmt = btn_id[4:]  # Remove "fmt-" prefix
            self.current_format = new_fmt
            event.stop()
    
    def on_key(self, event) -> None:
        """Handle left/right arrow keys."""
        formats = [f[0] for f in self.FORMATS]
        idx = formats.index(self.current_format) if self.current_format in formats else 0
        
        if event.key == "left":
            new_idx = (idx - 1) % len(formats)
            self.current_format = formats[new_idx]
            event.stop()
        elif event.key == "right":
            new_idx = (idx + 1) % len(formats)
            self.current_format = formats[new_idx]
            event.stop()


class KeyHelperBar(Static):
    """btop-style key helper bar at the bottom of the screen."""
    
    DEFAULT_CSS = """
    KeyHelperBar {
        dock: bottom;
        height: 1;
        background: #0a0a0a;
        color: #606060;
        padding: 0 1;
    }
    """
    
    def __init__(self, keys: list[tuple[str, str]], **kwargs):
        """Initialize with list of (key, description) tuples."""
        super().__init__(**kwargs)
        self.keys = keys
    
    def compose(self) -> ComposeResult:
        return []
    
    def on_mount(self):
        self._update_display()
    
    def _update_display(self):
        """Update the key helper display."""
        parts = []
        for key, desc in self.keys:
            parts.append(f"[#7f9825 bold]{key}[/][#505050]:{desc}[/]")
        self.update("  ".join(parts))


# ═══════════════════════════════════════════════════════════════════════════════
# MODAL SCREENS
# ═══════════════════════════════════════════════════════════════════════════════

class ChangeDirectoryModal(ModalScreen):
    """Modal for changing the project directory with mini file explorer."""
    
    BINDINGS = [("escape", "cancel", "Cancel")]
    
    def __init__(self, current_path: Path):
        super().__init__()
        self.current_path = current_path
        self._valid_path = True
    
    def compose(self) -> ComposeResult:
        with Container(id="change-dir-modal"):
            yield Static("📁 Change Project Directory", classes="modal-title")
            
            # Path input with suggester
            with Vertical(id="path-input-section"):
                yield Static("Enter path or browse below:", classes="modal-subtitle")
                yield Input(
                    value=str(self.current_path), 
                    placeholder="/path/to/project", 
                    id="dir-input",
                    suggester=PathSuggester(use_cache=False, case_sensitive=True)
                )
                yield Static("", id="path-validation", classes="validation-msg")
            
            # Navigation buttons
            with Horizontal(id="nav-buttons"):
                yield Button("⬆ Up", id="btn-up-dir", classes="nav-btn")
                yield Button("🏠 Home", id="btn-home-dir", classes="nav-btn")
            
            # Mini folder explorer
            with Vertical(id="folder-explorer-section"):
                yield Static("📂 Browse Folders:", classes="modal-subtitle")
                yield FolderOnlyTree(str(self.current_path), id="folder-tree")
            
            # Action buttons
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-modal-cancel", variant="default")
                yield Button("Confirm", id="btn-modal-confirm", variant="primary")
    
    def on_mount(self):
        self.query_one("#dir-input", Input).focus()
        self._validate_path(str(self.current_path))
    
    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn-modal-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-modal-confirm":
            self._confirm()
        elif event.button.id == "btn-up-dir":
            self._go_up()
        elif event.button.id == "btn-home-dir":
            self._go_home()
    
    def on_input_changed(self, event: Input.Changed):
        """Validate path as user types."""
        if event.input.id == "dir-input":
            self._validate_path(event.value)
    
    def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == "dir-input" and self._valid_path:
            self._confirm()
    
    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected):
        """Handle folder selection from tree."""
        selected_path = event.path
        input_widget = self.query_one("#dir-input", Input)
        input_widget.value = str(selected_path)
        self._validate_path(str(selected_path))
    
    def _validate_path(self, value: str):
        """Validate the path and update UI feedback."""
        validation = self.query_one("#path-validation", Static)
        confirm_btn = self.query_one("#btn-modal-confirm", Button)
        
        if not value.strip():
            validation.update("[#d4a520]⚠ Please enter a directory path[/]")
            self._valid_path = False
            confirm_btn.disabled = True
            return
        
        try:
            target = Path(value).expanduser().resolve()
            
            if not target.exists():
                validation.update("[#c73030]✗ Path does not exist[/]")
                self._valid_path = False
                confirm_btn.disabled = True
            elif not target.is_dir():
                validation.update("[#c73030]✗ Path is not a directory[/]")
                self._valid_path = False
                confirm_btn.disabled = True
            elif not os.access(target, os.R_OK):
                validation.update("[#c73030]✗ Permission denied[/]")
                self._valid_path = False
                confirm_btn.disabled = True
            else:
                validation.update("[#7f9825]✓ Valid directory[/]")
                self._valid_path = True
                confirm_btn.disabled = False
        except Exception as e:
            validation.update(f"[#c73030]✗ Invalid: {str(e)[:30]}[/]")
            self._valid_path = False
            confirm_btn.disabled = True
    
    def _go_up(self):
        """Navigate to parent directory."""
        input_widget = self.query_one("#dir-input", Input)
        try:
            current = Path(input_widget.value).expanduser()
            parent = current.parent
            if parent != current:  # Not at root
                input_widget.value = str(parent)
                self._validate_path(str(parent))
                self._update_folder_tree(parent)
        except Exception:
            pass
    
    def _go_home(self):
        """Navigate to home directory."""
        home = Path.home()
        input_widget = self.query_one("#dir-input", Input)
        input_widget.value = str(home)
        self._validate_path(str(home))
        self._update_folder_tree(home)
    
    def _update_folder_tree(self, new_path: Path):
        """Update the folder tree to show a new path."""
        try:
            # Validate path before attempting to create tree
            if not new_path.exists() or not new_path.is_dir():
                self.app.notify("Invalid directory path", severity="warning")
                return
            
            folder_section = self.query_one("#folder-explorer-section", Vertical)
            # Remove old tree safely
            try:
                old_tree = self.query_one("#folder-tree", FolderOnlyTree)
                old_tree.remove()
            except Exception:
                pass
            
            # Create new tree with the new path
            try:
                new_tree = FolderOnlyTree(str(new_path), id="folder-tree")
                folder_section.mount(new_tree)
            except Exception as e:
                # If tree creation fails, show error but don't crash
                self.app.notify(f"Could not browse: {str(e)[:30]}", severity="warning")
        except Exception as e:
            self.app.notify(f"Error: {str(e)[:30]}", severity="error")
    
    def _confirm(self):
        if not self._valid_path:
            self.app.notify("Please enter a valid directory path", severity="warning")
            return
        value = self.query_one("#dir-input", Input).value.strip()
        target = Path(value).expanduser().resolve()
        self.dismiss(target)
    
    def action_cancel(self):
        self.dismiss(None)


class HelpScreen(ModalScreen):
    """Help screen modal."""
    
    BINDINGS = [("escape", "close", "Close"), ("h", "close", "Close")]
    
    def compose(self) -> ComposeResult:
        with Container(id="help-overlay"):
            yield Static("⌨️  Keyboard Shortcuts", classes="help-title")
            yield Static("""
[bold #7f9825]Navigation[/]
  [#e4e4e4]↑/↓[/]       Move cursor in tree
  [#e4e4e4]←/→[/]       Collapse/expand folders

[bold #7f9825]Selection[/]
  [#e4e4e4]Space[/]     Toggle file/folder selection
  [#e4e4e4]Enter[/]     Open/close folder (select for files)
  [#e4e4e4]a[/]         Select all files
  [#e4e4e4]A[/]         Deselect all files

[bold #7f9825]Actions[/]
  [#e4e4e4]c[/]         Change directory
  [#e4e4e4]g[/]         Generate and copy to clipboard
  [#e4e4e4]r[/]         Refresh tree

[bold #7f9825]General[/]
  [#e4e4e4]h / ?[/]     Toggle this help
  [#e4e4e4]q[/]         Quit application
""", classes="help-content")
    
    def on_click(self):
        self.dismiss()
    
    def action_close(self):
        self.dismiss()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

class CodeClipApp(App):
    """CodeClip - Copy codebase to clipboard."""
    
    CSS_PATH = "terminal_app.css"
    TITLE = "CodeClip"
    
    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("h", "toggle_help", "Help", show=False),
        Binding("question_mark", "toggle_help", "Help", show=False),
        Binding("space", "toggle_select", "Select", show=False),
        Binding("enter", "toggle_node_or_select", "Enter", show=False),
        Binding("a", "select_all", "All", show=False),
        Binding("A", "deselect_all", "Deselect All", show=False),
        Binding("c", "change_dir", "Dir", show=False),
        Binding("g", "generate", "Copy", show=False),
        Binding("r", "refresh", "Refresh", show=False),
        Binding("tab", "focus_next_section", "Next Section", show=False),
        Binding("shift+tab", "focus_prev_section", "Prev Section", show=False),
    ]
    
    def __init__(self):
        super().__init__()
        self._state = self._load_state()
        last_dir = Path(self._state.get("last_dir", Path.cwd()))
        self.current_dir = last_dir if last_dir.is_dir() else Path.cwd()
        self._processing = False
        self._output_format = self._state.get("output_format", "markdown")
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        with Horizontal(id="main-container"):
            # Left panel - File tree
            with Vertical(id="left-panel"):
                with Container(id="left-panel-title-box"):
                    yield Static("📂 files", id="tree-title")
                    yield Static("", id="tree-stats")
                with VerticalScroll(id="file-tree-container"):
                    yield Tree("", id="file-tree")
            
            # Right panel - Controls
            with Vertical(id="right-panel"):
                # File types section
                with Vertical(id="file-types-section", classes="section-box"):
                    with Horizontal(id="file-types-header"):
                        yield Static("📋 types", classes="section-title")
                        yield Button("✓", id="btn-all-types", classes="mini-btn")
                        yield Button("✗", id="btn-no-types", classes="mini-btn")
                    yield VerticalScroll(id="file-types-container")
                
                # Format section
                with Vertical(id="format-section", classes="section-box"):
                    yield Static("📄 format", classes="section-title")
                    yield FormatSelector(initial_format=self._output_format, id="format-selector")
                
                # Controls section
                with Vertical(id="controls-section", classes="section-box"):
                    yield Static("⚡ actions", classes="section-title")
                    with Vertical(id="controls-container"):
                        yield Button("📋 Copy to Clipboard", id="btn-generate", classes="control-btn primary-btn")
                        with Horizontal(id="select-buttons"):
                            yield Button("Select All", id="btn-select-all", classes="control-btn half-btn")
                            yield Button("Clear All", id="btn-deselect-all", classes="control-btn half-btn")
                        yield Button("📁 Change Directory", id="btn-change-dir", classes="control-btn")
                
                # Status section
                with Vertical(id="status-section", classes="section-box"):
                    yield Static("📊 status", classes="section-title")
                    yield Static("Ready", id="status-text")
                    yield Static("", id="dir-path")
        
        # btop-style key helper bar at bottom
        yield KeyHelperBar([
            ("q", "quit"),
            ("h", "help"),
            ("tab", "section"),
            ("space", "select"),
            ("enter", "open"),
            ("←/→", "format"),
            ("g", "copy"),
            ("c", "dir"),
        ], id="key-helper")
    
    def on_mount(self):
        """Initialize the app on mount."""
        self.title = f"CodeClip - {self.current_dir.name}"
        self.sub_title = str(self.current_dir)
        self.load_directory()
    
    def on_format_selector_format_changed(self, event: FormatSelector.FormatChanged):
        """Handle format changes from FormatSelector."""
        self._output_format = event.format
        self._persist_state()
    
    def load_directory(self):
        """Load the current directory into the tree."""
        # Update header
        self.title = f"CodeClip - {self.current_dir.name}"
        self.sub_title = str(self.current_dir)
        
        # Build tree
        tree = self.query_one("#file-tree", Tree)
        tree.auto_expand = False
        tree.clear()
        tree.root.set_label(f"📁 {self.current_dir.name}")
        tree.root.data = {"path": "", "is_dir": True, "selected": True}
        
        folder_tree = build_folder_tree(self.current_dir)
        self._add_nodes(tree.root, folder_tree)
        tree.root.expand()
        
        # Update file types
        self._update_file_types()
        
        # Apply saved state
        self._apply_saved_state(tree)
        
        # Update status
        self._update_stats()
        self._update_dir_path()
        
        # Save state
        self._persist_state()
    
    def _add_nodes(self, parent_node, folder_tree):
        """Recursively add nodes to the tree."""
        # Add folders first
        for folder, sub_tree in sorted(folder_tree["subfolders"].items()):
            label = self._format_label(folder, True, is_dir=True)
            child = parent_node.add(label, data={"path": folder, "is_dir": True, "selected": True})
            self._add_nodes(child, sub_tree)
        
        # Add files
        for file in folder_tree["files"]:
            label = self._format_label(file, True, is_dir=False)
            parent_node.add_leaf(label, data={"path": file, "is_dir": False, "selected": True})
    
    def _format_label(self, name: str, selected, is_dir: bool) -> str:
        """Format a tree node label."""
        if is_dir:
            # Tri-state for folders: selected, unselected, partial
            if selected == "partial":
                icon = "[#d4a520]◧[/]"  # Orange half-filled for partial
            elif selected:
                icon = "[#7f9825]■[/]"  # Green filled for selected
            else:
                icon = "[#404040]□[/]"  # Dark gray empty for unselected
            return f"{icon} 📁 {name}"
        else:
            # Binary state for files
            icon = "[#7f9825]●[/]" if selected else "[#404040]○[/]"
            return f"{icon} {name}"
    
    def _refresh_node_label(self, node):
        """Refresh a node's label based on its selection state."""
        if not node or not node.data:
            return
        node.set_label(self._format_label(
            node.data.get("path", ""),
            node.data.get("selected", False),
            node.data.get("is_dir", False)
        ))
    
    def _update_file_types(self):
        """Update the file types section."""
        container = self.query_one("#file-types-container")
        
        # Clear existing children properly
        container.remove_children()
        
        # Scan extensions
        ext_counts, _ = scan_file_extensions(self.current_dir)
        sorted_exts = sorted(ext_counts.keys(), key=lambda e: ext_counts[e], reverse=True)
        
        # Load saved extensions
        saved_exts = set(self._state.get("selected_exts", []))
        
        # Store extension mapping using name attribute instead of id
        self._ext_checkboxes = []
        
        # Add checkboxes without IDs to avoid conflicts
        for ext in sorted_exts:
            count = ext_counts[ext]
            cb = Checkbox(f"{ext} ({count})", value=not saved_exts or ext in saved_exts, 
                         classes="ext-checkbox", name=ext.lower())
            self._ext_checkboxes.append((ext.lower(), cb))
            container.mount(cb)
    
    def _get_checkbox_ext(self, cb: Checkbox) -> str:
        """Get the extension for a checkbox."""
        return cb.name if cb.name else ""
    
    def _apply_saved_state(self, tree):
        """Apply saved selection state to the tree."""
        saved_files = {Path(p) for p in self._state.get("selected_files", []) if p}
        has_saved = bool(saved_files)
        
        for node in walk_tree(tree.root):
            if not node.data:
                continue
            if node.data.get("is_dir"):
                continue
            
            rel_path = node_relative_path(node)
            if has_saved:
                node.data["selected"] = rel_path in saved_files
            else:
                node.data["selected"] = True
            self._refresh_node_label(node)
        
        # Update directory states
        self._update_dir_selection_states()
    
    def _update_dir_selection_states(self):
        """Update directory selection states based on children (tri-state logic)."""
        tree = self.query_one("#file-tree", Tree)
        
        def calculate_folder_state(node):
            """Recursively calculate folder state from bottom up."""
            if not node.data or not node.data.get("is_dir"):
                return node.data.get("selected", False) if node.data else False
            
            # First, calculate states for all child folders
            for child in node.children:
                if child.data and child.data.get("is_dir"):
                    calculate_folder_state(child)
            
            # Now calculate this folder's state based on all children
            children_states = []
            for child in node.children:
                if child.data:
                    state = child.data.get("selected", False)
                    children_states.append(state)
            
            if not children_states:
                return node.data.get("selected", False)
            
            all_true = all(s is True for s in children_states)
            all_false = all(s is False for s in children_states)
            
            if all_true:
                node.data["selected"] = True
            elif all_false:
                node.data["selected"] = False
            else:
                node.data["selected"] = "partial"
            
            self._refresh_node_label(node)
            return node.data["selected"]
        
        calculate_folder_state(tree.root)
    
    def _update_stats(self):
        """Update the stats display."""
        tree = self.query_one("#file-tree", Tree)
        total = 0
        selected = 0
        
        for node in walk_tree(tree.root):
            if node.data and not node.data.get("is_dir"):
                total += 1
                if node.data.get("selected"):
                    selected += 1
        
        stats = self.query_one("#tree-stats", Static)
        stats.update(f"[#7f9825]{selected}[/]/{total}")
        
        status = self.query_one("#status-text", Static)
        if self._processing:
            pass  # Don't update during processing
        else:
            status.update(f"Selected: [#7f9825]{selected}[/] of {total} files")
    
    def _update_dir_path(self):
        """Update the directory path display."""
        dir_path = self.query_one("#dir-path", Static)
        path_str = str(self.current_dir)
        if len(path_str) > 35:
            path_str = "..." + path_str[-32:]
        dir_path.update(f"[#505050]📍 {path_str}[/]")
    
    def _persist_state(self):
        """Save current state to file."""
        try:
            tree = self.query_one("#file-tree", Tree)
        except Exception:
            return
        
        selected_files = []
        for node in walk_tree(tree.root):
            if not node.data or node.data.get("is_dir"):
                continue
            if node.data.get("selected"):
                rel_path = node_relative_path(node)
                if rel_path:
                    selected_files.append(rel_path.as_posix())
        
        selected_exts = []
        for cb in self.query(".ext-checkbox"):
            if isinstance(cb, Checkbox) and cb.value:
                ext = self._get_checkbox_ext(cb)
                if ext:
                    selected_exts.append(ext)
        
        state = {
            "last_dir": str(self.current_dir),
            "selected_files": selected_files,
            "selected_exts": selected_exts,
            "output_format": self._output_format,
        }
        self._state = state
        
        try:
            STATE_FILE.write_text(json.dumps(state, indent=2))
        except Exception:
            pass
    
    def _load_state(self):
        """Load state from file."""
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {}
    
    # ═══════════════════════════════════════════════════════════════════════════
    # EVENT HANDLERS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def on_tree_node_selected(self, event):
        """Handle tree node selection (click) - toggle selection."""
        node = event.node
        if node and node.data:
            self._do_toggle_selection(node)
    
    def _do_toggle_selection(self, node):
        """Toggle selection for a node."""
        current_state = node.data.get("selected", True)
        
        if current_state == "partial" or current_state is False:
            new_state = True
        else:
            new_state = False
        
        node.data["selected"] = new_state
        self._refresh_node_label(node)
        
        if node.data.get("is_dir"):
            self._propagate_selection(node, new_state)
        
        self._update_dir_selection_states()
        self._update_stats()
        self._persist_state()
    
    def _propagate_selection(self, node, selected):
        """Propagate selection state to all children."""
        selected = bool(selected) if selected != "partial" else True
        for child in node.children:
            if child.data:
                child.data["selected"] = selected
                self._refresh_node_label(child)
                if child.data.get("is_dir"):
                    self._propagate_selection(child, selected)
    
    def on_checkbox_changed(self, event: Checkbox.Changed):
        """Handle checkbox changes."""
        self._persist_state()
    
    def on_button_pressed(self, event: Button.Pressed):
        """Handle button presses."""
        btn_id = event.button.id
        if btn_id == "btn-generate":
            self.action_generate()
        elif btn_id == "btn-select-all":
            self.action_select_all()
        elif btn_id == "btn-deselect-all":
            self.action_deselect_all()
        elif btn_id == "btn-change-dir":
            self.action_change_dir()
        elif btn_id == "btn-all-types":
            self._select_all_types()
        elif btn_id == "btn-no-types":
            self._deselect_all_types()
    
    def _select_all_types(self):
        """Select all file type checkboxes."""
        for cb in self.query(".ext-checkbox"):
            if isinstance(cb, Checkbox):
                cb.value = True
        self._persist_state()
    
    def _deselect_all_types(self):
        """Deselect all file type checkboxes."""
        for cb in self.query(".ext-checkbox"):
            if isinstance(cb, Checkbox):
                cb.value = False
        self._persist_state()
    
    # Section focus order: file-tree -> file-types-container -> format-selector -> btn-generate
    _FOCUS_SECTIONS = ["#file-tree", "#file-types-container", "#format-selector", "#btn-generate"]
    _current_section_idx = 0
    
    def action_focus_next_section(self):
        """Focus the next major section."""
        self._current_section_idx = (self._current_section_idx + 1) % len(self._FOCUS_SECTIONS)
        self._focus_current_section()
    
    def action_focus_prev_section(self):
        """Focus the previous major section."""
        self._current_section_idx = (self._current_section_idx - 1) % len(self._FOCUS_SECTIONS)
        self._focus_current_section()
    
    def _focus_current_section(self):
        """Focus the current section by index."""
        selector = self._FOCUS_SECTIONS[self._current_section_idx]
        try:
            widget = self.query_one(selector)
            widget.focus()
        except Exception:
            pass
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ACTIONS
    # ═══════════════════════════════════════════════════════════════════════════
    
    def action_toggle_help(self):
        """Show help screen."""
        self.push_screen(HelpScreen())
    
    def action_toggle_node_or_select(self):
        """Smart Enter action: toggle folder expansion OR select files."""
        try:
            tree = self.query_one("#file-tree", Tree)
            node = tree.cursor_node
            if node and node.data:
                if node.data.get("is_dir"):
                    node.toggle()
                else:
                    self._do_toggle_selection(node)
        except Exception:
            pass

    def action_toggle_select(self):
        """Toggle selection for focused node (Space key)."""
        try:
            tree = self.query_one("#file-tree", Tree)
            node = tree.cursor_node
            if node and node.data:
                self._do_toggle_selection(node)
        except Exception:
            pass
    
    def action_select_all(self):
        """Select all files."""
        tree = self.query_one("#file-tree", Tree)
        for node in walk_tree(tree.root):
            if node.data:
                node.data["selected"] = True
                self._refresh_node_label(node)
        tree.root.data["selected"] = True
        self._refresh_node_label(tree.root)
        self._update_stats()
        self._persist_state()
        self.notify("All files selected", severity="information")
    
    def action_deselect_all(self):
        """Deselect all files."""
        tree = self.query_one("#file-tree", Tree)
        for node in walk_tree(tree.root):
            if node.data:
                node.data["selected"] = False
                self._refresh_node_label(node)
        tree.root.data["selected"] = False
        self._refresh_node_label(tree.root)
        self._update_stats()
        self._persist_state()
        self.notify("All files deselected", severity="information")
    
    def action_change_dir(self):
        """Open directory change modal."""
        def handle_result(new_path):
            if new_path:
                self.current_dir = new_path
                self.load_directory()
                self.notify(f"Changed to: {new_path.name}", severity="information")
        
        self.push_screen(ChangeDirectoryModal(self.current_dir), handle_result)
    
    def action_refresh(self):
        """Refresh the directory tree."""
        self.load_directory()
        self.notify("Directory refreshed", severity="information")
    
    def action_generate(self):
        """Generate and copy to clipboard."""
        if self._processing:
            self.notify("Already processing...", severity="warning")
            return
        
        include_exts = set()
        for cb in self.query(".ext-checkbox"):
            if isinstance(cb, Checkbox) and cb.value:
                ext = self._get_checkbox_ext(cb)
                if ext:
                    include_exts.add(ext.lower())
        
        tree = self.query_one("#file-tree", Tree)
        selected_files = collect_selected_files(tree, include_exts, self.current_dir)
        
        if not selected_files:
            self.notify("No files selected or matching filters", severity="warning")
            return
        
        self._processing = True
        status = self.query_one("#status-text", Static)
        status.update("[#d4a520]⏳ Processing...[/]")
        
        thread = threading.Thread(target=self._process_files, args=(sorted(selected_files),))
        thread.daemon = True
        thread.start()
    
    def _process_files(self, files):
        """Process files and copy to clipboard (runs in thread)."""
        start_time = time.time()
        
        try:
            files_content = []
            file_count = 0
            total_size = 0
            errors = []
            
            for file_path in files:
                try:
                    rel_path = file_path.relative_to(self.current_dir)
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    lang = get_language(file_path.suffix)
                    
                    files_content.append((str(rel_path), content, lang))
                    file_count += 1
                    total_size += len(content.encode('utf-8'))
                except Exception as e:
                    errors.append(str(e))
            
            tree_string = get_tree_string(self.current_dir)
            
            if self._output_format == "xml":
                combined = format_output_xml(self.current_dir.name, tree_string, files_content)
            elif self._output_format == "plain":
                combined = format_output_plain(self.current_dir.name, tree_string, files_content)
            else:
                combined = format_output_markdown(self.current_dir.name, tree_string, files_content)
            
            success, msg = copy_to_clipboard(combined)
            
            duration = time.time() - start_time
            size_kb = total_size / 1024
            size_str = f"{size_kb/1024:.2f} MB" if size_kb >= 1024 else f"{size_kb:.1f} KB"
            
            if success:
                result_msg = f"[#7f9825]✓[/] Copied {file_count} files ({size_str}) in {duration:.1f}s"
            else:
                result_msg = f"[#d4a520]⚠[/] Generated but copy failed"
            
            if errors:
                result_msg += f" [#c73030]({len(errors)} errors)[/]"
            
            self.call_from_thread(self._finish_processing, result_msg, "information" if success else "warning")
        
        except Exception as e:
            self.call_from_thread(self._finish_processing, f"[#c73030]Error: {e}[/]", "error")
    
    def _finish_processing(self, message, severity):
        """Finish processing and update UI."""
        self._processing = False
        status = self.query_one("#status-text", Static)
        status.update(message)
        # Clean message for notification
        clean_msg = message
        for tag in ["[#7f9825]", "[#d4a520]", "[#c73030]", "[/]"]:
            clean_msg = clean_msg.replace(tag, "")
        self.notify(clean_msg, severity=severity)
        self._update_stats()


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = CodeClipApp()
    app.run()
