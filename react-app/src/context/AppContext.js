import { createContext, useCallback, useContext, useState } from 'react';

const AppContext = createContext();

export const useApp = () => {
    const context = useContext(AppContext);
    if (!context) {
        throw new Error('useApp must be used within an AppProvider');
    }
    return context;
};

export const AppProvider = ({ children }) => {
    // Project state
    const [currentProject, setCurrentProject] = useState(null);
    const [currentPath, setCurrentPath] = useState('');

    // Selection state
    const [selectedFiles, setSelectedFiles] = useState(new Set());
    const [selectedExtensions, setSelectedExtensions] = useState(new Set());

    // UI state
    const [loading, setLoading] = useState(false);
    const [loadingText, setLoadingText] = useState('Loading...');
    const [loadingCancelable, setLoadingCancelable] = useState(false);
    const [loadingOnCancel, setLoadingOnCancel] = useState(null);
    const [loadingProgress, setLoadingProgress] = useState(-1);
    const [status, setStatus] = useState({ message: '', type: 'info' });
    const [showDirectorySelection, setShowDirectorySelection] = useState(true);
    const [previewContent, setPreviewContent] = useState('');

    // Configuration state
    const [config, setConfig] = useState({
        MAX_FILES_PER_DIR_SCAN: 100,
        MAX_INITIAL_SCAN_DEPTH: 3,
        LARGE_DIR_THRESHOLD: 50,
        MAX_FILES_TO_SHOW_ALL: 100,
        TREE_SHOW_FIRST_FILES: 5,
        TREE_SHOW_LAST_FILES: 5,
        IGNORED_DIRS: [],
        IGNORED_FILES: [],
        IGNORED_DIR_PREFIXES: [],
        IGNORED_FILE_PREFIXES: []
    });

    // Loading handlers
    const showLoading = useCallback((text = 'Loading...', cancelable = false, onCancel = null, progress = -1) => {
        setLoadingText(text);
        setLoadingCancelable(cancelable);
        setLoadingOnCancel(() => onCancel);
        setLoadingProgress(progress);
        setLoading(true);
    }, []);

    const hideLoading = useCallback(() => {
        setLoading(false);
        setLoadingCancelable(false);
        setLoadingOnCancel(null);
        setLoadingProgress(-1);
    }, []);

    const updateLoadingProgress = useCallback((progress) => {
        setLoadingProgress(progress);
    }, []);

    // Status handlers
    const showStatus = useCallback((message, type = 'info') => {
        setStatus({ message, type });
    }, []);

    const clearStatus = useCallback(() => {
        setStatus({ message: '', type: 'info' });
    }, []);

    // File selection handlers
    const toggleFile = useCallback((filePath) => {
        setSelectedFiles(prev => {
            const newSet = new Set(prev);
            if (newSet.has(filePath)) {
                newSet.delete(filePath);
            } else {
                newSet.add(filePath);
            }
            return newSet;
        });
    }, []);

    const toggleExtension = useCallback((extension) => {
        setSelectedExtensions(prev => {
            const newSet = new Set(prev);
            if (newSet.has(extension)) {
                newSet.delete(extension);
            } else {
                newSet.add(extension);
            }
            return newSet;
        });
    }, []);

    const selectAllFiles = useCallback(() => {
        if (currentProject?.tree) {
            const allFiles = new Set();
            const collectFiles = (tree, path = '') => {
                // Add files
                tree.files?.forEach(file => {
                    const filePath = path ? `${path}/${file}` : file;
                    allFiles.add(filePath);
                });
                // Recursively collect from subfolders
                Object.entries(tree.subfolders || {}).forEach(([folderName, subTree]) => {
                    const folderPath = path ? `${path}/${folderName}` : folderName;
                    collectFiles(subTree, folderPath);
                });
            };
            collectFiles(currentProject.tree);
            setSelectedFiles(allFiles);
        }
    }, [currentProject]);

    const deselectAllFiles = useCallback(() => {
        setSelectedFiles(new Set());
    }, []);

    const selectAllExtensions = useCallback(() => {
        if (currentProject?.extensions) {
            setSelectedExtensions(new Set(Object.keys(currentProject.extensions)));
        }
    }, [currentProject]);

    const deselectAllExtensions = useCallback(() => {
        setSelectedExtensions(new Set());
    }, []);

    // Check folder selection state (returns 'checked', 'indeterminate', or 'unchecked')
    const getFolderSelectionState = useCallback((folderPath) => {
        if (!currentProject?.tree) return 'unchecked';

        const collectFilesInFolder = (tree, path = '', targetPath = '') => {
            const files = [];

            if (path === targetPath || path.startsWith(targetPath + '/')) {
                // Add all files in this level
                tree.files?.forEach(file => {
                    const filePath = path ? `${path}/${file}` : file;
                    files.push(filePath);
                });
            }

            // Recursively check subfolders
            Object.entries(tree.subfolders || {}).forEach(([folderName, subTree]) => {
                const newPath = path ? `${path}/${folderName}` : folderName;
                files.push(...collectFilesInFolder(subTree, newPath, targetPath));
            });

            return files;
        };

        const files = collectFilesInFolder(currentProject.tree, '', folderPath);
        if (files.length === 0) return 'unchecked';

        const selectedCount = files.filter(file => selectedFiles.has(file)).length;

        if (selectedCount === 0) return 'unchecked';
        if (selectedCount === files.length) return 'checked';
        return 'indeterminate';
    }, [currentProject, selectedFiles]);

    // Toggle folder and all its contents
    const toggleFolder = useCallback((folderPath, checked) => {
        if (!currentProject?.tree) return;

        const collectFilesInFolder = (tree, path = '', targetPath = '') => {
            const files = [];

            if (path === targetPath || path.startsWith(targetPath + '/')) {
                // Add all files in this level
                tree.files?.forEach(file => {
                    const filePath = path ? `${path}/${file}` : file;
                    files.push(filePath);
                });
            }

            // Recursively check subfolders
            Object.entries(tree.subfolders || {}).forEach(([folderName, subTree]) => {
                const newPath = path ? `${path}/${folderName}` : folderName;
                files.push(...collectFilesInFolder(subTree, newPath, targetPath));
            });

            return files;
        };

        const files = collectFilesInFolder(currentProject.tree, '', folderPath);

        setSelectedFiles(prev => {
            const newSet = new Set(prev);
            files.forEach(file => {
                if (checked) {
                    newSet.add(file);
                } else {
                    newSet.delete(file);
                }
            });
            return newSet;
        });
    }, [currentProject]);

    const value = {
        // State
        currentProject,
        currentPath,
        selectedFiles,
        selectedExtensions,
        loading,
        loadingText,
        loadingCancelable,
        loadingOnCancel,
        loadingProgress,
        status,
        showDirectorySelection,
        previewContent,
        config,

        // Setters
        setCurrentProject,
        setCurrentPath,
        setSelectedFiles,
        setSelectedExtensions,
        setShowDirectorySelection,
        setPreviewContent,
        setConfig,

        // Actions
        showLoading,
        hideLoading,
        updateLoadingProgress,
        showStatus,
        clearStatus,
        toggleFile,
        toggleExtension,
        selectAllFiles,
        deselectAllFiles,
        selectAllExtensions,
        deselectAllExtensions,
        toggleFolder,
        getFolderSelectionState
    };

    return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
};
