from pathlib import Path
import threading
import customtkinter as ctk
from PIL import Image, ImageDraw
from collections import Counter
import time
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

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
LIGHT_NESTED_BG = "#3c3c3c"
DARK_NESTED_BG = "#303030"
INDICATOR_WIDTH = 18
NESTED_BG_PAD_X = 10
NESTED_BG_CORNER_RADIUS = 6
# Adjusted to show ~4 rows of checkboxes (approx 30px per row)
FILE_TYPE_SECTION_MAX_HEIGHT = 160
INDENT_SIZE = 20  # Width for each indentation level
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


class DirectorySelectionDialog(ctk.CTkToplevel):
    """Custom directory selection dialog with beautiful UI matching the main theme."""

    def __init__(self, parent, initial_path, is_startup=False):
        super().__init__(parent)

        self.parent = parent
        self.current_path = Path(initial_path)
        self.selected_path = None
        self.is_startup = is_startup

        self.setup_window()
        self.create_widgets()
        self.populate_directory_list()

        # Make it modal and center the window
        self.transient(parent)

        # Center the window after everything is set up
        self.after(10, self.center_window)

        # Set up modal behavior
        self.grab_set()

    def setup_window(self):
        """Configure the window properties."""
        title = "Select Project Directory" if not self.is_startup else "Welcome to Codebase to Clipboard"
        self.title(title)

        # Set initial geometry (will be repositioned later)
        self.geometry("700x500")
        self.minsize(600, 400)

        # Use the same appearance as parent
        self.configure(fg_color=("gray95", "gray10"))

        # Ensure window is resizable
        self.resizable(True, True)

        # Make sure window starts visible
        self.deiconify()

    def center_window(self):
        """Center the dialog on the screen."""
        self.update_idletasks()

        # Get dialog dimensions
        dialog_width = 700
        dialog_height = 500

        # Always center on screen for consistent positioning
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2

        # Apply the calculated position
        self.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        # Force window update and ensure visibility
        self.update()
        self.deiconify()
        self.lift()

        # Briefly set topmost to ensure visibility
        self.attributes('-topmost', True)
        # Additional positioning verification after update
        self.after(100, lambda: self.attributes('-topmost', False))
        self.after(50, self._verify_position)

    def _verify_position(self):
        """Verify the window is properly positioned and visible."""
        try:
            # Get current window position
            current_x = self.winfo_x()
            current_y = self.winfo_y()

            # Get screen dimensions
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()

            # Check if window is off-screen or at invalid position
            if current_x < -100 or current_y < -100 or current_x > screen_width or current_y > screen_height:
                # Force center on screen if position is invalid
                x = (screen_width - 700) // 2
                y = (screen_height - 500) // 2
                self.geometry(f"700x500+{x}+{y}")
                self.lift()

        except Exception:
            # Fallback: just ensure window is lifted
            self.lift()

    def create_widgets(self):
        """Create all UI widgets."""
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        main_frame.grid_columnconfigure(0, weight=1)
        # Directory listing should expand
        main_frame.grid_rowconfigure(2, weight=1)

        # Header section (fixed height)
        self.create_header(main_frame)

        # Address bar section (fixed height)
        self.create_address_bar(main_frame)

        # Directory listing section (expandable)
        self.create_directory_listing(main_frame)

        # Footer buttons section (fixed height)
        self.create_footer_buttons(main_frame)

    def create_header(self, parent):
        """Create the header section."""
        header_frame = ctk.CTkFrame(parent, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 20))

        if self.is_startup:
            title_text = "🚀 Welcome to Codebase to Clipboard"
            subtitle_text = "Select your project directory to get started"
        else:
            title_text = "📁 Change Project Directory"
            subtitle_text = "Select a new directory for your project"

        title_label = ctk.CTkLabel(
            header_frame,
            text=title_text,
            font=("Arial", 24, "bold")
        )
        title_label.pack(anchor="w", pady=(0, 5))

        subtitle_label = ctk.CTkLabel(
            header_frame,
            text=subtitle_text,
            font=("Arial", 14),
            text_color=("gray40", "gray60")
        )
        subtitle_label.pack(anchor="w")

    def create_address_bar(self, parent):
        """Create the address bar section."""
        address_frame = ctk.CTkFrame(parent)
        address_frame.grid(row=1, column=0, sticky="ew", pady=(0, 15))
        # Address entry column (column 1) gets most space
        address_frame.grid_columnconfigure(1, weight=1)

        # Back button with secondary color and clearer text
        self.back_btn = ctk.CTkButton(
            address_frame,
            text="↰ Up Directory",
            width=110,
            height=35,
            command=self.go_back,
            font=("Arial", 11),
            fg_color=("gray70", "gray30"),
            hover_color=("gray60", "gray40")
        )
        self.back_btn.grid(row=0, column=0, padx=(15, 10), pady=15)

        # Editable address bar with path suggestions and validation
        self.address_entry = ctk.CTkEntry(
            address_frame,
            placeholder_text="Enter directory path or start typing...",
            height=35,
            font=("Consolas", 11)
        )
        self.address_entry.grid(
            row=0, column=1, padx=(0, 10), pady=15, sticky="ew")

        # Bind events for address bar functionality
        self.address_entry.bind("<Return>", self.on_address_enter)
        self.address_entry.bind("<KeyRelease>", self.on_address_key_release)
        self.address_entry.bind("<FocusIn>", self.on_address_focus_in)
        self.address_entry.bind("<Button-1>", self.on_address_click)

        # Go button for navigation
        self.go_btn = ctk.CTkButton(
            address_frame,
            text="Go",
            width=60,
            height=35,
            command=self.navigate_to_address,
            font=("Arial", 11),
            fg_color=("green", "darkgreen"),
            hover_color=("lightgreen", "green")
        )
        self.go_btn.grid(row=0, column=2, padx=(0, 15), pady=15)

        # Initialize suggestion tracking
        self.suggestion_var = None
        self.last_suggestion = ""

    def create_directory_listing(self, parent):
        """Create the directory listing section."""
        # Direct scrollable directory list without nested frame
        self.directory_list = ctk.CTkScrollableFrame(parent)
        self.directory_list.grid(
            row=2, column=0, sticky="nsew", padx=20, pady=(0, 15))
        self.directory_list.grid_columnconfigure(0, weight=1)

    def create_footer_buttons(self, parent):
        """Create the footer buttons section."""
        footer_frame = ctk.CTkFrame(parent, fg_color="transparent")
        footer_frame.grid(row=3, column=0, sticky="ew", pady=(0, 0))
        footer_frame.grid_columnconfigure(1, weight=1)  # Center column expands

        # File count info on the left
        self.file_count_label = ctk.CTkLabel(
            footer_frame,
            text="",
            font=("Arial", 10),
            text_color=("gray50", "gray50"),
            anchor="w"
        )
        self.file_count_label.grid(row=0, column=0, sticky="w", padx=(0, 10))

        # Button frame on the right
        button_frame = ctk.CTkFrame(footer_frame, fg_color="transparent")
        button_frame.grid(row=0, column=2, sticky="e")

        if self.is_startup:
            # Cancel button
            cancel_btn = ctk.CTkButton(
                button_frame,
                text="❌ Exit",
                width=100,
                height=35,
                fg_color=("gray70", "gray30"),
                hover_color=("gray60", "gray40"),
                command=self.on_cancel
            )
            cancel_btn.pack(side="right", padx=(10, 0))
        else:
            # Cancel button
            cancel_btn = ctk.CTkButton(
                button_frame,
                text="Cancel",
                width=100,
                height=35,
                fg_color=("gray70", "gray30"),
                hover_color=("gray60", "gray40"),
                command=self.on_cancel
            )
            cancel_btn.pack(side="right", padx=(10, 0))

        # Accept button
        accept_btn = ctk.CTkButton(
            button_frame,
            text="✓ Select This Directory" if not self.is_startup else "🚀 Continue",
            width=180,
            height=35,
            command=self.on_accept
        )
        accept_btn.pack(side="right")

    def populate_directory_list(self):
        """Populate the directory listing."""
        # Clear existing items
        for widget in self.directory_list.winfo_children():
            widget.destroy()

        # Reset scroll position to top
        if hasattr(self.directory_list, '_parent_canvas'):
            self.directory_list._parent_canvas.yview_moveto(0)

        # Update address bar with current path
        self.address_entry.delete(0, "end")
        self.address_entry.insert(0, str(self.current_path))

        # Force update before scanning directory
        self.update_idletasks()

        try:
            # Add directories (no need for parent '..' item since we have back button)
            directories = []
            files = []

            # Ensure path exists and is accessible
            if not self.current_path.exists():
                raise FileNotFoundError(
                    f"Path does not exist: {self.current_path}")

            if not self.current_path.is_dir():
                raise NotADirectoryError(
                    f"Path is not a directory: {self.current_path}")

            for item in sorted(self.current_path.iterdir()):
                if item.is_dir() and not is_ignored_dir(item.name):
                    directories.append(item)
                elif item.is_file():
                    files.append(item)

            # Add directories first
            for directory in directories:
                self.add_directory_item(f"📁 {directory.name}", directory)

            # Force refresh of the scrollable frame
            self.directory_list.update_idletasks()

            # Update file count in footer
            file_count = len(files)
            if hasattr(self, 'file_count_label'):
                if file_count > 0:
                    self.file_count_label.configure(
                        text=f"📄 {file_count} file{'s' if file_count != 1 else ''}")
                else:
                    self.file_count_label.configure(text="📄 No files")

            # Update back button state
            if hasattr(self, 'back_btn'):
                if self.current_path.parent != self.current_path:
                    self.back_btn.configure(state="normal")
                else:
                    self.back_btn.configure(state="disabled")

        except PermissionError:
            error_label = ctk.CTkLabel(
                self.directory_list,
                text="❌ Access denied to this directory",
                text_color="red"
            )
            error_label.pack(pady=20)
        except (FileNotFoundError, NotADirectoryError) as e:
            error_label = ctk.CTkLabel(
                self.directory_list,
                text=f"❌ {str(e)}",
                text_color="red"
            )
            error_label.pack(pady=20)
        except Exception as e:
            error_label = ctk.CTkLabel(
                self.directory_list,
                text=f"❌ Error: {str(e)}",
                text_color="red"
            )
            error_label.pack(pady=20)

    def add_directory_item(self, text, path, is_parent=False):
        """Add a directory item to the list."""
        item_frame = ctk.CTkFrame(self.directory_list)
        # Reduced padding for thinner items
        item_frame.pack(fill="x", padx=3, pady=1)
        item_frame.grid_columnconfigure(0, weight=1)

        label = ctk.CTkLabel(
            item_frame,
            text=text,
            anchor="w",
            font=("Arial", 11)  # Slightly smaller font
        )
        label.grid(row=0, column=0, sticky="ew",
                   padx=10, pady=6)  # Reduced padding

        # Make the entire frame clickable
        def on_click(event=None):
            if path.exists() and path.is_dir():
                self.current_path = path
                # Use after_idle to ensure proper UI update
                self.after_idle(self.populate_directory_list)
            else:
                # Handle case where directory might not exist or be accessible
                messagebox.showerror(
                    "Error", f"Cannot access directory: {path}")

        item_frame.bind("<Button-1>", on_click)
        label.bind("<Button-1>", on_click)

        # Hover effects
        def on_enter(event=None):
            item_frame.configure(fg_color=("gray80", "gray25"))

        def on_leave(event=None):
            item_frame.configure(fg_color=("gray90", "gray17"))

        item_frame.bind("<Enter>", on_enter)
        item_frame.bind("<Leave>", on_leave)
        label.bind("<Enter>", on_enter)
        label.bind("<Leave>", on_leave)

    def browse_directory(self):
        """Open system directory browser."""
        selected_dir = filedialog.askdirectory(
            title="Select Directory",
            initialdir=str(self.current_path)
        )

        if selected_dir:
            self.current_path = Path(selected_dir)
            self.populate_directory_list()

    def go_back(self):
        """Navigate to parent directory."""
        if self.current_path.parent != self.current_path:
            self.current_path = self.current_path.parent
            self.populate_directory_list()

    def on_address_enter(self, event=None):
        """Handle Enter key press in address bar."""
        self.navigate_to_address()

    def on_address_click(self, event=None):
        """Handle click on address bar."""
        # Select all text for easy editing
        self.address_entry.select_range(0, "end")

    def on_address_focus_in(self, event=None):
        """Handle focus in address bar."""
        # Clear placeholder behavior if needed
        current_text = self.address_entry.get()
        if not current_text or current_text == "Enter directory path or start typing...":
            self.address_entry.delete(0, "end")

    def on_address_key_release(self, event=None):
        """Handle key release in address bar for suggestions."""
        if not event:
            return
            
        current_text = self.address_entry.get()
        
        # Don't provide suggestions for very short input
        if len(current_text) < 2:
            return
            
        # Skip if it's a navigation key
        if event.keysym in ['Up', 'Down', 'Left', 'Right', 'Tab', 'Shift_L', 'Shift_R', 'Control_L', 'Control_R']:
            return
            
        # Provide path suggestions
        self.suggest_path_completion(current_text)

    def suggest_path_completion(self, partial_path):
        """Suggest path completion based on partial input."""
        try:
            path_obj = Path(partial_path)
            
            if partial_path.endswith('/') or partial_path.endswith('\\'):
                # User is looking for contents of this directory
                parent_dir = path_obj
            else:
                # User is typing a partial path
                parent_dir = path_obj.parent
                partial_name = path_obj.name.lower()
            
            if not parent_dir.exists() or not parent_dir.is_dir():
                return
                
            # Find matching directories
            matches = []
            try:
                for item in parent_dir.iterdir():
                    if item.is_dir() and not item.name.startswith('.'):
                        if partial_path.endswith('/') or partial_path.endswith('\\'):
                            matches.append(str(item))
                        elif item.name.lower().startswith(partial_name):
                            matches.append(str(item))
                
                # Show first match as suggestion (visual feedback could be added)
                if matches:
                    self.last_suggestion = matches[0]
                    
            except PermissionError:
                pass  # Ignore directories we can't access
                
        except (OSError, ValueError):
            pass  # Invalid path, no suggestions

    def navigate_to_address(self):
        """Navigate to the path entered in address bar."""
        path_text = self.address_entry.get().strip()
        
        if not path_text:
            self.show_error("Please enter a directory path.")
            return
            
        try:
            # Handle relative paths and expand user paths
            if path_text.startswith('~'):
                path_text = Path.home() / path_text[2:] if len(path_text) > 1 else Path.home()
            elif not Path(path_text).is_absolute():
                path_text = self.current_path / path_text
            else:
                path_text = Path(path_text)
            
            # Resolve any .. or . components
            path_text = path_text.resolve()
            
            # Validate the path
            if not path_text.exists():
                self.show_error(f"Path does not exist:\n{path_text}")
                return
                
            if not path_text.is_dir():
                self.show_error(f"Path is not a directory:\n{path_text}")
                return
                
            # Check if we have read access
            try:
                list(path_text.iterdir())
            except PermissionError:
                self.show_error(f"Access denied to directory:\n{path_text}")
                return
            
            # Navigate to the valid path
            self.current_path = path_text
            self.populate_directory_list()
            
        except Exception as e:
            self.show_error(f"Invalid path or error accessing directory:\n{str(e)}")

    def show_error(self, message):
        """Show error message to user."""
        # Create a simple error display in the directory list area temporarily
        for widget in self.directory_list.winfo_children():
            widget.destroy()
            
        error_frame = ctk.CTkFrame(self.directory_list)
        error_frame.pack(fill="x", padx=10, pady=10)
        
        error_label = ctk.CTkLabel(
            error_frame,
            text=f"❌ {message}",
            text_color="red",
            font=("Arial", 12),
            wraplength=500
        )
        error_label.pack(pady=10)
        
        # Add a button to go back to the current valid directory
        back_to_current_btn = ctk.CTkButton(
            error_frame,
            text="↶ Return to Current Directory",
            command=self.populate_directory_list,
            font=("Arial", 11),
            width=200
        )
        back_to_current_btn.pack(pady=(0, 10))

    def on_accept(self):
        """Handle accept button click."""
        if self.current_path.exists() and self.current_path.is_dir():
            self.selected_path = self.current_path
            self.grab_release()
            self.destroy()
        else:
            messagebox.showerror("Error", "Please select a valid directory.")

    def on_cancel(self):
        """Handle cancel button click."""
        self.selected_path = None
        self.grab_release()
        self.destroy()

    def show(self):
        """Show the dialog and return the selected path."""
        # Ensure the window is visible and properly positioned
        self.deiconify()
        self.lift()

        # Force focus and bring to front
        self.focus_force()
        self.attributes('-topmost', True)

        # Remove topmost after a brief moment to allow normal interaction
        self.after(200, lambda: self.attributes('-topmost', False))

        # Wait for the dialog to close
        try:
            self.wait_window()
        except Exception:
            # Handle case where window is already destroyed
            pass

        return self.selected_path


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

        # Initialize directory selection
        self.current_dir = self.select_initial_directory()
        if not self.current_dir:
            self.destroy()
            return

        self.limited_extensions = set()  # Track extensions that hit scanning limits

        self.initialize_project_data()

        # Update window title with project name
        self.title(f"Codebase to Clipboard - {self.current_dir.name}")

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

        # Directory info label
        self.current_dir_label = ctk.CTkLabel(
            folder_header, text=f"Project: {self.current_dir.name}",
            anchor="w", font=("Arial", 12, "italic"))
        self.current_dir_label.pack(side="left", padx=(10, 0))

        folder_button_frame = ctk.CTkFrame(
            folder_header, fg_color="transparent")
        folder_button_frame.pack(side="right")

        change_dir_btn = ctk.CTkButton(
            folder_button_frame, text="Change Project", width=120, height=28, command=self.change_directory)
        change_dir_btn.pack(side="right", padx=(5, 0))

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
        self.filetype_scrollable_frame = ctk.CTkScrollableFrame(
            type_scroll_container, fg_color="transparent")
        self.filetype_scrollable_frame.grid(row=0, column=0, sticky="nsew")
        self.filetype_scrollable_frame.grid_columnconfigure(
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
                self.filetype_scrollable_frame, text=label_text, variable=var,
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

    def select_initial_directory(self):
        """Show custom directory selection dialog at startup."""
        current_path = Path.cwd()

        # Create custom directory selection window
        dialog = DirectorySelectionDialog(self, current_path, is_startup=True)
        selected_path = dialog.show()

        return selected_path

    def show_directory_dialog(self):
        """Show custom directory selection dialog."""
        dialog = DirectorySelectionDialog(
            self, self.current_dir, is_startup=False)
        selected_path = dialog.show()

        return selected_path

    def change_directory(self):
        """Allow user to change the project directory from the main window."""
        new_dir = self.show_directory_dialog()
        if new_dir and new_dir != self.current_dir:
            # Update current directory
            self.current_dir = new_dir
            self.update_status("Loading new project directory...")

            # Reinitialize project data
            self.after(100, self._reload_project)

    def _reload_project(self):
        """Reload project data after directory change."""
        try:
            # Clear existing data
            self.clear_ui_data()

            # Reinitialize project data
            self.initialize_project_data()

            # Update UI
            self.update_current_dir_label()
            self.rebuild_ui()

            # Set initial state
            self.select_all_folders()
            self.update_file_type_counts()
            self.after(10, self.collapse_all_folders)

            self.update_status(f"Loaded project: {self.current_dir.name}")

        except Exception as e:
            messagebox.showerror(
                "Error", f"Failed to load directory: {str(e)}")
            self.update_status("Error loading directory")

    def initialize_project_data(self):
        """Initialize project data for the current directory."""
        self.file_extension_counts_initial = self.scan_file_extensions(
            self.current_dir)
        self.sorted_extensions = sorted(self.file_extension_counts_initial.keys(),
                                        key=lambda ext: self.file_extension_counts_initial[ext],
                                        reverse=True)

        self.folder_tree = self.build_folder_tree(self.current_dir)

    def update_current_dir_label(self):
        """Update the current directory label and window title."""
        if hasattr(self, 'current_dir_label'):
            self.current_dir_label.configure(
                text=f"Project: {self.current_dir.name}")

        # Update window title to show current project
        self.title(f"Codebase to Clipboard - {self.current_dir.name}")

    def clear_ui_data(self):
        """Clear existing UI data before reloading."""
        # Clear state dictionaries
        self.folder_vars.clear()
        self.folder_labels.clear()
        self.file_vars.clear()
        self.file_labels.clear()
        self.folder_children.clear()
        self.folder_parent.clear()
        # Don't clear file_type_vars and file_type_checkboxes here - let rebuild method handle it
        self.folder_widget_refs.clear()
        self.folder_states.clear()

        # Clear folder container
        if hasattr(self, 'folder_container'):
            for widget in self.folder_container.winfo_children():
                widget.destroy()

    def rebuild_ui(self):
        """Rebuild the UI components after directory change."""
        # Rebuild folder tree UI
        self.create_folder_ui(
            self.folder_tree, self.folder_container, parent_rel_path="", level=-1)

        # Rebuild file type checkboxes
        self.rebuild_file_type_checkboxes()

    def rebuild_file_type_checkboxes(self):
        """Rebuild file type checkboxes with new extensions."""
        if not hasattr(self, 'filetype_scrollable_frame'):
            print("Warning: filetype_scrollable_frame not found")
            return

        # Clear existing checkboxes
        for widget in self.filetype_scrollable_frame.winfo_children():
            widget.destroy()

        # Clear existing file type data
        self.file_type_vars.clear()
        self.file_type_checkboxes.clear()

        # Rebuild checkboxes with new extensions
        num_columns = 3
        for i, ext in enumerate(self.sorted_extensions):
            var = ctk.BooleanVar(value=True)
            self.file_type_vars[ext] = var
            count = self.file_extension_counts_initial.get(ext, 0)
            label_text = f"{ext} files ({count})"
            checkbox = ctk.CTkCheckBox(
                self.filetype_scrollable_frame, text=label_text, variable=var,
                command=self.update_file_type_counts
            )
            row = i // num_columns
            col = i % num_columns
            checkbox.grid(row=row, column=col, sticky="w", padx=10, pady=2)
            self.file_type_checkboxes[ext] = checkbox

        # Force update of the scrollable frame
        self.filetype_scrollable_frame.update_idletasks()

    def update_status(self, message):
        """Update the status label."""
        if hasattr(self, 'status_label'):
            self.status_label.configure(text=message)

    # --- Scan extensions ---
    def scan_file_extensions(self, base_path):
        base_path = Path(base_path)
        if is_ignored_dir(base_path.name) or path_contains_ignored_dir(str(base_path)):
            return Counter()

        extension_counts = Counter()
        # Track extensions that hit limits for special handling
        self.limited_extensions = set()

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
                            self.limited_extensions.add(ext.lower())
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
        return extension_counts

    def _get_language_from_extension(self, ext):
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

    # --- Create checkbox images ---
    def create_checkbox_images(self):
        size = 18
        border_width = 2
        check_width = 2
        radius = 3

        try:
            # Try to get colors from theme using the proper CTK color system
            current_mode = ctk.get_appearance_mode().lower()
            theme = ctk.ThemeManager.theme

            # Get colors for current appearance mode (0=light, 1=dark)
            mode_index = 1 if current_mode == "dark" else 0

            fg_color_raw = theme["CTkCheckBox"]["fg_color"][mode_index]
            border_color_raw = theme["CTkCheckBox"]["border_color"][mode_index]
            checkmark_color_raw = theme["CTkCheckBox"]["checkmark_color"][mode_index]
            text_color_raw = theme["CTkLabel"]["text_color"][mode_index]

            # Convert theme colors to hex if needed
            fg_color = fg_color_raw if fg_color_raw.startswith(
                "#") else "#2ECC71"
            border_color_checked = border_color_raw if border_color_raw.startswith(
                "#") else "#2ECC71"
            checkmark_color = checkmark_color_raw if checkmark_color_raw.startswith(
                "#") else "#FFFFFF"
            border_color_unchecked = text_color_raw if text_color_raw.startswith(
                "#") else "#888888"

            indeterminate_color = "#F39C12"  # Orange
            indeterminate_line_color = "#FFFFFF"  # White
        except (AttributeError, KeyError, TypeError, IndexError):
            # Use fallback colors if theme access fails
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
    def build_folder_tree(self, base_path, max_depth=None, current_depth=0):
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
                sub_tree = self.build_folder_tree(
                    entry, next_max_depth, current_depth + 1)
                # Always include directories, even if empty
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
                folder_rel_path = str(
                    Path(parent_rel_path) / folder) if parent_rel_path else folder
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
        # Count ALL files in selected folders, regardless of file type selection
        for folder_path, files_dict in self.file_vars.items():
            for file, var in files_dict.items():
                if var.get():  # Only count files in selected folders/files
                    ext = Path(file).suffix
                    if ext:
                        current_counts[ext.lower()] += 1

        for ext, checkbox in self.file_type_checkboxes.items():
            count = current_counts.get(ext, 0)
            # Only show 'many' if we know there are files but they were limited during scanning
            if (count == 0 and
                hasattr(self, 'limited_extensions') and
                    ext in self.limited_extensions):
                label_text = f"{ext} files (many)"
            else:
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
                        ext = Path(file).suffix
                        if ext and ext.lower() in include_exts:
                            full_path = self.current_dir / current_folder_path / file
                            selected_files_paths.append(str(full_path))

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
            # Fixed: Added comma to make it a proper tuple
            args=(sorted(selected_files_paths),),
        )
        thread.daemon = True
        thread.start()

    def _process_thread(self, selected_files_paths):
        start_time = time.time()
        try:
            # Generate directory tree with ALL non-ignored files, not just selected types
            directory_tree = get_tree_filtered_string(
                self.current_dir, allowed_extensions=None)  # None means show all files
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

                    # Get file extension for syntax highlighting
                    ext = file_path_obj.suffix
                    language = self._get_language_from_extension(ext)

                    combined_text += f"## {relative_path}\n\n```{language}\n{content}\n```\n\n"
                    file_count += 1
                    total_size += len(content.encode('utf-8'))
                except Exception as e:
                    error_msg = f"Error reading {Path(file_path).relative_to(self.current_dir)}: {e}"
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


if __name__ == "__main__":
    app = App()
    app.mainloop()
