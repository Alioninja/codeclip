import threading
import time
from pathlib import Path

from textual.app import App, ComposeResult
from textual.widgets import Header, Tree, Checkbox, Button, Static
from textual.containers import Vertical, Horizontal, VerticalScroll, Container
from textual.binding import Binding

from .config import STATE_FILE
from .core.state import load_state, save_state
from .core.scanner import scan_file_extensions, build_folder_tree, get_tree_string, walk_tree, node_relative_path, collect_selected_files
from .core.clipboard import copy_to_clipboard
from .utils.helpers import get_language
from .ui.widgets import FormatSelector, KeyHelperBar, NavigationScroll, FileTree, ActionButton, TypeToggle
from .ui.screens import ChangeDirectoryModal, HelpScreen
from .ui.formatters import format_output_markdown, format_output_xml, format_output_plain

class CodeClipApp(App):
    """CodeClip - Copy codebase to clipboard."""
    
    CSS_PATH = "terminal_app.css"
    TITLE = "CodeClip"
    
    BINDINGS = [
        Binding("q", "quit", "Quit", show=False),
        Binding("h", "toggle_help", "Help", show=False),
        Binding("question_mark", "toggle_help", "Help", show=False),
        Binding("space", "action_space", "Select", show=False),
        Binding("enter", "action_enter", "Enter", show=False),
        Binding("a", "select_all", "All", show=False),
        Binding("A", "deselect_all", "Deselect All", show=False),
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
        last_dir = Path(self._state.get("last_dir", Path.cwd()))
        self.current_dir = last_dir if last_dir.is_dir() else Path.cwd()
        self._processing = False
        self._output_format = self._state.get("output_format", "markdown")
        self._ext_checkboxes = []
    
    def compose(self) -> ComposeResult:
        yield Header()
        
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
            ("a", "All"),
            ("A", "Clear"),
            ("↑/↓/←/→", "Nav"),
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
        for node in walk_tree(tree.root):
            if not node.data or node.data.get("is_dir"):
                continue
            if node.data.get("selected"):
                rel_path = node_relative_path(node)
                if rel_path:
                    selected_files.append(rel_path.as_posix())
        
        selected_exts = []
        for cb in self.query(".ext-checkbox"):
            if isinstance(cb, TypeToggle) and cb.value:
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
            self.action_toggle_node_or_select()
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
        status.update("[#d4a520]⏳ Processing...[/]")
        
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
            
            # Prepare data for formatters
            project_name = self.current_dir.name
            tree_string = get_tree_string(self.current_dir, selected_exts if selected_exts else None)
            
            # Read file contents
            files_content = []
            for file_path in files:
                try:
                    content = file_path.read_text(errors='replace')
                    rel_path = file_path.relative_to(self.current_dir)
                    lang = get_language(file_path.suffix)
                    files_content.append((str(rel_path), content, lang))
                except Exception:
                    pass
            
            # Format output based on selected format
            if self._output_format == "markdown":
                output = format_output_markdown(project_name, tree_string, files_content)
            elif self._output_format == "xml":
                output = format_output_xml(project_name, tree_string, files_content)
            else:
                output = format_output_plain(project_name, tree_string, files_content)
            
            # Copy to clipboard
            success = copy_to_clipboard(output)
            
            if success:
                status.update(f"[#87af00]✓ Copied {len(files)} files![/]")
                self.notify(f"Copied {len(files)} files to clipboard!", severity="information")
            else:
                status.update("[#c73030]✗ Clipboard error[/]")
                self.notify("Failed to copy to clipboard", severity="error")
        except Exception as e:
            status.update(f"[#c73030]✗ Error: {str(e)[:30]}[/]")
            self.notify(f"Error: {e}", severity="error")
        finally:
            self._processing = False
    
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