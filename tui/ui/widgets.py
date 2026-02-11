import os
from pathlib import Path
from textual.widget import Widget
from textual.widgets import Button, Static, DirectoryTree, Tree, Checkbox
from textual.containers import VerticalScroll
from textual.app import ComposeResult
from textual.reactive import reactive
from textual.message import Message
from textual.suggester import Suggester
from textual.binding import Binding


class TypeToggle(Static):
    """A custom toggle widget that looks like the file tree items."""
    
    can_focus = True
    
    DEFAULT_CSS = """
    TypeToggle {
        height: 1;
        border: none;
        padding: 0;
        margin: 0;
        background: transparent;
        color: #e0e0e0;
    }
    TypeToggle:focus {
        background: $accent;
        color: $text;
        text-style: bold;
    }
    TypeToggle:hover {
        background: $accent 50%;
    }
    """
    
    class Changed(Message):
        """Posted when the toggle state changes."""
        def __init__(self, toggle):
            self.toggle = toggle
            super().__init__()

    def __init__(self, label: str, count: int, value: bool = False, name: str | None = None, **kwargs):
        super().__init__(name=name, **kwargs)
        self.ext_label = label
        self.count = count
        self.value = value
        
    def on_mount(self):
        self._refresh_label()

    def _refresh_label(self):
        icon = "[#00afff]■[/]" if self.value else "[#404040]□[/]"
        self.update(f"{icon} {self.ext_label} ({self.count})")

    def toggle(self):
        self.value = not self.value
        self._refresh_label()
        self.post_message(self.Changed(self))

    def on_click(self):
        self.toggle()
        
    def action_toggle(self):
        self.toggle()

    BINDINGS = [
        Binding("space", "toggle", "Toggle", show=False),
        Binding("enter", "toggle", "Toggle", show=False),
        Binding("tab", "app.focus_next_section", "Next Section", show=False),
        Binding("shift+tab", "app.focus_prev_section", "Prev Section", show=False),
    ]


class FormatButton(Button):
    """Button for format selection with left/right navigation."""
    
    BINDINGS = [
        Binding("left", "focus_prev", "Previous", show=False),
        Binding("right", "focus_next", "Next", show=False),
        Binding("space", "press_button", "Select", show=False),
        Binding("tab", "app.focus_next_section", "Next Section", show=False),
        Binding("shift+tab", "app.focus_prev_section", "Prev Section", show=False),
    ]
    
    def action_press_button(self):
        """Press this button."""
        self.press()
    
    def action_focus_prev(self):
        """Focus previous sibling button."""
        self._move_focus(-1)
    
    def action_focus_next(self):
        """Focus next sibling button."""
        self._move_focus(1)
    
    def _move_focus(self, direction: int):
        """Move focus to sibling button."""
        parent = self.parent
        if not parent:
            return
        children = [c for c in parent.children if isinstance(c, FormatButton)]
        if not children:
            return
        try:
            idx = children.index(self)
            new_idx = (idx + direction) % len(children)
            children[new_idx].focus()
        except ValueError:
            pass





class FormatSelector(Widget):
    """Format selector container."""
    
    FORMATS = [("markdown", "MD"), ("xml", "XML"), ("plain", "TXT")]
    
    can_focus = False
    
    DEFAULT_CSS = """
    FormatSelector {
        height: 2;
        layout: horizontal;
        align: center middle;
        padding: 0;
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
    FormatSelector .format-btn:focus {
        text-style: bold;
        color: #ffaf00;
    }
    FormatSelector .format-btn.format-active {
        background: #ffaf00;
        color: #101010;
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
            yield FormatButton(label, id=f"fmt-{fmt}", classes=classes)
    
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

class KeyHelperBar(Static):
    """btop-style key helper bar at the bottom of the screen."""
    
    DEFAULT_CSS = """
    KeyHelperBar {
        dock: bottom;
        height: auto;
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
            # btop style: Key in white/bold, Desc in gray/dim
            # Use braille blank (\u2800) between key and desc to keep them together.
            # Rich wraps on characters where str.isspace() is True; \u2800 is not
            # whitespace so Rich will never break the line between key and desc.
            parts.append(f"[bold #e0e0e0]{key}[/]\u2800[#606060]{desc}[/]")
        self.update("   ".join(parts))


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
        """Handle mount and auto-expand root to show folders."""
        try:
            # Reload and expand root to show contents
            self.reload()
            # Schedule expansion after reload completes
            self.call_after_refresh(self._expand_root)
        except Exception:
            pass
    
    def _expand_root(self):
        """Expand the root node to show folder contents."""
        try:
            if self.root and not self.root.is_expanded:
                self.root.expand()
        except Exception:
            pass


class FileTree(Tree):
    """Custom Tree widget with proper left/right arrow handling for expand/collapse."""
    
    BINDINGS = [
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("left", "collapse_or_parent", "Collapse", show=False),
        Binding("right", "expand_or_child", "Expand", show=False),
        Binding("tab", "app.focus_next_section", "Next Section", show=False),
        Binding("shift+tab", "app.focus_prev_section", "Prev Section", show=False),
        Binding("space", "app.toggle_select", "Select", show=False),
        Binding("enter", "app.toggle_select", "Select", show=False),
    ]
    
    def action_collapse_or_parent(self):
        """Collapse current node or move to parent (without triggering selection)."""
        node = self.cursor_node
        if node:
            if node.is_expanded:
                node.collapse()
            elif node.parent and node.parent.parent is not None:
                # Move cursor to parent folder without selecting
                self.move_cursor(node.parent)
    
    def action_expand_or_child(self):
        """Expand current node or move to first child (without triggering selection)."""
        node = self.cursor_node
        if node:
            if node.allow_expand:
                if not node.is_expanded:
                    node.expand()
                elif node.children:
                    # Move cursor to first child without selecting
                    self.move_cursor(node.children[0])


class NavigationScroll(VerticalScroll):
    """VerticalScroll containing checkboxes with up/down navigation between them."""
    
    BINDINGS = [
        Binding("up", "focus_prev_child", "Up", show=False),
        Binding("down", "focus_next_child", "Down", show=False),
        # Left/right do nothing - prevent any issues
        Binding("left", "noop", "Left", show=False),
        Binding("right", "noop", "Right", show=False),
        Binding("tab", "app.focus_next_section", "Next Section", show=False),
        Binding("shift+tab", "app.focus_prev_section", "Prev Section", show=False),
    ]
    
    def action_noop(self):
        """Do nothing - prevent crashes from unhandled keys."""
        pass
    
    def action_focus_prev_child(self):
        """Focus the previous child checkbox."""
        self._move_focus(-1)
    
    def action_focus_next_child(self):
        """Focus the next child checkbox."""
        self._move_focus(1)
    
    def _move_focus(self, direction: int):
        """Move focus to sibling checkbox."""
        focused = self.app.focused
        if not focused:
            # Focus first child
            if self.children:
                self.children[0].focus()
            return
        
        # Get focusable children
        children = [c for c in self.children if c.can_focus]
        if not children:
            return
        
        try:
            idx = children.index(focused)
            new_idx = idx + direction
            # Clamp to bounds (don't wrap)
            if 0 <= new_idx < len(children):
                children[new_idx].focus()
                # Scroll to make visible
                self.scroll_to_widget(children[new_idx])
        except ValueError:
            # Focused widget not in children, focus first
            children[0].focus()
