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
        this.loadQuickAccess();
    }

    initializeElements() {
        // Main elements
        this.welcomeScreen = document.getElementById('welcome-screen');
        this.appMain = document.getElementById('app-main');
        this.projectInfo = document.getElementById('project-info');
        this.projectName = document.getElementById('project-name');

        // Buttons
        this.selectDirectoryBtn = document.getElementById('select-directory-btn');
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

        // Modal elements
        this.directoryModal = document.getElementById('directory-modal');
        this.modalTitle = document.getElementById('modal-title');
        this.modalClose = document.getElementById('modal-close');
        this.modalCancel = document.getElementById('modal-cancel');
        this.modalSelect = document.getElementById('modal-select');
        this.backBtn = document.getElementById('back-btn');
        this.pathInput = document.getElementById('path-input');
        this.browseBtn = document.getElementById('browse-btn');
        this.quickAccess = document.getElementById('quick-access');
        this.directoryList = document.getElementById('directory-list');
        this.fileCountInfo = document.getElementById('file-count-info');

        // Loading
        this.loadingOverlay = document.getElementById('loading-overlay');
        this.loadingText = document.getElementById('loading-text');
    }

    attachEventListeners() {
        // Directory selection
        this.selectDirectoryBtn.addEventListener('click', () => this.showDirectoryModal());
        this.changeProjectBtn.addEventListener('click', () => this.showDirectoryModal());

        // File operations
        this.processBtn.addEventListener('click', () => this.processFiles());
        this.selectAllFoldersBtn.addEventListener('click', () => this.selectAllFolders());
        this.deselectAllFoldersBtn.addEventListener('click', () => this.deselectAllFolders());
        this.selectAllTypesBtn.addEventListener('click', () => this.selectAllTypes());
        this.deselectAllTypesBtn.addEventListener('click', () => this.deselectAllTypes());
        this.copyToClipboardBtn.addEventListener('click', () => this.copyToClipboard());

        // Modal events
        this.modalClose.addEventListener('click', () => this.hideDirectoryModal());
        this.modalCancel.addEventListener('click', () => this.hideDirectoryModal());
        this.modalSelect.addEventListener('click', () => this.selectCurrentDirectory());
        this.backBtn.addEventListener('click', () => this.navigateUp());
        this.browseBtn.addEventListener('click', () => this.openFileBrowser());

        // Close modal on outside click
        this.directoryModal.addEventListener('click', (e) => {
            if (e.target === this.directoryModal) {
                this.hideDirectoryModal();
            }
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'Enter' && !this.processBtn.disabled) {
                this.processFiles();
            }
            if (e.key === 'Escape' && this.directoryModal.classList.contains('show')) {
                this.hideDirectoryModal();
            }
        });
    }

    async loadQuickAccess() {
        try {
            const response = await fetch('/api/get-home-directories');
            const directories = await response.json();

            const quickAccessGrid = document.createElement('div');
            quickAccessGrid.className = 'quick-access-grid';

            const title = document.createElement('div');
            title.className = 'quick-access-title';
            title.textContent = 'Quick Access';

            this.quickAccess.appendChild(title);
            this.quickAccess.appendChild(quickAccessGrid);

            directories.forEach(dir => {
                const item = document.createElement('div');
                item.className = 'quick-access-item';
                item.innerHTML = `
                    <i class="fas fa-folder"></i>
                    <span>${dir.name}</span>
                `;
                item.addEventListener('click', () => {
                    this.currentPath = dir.path;
                    this.browseDirectory(dir.path);
                });
                quickAccessGrid.appendChild(item);
            });
        } catch (error) {
            console.error('Failed to load quick access:', error);
        }
    }

    showDirectoryModal() {
        this.directoryModal.classList.add('show');
        if (!this.currentPath) {
            this.loadQuickAccess();
        } else {
            this.browseDirectory(this.currentPath);
        }
    }

    hideDirectoryModal() {
        this.directoryModal.classList.remove('show');
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
            this.pathInput.value = this.currentPath;
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

    openFileBrowser() {
        // For web browsers, this would typically open a file dialog
        // Since we can't access the file system directly, we'll use the browse directory functionality
        const path = prompt('Enter directory path:', this.currentPath);
        if (path) {
            this.browseDirectory(path);
        }
    }

    async selectCurrentDirectory() {
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

            this.welcomeScreen.style.display = 'none';
            this.appMain.style.display = 'grid';
            this.projectInfo.style.display = 'flex';

            this.hideDirectoryModal();
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