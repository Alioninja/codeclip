"""
Core functionality for codebase processing - extracted from the original GUI application.
This module contains all the business logic without GUI dependencies.
"""

from pathlib import Path
from collections import Counter
import time
import traceback

# --- Configuration ---
IGNORED_DIRS = {"__pycache__", "venv", "env", "node_modules"}
IGNORED_FILES = {}
IGNORED_DIR_PREFIXES = ['.', '_']
IGNORED_FILE_PREFIXES = ['.']
MAX_FILES_PER_DIR_SCAN = 100
MAX_INITIAL_SCAN_DEPTH = 2
LARGE_DIR_THRESHOLD = 50
MAX_FILES_TO_SHOW_ALL = 25
TREE_SHOW_FIRST_FILES = 10
TREE_SHOW_LAST_FILES = 3

# Progress tracking
current_progress = 0


def _normalized_parts(value):
    """Return normalized, case-insensitive path parts."""
    normalized = str(Path(value)).lower()
    return tuple(part for part in Path(normalized).parts if part)


IGNORED_DIRS_COMPONENTS = [_normalized_parts(name) for name in IGNORED_DIRS]
IGNORED_DIRS_BASENAMES = {parts[0]
                          for parts in IGNORED_DIRS_COMPONENTS if len(parts) == 1}
IGNORED_FILES_NORMALIZED = {name.lower() for name in IGNORED_FILES}


def is_ignored_dir(name):
    """Check if directory should be ignored"""
    if name == '.' or name == '..':
        return False
    if name.lower() in IGNORED_DIRS_BASENAMES:
        return True
    return any(name.startswith(prefix) for prefix in IGNORED_DIR_PREFIXES)


def is_ignored_file(name):
    """Check if file should be ignored"""
    lower_name = name.lower()
    if lower_name in IGNORED_FILES_NORMALIZED:
        return True
    return any(name.startswith(prefix) for prefix in IGNORED_FILE_PREFIXES)


def path_contains_ignored_dir(path):
    """Check if path contains any ignored directory"""
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


def scan_file_extensions(base_path):
    """Scan directory for file extensions and their counts"""
    base_path = Path(base_path)
    if is_ignored_dir(base_path.name) or path_contains_ignored_dir(str(base_path)):
        return Counter()

    extension_counts = Counter()

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
                    all_files.append(item)
                elif item.is_dir() and not is_ignored_dir(item.name):
                    subdirs.append(item)

            # Process files in current directory
            if len(all_files) > MAX_FILES_PER_DIR_SCAN:
                sampled_files = all_files[:MAX_FILES_PER_DIR_SCAN //
                                          2] + all_files[-MAX_FILES_PER_DIR_SCAN // 2:]
                multiplier = len(all_files) / len(sampled_files)
                for file in sampled_files:
                    ext = file.suffix.lower()
                    if ext:
                        extension_counts[ext] += int(multiplier)
            else:
                for file in all_files:
                    ext = file.suffix.lower()
                    if ext:
                        extension_counts[ext] += 1

            # Recursively scan subdirectories
            for subdir in subdirs:
                scan_directory(subdir, current_depth + 1)

        except (OSError, PermissionError):
            pass

    scan_directory(base_path)
    return extension_counts


def build_folder_tree(base_path, max_depth=None, current_depth=0):
    """Build folder tree structure"""
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

        next_max_depth = 3 if max_depth is None else max_depth

        for entry in dirs:
            sub_tree = build_folder_tree(
                entry, next_max_depth, current_depth + 1)
            tree["subfolders"][entry.name] = sub_tree
    except OSError:
        pass

    return tree


def get_language_from_extension(ext):
    """Map file extensions to language identifiers for markdown code blocks"""
    ext = ext.lower()
    language_map = {
        '.py': 'python', '.js': 'javascript', '.ts': 'typescript',
        '.tsx': 'tsx', '.jsx': 'jsx', '.java': 'java',
        '.c': 'c', '.cpp': 'cpp', '.cc': 'cpp', '.cxx': 'cpp',
        '.h': 'c', '.hpp': 'cpp', '.cs': 'csharp', '.php': 'php',
        '.rb': 'ruby', '.go': 'go', '.rs': 'rust', '.swift': 'swift',
        '.kt': 'kotlin', '.scala': 'scala', '.sh': 'bash', '.bash': 'bash',
        '.zsh': 'zsh', '.fish': 'fish', '.ps1': 'powershell',
        '.bat': 'batch', '.cmd': 'batch', '.html': 'html', '.htm': 'html',
        '.xml': 'xml', '.css': 'css', '.scss': 'scss', '.sass': 'sass',
        '.less': 'less', '.json': 'json', '.yaml': 'yaml', '.yml': 'yaml',
        '.toml': 'toml', '.ini': 'ini', '.cfg': 'ini', '.conf': 'conf',
        '.md': 'markdown', '.markdown': 'markdown', '.rst': 'rst',
        '.txt': 'text', '.sql': 'sql', '.dockerfile': 'dockerfile',
        '.gitignore': 'gitignore', '.env': 'bash', '.r': 'r',
        '.m': 'matlab', '.pl': 'perl', '.lua': 'lua', '.vim': 'vim',
        '.asm': 'assembly', '.s': 'assembly'
    }
    return language_map.get(ext, '')


def get_tree_filtered_string(start_path, allowed_extensions=None, indent_char="    ", prefix=""):
    """Generate directory tree string with optional extension filtering"""
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

                if file_count > MAX_FILES_PER_DIR_SCAN:
                    too_many_files = True
                    break

                if allowed_extensions is None:
                    files.append(entry)
                else:
                    ext = entry.suffix.lower()
                    if ext in allowed_extensions:
                        files.append(entry)
            elif entry.is_dir():
                if not is_ignored_dir(name):
                    dirs.append(entry)

        dirs.sort(key=lambda e: e.name.lower())
        files.sort(key=lambda e: e.name.lower())

        # Apply file truncation if needed
        files_to_show = files
        omitted_count = 0
        performance_limit_msg = ""

        if too_many_files:
            if len(files) > MAX_FILES_TO_SHOW_ALL:
                first_files = files[:TREE_SHOW_FIRST_FILES]
                last_files = files[-TREE_SHOW_LAST_FILES:]
                files_to_show = first_files + last_files
                omitted_count = len(files) - len(files_to_show)
                performance_limit_msg = f"... (directory too large, showing first {TREE_SHOW_FIRST_FILES} and last {TREE_SHOW_LAST_FILES} of {file_count}+ files) ..."
            else:
                performance_limit_msg = f"... (directory too large, showing first {len(files)} of {file_count}+ files) ..."
        elif len(files) > MAX_FILES_TO_SHOW_ALL:
            first_files = files[:TREE_SHOW_FIRST_FILES]
            last_files = files[-TREE_SHOW_LAST_FILES:]
            files_to_show = first_files + last_files
            omitted_count = len(files) - len(files_to_show)

        all_entries = dirs + files_to_show

        if performance_limit_msg and len(dirs) < len(all_entries):
            lines.append(prefix + pointers["normal"] + performance_limit_msg)

        for i, entry in enumerate(all_entries):
            is_last_entry = (i == len(all_entries) - 1)

            if (omitted_count > 0 and entry in files and i == len(dirs) + TREE_SHOW_FIRST_FILES):
                omitted_pointer = pointers["normal"]
                lines.append(prefix + omitted_pointer +
                             f"... ({omitted_count} files omitted) ...")

            pointer = pointers["last"] if is_last_entry else pointers["normal"]
            extend = extender["last"] if is_last_entry else extender["normal"]

            if entry.is_dir():
                lines.append(prefix + pointer + entry.name + "/")
                subtree_str = get_tree_filtered_string(
                    entry, allowed_extensions, indent_char, prefix + extend)
                if subtree_str:
                    lines.append(subtree_str)
            else:
                lines.append(prefix + pointer + entry.name)

    except OSError:
        return ""

    return "\n".join(lines)


def process_selected_files(base_path, selected_files):
    """Process selected files and generate the output"""
    start_time = time.time()

    try:
        # Generate directory tree
        directory_tree = get_tree_filtered_string(
            base_path, allowed_extensions=None)
        combined_text = "PROJECT DIRECTORY STRUCTURE:\n" + directory_tree + \
            "\n\n" + "=" * 20 + " FILE CONTENTS " + "=" * 20 + "\n\n"

        file_count = 0
        total_size = 0
        errors = []

        for file_path in selected_files:
            try:
                file_path_obj = Path(file_path)
                base_path_obj = Path(base_path)
                relative_path = str(file_path_obj.relative_to(
                    base_path_obj)).replace("\\", "/")

                with open(file_path_obj, 'r', encoding='utf-8', errors='ignore') as file:
                    content = file.read()

                file_size = len(content.encode('utf-8'))
                total_size += file_size

                ext = file_path_obj.suffix.lower()
                language = get_language_from_extension(ext)

                combined_text += f"FILE: {relative_path}\n"
                if language:
                    combined_text += f"```{language}\n{content}\n```\n\n"
                else:
                    combined_text += f"```\n{content}\n```\n\n"

                file_count += 1

            except Exception as e:
                error_msg = f"Error reading {file_path}: {e}"
                errors.append(error_msg)
                print(error_msg)

        end_time = time.time()
        duration = end_time - start_time
        kb_size = total_size / 1024
        mb_size = kb_size / 1024
        size_str = f"{mb_size:.2f} MB" if mb_size >= 1 else f"{kb_size:.1f} KB"

        return {
            'success': True,
            'content': combined_text,
            'file_count': file_count,
            'total_size': total_size,
            'size_display': size_str,
            'duration': duration,
            'errors': errors
        }

    except Exception as e:
        print(f"Error during processing: {e}")
        traceback.print_exc()
        return {
            'success': False,
            'error': str(e)
        }


def process_selected_files_with_progress(base_path, selected_files):
    """Process selected files with progress tracking - optimized version"""
    global current_progress
    start_time = time.time()

    try:
        # Reset progress
        current_progress = 0

        # Generate directory tree quickly (no progress needed for this)
        directory_tree = get_tree_filtered_string(
            base_path, allowed_extensions=None)
        combined_text = "PROJECT DIRECTORY STRUCTURE:\n" + directory_tree + \
            "\n\n" + "=" * 20 + " FILE CONTENTS " + "=" * 20 + "\n\n"

        file_count = 0
        total_size = 0
        errors = []
        total_files = len(selected_files)

        # Process files with progress tracking
        for index, file_path in enumerate(selected_files):
            try:
                file_path_obj = Path(file_path)
                base_path_obj = Path(base_path)
                relative_path = str(file_path_obj.relative_to(
                    base_path_obj)).replace("\\", "/")

                with open(file_path_obj, 'r', encoding='utf-8', errors='ignore') as file:
                    content = file.read()

                file_size = len(content.encode('utf-8'))
                total_size += file_size

                ext = file_path_obj.suffix.lower()
                language = get_language_from_extension(ext)

                combined_text += f"FILE: {relative_path}\n"
                if language:
                    combined_text += f"```{language}\n{content}\n```\n\n"
                else:
                    combined_text += f"```\n{content}\n```\n\n"

                file_count += 1

                # Update progress
                current_progress = int((index + 1) / total_files * 100)

            except Exception as e:
                error_msg = f"Error reading {file_path}: {e}"
                errors.append(error_msg)
                print(error_msg)

        end_time = time.time()
        duration = end_time - start_time
        kb_size = total_size / 1024
        mb_size = kb_size / 1024
        size_str = f"{mb_size:.2f} MB" if mb_size >= 1 else f"{kb_size:.1f} KB"

        # Clear progress
        current_progress = 0

        return {
            'success': True,
            'content': combined_text,
            'file_count': file_count,
            'total_size': total_size,
            'size_display': size_str,
            'duration': duration,
            'errors': errors
        }

    except Exception as e:
        print(f"Error during processing: {e}")
        traceback.print_exc()
        # Clear progress on error
        current_progress = 0
        return {
            'success': False,
            'error': str(e)
        }
