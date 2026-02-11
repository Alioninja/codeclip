import os
from pathlib import Path
from textual.screen import ModalScreen
from textual.app import ComposeResult
from textual.containers import Container, Vertical, Horizontal, VerticalScroll
from textual.widgets import Static, Input, Button, DirectoryTree, ProgressBar, Label
from textual.binding import Binding
from textual.message import Message
from .widgets import PathSuggester, FolderOnlyTree


class FormatOption(Static):
    """A custom radio-style option widget with proper focus/hover support."""

    can_focus = True

    BINDINGS = [
        Binding("space", "select", "Select", show=False),
        Binding("enter", "select", "Select", show=False),
        Binding("left", "focus_prev_option", "Previous", show=False),
        Binding("right", "focus_next_option", "Next", show=False),
    ]

    class Selected(Message):
        """Posted when this option is selected."""
        def __init__(self, option: "FormatOption"):
            self.option = option
            super().__init__()

    def __init__(self, label: str, format_key: str, selected: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.label_text = label
        self.format_key = format_key
        self.selected = selected

    def on_mount(self):
        self._refresh_display()

    def _refresh_display(self):
        icon = "●" if self.selected else "○"
        self.update(f"{icon} {self.label_text}")

    def set_selected(self, value: bool):
        self.selected = value
        self._refresh_display()

    def action_select(self):
        self.post_message(self.Selected(self))

    def on_click(self):
        self.post_message(self.Selected(self))

    def action_focus_prev_option(self):
        self._move_focus(-1)

    def action_focus_next_option(self):
        self._move_focus(1)

    def _move_focus(self, direction: int):
        parent = self.parent
        if not parent:
            return
        siblings = [c for c in parent.children if isinstance(c, FormatOption)]
        if not siblings:
            return
        try:
            idx = siblings.index(self)
            new_idx = (idx + direction) % len(siblings)
            siblings[new_idx].focus()
        except ValueError:
            pass

class ChangeDirectoryModal(ModalScreen):
    """Modal for changing the project directory with mini file explorer."""
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("tab", "modal_focus_next", "Next", priority=True),
        Binding("shift+tab", "modal_focus_previous", "Previous", priority=True),
        Binding("up", "nav_up", "Up", show=False),
        Binding("down", "nav_down", "Down", show=False),
        Binding("left", "nav_left", "Left", show=False),
        Binding("right", "nav_right", "Right", show=False),
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
        
    def action_nav_up(self):
        """Navigate up between sections."""
        focused = self.app.focused
        if not focused:
            return
            
        if focused.id in ["btn-up-dir", "btn-home-dir"]:
            self.query_one("#dir-input").focus()
        elif focused.id == "folder-tree":
            # Optional: Allow escaping tree with Up if at top? 
            # For now, let Tree handle Up (scrolling)
            pass
        elif focused.id in ["btn-modal-cancel", "btn-modal-confirm"]:
            self.query_one("#folder-tree").focus()
            
    def action_nav_down(self):
        """Navigate down between sections."""
        focused = self.app.focused
        if not focused:
            return
            
        if focused.id == "dir-input":
            self.query_one("#btn-up-dir").focus()
        elif focused.id in ["btn-up-dir", "btn-home-dir"]:
            self.query_one("#folder-tree").focus()
        elif focused.id == "folder-tree":
            # Tree handles down, usually.
            pass
            
    def action_nav_left(self):
        """Navigate left between buttons."""
        focused = self.app.focused
        if not focused:
            return
            
        if focused.id == "btn-home-dir":
            self.query_one("#btn-up-dir").focus()
        elif focused.id == "btn-modal-confirm":
            self.query_one("#btn-modal-cancel").focus()
            
    def action_nav_right(self):
        """Navigate right between buttons."""
        focused = self.app.focused
        if not focused:
            return
            
        if focused.id == "btn-up-dir":
            self.query_one("#btn-home-dir").focus()
        elif focused.id == "btn-modal-cancel":
            self.query_one("#btn-modal-confirm").focus()
    
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
  [#e4e4e4]Space/Enter[/] Toggle file/folder selection
  [#e4e4e4]a[/]         Select all files
  [#e4e4e4]A[/]         Deselect all files

[bold #7f9825]Actions[/]
  [#e4e4e4]c[/]         Change directory
  [#e4e4e4]g[/]         Generate and copy to clipboard
  [#e4e4e4]r[/]         Refresh tree
  [#e4e4e4]m[/]         Open menu (settings, etc.)

[bold #7f9825]General[/]
  [#e4e4e4]h / ?[/]     Toggle this help
  [#e4e4e4]q[/]         Quit application
""", classes="help-content")
    
    def on_click(self):
        self.dismiss()
    
    def action_close(self):
        self.dismiss()


class CopyProgressModal(ModalScreen):
    """Modal showing progress of the copy operation with cancel capability."""
    
    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
    ]
    
    def __init__(self, total_files: int):
        super().__init__()
        self.total_files = total_files
        self.current_file = 0
        self.cancelled = False
        self._result = None
        self._error = None
    
    def compose(self) -> ComposeResult:
        with Container(id="progress-modal"):
            yield Static("📋 Copying to Clipboard", classes="modal-title")
            yield Static("", id="progress-status")
            yield ProgressBar(total=100, show_eta=False, id="copy-progress")
            yield Static("", id="progress-file")
            with Horizontal(classes="modal-buttons"):
                yield Button("Cancel", id="btn-cancel-copy", variant="error")
    
    def on_mount(self):
        """Start with 0% progress."""
        self.update_progress(0, "Starting...")
    
    def update_progress(self, current: int, filename: str = ""):
        """Update progress display."""
        if self.cancelled:
            return
        self.current_file = current
        progress = int((current / self.total_files) * 100) if self.total_files > 0 else 0
        
        try:
            status = self.query_one("#progress-status", Static)
            status.update(f"Processing file {current} of {self.total_files}")
            
            progress_bar = self.query_one("#copy-progress", ProgressBar)
            progress_bar.update(progress=progress)
            
            file_label = self.query_one("#progress-file", Static)
            if filename:
                # Truncate long filenames
                if len(filename) > 40:
                    filename = "..." + filename[-37:]
                file_label.update(f"[#606060]{filename}[/]")
        except Exception:
            pass
    
    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn-cancel-copy":
            self.action_cancel()
    
    def action_cancel(self):
        """Cancel the copy operation."""
        self.cancelled = True
        try:
            status = self.query_one("#progress-status", Static)
            status.update("[#d4a520]Cancelling...[/]")
        except Exception:
            pass
        # Dismiss with cancelled result
        self.dismiss((False, "Cancelled by user", 0))


class SettingsScreen(ModalScreen):
    """Settings modal for configuring long list summarization thresholds."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel", priority=True),
        Binding("tab", "settings_focus_next", "Next", priority=True),
        Binding("shift+tab", "settings_focus_prev", "Previous", priority=True),
        Binding("left", "btn_prev", "Previous", show=False),
        Binding("right", "btn_next", "Next", show=False),
    ]

    FOCUS_ORDER = [
        "#input-max-files",
        "#input-show-first",
        "#input-show-last",
        "#input-max-dirs",
        "#input-show-first-dirs",
        "#input-show-last-dirs",
        "#fmt-markdown",
        "#tv-full",
        "#btn-settings-cancel",
        "#btn-settings-save",
    ]

    FORMAT_MAP = [
        ("markdown", "Markdown"),
        ("xml", "XML"),
        ("plain", "Plain Text"),
    ]

    TREE_VIEW_MAP = [
        ("full", "Full"),
        ("selection", "Selection"),
    ]

    def __init__(
        self,
        max_files_to_show_all: int = 25,
        tree_show_first: int = 10,
        tree_show_last: int = 3,
        max_dirs_to_show_all: int = 25,
        tree_show_first_dirs: int = 10,
        tree_show_last_dirs: int = 3,
        current_format: str = "markdown",
        current_tree_view: str = "full",
    ):
        super().__init__()
        self._max_files_to_show_all = max_files_to_show_all
        self._tree_show_first = tree_show_first
        self._tree_show_last = tree_show_last
        self._max_dirs_to_show_all = max_dirs_to_show_all
        self._tree_show_first_dirs = tree_show_first_dirs
        self._tree_show_last_dirs = tree_show_last_dirs
        self._current_format = current_format
        self._current_tree_view = current_tree_view

    def compose(self) -> ComposeResult:
        with Container(id="settings-modal"):
            yield Static("⚙  Settings", id="settings-title", classes="modal-title")

            # Scrollable content area
            with VerticalScroll(id="settings-scroll"):
                # Two-column layout: files left, directories right
                with Horizontal(id="settings-columns"):
                    # File long list summarization section (left column)
                    with Vertical(id="settings-section"):
                        yield Static(
                            "[bold #7f9825]File Summarization[/]\n"
                            "[#808080]When a directory has more\n"
                            "files than the threshold,\n"
                            "only first/last N are shown.[/]",
                            id="settings-description",
                        )

                        with Vertical(classes="setting-row"):
                            yield Label("Max files before summarizing:", classes="setting-label")
                            yield Input(
                                value=str(self._max_files_to_show_all),
                                placeholder="25",
                                id="input-max-files",
                                type="integer",
                            )

                        with Vertical(classes="setting-row"):
                            yield Label("Show first N files:", classes="setting-label")
                            yield Input(
                                value=str(self._tree_show_first),
                                placeholder="10",
                                id="input-show-first",
                                type="integer",
                            )

                        with Vertical(classes="setting-row"):
                            yield Label("Show last N files:", classes="setting-label")
                            yield Input(
                                value=str(self._tree_show_last),
                                placeholder="3",
                                id="input-show-last",
                                type="integer",
                            )

                    # Directory long list summarization section (right column)
                    with Vertical(id="settings-section-dirs"):
                        yield Static(
                            "[bold #7f9825]Directory Summarization[/]\n"
                            "[#808080]When a directory has more\n"
                            "subdirs than the threshold,\n"
                            "only first/last N are shown.[/]",
                            id="settings-description-dirs",
                        )

                        with Vertical(classes="setting-row"):
                            yield Label("Max dirs before summarizing:", classes="setting-label")
                            yield Input(
                                value=str(self._max_dirs_to_show_all),
                                placeholder="25",
                                id="input-max-dirs",
                                type="integer",
                            )

                        with Vertical(classes="setting-row"):
                            yield Label("Show first N dirs:", classes="setting-label")
                            yield Input(
                                value=str(self._tree_show_first_dirs),
                                placeholder="10",
                                id="input-show-first-dirs",
                                type="integer",
                            )

                        with Vertical(classes="setting-row"):
                            yield Label("Show last N dirs:", classes="setting-label")
                            yield Input(
                                value=str(self._tree_show_last_dirs),
                                placeholder="3",
                                id="input-show-last-dirs",
                                type="integer",
                            )

                # Output format section (full width)
                with Vertical(id="settings-format-section"):
                    yield Static(
                        "[bold #7f9825]Output Format[/]",
                        id="settings-format-label",
                    )
                    with Horizontal(id="settings-format-options"):
                        for fmt_key, fmt_label in self.FORMAT_MAP:
                            yield FormatOption(
                                fmt_label,
                                format_key=fmt_key,
                                selected=(fmt_key == self._current_format),
                                id=f"fmt-{fmt_key}",
                            )

                # Tree view mode section (full width)
                with Vertical(id="settings-treeview-section"):
                    yield Static(
                        "[bold #7f9825]Directory Tree View[/]",
                        id="settings-treeview-label",
                    )
                    with Horizontal(id="settings-treeview-options"):
                        for tv_key, tv_label in self.TREE_VIEW_MAP:
                            yield FormatOption(
                                tv_label,
                                format_key=tv_key,
                                selected=(tv_key == self._current_tree_view),
                                id=f"tv-{tv_key}",
                            )

            yield Static("", id="settings-validation", classes="validation-msg")

            # Action buttons (always visible at bottom)
            with Horizontal(id="settings-buttons", classes="modal-buttons"):
                yield Button("Cancel", id="btn-settings-cancel", variant="default")
                yield Button("Save", id="btn-settings-save", variant="primary")

    def on_mount(self):
        self.query_one("#input-max-files", Input).focus()

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

    def action_settings_focus_next(self):
        """Focus next widget within settings modal."""
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

    def action_settings_focus_prev(self):
        """Focus previous widget within settings modal."""
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

    def action_btn_prev(self):
        """Focus previous button when on a settings button."""
        focused = self.app.focused
        if focused and focused.id == "btn-settings-save":
            self.query_one("#btn-settings-cancel", Button).focus()

    def action_btn_next(self):
        """Focus next button when on a settings button."""
        focused = self.app.focused
        if focused and focused.id == "btn-settings-cancel":
            self.query_one("#btn-settings-save", Button).focus()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "btn-settings-cancel":
            self.dismiss(None)
        elif event.button.id == "btn-settings-save":
            self._save()

    def on_format_option_selected(self, event: FormatOption.Selected):
        """Handle format option selection - update options within the same group."""
        selected = event.option
        parent = selected.parent
        if not parent:
            return
        for option in parent.query(FormatOption):
            option.set_selected(option is selected)

    def on_input_submitted(self, event: Input.Submitted):
        """Save on Enter from any input."""
        self._save()

    def _save(self):
        """Validate and save settings."""
        validation = self.query_one("#settings-validation", Static)

        try:
            max_files = int(self.query_one("#input-max-files", Input).value)
            show_first = int(self.query_one("#input-show-first", Input).value)
            show_last = int(self.query_one("#input-show-last", Input).value)
            max_dirs = int(self.query_one("#input-max-dirs", Input).value)
            show_first_dirs = int(self.query_one("#input-show-first-dirs", Input).value)
            show_last_dirs = int(self.query_one("#input-show-last-dirs", Input).value)
        except (ValueError, TypeError):
            validation.update("[#c73030]✗ All values must be positive integers[/]")
            return

        if max_files < 1 or max_dirs < 1:
            validation.update("[#c73030]✗ Max thresholds must be at least 1[/]")
            return
        if show_first < 0 or show_last < 0 or show_first_dirs < 0 or show_last_dirs < 0:
            validation.update("[#c73030]✗ Show first/last cannot be negative[/]")
            return
        if show_first + show_last >= max_files:
            validation.update("[#c73030]✗ File first + last must be less than max files[/]")
            return
        if show_first_dirs + show_last_dirs >= max_dirs:
            validation.update("[#c73030]✗ Dir first + last must be less than max dirs[/]")
            return

        # Get selected format from FormatOption widgets
        output_format = self._current_format
        for option in self.query_one("#settings-format-options").query(FormatOption):
            if option.selected:
                output_format = option.format_key
                break

        # Get selected tree view mode from FormatOption widgets
        tree_view_mode = self._current_tree_view
        for option in self.query_one("#settings-treeview-options").query(FormatOption):
            if option.selected:
                tree_view_mode = option.format_key
                break

        self.dismiss({
            "max_files_to_show_all": max_files,
            "tree_show_first": show_first,
            "tree_show_last": show_last,
            "max_dirs_to_show_all": max_dirs,
            "tree_show_first_dirs": show_first_dirs,
            "tree_show_last_dirs": show_last_dirs,
            "output_format": output_format,
            "tree_view_mode": tree_view_mode,
        })

    def action_cancel(self):
        self.dismiss(None)
