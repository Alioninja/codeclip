from pathlib import Path
from collections import Counter
from ..config import (
    MAX_INITIAL_SCAN_DEPTH, MAX_FILES_PER_DIR_SCAN,
    IGNORED_DIRS, IGNORED_FILES,
    MAX_FILES_TO_SHOW_ALL, TREE_SHOW_FIRST_FILES, TREE_SHOW_LAST_FILES,
    MAX_DIRS_TO_SHOW_ALL, TREE_SHOW_FIRST_DIRS, TREE_SHOW_LAST_DIRS
)
from ..utils.helpers import (
    is_ignored_dir, is_ignored_file, path_contains_ignored_dir
)

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


def get_tree_string(start_path, allowed_extensions=None,
                    max_files_to_show_all=None, tree_show_first=None, tree_show_last=None,
                    max_dirs_to_show_all=None, tree_show_first_dirs=None, tree_show_last_dirs=None,
                    tree_view_mode="full", selected_files=None):
    """Generate a string representation of the directory tree.

    When a directory has more files than max_files_to_show_all, only the first
    tree_show_first and last tree_show_last files are shown, with a summary
    message indicating how many files were omitted.

    The same logic applies to directories using the max_dirs_to_show_all,
    tree_show_first_dirs, and tree_show_last_dirs parameters.

    When tree_view_mode is "selection", only directories containing selected
    files are expanded. Other directories are shown but not recursed into.
    selected_files should be a set of absolute Path objects.
    """
    start_path = Path(start_path)
    if path_contains_ignored_dir(str(start_path)):
        return ""

    # Use config defaults if not specified
    if max_files_to_show_all is None:
        max_files_to_show_all = MAX_FILES_TO_SHOW_ALL
    if tree_show_first is None:
        tree_show_first = TREE_SHOW_FIRST_FILES
    if tree_show_last is None:
        tree_show_last = TREE_SHOW_LAST_FILES
    if max_dirs_to_show_all is None:
        max_dirs_to_show_all = MAX_DIRS_TO_SHOW_ALL
    if tree_show_first_dirs is None:
        tree_show_first_dirs = TREE_SHOW_FIRST_DIRS
    if tree_show_last_dirs is None:
        tree_show_last_dirs = TREE_SHOW_LAST_DIRS

    # Build a set of directory paths that contain selected files (for selection mode)
    selected_dirs = set()
    if tree_view_mode == "selection" and selected_files:
        for f in selected_files:
            parent = f.parent
            while parent != start_path and str(parent).startswith(str(start_path)):
                selected_dirs.add(parent)
                parent = parent.parent
            selected_dirs.add(start_path)

    lines = []

    def _dir_has_selection(dir_path):
        """Check if a directory (or any descendant) contains a selected file."""
        return dir_path in selected_dirs

    def walk(path, prefix=""):
        try:
            entries = list(path.iterdir())
            dirs = sorted([e for e in entries if e.is_dir() and not is_ignored_dir(e.name)], key=lambda e: e.name.lower())
            files = sorted([e for e in entries if e.is_file() and not is_ignored_file(e.name)], key=lambda e: e.name.lower())

            if allowed_extensions:
                files = [f for f in files if f.suffix.lower() in allowed_extensions]

            # In selection mode, only show files that are selected
            if tree_view_mode == "selection" and selected_files:
                files = [f for f in files if f in selected_files]

            # Apply directory list truncation for long lists
            dirs_to_show = dirs
            dirs_omitted_count = 0
            if len(dirs) > max_dirs_to_show_all:
                first_dirs = dirs[:tree_show_first_dirs]
                last_dirs = dirs[-tree_show_last_dirs:] if tree_show_last_dirs > 0 else []
                dirs_to_show = first_dirs + last_dirs
                dirs_omitted_count = len(dirs) - len(dirs_to_show)

            # Apply file list truncation for long lists
            files_to_show = files
            files_omitted_count = 0
            if len(files) > max_files_to_show_all:
                first_files = files[:tree_show_first]
                last_files = files[-tree_show_last:] if tree_show_last > 0 else []
                files_to_show = first_files + last_files
                files_omitted_count = len(files) - len(files_to_show)

            all_entries = dirs_to_show + files_to_show
            total_lines = len(all_entries) + (1 if dirs_omitted_count > 0 else 0) + (1 if files_omitted_count > 0 else 0)
            dirs_section_len = len(dirs_to_show) + (1 if dirs_omitted_count > 0 else 0)
            line_idx = 0
            dirs_omitted_inserted = False
            files_omitted_inserted = False

            for i, entry in enumerate(all_entries):
                # Insert dirs omitted message between first and last dirs
                if (dirs_omitted_count > 0 and not dirs_omitted_inserted
                        and i >= tree_show_first_dirs and i < len(dirs_to_show)):
                    dirs_omitted_inserted = True
                    is_last_line = line_idx == total_lines - 1
                    pointer = "└── " if is_last_line else "├── "
                    lines.append(f"{prefix}{pointer}... ({dirs_omitted_count} dirs omitted) ...")
                    line_idx += 1

                # Insert files omitted message between first and last files
                files_idx = i - len(dirs_to_show)
                if (files_omitted_count > 0 and not files_omitted_inserted
                        and files_idx >= 0 and files_idx >= tree_show_first):
                    files_omitted_inserted = True
                    is_last_line = line_idx == total_lines - 1
                    pointer = "└── " if is_last_line else "├── "
                    lines.append(f"{prefix}{pointer}... ({files_omitted_count} files omitted) ...")
                    line_idx += 1

                is_last_line = line_idx == total_lines - 1
                pointer = "└── " if is_last_line else "├── "

                if entry.is_dir():
                    lines.append(f"{prefix}{pointer}{entry.name}/")
                    extension = "    " if is_last_line else "│   "
                    if not path_contains_ignored_dir(str(entry)):
                        # In selection mode, only recurse into dirs that have selected files
                        if tree_view_mode == "selection" and selected_files:
                            if _dir_has_selection(entry):
                                walk(entry, prefix + extension)
                        else:
                            walk(entry, prefix + extension)
                else:
                    lines.append(f"{prefix}{pointer}{entry.name}")
                line_idx += 1

            # Handle edge case: omitted messages at the end when no trailing entries
            if dirs_omitted_count > 0 and not dirs_omitted_inserted:
                is_last_line = line_idx == total_lines - 1
                pointer = "└── " if is_last_line else "├── "
                lines.append(f"{prefix}{pointer}... ({dirs_omitted_count} dirs omitted) ...")
                line_idx += 1
            if files_omitted_count > 0 and not files_omitted_inserted:
                is_last_line = line_idx == total_lines - 1
                pointer = "└── " if is_last_line else "├── "
                lines.append(f"{prefix}{pointer}... ({files_omitted_count} files omitted) ...")
        except OSError:
            pass

    walk(start_path)
    return "\n".join(lines)


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
