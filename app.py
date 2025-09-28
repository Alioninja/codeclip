#!/usr/bin/env python3
"""
Codebase to Clipboard - Web Application
A Flask-based web application for converting codebases to clipboard text.
"""

import os
import json
import time
import threading
from pathlib import Path
from collections import Counter
from flask import Flask, render_template, request, jsonify
import webbrowser
from threading import Timer

# Import the core functionality from the original script
from codebase_core import (
    scan_file_extensions, build_folder_tree, get_tree_filtered_string,
    process_selected_files, is_ignored_dir, is_ignored_file, path_contains_ignored_dir,
    IGNORED_DIRS, IGNORED_FILES, IGNORED_DIR_PREFIXES, IGNORED_FILE_PREFIXES,
    MAX_FILES_PER_DIR_SCAN, MAX_INITIAL_SCAN_DEPTH, LARGE_DIR_THRESHOLD
)

app = Flask(__name__)
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
    """Main page"""
    return render_template('index.html')


@app.route('/favicon.ico')
def favicon():
    """Serve favicon"""
    return app.send_static_file('favicon.ico')


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

        if not current_project['path']:
            return jsonify({'error': 'No project directory selected'}), 400

        if not selected_files:
            return jsonify({'error': 'No files selected'}), 400

        # Filter files by selected extensions
        filtered_files = []
        for file_path in selected_files:
            file_ext = Path(file_path).suffix.lower()
            if not selected_extensions or file_ext in selected_extensions:
                filtered_files.append(file_path)

        print(f"DEBUG: Filtered to {len(filtered_files)} files")

        if not filtered_files:
            return jsonify({'error': 'No files match selected file types'}), 400

        # Process files
        result = process_selected_files(
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


def serialize_tree(tree, path_prefix=""):
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
    webbrowser.open('http://127.0.0.1:5000')


if __name__ == '__main__':
    # Open browser after a short delay
    Timer(1.5, open_browser).start()

    print("🚀 Starting Codebase to Clipboard Web Application...")
    print("📍 Open your browser to: http://127.0.0.1:5000")
    print("💡 The application will open automatically in a moment.")
    print("🛑 Press Ctrl+C to stop the server")

    app.run(debug=True, host='127.0.0.1', port=5000, threaded=True)
