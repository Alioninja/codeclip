from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════
IGNORED_DIRS = {"__pycache__", "venv", "env", "node_modules", ".git", ".svn"}
IGNORED_FILES = set()
IGNORED_DIR_PREFIXES = ['.', '_']
IGNORED_FILE_PREFIXES = ['.']

# Performance limits
MAX_FILES_PER_DIR_SCAN = 100
MAX_INITIAL_SCAN_DEPTH = 3
LARGE_DIR_THRESHOLD = 50

# File tree display limits (long list summarization)
MAX_FILES_TO_SHOW_ALL = 25   # Show all files if count is <= this number
TREE_SHOW_FIRST_FILES = 10   # Number of first files to show when truncating
TREE_SHOW_LAST_FILES = 3     # Number of last files to show when truncating

# State file
STATE_FILE = Path.home() / ".codeclip_state.json"

# Output formats
OUTPUT_FORMATS = ["markdown", "xml", "plain"]

# Language Mapping
LANGUAGE_MAP = {
    '.py': 'python', '.js': 'javascript', '.ts': 'typescript', '.tsx': 'tsx',
    '.jsx': 'jsx', '.java': 'java', '.c': 'c', '.cpp': 'cpp', '.cc': 'cpp',
    '.cxx': 'cpp', '.h': 'c', '.hpp': 'cpp', '.cs': 'csharp', '.php': 'php',
    '.rb': 'ruby', '.go': 'go', '.rs': 'rust', '.swift': 'swift', '.kt': 'kotlin',
    '.scala': 'scala', '.sh': 'bash', '.bash': 'bash', '.zsh': 'zsh',
    '.fish': 'fish', '.ps1': 'powershell', '.bat': 'batch', '.cmd': 'batch',
    '.html': 'html', '.htm': 'html', '.xml': 'xml', '.css': 'css',
    '.scss': 'scss', '.sass': 'sass', '.less': 'less', '.json': 'json',
    '.yaml': 'yaml', '.yml': 'yaml', '.toml': 'toml', '.ini': 'ini',
    '.cfg': 'ini', '.conf': 'conf', '.md': 'markdown', '.markdown': 'markdown',
    '.rst': 'rst', '.txt': 'text', '.sql': 'sql', '.dockerfile': 'dockerfile',
    '.gitignore': 'gitignore', '.env': 'bash', '.r': 'r', '.m': 'matlab',
    '.pl': 'perl', '.lua': 'lua', '.vim': 'vim', '.asm': 'assembly', '.s': 'assembly',
}
