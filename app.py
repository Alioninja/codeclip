#!/usr/bin/env python3
"""
Codebase to Clipboard - Web Application
A Flask-based web application for converting codebases to clipboard text.
"""

import os
import json
import time
import threading
import platform
import shutil
import subprocess
from pathlib import Path
from collections import Counter
from flask import Flask, request, jsonify, send_from_directory
import webbrowser
from threading import Timer

# Import the core functionality from the original script
from codebase_core import (
    scan_file_extensions, build_folder_tree, get_tree_filtered_string,
    process_selected_files, process_selected_files_with_progress, is_ignored_dir, is_ignored_file, path_contains_ignored_dir,
    IGNORED_DIRS, IGNORED_FILES, IGNORED_DIR_PREFIXES, IGNORED_FILE_PREFIXES,
    MAX_FILES_PER_DIR_SCAN, MAX_INITIAL_SCAN_DEPTH, LARGE_DIR_THRESHOLD
)

# React build directory
REACT_BUILD_DIR = os.path.join(os.path.dirname(__file__), 'react-app', 'build')

# Initialize Flask app with React build
app = Flask(__name__,
            static_folder=os.path.join(REACT_BUILD_DIR, 'static'),
            static_url_path='/static')

app.secret_key = 'your-secret-key-here'  # Change this in production

# Global variables to store current project state
current_project = {
    'path': None,
    'tree': None,
    'extensions': None,
    'sorted_extensions': None
}


@app.route('/')
def index():
    """Main page - serve React app"""
    return send_from_directory(REACT_BUILD_DIR, 'index.html')


@app.route('/favicon.ico')
def favicon():
    """Serve favicon"""
    try:
        return send_from_directory(REACT_BUILD_DIR, 'favicon.ico')
    except:
        # Fallback to default Flask behavior
        return '', 404


@app.route('/api/select-directory', methods=['POST'])
def select_directory():
    """Handle directory selection"""
    try:
        data = request.json
        directory_path = data.get('path', '')

        print(f"DEBUG: Selecting directory: {directory_path}")

        if not directory_path:
            return jsonify({'error': 'No directory path provided'}), 400

        path = Path(directory_path)
        if not path.exists() or not path.is_dir():
            return jsonify({'error': 'Invalid directory path'}), 400

        # Initialize project data
        print(f"DEBUG: Scanning extensions for {path}")
        extensions = scan_file_extensions(path)
        print(
            f"DEBUG: Found {len(extensions)} extensions: {list(extensions.keys())}")

        sorted_extensions = sorted(
            extensions.keys(), key=lambda x: extensions[x], reverse=True)

        print(f"DEBUG: Building folder tree")
        tree = build_folder_tree(path)
        print(
            f"DEBUG: Tree has {len(tree.get('subfolders', {}))} subfolders and {len(tree.get('files', []))} files")

        # Update global state
        current_project.update({
            'path': str(path),
            'tree': tree,
            'extensions': extensions,
            'sorted_extensions': sorted_extensions
        })

        result = {
            'success': True,
            'project_name': path.name,
            'path': str(path),
            'extensions': {ext: count for ext, count in extensions.items()},
            'tree': serialize_tree(tree)
        }

        print(f"DEBUG: Returning success response")
        return jsonify(result)

    except Exception as e:
        print(f"ERROR in select_directory: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/browse-directory', methods=['POST'])
def browse_directory():
    """Browse directory contents"""
    try:
        data = request.json
        directory_path = data.get('path', Path.cwd())

        path = Path(directory_path)
        if not path.exists() or not path.is_dir():
            return jsonify({'error': 'Invalid directory path'}), 400

        directories = []
        try:
            for item in sorted(path.iterdir(), key=lambda x: x.name.lower()):
                if item.is_dir() and not is_ignored_dir(item.name):
                    directories.append({
                        'name': item.name,
                        'path': str(item),
                        'is_dir': True
                    })
        except PermissionError:
            return jsonify({'error': 'Permission denied'}), 403

        return jsonify({
            'current_path': str(path),
            'parent_path': str(path.parent) if path.parent != path else None,
            'directories': directories
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/process', methods=['POST'])
def process_files():
    """Process selected files and return the result"""
    try:
        data = request.json
        selected_files = data.get('selected_files', [])
        selected_extensions = data.get('selected_extensions', [])

        print(
            f"DEBUG: Processing {len(selected_files)} files with extensions {selected_extensions}")

        if not current_project.get('path'):
            return jsonify({'error': 'No project directory selected'}), 400

        if not selected_files:
            return jsonify({'error': 'No files selected'}), 400

        # Reset progress
        import codebase_core
        codebase_core.current_progress = 0

        # Check if this is a browser-selected directory
        if current_project.get('is_browser_directory'):
            # For browser directories, we need to handle file processing differently
            result = process_browser_selected_files(
                current_project.get('original_structure'),
                selected_files,
                selected_extensions,
                current_project['path']
            )
        else:
            # Traditional path-based processing
            # Filter files by selected extensions
            filtered_files = []
            for file_path in selected_files:
                file_ext = Path(file_path).suffix.lower()
                if not selected_extensions or file_ext in selected_extensions:
                    filtered_files.append(file_path)

            print(f"DEBUG: Filtered to {len(filtered_files)} files")

            if not filtered_files:
                return jsonify({'error': 'No files match selected file types'}), 400

            # Process files using the existing method with progress callback
            result = process_selected_files_with_progress(
                current_project['path'],
                filtered_files
            )

        print(
            f"DEBUG: Processing result: success={result.get('success')}, files={result.get('file_count')}")
        return jsonify(result)

    except Exception as e:
        print(f"ERROR in process_files: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/progress')
def get_progress():
    """Get current processing progress"""
    try:
        import codebase_core
        progress = getattr(codebase_core, 'current_progress', 0)
        return jsonify({'progress': progress})
    except Exception as e:
        return jsonify({'progress': 0})


@app.route('/api/get-common-directories')
def get_common_directories():
    """Get common directories that users might want to browse"""
    directories = []

    try:
        import os
        import platform

        home = Path.home()

        # Common directories based on OS
        if platform.system() == 'Windows':
            common_paths = [
                home,
                home / "Documents",
                home / "Desktop",
                home / "Downloads",
                Path("C:/"),
                Path("D:/") if Path("D:/").exists() else None,
                Path("C:/Users"),
                Path("C:/Program Files"),
                Path(
                    "C:/Program Files (x86)") if Path("C:/Program Files (x86)").exists() else None,
            ]
        elif platform.system() == 'Darwin':  # macOS
            common_paths = [
                home,
                home / "Documents",
                home / "Desktop",
                home / "Downloads",
                Path("/Applications"),
                Path("/Users"),
                Path("/Volumes"),
            ]
        else:  # Linux
            common_paths = [
                home,
                home / "Documents",
                home / "Desktop",
                home / "Downloads",
                Path("/home"),
                Path("/opt"),
                Path("/usr"),
                Path("/var"),
            ]

        # Filter existing paths and format them
        for path in common_paths:
            if path and path.exists() and path.is_dir():
                try:
                    # Check if we can list the directory (permissions)
                    list(path.iterdir())
                    directories.append({
                        'name': str(path.name) if path.name else str(path),
                        'path': str(path),
                        'type': 'common'
                    })
                except (PermissionError, OSError):
                    # Skip directories we can't access
                    continue

        return jsonify(directories)

    except Exception as e:
        print(f"Error getting common directories: {e}")
        return jsonify([])


@app.route('/api/get-current-directory')
def get_current_directory():
    """Get the current working directory"""
    cwd = Path.cwd()
    return jsonify({
        'name': cwd.name,
        'path': str(cwd)
    })


@app.route('/api/get-home-directories')
def get_home_directories():
    """Get common directories for quick access"""
    directories = []

    # Add common directories
    home = Path.home()
    desktop = home / "Desktop"
    documents = home / "Documents"
    downloads = home / "Downloads"

    for dir_path in [home, desktop, documents, downloads]:
        if dir_path.exists():
            directories.append({
                'name': dir_path.name,
                'path': str(dir_path)
            })

    # Add current working directory
    cwd = Path.cwd()
    directories.insert(0, {
        'name': f"Current Directory ({cwd.name})",
        'path': str(cwd)
    })

    return jsonify(directories)


@app.route('/api/process-directory-structure', methods=['POST'])
def process_directory_structure():
    """Process directory structure from File System Access API"""
    try:
        data = request.json
        directory_structure = data.get('directoryStructure')
        root_name = data.get('rootName', 'Selected Folder')

        if not directory_structure:
            return jsonify({'error': 'No directory structure provided'}), 400

        print(f"DEBUG: Processing directory structure for: {root_name}")

        # Convert the browser directory structure to our internal format
        extensions = Counter()
        tree = convert_browser_structure_to_tree(
            directory_structure, extensions)

        print(
            f"DEBUG: Found {len(extensions)} extensions: {list(extensions.keys())}")

        sorted_extensions = sorted(
            extensions.keys(), key=lambda x: extensions[x], reverse=True)

        # Update global state with virtual path
        virtual_path = f"browser-selected:{root_name}"
        current_project.update({
            'path': virtual_path,
            'tree': tree,
            'extensions': extensions,
            'sorted_extensions': sorted_extensions,
            'is_browser_directory': True,
            'original_structure': directory_structure
        })

        result = {
            'success': True,
            'project_name': root_name,
            'virtual_path': virtual_path,
            'extensions': {ext: count for ext, count in extensions.items()},
            'tree': serialize_tree(tree)
        }

        print(f"DEBUG: Successfully processed browser directory structure")
        return jsonify(result)

    except Exception as e:
        print(f"ERROR in process_directory_structure: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def convert_browser_structure_to_tree(structure, extensions, path_prefix=""):
    """Convert browser directory structure to our internal tree format"""
    tree = {
        'files': [],
        'subfolders': {}
    }

    if not structure.get('children'):
        return tree

    for child in structure['children']:
        child_name = child['name']

        if child['type'] == 'file':
            # Skip ignored files
            if not is_ignored_file(child_name):
                tree['files'].append(child_name)

                # Extract file extension
                if '.' in child_name:
                    ext = child_name.split('.')[-1].lower()
                    if ext:  # Don't count empty extensions
                        extensions[ext] += 1

        elif child['type'] == 'directory':
            # Skip ignored directories
            if not is_ignored_dir(child_name):
                child_path = f"{path_prefix}/{child_name}" if path_prefix else child_name
                subtree = convert_browser_structure_to_tree(
                    child, extensions, child_path)
                tree['subfolders'][child_name] = subtree

    return tree


@app.route('/api/find-directory', methods=['POST'])
def find_directory():
    """Find a directory by name in common locations"""
    try:
        data = request.json
        directory_name = data.get('name', '')

        if not directory_name:
            return jsonify({'error': 'No directory name provided'}), 400

        # Get common directories to search in
        common_dirs = []

        # Add current working directory
        try:
            current_dir = os.getcwd()
            common_dirs.append(current_dir)
        except:
            pass

        # Add user directories
        try:
            home_dir = Path.home()
            common_dirs.extend([
                str(home_dir),
                str(home_dir / 'Documents'),
                str(home_dir / 'Desktop'),
                str(home_dir / 'Downloads'),
            ])
        except:
            pass

        # Add system directories
        if os.name == 'nt':  # Windows
            common_dirs.extend([
                'C:\\Projects',
                'C:\\',
                'D:\\',
            ])
        else:  # Unix-like
            common_dirs.extend([
                '/opt',
                '/usr/local',
                '/Applications' if os.uname().sysname == 'Darwin' else '/usr/share'
            ])

        # Search for the directory
        found_paths = []
        for parent_dir in common_dirs:
            try:
                parent_path = Path(parent_dir)
                if parent_path.exists() and parent_path.is_dir():
                    # Look for exact match
                    target_path = parent_path / directory_name
                    if target_path.exists() and target_path.is_dir():
                        found_paths.append(str(target_path))

                    # Also search subdirectories (limited depth for performance)
                    try:
                        for item in parent_path.iterdir():
                            if item.is_dir() and item.name == directory_name:
                                found_paths.append(str(item))
                    except (PermissionError, OSError):
                        continue
            except (PermissionError, OSError, Exception):
                continue

        # Remove duplicates while preserving order
        unique_paths = []
        seen = set()
        for path in found_paths:
            if path not in seen:
                unique_paths.append(path)
                seen.add(path)

        return jsonify({
            'success': True,
            'found_paths': unique_paths[:10],  # Limit to 10 results
            'directory_name': directory_name
        })

    except Exception as e:
        print(f"ERROR in find_directory: {str(e)}")
        return jsonify({'error': str(e)}), 500


def process_browser_selected_files(directory_structure, selected_files, selected_extensions, virtual_path):
    """Process files selected from browser directory structure"""
    try:
        # Since we can't actually read file contents from the browser due to security restrictions,
        # we'll create a placeholder response that explains this limitation

        # Filter selected files by extension
        filtered_files = []
        for file_path in selected_files:
            file_ext = Path(file_path).suffix.lower()
            if not selected_extensions or file_ext in selected_extensions:
                filtered_files.append(file_path)

        if not filtered_files:
            return {'success': False, 'error': 'No files match selected file types'}

        # Create a summary of what would be processed
        file_summary = []
        for file_path in filtered_files[:10]:  # Show first 10 files
            file_summary.append(f"- {file_path}")

        if len(filtered_files) > 10:
            file_summary.append(
                f"... and {len(filtered_files) - 10} more files")

        # Create the result text
        result_text = f"""# Codebase Structure: {directory_structure['name']}

## ⚠️ Browser Security Limitation

Due to browser security restrictions, file contents cannot be read directly from the File System Access API.

To process the actual file contents, please:
1. Use the traditional "Browse" button and manually enter the directory path, or
2. Copy this project to a location the web app can access

## Selected Files ({len(filtered_files)} files)

{chr(10).join(file_summary)}

## File Extensions

Selected extensions: {', '.join(selected_extensions) if selected_extensions else 'All'}

---

*To get the actual file contents, please use the manual path entry method instead of browser folder selection.*
"""

        return {
            'success': True,
            'content': result_text,
            'file_count': len(filtered_files),
            'total_chars': len(result_text),
            'is_browser_limitation': True
        }

    except Exception as e:
        print(f"ERROR in process_browser_selected_files: {str(e)}")
        return {'success': False, 'error': str(e)}


def serialize_tree(tree, path_prefix=None):
    """Convert tree structure to JSON-serializable format"""
    result = {
        'files': tree.get('files', []),
        'subfolders': {},
        'is_large': tree.get('is_large', False)
    }

    for folder_name, subtree in tree.get('subfolders', {}).items():
        folder_path = f"{path_prefix}/{folder_name}" if path_prefix else folder_name
        result['subfolders'][folder_name] = serialize_tree(
            subtree, folder_path)

    return result


def open_browser():
    """Open web browser to the application"""
    webbrowser.open('http://127.0.0.1:8080')


def browse_directory_native():
    """Open a native directory picker using platform-specific utilities with a console fallback."""
    system = platform.system()
    current_dir = os.getcwd()

    def _log_error(tool, message):
        if message:
            print(f"{tool} directory selection error: {message}")

    try:
        if system == 'Windows':
            powershell = shutil.which(
                'powershell.exe') or shutil.which('powershell')
            if powershell:
                preset_dir = current_dir.replace("'", "''")
                script = f"""Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = 'Select a Project Directory'
$dialog.ShowNewFolderButton = $false
$dialog.SelectedPath = '{preset_dir}'
$result = $dialog.ShowDialog()
if ($result -eq [System.Windows.Forms.DialogResult]::OK) {{
    Write-Output $dialog.SelectedPath
}}
""".strip()
                try:
                    result = subprocess.run(
                        [powershell, '-Sta', '-NoProfile',
                            '-ExecutionPolicy', 'Bypass', '-Command', script],
                        capture_output=True,
                        text=True,
                        timeout=120
                    )
                    if result.returncode == 0:
                        selected_path = result.stdout.strip()
                        if selected_path:
                            return selected_path
                    else:
                        _log_error('PowerShell', result.stderr.strip())
                except subprocess.TimeoutExpired:
                    print("PowerShell dialog timeout - user may have closed it")
                    return None
        elif system == 'Darwin':
            osascript = shutil.which('osascript')
            if osascript:
                escaped_dir = current_dir.replace('"', '\"')
                script = (
                    'POSIX path of (choose folder with prompt "Select a Project Directory" '
                    f'default location POSIX file "{escaped_dir}")'
                )
                result = subprocess.run(
                    [osascript, '-e', script],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    selected_path = result.stdout.strip()
                    if selected_path:
                        return selected_path
                else:
                    stderr = result.stderr.strip()
                    if stderr and 'User canceled' not in stderr:
                        _log_error('osascript', stderr)
        else:
            zenity = shutil.which('zenity')
            if zenity:
                result = subprocess.run(
                    [
                        zenity,
                        '--file-selection',
                        '--directory',
                        '--title=Select a Project Directory',
                        f'--filename={current_dir}{os.sep}'
                    ],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    selected_path = result.stdout.strip()
                    if selected_path:
                        return selected_path
                else:
                    stderr = result.stderr.strip()
                    if stderr and 'user' not in stderr.lower():
                        _log_error('zenity', stderr)
            kdialog = shutil.which('kdialog')
            if kdialog:
                result = subprocess.run(
                    [kdialog, '--getexistingdirectory', current_dir,
                        '--title', 'Select a Project Directory'],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    selected_path = result.stdout.strip()
                    if selected_path:
                        return selected_path
                else:
                    stderr = result.stderr.strip()
                    if stderr and 'cancel' not in stderr.lower():
                        _log_error('kdialog', stderr)
    except Exception as exc:
        _log_error('Native picker', str(exc))

    print('Unable to open a native directory picker; falling back to console input.')
    try:
        user_input = input(
            'Enter directory path (leave blank to cancel): ').strip()
    except (EOFError, KeyboardInterrupt):
        return None

    if not user_input:
        return None

    candidate = Path(user_input).expanduser()
    if candidate.exists() and candidate.is_dir():
        return str(candidate.resolve())
    print(f'Invalid directory provided: {candidate}')
    return None


@app.route('/api/browse-native', methods=['POST'])
def browse_native():
    """Handle native directory browsing using platform-specific tooling."""
    try:
        print("DEBUG: Opening native directory browser...")
        directory_path = browse_directory_native()

        if directory_path:
            print(f"DEBUG: Selected directory: {directory_path}")
            return jsonify({'success': True, 'path': directory_path})
        else:
            print("DEBUG: No directory selected (user cancelled)")
            return jsonify({'success': False, 'error': 'No directory selected'})

    except Exception as e:
        print(f"ERROR in browse_native: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/get-config')
def get_config():
    """Get current configuration values"""
    try:
        import codebase_core
        config = {
            'MAX_FILES_PER_DIR_SCAN': codebase_core.MAX_FILES_PER_DIR_SCAN,
            'MAX_INITIAL_SCAN_DEPTH': codebase_core.MAX_INITIAL_SCAN_DEPTH,
            'LARGE_DIR_THRESHOLD': codebase_core.LARGE_DIR_THRESHOLD,
            'MAX_FILES_TO_SHOW_ALL': codebase_core.MAX_FILES_TO_SHOW_ALL,
            'TREE_SHOW_FIRST_FILES': codebase_core.TREE_SHOW_FIRST_FILES,
            'TREE_SHOW_LAST_FILES': codebase_core.TREE_SHOW_LAST_FILES,
            'IGNORED_DIRS': list(codebase_core.IGNORED_DIRS),
            'IGNORED_FILES': list(codebase_core.IGNORED_FILES),
            'IGNORED_DIR_PREFIXES': codebase_core.IGNORED_DIR_PREFIXES,
            'IGNORED_FILE_PREFIXES': codebase_core.IGNORED_FILE_PREFIXES
        }
        return jsonify({'success': True, 'config': config})
    except Exception as e:
        print(f"ERROR in get_config: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/update-config', methods=['POST'])
def update_config():
    """Update configuration values"""
    try:
        data = request.json
        config = data.get('config', {})

        import codebase_core

        # Update the configuration values
        if 'MAX_FILES_PER_DIR_SCAN' in config:
            codebase_core.MAX_FILES_PER_DIR_SCAN = config['MAX_FILES_PER_DIR_SCAN']
        if 'MAX_INITIAL_SCAN_DEPTH' in config:
            codebase_core.MAX_INITIAL_SCAN_DEPTH = config['MAX_INITIAL_SCAN_DEPTH']
        if 'LARGE_DIR_THRESHOLD' in config:
            codebase_core.LARGE_DIR_THRESHOLD = config['LARGE_DIR_THRESHOLD']
        if 'MAX_FILES_TO_SHOW_ALL' in config:
            codebase_core.MAX_FILES_TO_SHOW_ALL = config['MAX_FILES_TO_SHOW_ALL']
        if 'TREE_SHOW_FIRST_FILES' in config:
            codebase_core.TREE_SHOW_FIRST_FILES = config['TREE_SHOW_FIRST_FILES']
        if 'TREE_SHOW_LAST_FILES' in config:
            codebase_core.TREE_SHOW_LAST_FILES = config['TREE_SHOW_LAST_FILES']

        # Update ignore settings
        if 'IGNORED_DIRS' in config:
            codebase_core.IGNORED_DIRS = set(config['IGNORED_DIRS'])
            # Rebuild dependent structures
            codebase_core.IGNORED_DIRS_COMPONENTS = [
                codebase_core._normalized_parts(name) for name in codebase_core.IGNORED_DIRS]
            codebase_core.IGNORED_DIRS_BASENAMES = {
                parts[0] for parts in codebase_core.IGNORED_DIRS_COMPONENTS if len(parts) == 1}
        if 'IGNORED_FILES' in config:
            codebase_core.IGNORED_FILES = set(config['IGNORED_FILES'])
            codebase_core.IGNORED_FILES_NORMALIZED = {
                name.lower() for name in codebase_core.IGNORED_FILES}
        if 'IGNORED_DIR_PREFIXES' in config:
            codebase_core.IGNORED_DIR_PREFIXES = config['IGNORED_DIR_PREFIXES']
        if 'IGNORED_FILE_PREFIXES' in config:
            codebase_core.IGNORED_FILE_PREFIXES = config['IGNORED_FILE_PREFIXES']

        print(f"DEBUG: Configuration updated: {config}")
        return jsonify({'success': True, 'message': 'Configuration updated successfully'})
    except Exception as e:
        print(f"ERROR in update_config: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reset-config', methods=['POST'])
def reset_config():
    """Reset configuration to default values"""
    try:
        import codebase_core

        # Reset to default values
        codebase_core.MAX_FILES_PER_DIR_SCAN = 100
        codebase_core.MAX_INITIAL_SCAN_DEPTH = 2
        codebase_core.LARGE_DIR_THRESHOLD = 50
        codebase_core.MAX_FILES_TO_SHOW_ALL = 25
        codebase_core.TREE_SHOW_FIRST_FILES = 10
        codebase_core.TREE_SHOW_LAST_FILES = 3

        # Reset ignore settings
        codebase_core.IGNORED_DIRS = {
            "__pycache__", "venv", "env", "node_modules"}
        codebase_core.IGNORED_FILES = set()
        codebase_core.IGNORED_DIR_PREFIXES = ['.', '_']
        codebase_core.IGNORED_FILE_PREFIXES = ['.']

        # Rebuild dependent structures
        codebase_core.IGNORED_DIRS_COMPONENTS = [
            codebase_core._normalized_parts(name) for name in codebase_core.IGNORED_DIRS]
        codebase_core.IGNORED_DIRS_BASENAMES = {
            parts[0] for parts in codebase_core.IGNORED_DIRS_COMPONENTS if len(parts) == 1}
        codebase_core.IGNORED_FILES_NORMALIZED = {
            name.lower() for name in codebase_core.IGNORED_FILES}

        print("DEBUG: Configuration reset to defaults")
        return jsonify({'success': True, 'message': 'Configuration reset to defaults'})
    except Exception as e:
        print(f"ERROR in reset_config: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    # Open browser after a short delay
    Timer(1.5, open_browser).start()

    print("🚀 Starting Codebase to Clipboard Web Application...")
    print("✨ Using React interface (modern UI)")
    print("📍 Open your browser to: http://127.0.0.1:8080")
    print("💡 The application will open automatically in a moment.")
    print("🛑 Press Ctrl+C to stop the server")

    app.run(debug=True, host='127.0.0.1', port=8080, threaded=True)
