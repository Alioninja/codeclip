import os
from pathlib import Path
from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Static, Input, Button, DirectoryTree
from textual.binding import Binding
from .widgets import PathSuggester, FolderOnlyTree

class ChangeDirectoryModal(ModalScreen):
    """Modal for changing the project directory with mini file explorer."""
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("tab", "modal_focus_next", "Next", priority=True),
        Binding("shift+tab", "modal_focus_previous", "Previous", priority=True),
    ]
    
    # Define the focus order for widgets in this modal
    FOCUS_ORDER = [
        "#dir-input",
        "#btn-up-dir", 
        "#btn-home-dir",
        "#folder-tree",
        "#btn-modal-cancel",
        "#btn-modal-confirm",
    ]
    
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
    
    def _get_focusable_widgets(self):
        """Get list of focusable widgets in order."""
        widgets = []
        for selector in self.FOCUS_ORDER:
            try:
                widget = self.query_one(selector)
                if widget.can_focus:
                    widgets.append(widget)
            except Exception:
                pass
        return widgets
    
    def action_modal_focus_next(self):
        """Focus next widget within modal only."""
        widgets = self._get_focusable_widgets()
        if not widgets:
            return
        
        focused = self.app.focused
        try:
            idx = widgets.index(focused)
            next_idx = (idx + 1) % len(widgets)
        except ValueError:
            next_idx = 0
        
        widgets[next_idx].focus()
    
    def action_modal_focus_previous(self):
        """Focus previous widget within modal only."""
        widgets = self._get_focusable_widgets()
        if not widgets:
            return
        
        focused = self.app.focused
        try:
            idx = widgets.index(focused)
            prev_idx = (idx - 1) % len(widgets)
        except ValueError:
            prev_idx = len(widgets) - 1
        
        widgets[prev_idx].focus()
    
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
            # Resolve and validate path
            new_path = new_path.resolve()
            if not new_path.exists() or not new_path.is_dir():
                self.app.notify("Invalid directory path", severity="warning")
                return
            
            # Try to get existing tree and update its path
            try:
                tree = self.query_one("#folder-tree", FolderOnlyTree)
                tree.path = new_path
                tree.reload()
                # Expand root after reload
                self.call_after_refresh(lambda: self._expand_tree_root(tree))
            except Exception as e:
                self.app.notify(f"Could not browse: {str(e)[:30]}", severity="warning")
        except Exception as e:
            self.app.notify(f"Error: {str(e)[:30]}", severity="error")
    
    def _expand_tree_root(self, tree: FolderOnlyTree):
        """Helper to expand tree root after it's mounted."""
        try:
            if tree.root and not tree.root.is_expanded:
                tree.root.expand()
        except Exception:
            pass
    
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
  [#e4e4e4]Tab[/]       Switch focus between panels

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
