import { useApp } from '../context/AppContext';
import api from '../utils/api';
import ConfigPanel from './ConfigPanel';
import DirectoryBrowser from './DirectoryBrowser';
import './DirectorySelection.css';

const DirectorySelection = () => {
    const {
        currentPath,
        setCurrentProject,
        setShowDirectorySelection,
        setSelectedFiles,
        setSelectedExtensions,
        showLoading,
        hideLoading,
        showStatus
    } = useApp();

    const handleSelectDirectory = async () => {
        if (!currentPath) {
            showStatus('Please select a directory', 'error');
            return;
        }

        try {
            showLoading('Loading project...');
            const data = await api.selectDirectory(currentPath);

            setCurrentProject(data);

            // Auto-select all files and extensions
            const allFiles = new Set();
            const collectFiles = (tree, path = '') => {
                tree.files?.forEach(file => {
                    const filePath = path ? `${path}/${file}` : file;
                    allFiles.add(filePath);
                });
                Object.entries(tree.subfolders || {}).forEach(([folderName, subTree]) => {
                    const folderPath = path ? `${path}/${folderName}` : folderName;
                    collectFiles(subTree, folderPath);
                });
            };
            collectFiles(data.tree);
            setSelectedFiles(allFiles);
            setSelectedExtensions(new Set(Object.keys(data.extensions)));

            setShowDirectorySelection(false);
            showStatus(`Loaded project: ${data.project_name}`, 'success');
        } catch (error) {
            console.error('Select directory error:', error);
            showStatus(`Error: ${error.message}`, 'error');
        } finally {
            hideLoading();
        }
    };

    return (
        <main className="main-content">
            <div className="directory-selection">
                <div className="selection-container">
                    {/* Directory Selection Card */}
                    <div className="directory-selection-card">
                        <div className="directory-selection-header">
                            <div className="selection-icon">
                                <i className="fas fa-folder-open"></i>
                            </div>
                            <h2>Select Project Directory</h2>
                            <p>Choose the directory containing your project files</p>
                        </div>

                        <DirectoryBrowser onSelectDirectory={handleSelectDirectory} />

                        <div className="directory-footer">
                            <button
                                className="btn btn-primary btn-large"
                                onClick={handleSelectDirectory}
                            >
                                <i className="fas fa-check"></i> Select This Directory
                            </button>
                        </div>
                    </div>

                    {/* Configuration Card */}
                    <ConfigPanel />
                </div>
            </div>
        </main>
    );
};

export default DirectorySelection;
