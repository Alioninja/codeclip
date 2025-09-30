import { useEffect, useRef, useState } from 'react';
import { useApp } from '../context/AppContext';
import api from '../utils/api';
import './DirectoryBrowser.css';

const DirectoryBrowser = ({ onSelectDirectory }) => {
    const { currentPath, setCurrentPath, showLoading, hideLoading, showStatus } = useApp();
    const [directories, setDirectories] = useState([]);
    const [pathInputValue, setPathInputValue] = useState('');
    const [showGoButton, setShowGoButton] = useState(false);
    const [canGoUp, setCanGoUp] = useState(false);
    const cancelledRef = useRef(false);

    useEffect(() => {
        initializeDirectory();
    }, []);

    useEffect(() => {
        setPathInputValue(currentPath);
    }, [currentPath]);

    const initializeDirectory = async () => {
        try {
            const data = await api.getCurrentDirectory();
            if (data.path) {
                browseDirectory(data.path);
            } else {
                browseDirectory('');
            }
        } catch (error) {
            console.error('Failed to get current directory:', error);
            showStatus('Failed to load directory', 'error');
        }
    };

    const browseDirectory = async (path) => {
        try {
            showLoading('Loading directory...');
            const data = await api.browseDirectory(path);

            setCurrentPath(data.current_path);
            setPathInputValue(data.current_path);
            setDirectories(data.directories);
            setCanGoUp(!!data.parent_path);
            setShowGoButton(false);
        } catch (error) {
            console.error('Browse directory error:', error);
            showStatus(`Error: ${error.message}`, 'error');
        } finally {
            hideLoading();
        }
    };

    const handleNavigateUp = () => {
        if (currentPath) {
            const pathSep = currentPath.includes('\\') ? '\\' : '/';
            const parts = currentPath.split(/[/\\]/);
            const parentPath = parts.slice(0, -1).join(pathSep) || (pathSep === '\\' ? 'C:\\' : '/');
            browseDirectory(parentPath);
        }
    };

    const handlePathInputChange = (e) => {
        const newValue = e.target.value;
        setPathInputValue(newValue);
        setShowGoButton(newValue.trim() !== currentPath);
    };

    const handlePathInputBlur = () => {
        if (pathInputValue.trim() === '') {
            setPathInputValue(currentPath);
            setShowGoButton(false);
        }
    };

    const handleNavigateToPath = async () => {
        const newPath = pathInputValue.trim();
        if (!newPath) {
            showStatus('Please enter a valid path', 'error');
            return;
        }

        try {
            await browseDirectory(newPath);
            setShowGoButton(false);
        } catch (error) {
            setPathInputValue(currentPath);
            setShowGoButton(false);
        }
    };

    const handleKeyPress = (e) => {
        if (e.key === 'Enter') {
            handleNavigateToPath();
        }
    };

    const handleDirectoryClick = (dirPath) => {
        browseDirectory(dirPath);
    };

    const handleDirectoryDoubleClick = (dirPath) => {
        setCurrentPath(dirPath);
        if (onSelectDirectory) {
            onSelectDirectory(dirPath);
        }
    };

    const handleBrowseNative = async () => {
        try {
            cancelledRef.current = false;

            showLoading('Opening native directory browser...', true, () => {
                cancelledRef.current = true;
            });

            const data = await api.browseNative();

            // Check if cancelled after API call completes
            if (cancelledRef.current) {
                showStatus('Operation cancelled', 'info');
                return;
            }

            if (data.success && data.path) {
                showStatus('Directory selected successfully!', 'success');
                await browseDirectory(data.path);
            } else if (data.error === 'No directory selected') {
                showStatus('Directory selection cancelled', 'info');
            } else {
                showStatus('Failed to open directory browser', 'warning');
            }
        } catch (error) {
            if (cancelledRef.current) {
                showStatus('Operation cancelled', 'info');
                return;
            }
            console.error('Native browser error:', error);
            showStatus(`Error: ${error.message}`, 'error');
        } finally {
            if (!cancelledRef.current) {
                hideLoading();
            }
        }
    };

    return (
        <div className="directory-browser">
            <div className="browser-toolbar">
                <button
                    className="btn btn-sm"
                    onClick={handleNavigateUp}
                    disabled={!canGoUp}
                >
                    <i className="fas fa-arrow-left"></i> Up Directory
                </button>
                <div className="current-path">
                    <input
                        type="text"
                        value={pathInputValue}
                        onChange={handlePathInputChange}
                        onBlur={handlePathInputBlur}
                        onKeyPress={handleKeyPress}
                        placeholder="Enter directory path..."
                        className={showGoButton ? 'modified' : ''}
                    />
                    {showGoButton && (
                        <button
                            className="btn btn-sm btn-success"
                            onClick={handleNavigateToPath}
                        >
                            <i className="fas fa-arrow-right"></i> Go
                        </button>
                    )}
                    <button className="btn btn-sm btn-primary" onClick={handleBrowseNative}>
                        <i className="fas fa-folder-open"></i> Browse
                    </button>
                </div>
            </div>

            <div className="directory-list">
                {directories.map((dir, index) => (
                    <div
                        key={index}
                        className="directory-item"
                        onClick={() => handleDirectoryClick(dir.path)}
                        onDoubleClick={() => handleDirectoryDoubleClick(dir.path)}
                    >
                        <i className="fas fa-folder"></i>
                        <span>{dir.name}</span>
                    </div>
                ))}
            </div>

            <div className="directory-actions">
                <div className="directory-info">
                    <span>{directories.length} directories</span>
                </div>
            </div>
        </div>
    );
};

export default DirectoryBrowser;
