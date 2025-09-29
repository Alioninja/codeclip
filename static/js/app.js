// Codebase to Clipboard - Web Application JavaScript

class CodebaseApp {
    constructor() {
        this.currentProject = null;
        this.selectedFiles = new Set();
        this.selectedExtensions = new Set();
        this.directoryCache = new Map();
        this.currentPath = '';

        this.initializeElements();
        this.attachEventListeners();
        this.initializeDirectoryBrowser();
    }

    initializeElements() {
        // Main elements
        this.directorySelection = document.getElementById('directory-selection');
        this.appMain = document.getElementById('app-main');
        this.projectInfo = document.getElementById('project-info');
        this.projectName = document.getElementById('project-name');

        // Buttons
        this.changeProjectBtn = document.getElementById('change-project-btn');
        this.processBtn = document.getElementById('process-btn');
        this.selectAllFoldersBtn = document.getElementById('select-all-folders');
        this.deselectAllFoldersBtn = document.getElementById('deselect-all-folders');
        this.selectAllTypesBtn = document.getElementById('select-all-types');
        this.deselectAllTypesBtn = document.getElementById('deselect-all-types');
        this.copyToClipboardBtn = document.getElementById('copy-to-clipboard');

        // Content areas
        this.fileTree = document.getElementById('file-tree');
        this.fileTypes = document.getElementById('file-types');
        this.statusMessage = document.getElementById('status-message');
        this.previewSection = document.getElementById('preview-section');
        this.previewText = document.getElementById('preview-text');

        // Directory browser elements (now in main interface)
        this.backBtn = document.getElementById('back-btn');
        this.pathInput = document.getElementById('path-input');
        this.goBtn = document.getElementById('go-btn');
        this.browseBtn = document.getElementById('browse-btn');
        this.directoryList = document.getElementById('directory-list');
        this.fileCountInfo = document.getElementById('file-count-info');
        this.selectCurrentDirBtn = document.getElementById('select-current-dir');

        // Loading
        this.loadingOverlay = document.getElementById('loading-overlay');
        this.loadingText = document.getElementById('loading-text');
    }

    attachEventListeners() {
        // Directory selection - now main interface
        if (this.changeProjectBtn) {
            this.changeProjectBtn.addEventListener('click', () => this.showDirectorySelection());
        }
        this.backBtn.addEventListener('click', () => this.navigateUp());
        if (this.goBtn) {
            this.goBtn.addEventListener('click', () => this.navigateToPath());
        }
        this.browseBtn.addEventListener('click', () => this.openFileBrowser());
        this.selectCurrentDirBtn.addEventListener('click', () => this.selectCurrentDirectory());

        // Path input change detection
        if (this.pathInput) {
            this.pathInput.addEventListener('input', () => this.onPathInputChange());
            this.pathInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.navigateToPath();
                }
            });
            this.pathInput.addEventListener('blur', () => this.onPathInputBlur());
        }

        // File operations
        if (this.processBtn) {
            this.processBtn.addEventListener('click', () => this.processFiles());
        }
        if (this.selectAllFoldersBtn) {
            this.selectAllFoldersBtn.addEventListener('click', () => this.selectAllFolders());
        }
        if (this.deselectAllFoldersBtn) {
            this.deselectAllFoldersBtn.addEventListener('click', () => this.deselectAllFolders());
        }
        if (this.selectAllTypesBtn) {
            this.selectAllTypesBtn.addEventListener('click', () => this.selectAllTypes());
        }
        if (this.deselectAllTypesBtn) {
            this.deselectAllTypesBtn.addEventListener('click', () => this.deselectAllTypes());
        }
        if (this.copyToClipboardBtn) {
            this.copyToClipboardBtn.addEventListener('click', () => this.copyToClipboard());
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter' && this.processBtn && !this.processBtn.disabled) {
                this.processFiles();
            }
        });
    }

    async initializeDirectoryBrowser() {
        // Load current directory on startup
        try {
            const response = await fetch('/api/get-current-directory');
            const data = await response.json();
            if (data.path) {
                this.currentPath = data.path;
                this.browseDirectory(this.currentPath);
            } else {
                // Fallback to user home directory
                this.browseDirectory('');
            }
        } catch (error) {
            console.error('Failed to get current directory:', error);
            this.showStatus('Failed to load directory', 'error');
        }
    }

    showDirectorySelection() {
        this.directorySelection.style.display = 'flex';
        this.appMain.style.display = 'none';
        this.projectInfo.style.display = 'none';
        // Refresh current directory
        if (this.currentPath) {
            this.browseDirectory(this.currentPath);
        }
    }

    showLoading(text = 'Loading...') {
        this.loadingText.textContent = text;
        this.loadingOverlay.style.display = 'flex';
    }

    hideLoading() {
        this.loadingOverlay.style.display = 'none';
    }

    showStatus(message, type = 'info') {
        this.statusMessage.textContent = message;
        this.statusMessage.className = `status-message ${type}`;
    }

    async browseDirectory(path) {
        try {
            console.log('Browsing directory:', path);
            this.showLoading('Loading directory...');

            const response = await fetch('/api/browse-directory', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to browse directory');
            }

            this.currentPath = data.current_path;
            if (this.pathInput) {
                this.pathInput.value = this.currentPath;
                this.pathInput.classList.remove('modified');
            }
            if (this.goBtn) {
                this.goBtn.style.display = 'none';
            }
            this.backBtn.disabled = !data.parent_path;

            this.populateDirectoryList(data.directories);

        } catch (error) {
            console.error('Browse directory error:', error);
            this.showStatus(`Error: ${error.message}`, 'error');
        } finally {
            this.hideLoading();
        }
    }

    populateDirectoryList(directories) {
        this.directoryList.innerHTML = '';

        directories.forEach(dir => {
            const item = document.createElement('div');
            item.className = 'directory-item';
            item.innerHTML = `
                <i class="fas fa-folder"></i>
                <span>${dir.name}</span>
            `;
            item.addEventListener('click', () => {
                this.browseDirectory(dir.path);
            });
            item.addEventListener('dblclick', () => {
                this.currentPath = dir.path;
                this.selectCurrentDirectory();
            });
            this.directoryList.appendChild(item);
        });

        this.fileCountInfo.textContent = `${directories.length} directories`;
    }

    navigateUp() {
        if (this.currentPath) {
            const pathSep = this.currentPath.includes('\\') ? '\\' : '/';
            const parts = this.currentPath.split(/[/\\]/);
            const parentPath = parts.slice(0, -1).join(pathSep) || (pathSep === '\\' ? 'C:\\' : '/');
            this.browseDirectory(parentPath);
        }
    }

    onPathInputChange() {
        if (!this.pathInput || !this.goBtn) return;

        const currentValue = this.pathInput.value.trim();
        const isModified = currentValue !== this.currentPath;

        if (isModified) {
            this.pathInput.classList.add('modified');
            this.goBtn.style.display = 'inline-flex';
        } else {
            this.pathInput.classList.remove('modified');
            this.goBtn.style.display = 'none';
        }
    }

    onPathInputBlur() {
        if (!this.pathInput || !this.goBtn) return;

        // If the path wasn't changed, reset to current path
        const currentValue = this.pathInput.value.trim();
        if (currentValue === '') {
            this.pathInput.value = this.currentPath;
            this.pathInput.classList.remove('modified');
            this.goBtn.style.display = 'none';
        }
    }

    async navigateToPath() {
        if (!this.pathInput) return;

        const newPath = this.pathInput.value.trim();
        if (!newPath) {
            this.showStatus('Please enter a valid path', 'error');
            return;
        }

        try {
            await this.browseDirectory(newPath);
            if (this.pathInput && this.goBtn) {
                this.pathInput.classList.remove('modified');
                this.goBtn.style.display = 'none';
            }
        } catch (error) {
            // browseDirectory already handles error display
            // Reset input to current path on error
            if (this.pathInput && this.goBtn) {
                this.pathInput.value = this.currentPath;
                this.pathInput.classList.remove('modified');
                this.goBtn.style.display = 'none';
            }
        }
    }

    async openFileBrowser() {
        // First, try the native Python-based directory picker (best option)
        try {
            this.showStatus('Opening native directory browser...', 'info');
            console.log('Attempting to open native file browser...');

            const response = await fetch('/api/browse-native', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const data = await response.json();
            console.log('Native browser response:', data);

            if (data.success && data.path) {
                console.log('Native directory picker succeeded:', data.path);
                this.showStatus('Directory selected successfully!', 'success');
                this.currentPath = data.path;
                this.selectCurrentDirectory();
                return;
            } else if (!data.success && data.error) {
                console.log('Native directory picker failed:', data.error);
                if (data.error !== 'No directory selected') {
                    this.showStatus('Native directory picker not available, using browser fallback...', 'warning');
                }
            }
        } catch (error) {
            console.log('Native directory picker error:', error);
            this.showStatus('Native directory picker not available, using browser fallback...', 'warning');
        }

        // Fallback 1: Try modern File System Access API (Chrome 86+, Edge 86+)
        if ('showDirectoryPicker' in window) {
            try {
                console.log('Trying File System Access API...');
                this.showStatus('Opening browser directory picker...', 'info');

                const directoryHandle = await window.showDirectoryPicker({
                    mode: 'read'
                });

                // Process the directory directly using the handle
                const folderName = directoryHandle.name;
                console.log('File System Access API succeeded:', folderName);
                this.showStatus('Processing selected folder...', 'info');
                await this.processDirectoryHandle(directoryHandle);
                return;

            } catch (error) {
                if (error.name === 'AbortError') {
                    // User cancelled - that's fine
                    this.showStatus('Directory selection cancelled', 'info');
                    return;
                } else {
                    console.log('File System Access API error:', error);
                    this.showStatus('Browser directory picker failed, trying manual entry...', 'warning');
                }
            }
        }

        // Fallback 2: Manual path entry dialog
        console.log('Using manual path entry as final fallback');
        this.showStatus('Please enter the directory path manually', 'info');
        this.showManualPathDialog();
    }

    async processDirectoryHandle(directoryHandle) {
        try {
            this.showStatus('Reading directory contents...', 'info');

            // Read the directory structure using File System Access API
            const directoryData = await this.readDirectoryStructure(directoryHandle);

            if (directoryData) {
                // Send the directory structure to Python for processing
                this.showStatus('Processing directory structure...', 'info');
                await this.processDirectoryData(directoryData);
            } else {
                throw new Error('Failed to read directory structure');
            }
        } catch (error) {
            console.error('Error processing directory handle:', error);
            this.showStatus('Error processing selected folder. Falling back to path entry.', 'error');
            // Fallback to manual dialog
            this.showModernFolderDialog(directoryHandle.name, directoryHandle);
        }
    } async readDirectoryStructure(directoryHandle, maxDepth = 3, currentDepth = 0) {
        try {
            const structure = {
                name: directoryHandle.name,
                type: 'directory',
                children: []
            };

            // Don't read too deep to avoid performance issues
            if (currentDepth >= maxDepth) {
                return structure;
            }

            let fileCount = 0;
            const maxFiles = 200; // Limit files to avoid browser hanging

            for await (const [name, handle] of directoryHandle.entries()) {
                if (fileCount >= maxFiles) {
                    console.log(`Limiting directory scan to ${maxFiles} files for performance`);
                    break;
                }

                if (handle.kind === 'file') {
                    structure.children.push({
                        name: name,
                        type: 'file'
                    });
                    fileCount++;
                } else if (handle.kind === 'directory') {
                    // Recursively read subdirectories (but limit depth)
                    const subDir = await this.readDirectoryStructure(handle, maxDepth, currentDepth + 1);
                    structure.children.push(subDir);
                    fileCount++;
                }
            }

            return structure;
        } catch (error) {
            console.error('Error reading directory structure:', error);
            return null;
        }
    }

    async processDirectoryData(directoryData) {
        try {
            const response = await fetch('/api/process-directory-structure', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    directoryStructure: directoryData,
                    rootName: directoryData.name
                })
            });

            if (response.ok) {
                const result = await response.json();
                if (result.success) {
                    // Update the UI with the processed directory data
                    this.updateDirectoryView(result);
                    this.showStatus(`Successfully loaded "${directoryData.name}" project`, 'success');
                } else {
                    throw new Error(result.error || 'Failed to process directory');
                }
            } else {
                throw new Error('Server error processing directory');
            }
        } catch (error) {
            console.error('Error processing directory data:', error);
            this.showStatus('Error processing directory structure', 'error');
            throw error;
        }
    }

    updateDirectoryView(result) {
        // Update the current project data
        this.currentProject = {
            name: result.project_name,
            path: result.virtual_path || result.project_name,
            extensions: result.extensions,
            tree: result.tree
        };

        // Clear any existing content
        this.clearResults();

        // Update directory info
        if (this.directoryInfo) {
            this.directoryInfo.innerHTML = `
                <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 1rem;">
                    <i class="fas fa-folder-open" style="color: var(--primary-color);"></i>
                    <h3 style="margin: 0; color: var(--text-primary);">${result.project_name}</h3>
                </div>
                <div style="color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 1rem;">
                    Loaded from browser directory selection
                </div>
            `;
            this.directoryInfo.style.display = 'block';
        }

        // Update extensions checkboxes
        this.updateExtensionsList(result.extensions);

        // Show the file browser section
        if (this.fileBrowser) {
            this.fileBrowser.style.display = 'block';
        }

        // Enable the generate button
        if (this.generateBtn) {
            this.generateBtn.disabled = false;
            this.generateBtn.textContent = 'Generate Codebase Text';
        }
    } async createTempDirectoryInfo(directoryHandle) {
        try {
            // Use the new find-directory API to locate the folder
            const response = await fetch('/api/find-directory', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: directoryHandle.name })
            });

            if (response.ok) {
                const data = await response.json();
                if (data.success && data.found_paths && data.found_paths.length > 0) {
                    // Use the first found path
                    const foundPath = data.found_paths[0];
                    console.log(`Found directory: ${foundPath}`);
                    return foundPath;
                }
            }

            return null;
        } catch (error) {
            console.error('Error finding directory:', error);
            return null;
        }
    }

    async getCommonDirectories() {
        try {
            const response = await fetch('/api/get-common-directories');
            const data = await response.json();
            return data.success ? data.directories : [];
        } catch (error) {
            // Fallback common directories
            if (navigator.platform.includes('Win')) {
                return ['C:\\\\Users\\\\' + (navigator.userAgent.includes('Chrome') ? 'username' : 'user'), 'C:\\\\Projects', 'D:\\\\'];
            } else if (navigator.platform.includes('Mac')) {
                return ['/Users/username', '/Applications'];
            } else {
                return ['/home/username', '/opt', '/usr/local'];
            }
        }
    }

    showPathSelectionDialog(folderName, foundPaths) {
        const overlay = document.createElement('div');
        overlay.style.cssText = `
            position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(4px);
            display: flex; align-items: center; justify-content: center; z-index: 2002;
        `;

        const dialog = document.createElement('div');
        dialog.style.cssText = `
            background: var(--bg-card); border: 1px solid var(--border-color);
            border-radius: var(--radius-lg); box-shadow: var(--shadow-lg);
            width: 90%; max-width: 600px; padding: 0; overflow: hidden;
        `;

        const pathButtons = foundPaths.map((path, index) => `
            <button class="found-path-btn" data-path="${path}" style="
                display: block; width: 100%; padding: 1rem; margin-bottom: 0.5rem;
                background: var(--bg-tertiary); border: 1px solid var(--border-color);
                border-radius: var(--radius-sm); color: var(--text-primary); text-align: left;
                cursor: pointer; font-family: monospace; font-size: 0.9rem;
                transition: all 0.15s ease;
            ">
                <div style="display: flex; align-items: center; gap: 0.75rem;">
                    <i class="fas fa-folder" style="color: var(--primary-color); font-size: 1rem;"></i>
                    <div style="flex: 1;">
                        <div style="font-weight: 500; margin-bottom: 0.25rem;">${path}</div>
                        <div style="font-size: 0.8rem; color: var(--text-secondary); opacity: 0.8;">
                            ${path.split(/[\\/]/).slice(-2).join(' → ')}
                        </div>
                    </div>
                </div>
            </button>
        `).join('');

        dialog.innerHTML = `
            <div style="padding: 1.5rem; border-bottom: 1px solid var(--border-color); background: var(--bg-tertiary);">
                <h3 style="margin: 0; font-size: 1.2rem; color: var(--text-primary); display: flex; align-items: center; gap: 0.5rem;">
                    <i class="fas fa-search" style="color: var(--success-color);"></i>
                    Found "${folderName}" in ${foundPaths.length} locations
                </h3>
                <p style="margin: 0.5rem 0 0; color: var(--text-secondary); font-size: 0.9rem;">
                    Select the correct path to browse:
                </p>
            </div>
            <div style="padding: 1.5rem; max-height: 60vh; overflow-y: auto;">
                ${pathButtons}
            </div>
            <div style="padding: 1rem 1.5rem; border-top: 1px solid var(--border-color); background: var(--bg-tertiary); display: flex; justify-content: flex-end; gap: 1rem;">
                <button id="cancel-path-selection" class="btn btn-secondary">Cancel</button>
                <button id="manual-path-entry" class="btn btn-outline">Enter Path Manually</button>
            </div>
        `;

        overlay.appendChild(dialog);
        document.body.appendChild(overlay);

        const closeDialog = () => document.body.removeChild(overlay);

        // Handle path selection
        dialog.querySelectorAll('.found-path-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const path = btn.getAttribute('data-path');
                this.browseDirectory(path);
                closeDialog();
            });

            btn.addEventListener('mouseenter', () => {
                btn.style.background = 'var(--bg-hover)';
                btn.style.borderColor = 'var(--primary-color)';
                btn.style.transform = 'translateY(-2px)';
            });

            btn.addEventListener('mouseleave', () => {
                btn.style.background = 'var(--bg-tertiary)';
                btn.style.borderColor = 'var(--border-color)';
                btn.style.transform = 'translateY(0)';
            });
        });

        // Handle buttons
        dialog.querySelector('#cancel-path-selection').addEventListener('click', closeDialog);
        dialog.querySelector('#manual-path-entry').addEventListener('click', () => {
            closeDialog();
            this.showModernFolderDialog(folderName, null);
        });

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeDialog();
        });
    }

    async showModernFolderDialog(folderName, directoryHandle) {
        const overlay = document.createElement('div');
        overlay.style.cssText = `
            position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(4px);
            display: flex; align-items: center; justify-content: center; z-index: 2002;
        `;

        const dialog = document.createElement('div');
        dialog.style.cssText = `
            background: var(--bg-card); border: 1px solid var(--border-color);
            border-radius: var(--radius-lg); box-shadow: var(--shadow-lg);
            width: 90%; max-width: 700px; padding: 0; overflow: hidden;
        `;

        // Generate better path suggestions based on common locations
        const generatePathSuggestions = async () => {
            const suggestions = [];

            // Try to get common directories from backend
            try {
                const response = await fetch('/api/get-common-directories');
                const data = await response.json();

                if (data.success && data.directories) {
                    // Add folder to each common directory
                    data.directories.forEach(dir => {
                        const separator = dir.includes('/') ? '/' : '\\\\';
                        suggestions.push(dir + separator + folderName);
                    });
                }
            } catch (error) {
                console.log('Could not fetch common directories, using fallback paths');
            }

            // Fallback suggestions based on platform
            if (suggestions.length === 0) {
                if (navigator.platform.includes('Win')) {
                    // Windows suggestions
                    suggestions.push(`C:\\\\Users\\\\username\\\\${folderName}`);
                    suggestions.push(`C:\\\\Users\\\\username\\\\Documents\\\\${folderName}`);
                    suggestions.push(`C:\\\\Users\\\\username\\\\Desktop\\\\${folderName}`);
                    suggestions.push(`C:\\\\Users\\\\username\\\\Downloads\\\\${folderName}`);
                    suggestions.push(`C:\\\\Projects\\\\${folderName}`);
                    suggestions.push(`D:\\\\${folderName}`);
                } else if (navigator.platform.includes('Mac')) {
                    // macOS suggestions
                    suggestions.push(`/Users/username/${folderName}`);
                    suggestions.push(`/Users/username/Documents/${folderName}`);
                    suggestions.push(`/Users/username/Desktop/${folderName}`);
                    suggestions.push(`/Users/username/Downloads/${folderName}`);
                    suggestions.push(`/Applications/${folderName}`);
                } else {
                    // Linux suggestions
                    suggestions.push(`/home/username/${folderName}`);
                    suggestions.push(`/home/username/Documents/${folderName}`);
                    suggestions.push(`/home/username/Desktop/${folderName}`);
                    suggestions.push(`/home/username/Downloads/${folderName}`);
                    suggestions.push(`/opt/${folderName}`);
                    suggestions.push(`/usr/local/${folderName}`);
                }
            }

            return suggestions;
        };

        // Generate suggestions asynchronously
        const pathSuggestions = await generatePathSuggestions();
        const suggestionsHTML = pathSuggestions.map((path, index) => `
            <button class="path-suggestion-btn" data-path="${path}" style="
                display: block; width: 100%; padding: 0.75rem 1rem; margin-bottom: 0.5rem;
                background: var(--bg-tertiary); border: 1px solid var(--border-color);
                border-radius: var(--radius-sm); color: var(--text-primary); text-align: left;
                cursor: pointer; font-family: monospace; font-size: 0.85rem;
                transition: all 0.15s ease;
            ">
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                    <i class="fas fa-folder" style="color: var(--primary-color); font-size: 0.8rem;"></i>
                    <span style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${path}</span>
                </div>
            </button>
        `).join('');

        dialog.innerHTML = `
            <div style="padding: 1.5rem; border-bottom: 1px solid var(--border-color); background: var(--bg-tertiary);">
                <h3 style="margin: 0; font-size: 1.2rem; color: var(--text-primary); display: flex; align-items: center; gap: 0.5rem;">
                    <i class="fas fa-check-circle" style="color: var(--success-color);"></i>
                    Folder "${folderName}" Selected
                </h3>
                <p style="margin: 0.5rem 0 0; color: var(--text-secondary); font-size: 0.9rem;">
                    Click a suggested path or enter the full path manually
                </p>
            </div>
            <div style="padding: 1.5rem; max-height: 60vh; overflow-y: auto;">
                <div style="margin-bottom: 1.5rem;">
                    <h4 style="margin: 0 0 1rem 0; color: var(--text-primary); font-size: 1rem; display: flex; align-items: center; gap: 0.5rem;">
                        <i class="fas fa-lightbulb" style="color: var(--warning-color);"></i>
                        Common Path Suggestions:
                    </h4>
                    <div style="max-height: 250px; overflow-y: auto;">
                        ${suggestionsHTML}
                    </div>
                </div>
                
                <div style="margin-bottom: 1rem;">
                    <label style="display: block; color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 0.5rem; font-weight: 500;">
                        Or enter the full path manually:
                    </label>
                    <input type="text" id="modern-folder-path" 
                           placeholder="Enter full system path to ${folderName}..."
                           value="${this.currentPath || ''}"
                           style="width: 100%; padding: 0.75rem; background: var(--bg-primary); border: 1px solid var(--border-color); border-radius: var(--radius-sm); color: var(--text-primary); font-family: monospace; font-size: 0.9rem;">
                </div>
                
                <div style="display: flex; align-items: flex-start; gap: 0.5rem; color: var(--text-muted); font-size: 0.8rem; line-height: 1.4; padding: 1rem; background: var(--bg-primary); border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
                    <i class="fas fa-info-circle" style="color: var(--primary-color); margin-top: 0.1rem;"></i>
                    <div>
                        <strong>Why is this needed?</strong> For security, browsers can't reveal full file paths. 
                        Try the suggested paths above, or copy the full path from your file manager 
                        (Windows: Shift+Right-click folder → "Copy as path").
                    </div>
                </div>
            </div>
            <div style="padding: 1rem 1.5rem; border-top: 1px solid var(--border-color); background: var(--bg-tertiary); display: flex; justify-content: flex-end; gap: 1rem;">
                <button id="cancel-modern" class="btn btn-secondary">Cancel</button>
                <button id="browse-modern" class="btn btn-primary">
                    <i class="fas fa-folder-open"></i> Browse This Folder
                </button>
            </div>
        `;

        overlay.appendChild(dialog);
        document.body.appendChild(overlay);

        const pathInput = dialog.querySelector('#modern-folder-path');
        const cancelBtn = dialog.querySelector('#cancel-modern');
        const browseBtn = dialog.querySelector('#browse-modern');
        const suggestionBtns = dialog.querySelectorAll('.path-suggestion-btn');

        // Handle path suggestion clicks
        suggestionBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const path = btn.getAttribute('data-path');
                pathInput.value = path;
                pathInput.focus();
                pathInput.style.borderColor = 'var(--success-color)';
                setTimeout(() => {
                    pathInput.style.borderColor = 'var(--border-color)';
                }, 1500);
            });

            btn.addEventListener('mouseenter', () => {
                btn.style.background = 'var(--bg-hover)';
                btn.style.borderColor = 'var(--border-hover)';
            });

            btn.addEventListener('mouseleave', () => {
                btn.style.background = 'var(--bg-tertiary)';
                btn.style.borderColor = 'var(--border-color)';
            });
        });

        const closeDialog = () => document.body.removeChild(overlay);

        const browsePath = () => {
            const path = pathInput.value.trim();
            if (path) {
                this.browseDirectory(path);
                closeDialog();
            } else {
                pathInput.focus();
                pathInput.style.borderColor = 'var(--danger-color)';
                this.showStatus('Please enter a path or click a suggestion above', 'error');
                setTimeout(() => {
                    pathInput.style.borderColor = 'var(--border-color)';
                }, 2000);
            }
        };

        cancelBtn.addEventListener('click', closeDialog);
        browseBtn.addEventListener('click', browsePath);

        pathInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') browsePath();
        });

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeDialog();
        });

        // Auto-focus and pre-fill with best guess
        setTimeout(() => {
            if (!pathInput.value && pathSuggestions.length > 0) {
                // Use the first suggestion as default
                pathInput.value = pathSuggestions[0];
            }
            pathInput.focus();
            pathInput.select();
        }, 100);
    } showManualPathDialog() {
        const overlay = document.createElement('div');
        overlay.style.cssText = `
            position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(4px);
            display: flex; align-items: center; justify-content: center; z-index: 2002;
        `;

        const dialog = document.createElement('div');
        dialog.style.cssText = `
            background: var(--bg-card); border: 1px solid var(--border-color);
            border-radius: var(--radius-lg); box-shadow: var(--shadow-lg);
            width: 90%; max-width: 600px; padding: 0; overflow: hidden;
        `;

        dialog.innerHTML = `
            <div style="padding: 1.5rem; border-bottom: 1px solid var(--border-color); background: var(--bg-tertiary);">
                <h3 style="margin: 0; font-size: 1.2rem; color: var(--text-primary); display: flex; align-items: center; gap: 0.5rem;">
                    <i class="fas fa-folder-open" style="color: var(--primary-color);"></i>
                    Enter Directory Path
                </h3>
                <p style="margin: 0.5rem 0 0; color: var(--text-secondary); font-size: 0.9rem;">
                    Your browser doesn't support direct folder selection. Please enter the path manually.
                </p>
            </div>
            <div style="padding: 1.5rem;">
                <div style="margin-bottom: 1rem;">
                    <label style="display: block; color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 0.5rem; font-weight: 500;">
                        Directory Path:
                    </label>
                    <input type="text" id="manual-path-input" 
                           placeholder="Enter full directory path..."
                           value="${this.currentPath || ''}"
                           style="width: 100%; padding: 0.75rem; background: var(--bg-primary); border: 1px solid var(--border-color); border-radius: var(--radius-sm); color: var(--text-primary); font-family: monospace; font-size: 0.9rem; margin-bottom: 1rem;">
                </div>
                
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 0.5rem; margin-bottom: 1rem;">
                    <div style="padding: 0.75rem; background: var(--bg-tertiary); border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
                        <div style="font-weight: 500; color: var(--text-primary); margin-bottom: 0.25rem;">Windows:</div>
                        <div style="font-family: monospace; font-size: 0.8rem; color: var(--text-muted);">C:\\\\Users\\\\YourName\\\\Documents</div>
                    </div>
                    <div style="padding: 0.75rem; background: var(--bg-tertiary); border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
                        <div style="font-weight: 500; color: var(--text-primary); margin-bottom: 0.25rem;">Mac:</div>
                        <div style="font-family: monospace; font-size: 0.8rem; color: var(--text-muted);">/Users/username/Documents</div>
                    </div>
                    <div style="padding: 0.75rem; background: var(--bg-tertiary); border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
                        <div style="font-weight: 500; color: var(--text-primary); margin-bottom: 0.25rem;">Linux:</div>
                        <div style="font-family: monospace; font-size: 0.8rem; color: var(--text-muted);">/home/username/projects</div>
                    </div>
                </div>
                
                <div style="display: flex; align-items: flex-start; gap: 0.5rem; color: var(--text-muted); font-size: 0.8rem; line-height: 1.4;">
                    <i class="fas fa-lightbulb" style="color: var(--warning-color); margin-top: 0.1rem;"></i>
                    <div>
                        <strong>Tip:</strong> You can copy and paste the full path from your file manager. 
                        On Windows: Shift+Right-click a folder → "Copy as path"
                    </div>
                </div>
            </div>
            <div style="padding: 1rem 1.5rem; border-top: 1px solid var(--border-color); background: var(--bg-tertiary); display: flex; justify-content: flex-end; gap: 1rem;">
                <button id="cancel-manual" class="btn btn-secondary">Cancel</button>
                <button id="browse-manual" class="btn btn-primary">
                    <i class="fas fa-folder-open"></i> Browse Directory
                </button>
            </div>
        `;

        overlay.appendChild(dialog);
        document.body.appendChild(overlay);

        const pathInput = dialog.querySelector('#manual-path-input');
        const cancelBtn = dialog.querySelector('#cancel-manual');
        const browseBtn = dialog.querySelector('#browse-manual');

        const closeDialog = () => document.body.removeChild(overlay);

        const browsePath = () => {
            const path = pathInput.value.trim();
            if (path) {
                this.browseDirectory(path);
                closeDialog();
            } else {
                pathInput.focus();
                pathInput.style.borderColor = 'var(--danger-color)';
                setTimeout(() => {
                    pathInput.style.borderColor = 'var(--border-color)';
                }, 2000);
            }
        };

        cancelBtn.addEventListener('click', closeDialog);
        browseBtn.addEventListener('click', browsePath);

        pathInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') browsePath();
        });

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeDialog();
        });

        setTimeout(() => {
            pathInput.focus();
            pathInput.select();
        }, 100);
    }

    openFolderPicker() {
        // Create file input with webkitdirectory for folder selection
        const input = document.createElement('input');
        input.type = 'file';
        input.webkitdirectory = true;  // This makes it select folders instead of files
        input.multiple = true;
        input.style.display = 'none';

        input.addEventListener('change', (event) => {
            const files = event.target.files;
            if (files.length > 0) {
                // Get directory path from the selected files
                const firstFile = files[0];
                const relativePath = firstFile.webkitRelativePath;

                if (relativePath) {
                    // Extract the directory path
                    const pathParts = relativePath.split('/');
                    pathParts.pop(); // Remove the filename

                    // Ask user for the full system path
                    const dirName = pathParts.join('/');
                    this.showFolderPathDialog(dirName, firstFile);
                } else {
                    this.showStatus('Could not determine folder path. Please enter path manually.', 'warning');
                    this.pathInput.focus();
                }
            }
            document.body.removeChild(input);
        });

        document.body.appendChild(input);
        input.click();
    }

    showFolderPathDialog(selectedFolder, sampleFile) {
        const overlay = document.createElement('div');
        overlay.style.cssText = `
            position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(15, 23, 42, 0.9); backdrop-filter: blur(4px);
            display: flex; align-items: center; justify-content: center; z-index: 2002;
        `;

        const dialog = document.createElement('div');
        dialog.style.cssText = `
            background: var(--bg-card); border: 1px solid var(--border-color);
            border-radius: var(--radius-lg); box-shadow: var(--shadow-lg);
            width: 90%; max-width: 600px; padding: 0; overflow: hidden;
        `;

        dialog.innerHTML = `
            <div style="padding: 1.5rem; border-bottom: 1px solid var(--border-color); background: var(--bg-tertiary);">
                <h3 style="margin: 0; font-size: 1.2rem; color: var(--text-primary); display: flex; align-items: center; gap: 0.5rem;">
                    <i class="fas fa-folder-open" style="color: var(--primary-color);"></i>
                    Folder Selected
                </h3>
            </div>
            <div style="padding: 1.5rem;">
                <div style="margin-bottom: 1rem; padding: 1rem; background: var(--bg-primary); border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
                    <div style="color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 0.5rem;">Selected folder:</div>
                    <div style="color: var(--text-primary); font-weight: 500; font-family: monospace;">${selectedFolder}</div>
                    <div style="color: var(--text-muted); font-size: 0.8rem; margin-top: 0.5rem;">Sample file: ${sampleFile.name}</div>
                </div>
                
                <div style="margin-bottom: 1rem;">
                    <label style="display: block; color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 0.5rem; font-weight: 500;">
                        Enter the full system path to this folder:
                    </label>
                    <input type="text" id="folder-path-input" 
                           placeholder="e.g., C:\\Users\\YourName\\Projects\\${selectedFolder.split('/').pop()} or /home/user/projects/${selectedFolder.split('/').pop()}"
                           value="${this.currentPath || ''}"
                           style="width: 100%; padding: 0.75rem; background: var(--bg-primary); border: 1px solid var(--border-color); border-radius: var(--radius-sm); color: var(--text-primary); font-family: monospace; font-size: 0.9rem;">
                </div>
                
                <div style="display: flex; align-items: flex-start; gap: 0.5rem; color: var(--text-muted); font-size: 0.8rem; line-height: 1.4;">
                    <i class="fas fa-info-circle" style="color: var(--primary-color); margin-top: 0.1rem;"></i>
                    <div>
                        Due to browser security, we can't get the full path automatically. 
                        Please enter the complete path where this "${selectedFolder}" folder is located on your system.
                    </div>
                </div>
            </div>
            <div style="padding: 1rem 1.5rem; border-top: 1px solid var(--border-color); background: var(--bg-tertiary); display: flex; justify-content: flex-end; gap: 1rem;">
                <button id="cancel-folder" class="btn btn-secondary">Cancel</button>
                <button id="browse-folder" class="btn btn-primary">
                    <i class="fas fa-check"></i> Browse This Folder
                </button>
            </div>
        `;

        overlay.appendChild(dialog);
        document.body.appendChild(overlay);

        const pathInput = dialog.querySelector('#folder-path-input');
        const cancelBtn = dialog.querySelector('#cancel-folder');
        const browseBtn = dialog.querySelector('#browse-folder');

        const closeDialog = () => document.body.removeChild(overlay);

        const browsePath = () => {
            const path = pathInput.value.trim();
            if (path) {
                this.browseDirectory(path);
                closeDialog();
            } else {
                pathInput.focus();
                pathInput.style.borderColor = 'var(--danger-color)';
                setTimeout(() => {
                    pathInput.style.borderColor = 'var(--border-color)';
                }, 2000);
            }
        };

        cancelBtn.addEventListener('click', closeDialog);
        browseBtn.addEventListener('click', browsePath);

        pathInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') browsePath();
        });

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeDialog();
        });

        // Focus and try to suggest a path
        setTimeout(() => {
            pathInput.focus();
            pathInput.select();

            // Try to pre-fill with a reasonable guess
            if (!pathInput.value) {
                const folderName = selectedFolder.split('/').pop();
                if (navigator.platform.includes('Win')) {
                    pathInput.value = `C:\\Users\\${navigator.userAgent.includes('Windows') ? 'YourName' : 'User'}\\${folderName}`;
                } else {
                    pathInput.value = `/home/user/${folderName}`;
                }
            }
        }, 100);
    }

    async selectCurrentDirectory() {
        // Create a simple, clean dialog for path entry
        const currentPath = this.currentPath || '';

        // Create modal-like overlay
        const overlay = document.createElement('div');
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(15, 23, 42, 0.9);
            backdrop-filter: blur(4px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 2001;
        `;

        // Create dialog
        const dialog = document.createElement('div');
        dialog.style.cssText = `
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-lg);
            width: 90%;
            max-width: 500px;
            padding: 0;
            overflow: hidden;
        `;

        dialog.innerHTML = `
            <div style="padding: 1.5rem; border-bottom: 1px solid var(--border-color); background: var(--bg-tertiary);">
                <h3 style="margin: 0; font-size: 1.1rem; font-weight: 500; color: var(--text-primary);">Enter Directory Path</h3>
            </div>
            <div style="padding: 1.5rem;">
                <label style="display: block; color: var(--text-secondary); font-size: 0.9rem; margin-bottom: 0.5rem;">Directory Path:</label>
                <input type="text" id="path-input-dialog" value="${currentPath}" placeholder="Enter full directory path..."
                       style="width: 100%; padding: 0.75rem; background: var(--bg-primary); border: 1px solid var(--border-color); border-radius: var(--radius-sm); color: var(--text-primary); font-size: 0.9rem; margin-bottom: 1rem;">
                <div style="display: flex; align-items: flex-start; gap: 0.5rem; color: var(--text-muted); font-size: 0.8rem; line-height: 1.4;">
                    <i class="fas fa-info-circle" style="color: var(--primary-color); margin-top: 0.1rem;"></i>
                    <span>Enter the full path to the directory (e.g., C:\\\\Users\\\\YourName\\\\Documents on Windows or /home/username/Documents on Linux/Mac)</span>
                </div>
            </div>
            <div style="padding: 1rem 1.5rem; border-top: 1px solid var(--border-color); background: var(--bg-tertiary); display: flex; justify-content: flex-end; gap: 1rem;">
                <button id="cancel-path" class="btn btn-secondary">Cancel</button>
                <button id="browse-path" class="btn btn-primary">Browse Directory</button>
            </div>
        `;

        overlay.appendChild(dialog);
        document.body.appendChild(overlay);

        const input = dialog.querySelector('#path-input-dialog');
        const cancelBtn = dialog.querySelector('#cancel-path');
        const browseBtn = dialog.querySelector('#browse-path');

        const closeDialog = () => {
            document.body.removeChild(overlay);
        };

        const browse = () => {
            const path = input.value.trim();
            if (path) {
                this.browseDirectory(path);
                closeDialog();
            }
        };

        cancelBtn.addEventListener('click', closeDialog);
        browseBtn.addEventListener('click', browse);

        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                browse();
            }
        });

        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                closeDialog();
            }
        });

        // Focus and select input
        setTimeout(() => {
            input.focus();
            input.select();
        }, 100);
    } async selectCurrentDirectory() {
        if (!this.currentPath) {
            this.showStatus('Please select a directory', 'error');
            return;
        }

        try {
            console.log('Selecting directory:', this.currentPath);
            this.showLoading('Loading project...');

            const response = await fetch('/api/select-directory', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path: this.currentPath })
            });

            const data = await response.json();
            console.log('Directory selection response:', data);

            if (!response.ok) {
                throw new Error(data.error || 'Failed to select directory');
            }

            this.currentProject = data;
            this.projectName.textContent = data.project_name;

            console.log('Populating file tree with:', data.tree);
            this.populateFileTree(data.tree);

            console.log('Populating file types with:', data.extensions);
            this.populateFileTypes(data.extensions);

            // Switch to main app interface
            this.directorySelection.style.display = 'none';
            this.appMain.style.display = 'grid';
            this.projectInfo.style.display = 'flex';

            this.showStatus(`Loaded project: ${data.project_name}`, 'success');

            // Auto-select all initially
            setTimeout(() => {
                this.selectAllFolders();
                this.selectAllTypes();
            }, 100);

        } catch (error) {
            console.error('Select directory error:', error);
            this.showStatus(`Error: ${error.message}`, 'error');
        } finally {
            this.hideLoading();
        }
    }

    populateFileTree(tree, container = null, path = '') {
        if (!container) {
            container = this.fileTree;
            container.innerHTML = '';
        }

        // Add folders
        Object.entries(tree.subfolders || {}).forEach(([folderName, subTree]) => {
            const folderPath = path ? `${path}/${folderName}` : folderName;
            const hasChildren = Object.keys(subTree.subfolders || {}).length > 0 || (subTree.files || []).length > 0;
            const folderItem = this.createTreeItem(folderName, 'folder', folderPath, hasChildren);
            container.appendChild(folderItem);

            if (hasChildren) {
                const childrenContainer = document.createElement('div');
                childrenContainer.className = 'tree-children';
                childrenContainer.style.display = 'none';
                folderItem.appendChild(childrenContainer);

                this.populateFileTree(subTree, childrenContainer, folderPath);
            }
        });

        // Add files
        (tree.files || []).forEach(fileName => {
            const filePath = path ? `${path}/${fileName}` : fileName;
            const fileItem = this.createTreeItem(fileName, 'file', filePath, false);
            container.appendChild(fileItem);
        });
    } createTreeItem(name, type, path, hasChildren) {
        const item = document.createElement('div');
        item.className = 'tree-item';
        item.dataset.path = path;
        item.dataset.type = type;

        const toggle = document.createElement('div');
        toggle.className = 'tree-toggle';
        toggle.innerHTML = hasChildren ? '<i class="fas fa-chevron-right"></i>' : '';

        const icon = document.createElement('div');
        icon.className = 'tree-icon';
        icon.innerHTML = type === 'folder' ? '<i class="fas fa-folder"></i>' : '<i class="fas fa-file"></i>';

        const checkbox = document.createElement('label');
        checkbox.className = 'checkbox';
        const checkboxInput = document.createElement('input');
        checkboxInput.type = 'checkbox';
        const checkboxIcon = document.createElement('div');
        checkboxIcon.className = 'checkbox-icon';
        checkboxIcon.innerHTML = '<i class="fas fa-check" style="font-size: 10px;"></i>';
        checkbox.appendChild(checkboxInput);
        checkbox.appendChild(checkboxIcon);

        // Add event listener directly
        checkboxInput.addEventListener('change', (e) => {
            this.handleItemSelection(path, type, e.target.checked);
        });

        const label = document.createElement('div');
        label.className = 'tree-label';
        label.textContent = name;

        item.appendChild(toggle);
        item.appendChild(icon);
        item.appendChild(checkbox);
        item.appendChild(label);

        // Toggle functionality for folders
        if (hasChildren) {
            toggle.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggleTreeItem(item);
            });

            label.addEventListener('dblclick', (e) => {
                e.stopPropagation();
                this.toggleTreeItem(item);
            });
        }

        return item;
    }

    toggleTreeItem(item) {
        const toggle = item.querySelector('.tree-toggle i');
        const children = item.querySelector('.tree-children');

        if (children) {
            const isExpanded = children.style.display !== 'none';
            children.style.display = isExpanded ? 'none' : 'block';
            toggle.className = isExpanded ? 'fas fa-chevron-right' : 'fas fa-chevron-down';
        }
    }

    handleItemSelection(path, type, checked) {
        if (type === 'file') {
            if (checked) {
                this.selectedFiles.add(path);
            } else {
                this.selectedFiles.delete(path);
            }
        } else {
            // Handle folder selection - would need to implement recursive selection
            this.toggleFolderSelection(path, checked);
        }

        this.updateProcessButton();
    }

    toggleFolderSelection(folderPath, checked) {
        // Find all files in this folder and toggle them
        const treeItems = this.fileTree.querySelectorAll('.tree-item');
        treeItems.forEach(item => {
            const itemPath = item.dataset.path;
            const itemType = item.dataset.type;

            if (itemPath.startsWith(folderPath + '/') || itemPath === folderPath) {
                const checkbox = item.querySelector('input[type="checkbox"]');
                if (checkbox) {
                    checkbox.checked = checked;

                    if (itemType === 'file') {
                        if (checked) {
                            this.selectedFiles.add(itemPath);
                        } else {
                            this.selectedFiles.delete(itemPath);
                        }
                    }
                }
            }
        });
    }

    populateFileTypes(extensions) {
        this.fileTypes.innerHTML = '';

        const grid = document.createElement('div');
        grid.className = 'file-type-grid';

        Object.entries(extensions).forEach(([ext, count]) => {
            const item = document.createElement('label');
            item.className = 'file-type-item checkbox';

            const input = document.createElement('input');
            input.type = 'checkbox';
            input.checked = true;

            const icon = document.createElement('div');
            icon.className = 'checkbox-icon';
            icon.innerHTML = '<i class="fas fa-check" style="font-size: 10px;"></i>';

            const span = document.createElement('span');
            span.textContent = `${ext} files (${count})`;

            item.appendChild(input);
            item.appendChild(icon);
            item.appendChild(span);

            // Add event listener
            input.addEventListener('change', (e) => {
                this.handleExtensionSelection(ext, e.target.checked);
            });

            grid.appendChild(item);
            this.selectedExtensions.add(ext);
        });

        this.fileTypes.appendChild(grid);
    } handleExtensionSelection(extension, checked) {
        if (checked) {
            this.selectedExtensions.add(extension);
        } else {
            this.selectedExtensions.delete(extension);
        }
        this.updateProcessButton();
    }

    selectAllFolders() {
        const checkboxes = this.fileTree.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            checkbox.checked = true;
            const item = checkbox.closest('.tree-item');
            const path = item.dataset.path;
            const type = item.dataset.type;

            if (type === 'file') {
                this.selectedFiles.add(path);
            }
        });
        this.updateProcessButton();
    }

    deselectAllFolders() {
        const checkboxes = this.fileTree.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            checkbox.checked = false;
            const item = checkbox.closest('.tree-item');
            const path = item.dataset.path;
            const type = item.dataset.type;

            if (type === 'file') {
                this.selectedFiles.delete(path);
            }
        });
        this.selectedFiles.clear();
        this.updateProcessButton();
    }

    selectAllTypes() {
        const checkboxes = this.fileTypes.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            checkbox.checked = true;
        });

        this.selectedExtensions.clear();
        this.fileTypes.querySelectorAll('.file-type-item').forEach(item => {
            const text = item.textContent;
            const match = text.match(/^(\.\w+)/);
            if (match) {
                this.selectedExtensions.add(match[1]);
            }
        });
        this.updateProcessButton();
    }

    deselectAllTypes() {
        const checkboxes = this.fileTypes.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            checkbox.checked = false;
        });
        this.selectedExtensions.clear();
        this.updateProcessButton();
    }

    updateProcessButton() {
        const hasFiles = this.selectedFiles.size > 0;
        const hasTypes = this.selectedExtensions.size > 0;
        this.processBtn.disabled = !hasFiles || !hasTypes;
    }

    async processFiles() {
        if (!this.currentProject || this.selectedFiles.size === 0) {
            this.showStatus('Please select files to process', 'error');
            return;
        }

        try {
            this.showLoading('Processing files...');
            this.processBtn.disabled = true;

            const selectedFilesArray = Array.from(this.selectedFiles).map(path => {
                // Use proper path separator based on the project path
                const separator = this.currentProject.path.includes('\\') ? '\\' : '/';
                return this.currentProject.path + separator + path.replace(/[/\\]/g, separator);
            });

            const response = await fetch('/api/process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    selected_files: selectedFilesArray,
                    selected_extensions: Array.from(this.selectedExtensions)
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Processing failed');
            }

            if (data.success) {
                // Copy to clipboard
                await navigator.clipboard.writeText(data.content);

                // Show preview
                this.previewText.value = data.content;
                this.previewSection.style.display = 'flex';

                this.showStatus(
                    `Copied ${data.file_count} files (${data.size_display}) in ${data.duration.toFixed(2)}s`,
                    'success'
                );

                if (data.errors && data.errors.length > 0) {
                    console.warn('Processing errors:', data.errors);
                }
            } else {
                throw new Error(data.error || 'Processing failed');
            }

        } catch (error) {
            console.error('Process files error:', error);
            this.showStatus(`Error: ${error.message}`, 'error');
        } finally {
            this.hideLoading();
            this.processBtn.disabled = false;
        }
    }

    async copyToClipboard() {
        try {
            await navigator.clipboard.writeText(this.previewText.value);
            this.showStatus('Copied to clipboard!', 'success');
        } catch (error) {
            console.error('Copy to clipboard error:', error);
            this.showStatus('Failed to copy to clipboard', 'error');
        }
    }
}

// Initialize the app when the page loads
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new CodebaseApp();

    // Make app methods available globally for event handlers
    window.app = app;
});