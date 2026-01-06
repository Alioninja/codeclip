from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Tree, Checkbox, Button, Static
from textual.containers import Vertical, Horizontal, VerticalScroll, Container
from textual.binding import Binding

from .config import STATE_FILE
from .core.state import load_state, save_state
from .core.scanner import scan_file_extensions, build_folder_tree, get_tree_string, walk_tree, node_relative_path, collect_selected_files
from .core.clipboard import copy_to_clipboard
from .utils.helpers import get_language
from .ui.widgets import FormatSelector, KeyHelperBar, NavigationScroll, FileTree, ActionButton, TypeToggle
from .ui.screens import ChangeDirectoryModal, HelpScreen, CopyProgressModal
from .ui.formatters import format_output_markdown, format_output_xml, format_output_plain

class CodeClipApp(App):
    """CodeClip - Copy codebase to clipboard."""
    
    CSS_PATH = Path(__file__).parent / "terminal_app.tcss"
    TITLE = "CodeClip"
    
    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("h", "toggle_help", "Help", show=False),
        Binding("question_mark", "toggle_help", "Help", show=False),
        Binding("space", "action_space", "Select", show=False),
        Binding("enter", "action_enter", "Enter", show=False),
        Binding("ctrl+a", "toggle_all", "All/Clear", show=False),
        Binding("c", "change_dir", "Dir", show=False),
        Binding("g", "generate", "Copy", show=False),
        Binding("r", "refresh", "Refresh", show=False),
        Binding("tab", "focus_next_section", "Next Section", show=False),
        Binding("shift+tab", "focus_prev_section", "Prev Section", show=False),
        Binding("m", "command_palette", "Menu", show=False),
    ]
    
    def __init__(self):
        super().__init__()
        self._state = load_state()
        # Always use the current working directory (where user ran the command from)
        # This makes the tool work as expected when running `codeclip` from a terminal
        self.current_dir = Path.cwd()
        self._processing = False
        self._output_format = self._state.get("output_format", "markdown")
        self._ext_checkboxes = []
        self._copy_data = {}
        
        # Restore saved theme
        saved_theme = self._state.get("theme", "textual-dark")
        try:
            self.theme = saved_theme
        except Exception:
            self.theme = "textual-dark"
    
    def compose(self) -> ComposeResult:
        with Horizontal(id="main-container"):
            # Left panel - File tree
            with Vertical(id="left-panel"):
                with Container(id="left-panel-title-box"):
                    yield Static("📂 files", id="tree-title")
                    yield Static("", id="tree-stats")
                with VerticalScroll(id="file-tree-container"):
                    yield FileTree("Loading...", id="file-tree")
            
            # Right panel - Controls
            with Vertical(id="right-panel"):
                # File types section
                with Vertical(id="file-types-section", classes="section-box"):
                    with Horizontal(id="file-types-header"):
                        yield Static("📋 types", classes="section-title")
                        yield Button("✓", id="btn-all-types", classes="mini-btn")
                        yield Button("✗", id="btn-no-types", classes="mini-btn")
                    # Use NavigationScroll to allow arrow keys to bubble
                    yield NavigationScroll(id="file-types-container")
                
                # Format section
                with Vertical(id="format-section", classes="section-box"):
                    yield Static("📄 format", classes="section-title")
                    yield FormatSelector(initial_format=self._output_format, id="format-selector")
                
                # Controls section
                with Vertical(id="controls-section", classes="section-box"):
                    yield Static("⚡ actions", classes="section-title")
                    with Vertical(id="controls-container"):
                        yield ActionButton("📋 Copy to Clipboard", id="btn-generate", classes="control-btn primary-btn")
                        with Horizontal(id="select-buttons"):
                            yield ActionButton("Select All", id="btn-select-all", classes="control-btn half-btn")
                            yield ActionButton("Clear All", id="btn-deselect-all", classes="control-btn half-btn")
                        yield ActionButton("📁 Change Directory", id="btn-change-dir", classes="control-btn")
                
                # Status section
                with Vertical(id="status-section", classes="section-box"):
                    yield Static("📊 status", classes="section-title")
                    yield Static("Ready", id="status-text")
                    yield Static("", id="dir-path")
        
        # btop-style key helper bar at bottom
        yield KeyHelperBar([
            ("q", "Quit"),
            ("h", "Help"),
            ("m", "Menu"),
            ("Tab", "Focus"),
            ("Space", "Select"),
            ("Ctrl+A", "All/Clear"),
            ("g", "Copy"),
            ("c", "Dir"),
        ], id="key-helper")
    
    def on_mount(self):
        """Initialize the app on mount."""
        self.title = f"CodeClip - {self.current_dir.name}"
        self.sub_title = str(self.current_dir)
        self.load_directory()
        # Schedule focus on file tree after UI is ready
        self.call_after_refresh(self._initial_focus)
    
    def _initial_focus(self):
        """Set initial focus on file tree with cursor positioned."""
        try:
            tree = self.query_one("#file-tree", FileTree)
            tree.focus()
            # Move cursor to first visible node to ensure arrow keys work
            if tree.root.children:
                tree.move_cursor(tree.root.children[0])
            elif tree.root:
                tree.move_cursor(tree.root)
        except Exception:
            pass

    def on_format_selector_format_changed(self, event: FormatSelector.FormatChanged):
        """Handle format changes from FormatSelector."""
        self._output_format = event.format
        self._persist_state()
    
    def watch_theme(self, theme: str) -> None:
        """Watch for theme changes and persist them."""
        self._persist_state()
    
    def load_directory(self):
        """Load the current directory into the tree."""
        # Update header
        self.title = f"CodeClip - {self.current_dir.name}"
        self.sub_title = str(self.current_dir)
        
        # Build tree
        tree = self.query_one("#file-tree", FileTree)
        tree.auto_expand = False
        tree.show_root = False  # Hide root node, we show dir name in title
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
        
        # Don't persist state here - only persist when user makes changes
        # This prevents overwriting saved state before it's properly applied
    
    def _has_files(self, folder_tree):
        """Check if a folder tree contains any files (recursively)."""
        if folder_tree.get("files"):
            return True
        for sub_tree in folder_tree.get("subfolders", {}).values():
            if self._has_files(sub_tree):
                return True
        return False
    
    def _add_nodes(self, parent_node, folder_tree):
        """Recursively add nodes to the tree."""
        # Add folders first (only if they contain files somewhere)
        for folder, sub_tree in sorted(folder_tree["subfolders"].items()):
            if not self._has_files(sub_tree):
                # Skip empty folders (no files in this folder or any subfolder)
                continue
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
                icon = "[#d4a520]⊟[/]"  # Orange horizontal dash for partial
            elif selected:
                icon = "[#00afff]■[/]"  # Cyan filled for selected
            else:
                icon = "[#404040]□[/]"  # Dark gray empty for unselected
            return f"{icon} 📁 {name}"
        else:
            # Binary state for files - use checkboxes too
            icon = "[#00afff]■[/]" if selected else "[#404040]□[/]"
            # Add padding to align with folder arrow and a neutral file icon
            return f"  {icon} [#303030]📄[/] {name}"
    
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
            cb = TypeToggle(ext, count, value=not saved_exts or ext in saved_exts, 
                         classes="ext-checkbox", name=ext.lower())
            self._ext_checkboxes.append((ext.lower(), cb))
            container.mount(cb)
    
    def _get_checkbox_ext(self, cb: TypeToggle) -> str:
        """Get the extension for a checkbox."""
        return cb.name if cb.name else ""
    
    def _apply_saved_state(self, tree):
        """Apply saved selection state to the tree."""
        # Check if we're in the same directory as last time
        last_dir = self._state.get("last_dir", "")
        is_same_dir = last_dir == str(self.current_dir)
        
        # Check if we have explicit state saved (including empty selections)
        has_explicit_state = "selected_files" in self._state and is_same_dir
        
        if not has_explicit_state:
            # New directory or no saved state - all files stay selected (default from _add_nodes)
            # Just update directory states
            self._update_dir_selection_states()
            return
        
        # Get saved files as posix strings for comparison
        saved_files = set(self._state.get("selected_files", []))
        
        # Also get the set of all files that existed in last save
        # Files not in saved_files but that existed = were deselected
        # Files not seen before = new files, should be selected by default
        saved_all_files = set(self._state.get("all_files", []))
        
        # Count for debugging
        selected_count = 0
        deselected_count = 0
        new_file_count = 0
        
        for node in walk_tree(tree.root):
            if not node.data:
                continue
            if node.data.get("is_dir"):
                continue
            
            rel_path = node_relative_path(node)
            rel_path_str = rel_path.as_posix() if rel_path else ""
            
            if saved_all_files:
                # We have a record of all files from last run
                if rel_path_str in saved_all_files:
                    # File existed before - restore its saved state
                    is_selected = rel_path_str in saved_files
                    node.data["selected"] = is_selected
                    if is_selected:
                        selected_count += 1
                    else:
                        deselected_count += 1
                else:
                    # New file - default to selected
                    node.data["selected"] = True
                    new_file_count += 1
            else:
                # Old state format without all_files - use old behavior
                node.data["selected"] = rel_path_str in saved_files
            
            self._refresh_node_label(node)
        
        # Update directory states based on children
        self._update_dir_selection_states()
    
    def _update_dir_selection_states(self):
        """Update directory selection states based on children (tri-state logic)."""
        tree = self.query_one("#file-tree", FileTree)
        
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
                # Empty folder - default to False (unselected)
                # This prevents empty folders from causing parent to show as "partial"
                node.data["selected"] = False
                self._refresh_node_label(node)
                return False
            
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
        tree = self.query_one("#file-tree", FileTree)
        total = 0
        selected = 0
        
        for node in walk_tree(tree.root):
            if node.data and not node.data.get("is_dir"):
                total += 1
                if node.data.get("selected"):
                    selected += 1
        
        stats = self.query_one("#tree-stats", Static)
        stats.update(f"[#00afff]{selected}[/]/{total}")
        
        status = self.query_one("#status-text", Static)
        if self._processing:
            pass  # Don't update during processing
        else:
            status.update(f"Selected: [#00afff]{selected}[/] of {total} files")
    
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
            tree = self.query_one("#file-tree", FileTree)
        except Exception:
            return
        
        selected_files = []
        all_files = []
        for node in walk_tree(tree.root):
            if not node.data or node.data.get("is_dir"):
                continue
            rel_path = node_relative_path(node)
            if rel_path:
                path_str = rel_path.as_posix()
                all_files.append(path_str)
                if node.data.get("selected"):
                    selected_files.append(path_str)
        
        selected_exts = []
        for cb in self.query(".ext-checkbox"):
            if isinstance(cb, TypeToggle) and cb.value:
                ext = self._get_checkbox_ext(cb)
                if ext:
                    selected_exts.append(ext)
        
        state = {
            "last_dir": str(self.current_dir),
            "selected_files": selected_files,
            "all_files": all_files,
            "selected_exts": selected_exts,
            "output_format": self._output_format,
            "theme": self.theme,
        }
        self._state = state
        save_state(state)
    
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
    
    def on_type_toggle_changed(self, event: TypeToggle.Changed):
        """Handle type toggle changes."""
        self._persist_state()
    
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
            if isinstance(cb, TypeToggle):
                cb.value = True
                cb._refresh_label()
        self._persist_state()
    
    def _deselect_all_types(self):
        """Deselect all file type checkboxes."""
        for cb in self.query(".ext-checkbox"):
            if isinstance(cb, TypeToggle):
                cb.value = False
                cb._refresh_label()
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
            # For containers, focus the first child if possible
            if selector == "#file-types-container":
                container = self.query_one(selector)
                if container.children:
                    container.children[0].focus()
                else:
                    container.focus()
            elif selector == "#format-selector":
                # Focus the active format button
                selector_widget = self.query_one(selector, FormatSelector)
                fmt = selector_widget.current_format
                try:
                    self.query_one(f"#fmt-{fmt}", Button).focus()
                except:
                    selector_widget.focus()
            else:
                widget = self.query_one(selector)
                widget.focus()
        except Exception:
            pass
    
    # ═══════════════════════════════════════════════════════════════════════════
    # ACTIONS & NAVIGATION
    # ═══════════════════════════════════════════════════════════════════════════
    
    def action_space(self):
        """Handle Space key."""
        focused = self.focused
        if isinstance(focused, Tree):
            self.action_toggle_select()
        elif isinstance(focused, Checkbox):
            focused.toggle()
        elif isinstance(focused, TypeToggle):
            focused.toggle()
        elif isinstance(focused, Button):
            focused.press()
            
    def action_enter(self):
        """Handle Enter key."""
        focused = self.focused
        if isinstance(focused, Tree):
            self.action_toggle_select()
        elif isinstance(focused, Checkbox):
            focused.toggle()
        elif isinstance(focused, TypeToggle):
            focused.toggle()
        elif isinstance(focused, Button):
            focused.press()

    def action_toggle_select(self):
        """Toggle selection for the current tree node."""
        tree = self.query_one("#file-tree", FileTree)
        node = tree.cursor_node
        if node and node.data:
            self._do_toggle_selection(node)
    
    def action_toggle_node_or_select(self):
        """Expand/collapse folder, or toggle selection for files."""
        tree = self.query_one("#file-tree", FileTree)
        node = tree.cursor_node
        if node and node.data:
            if node.data.get("is_dir"):
                node.toggle()
            else:
                self._do_toggle_selection(node)
    
    def action_generate(self):
        """Generate and copy to clipboard."""
        if self._processing:
            return
        
        self._processing = True
        status = self.query_one("#status-text", Static)
        status.update("[#d4a520]⏳ Preparing...[/]")
        
        try:
            tree = self.query_one("#file-tree", FileTree)
            
            # Get selected extensions
            selected_exts = set()
            for cb in self.query(".ext-checkbox"):
                if isinstance(cb, TypeToggle) and cb.value:
                    ext = self._get_checkbox_ext(cb)
                    if ext:
                        selected_exts.add(ext)
            
            # Collect selected files
            files = collect_selected_files(tree, selected_exts, self.current_dir)
            
            if not files:
                status.update("[#c73030]✗ No files selected[/]")
                self.notify("No files selected!", severity="warning")
                self._processing = False
                return
            
            # Store data for the copy operation
            self._copy_data = {
                "files": files,
                "selected_exts": selected_exts,
                "project_name": self.current_dir.name,
            }
            
            # Show progress modal
            modal = CopyProgressModal(len(files))
            self.push_screen(modal, self._on_copy_complete)
            
            # Start the copy operation as a worker
            self.run_worker(
                self._do_copy_operation(modal),
                name="copy_operation",
                exclusive=True,
            )
        except Exception as e:
            status.update(f"[#c73030]✗ Error: {str(e)[:30]}[/]")
            self.notify(f"Error: {e}", severity="error")
            self._processing = False
    
    async def _do_copy_operation(self, modal: CopyProgressModal):
        """Perform the copy operation with progress updates."""
        import asyncio
        
        files = self._copy_data["files"]
        selected_exts = self._copy_data["selected_exts"]
        project_name = self._copy_data["project_name"]
        
        try:
            # Prepare data for formatters
            tree_string = get_tree_string(self.current_dir, selected_exts if selected_exts else None)
            
            # Read file contents with progress updates
            files_content = []
            for i, file_path in enumerate(files):
                # Check if cancelled
                if modal.cancelled:
                    return
                
                # Update progress
                rel_path = file_path.relative_to(self.current_dir)
                modal.update_progress(i + 1, str(rel_path))
                
                try:
                    content = file_path.read_text(errors='replace')
                    lang = get_language(file_path.suffix)
                    files_content.append((str(rel_path), content, lang))
                except Exception:
                    pass
                
                # Small delay to allow UI updates and check for cancel
                await asyncio.sleep(0.01)
            
            # Check if cancelled before copying
            if modal.cancelled:
                return
            
            # Format output based on selected format
            if self._output_format == "markdown":
                output = format_output_markdown(project_name, tree_string, files_content)
            elif self._output_format == "xml":
                output = format_output_xml(project_name, tree_string, files_content)
            else:
                output = format_output_plain(project_name, tree_string, files_content)
            
            # Check if cancelled before clipboard operation
            if modal.cancelled:
                return
            
            # Copy to clipboard
            success, msg = copy_to_clipboard(output)
            
            if not modal.cancelled:
                if success:
                    modal.dismiss((True, f"Copied {len(files)} files!", len(files)))
                else:
                    modal.dismiss((False, msg, 0))
        except Exception as e:
            if not modal.cancelled:
                modal.dismiss((False, str(e), 0))
    
    def _on_copy_complete(self, result):
        """Handle copy operation completion."""
        self._processing = False
        status = self.query_one("#status-text", Static)
        
        if result is None:
            status.update("[#c73030]✗ Cancelled[/]")
            return
        
        success, message, file_count = result
        
        if success:
            status.update(f"[#87af00]✓ {message}[/]")
            self.notify(message, severity="information")
        elif "Cancelled" in message:
            status.update("[#d4a520]⚠ Cancelled[/]")
            self.notify("Copy operation cancelled", severity="warning")
        else:
            status.update(f"[#c73030]✗ {message[:30]}[/]")
            self.notify(f"Error: {message}", severity="error")
    
    def action_toggle_all(self):
        """Toggle between Select All and Deselect All based on current focus."""
        focused = self.focused
        
        # Check if focus is on file tree
        if isinstance(focused, FileTree):
            tree = self.query_one("#file-tree", FileTree)
            # If root is fully selected (True), deselect all. Otherwise select all.
            if tree.root.data.get("selected") is True:
                self.action_deselect_all()
            else:
                self.action_select_all()
            return
        
        # Check if focus is on a type toggle (file types section)
        if isinstance(focused, TypeToggle):
            # Check if all types are selected
            all_selected = all(
                cb.value for cb in self.query(".ext-checkbox")
                if isinstance(cb, TypeToggle)
            )
            if all_selected:
                self._deselect_all_types()
            else:
                self._select_all_types()
            return
        
        # Check if focus is within the file-types-container
        try:
            types_container = self.query_one("#file-types-container")
            if focused and focused in types_container.walk_children():
                all_selected = all(
                    cb.value for cb in self.query(".ext-checkbox")
                    if isinstance(cb, TypeToggle)
                )
                if all_selected:
                    self._deselect_all_types()
                else:
                    self._select_all_types()
                return
        except Exception:
            pass
        
        # If focus is elsewhere, do nothing
        pass

    def action_select_all(self):
        """Select all files in the tree."""
        tree = self.query_one("#file-tree", FileTree)
        for node in walk_tree(tree.root):
            if node.data:
                node.data["selected"] = True
                self._refresh_node_label(node)
        self._update_dir_selection_states()
        self._update_stats()
        self._persist_state()
    
    def action_deselect_all(self):
        """Deselect all files in the tree."""
        tree = self.query_one("#file-tree", FileTree)
        for node in walk_tree(tree.root):
            if node.data:
                node.data["selected"] = False
                self._refresh_node_label(node)
        self._update_dir_selection_states()
        self._update_stats()
        self._persist_state()
    
    def action_change_dir(self):
        """Open the change directory modal."""
        self.push_screen(ChangeDirectoryModal(self.current_dir), self._on_dir_changed)
    
    def _on_dir_changed(self, new_dir):
        """Handle directory change from modal."""
        if new_dir:
            self.current_dir = Path(new_dir)
            self.load_directory()
    
    def action_toggle_help(self):
        """Toggle help screen."""
        self.push_screen(HelpScreen())
    
    def action_refresh(self):
        """Refresh the current directory."""
        self.load_directory()

def run():
    """Entry point for the console script."""
    app = CodeClipApp()
    app.run()