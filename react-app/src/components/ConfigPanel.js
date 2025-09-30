import { useEffect } from 'react';
import { useApp } from '../context/AppContext';
import api from '../utils/api';
import './ConfigPanel.css';

const ConfigPanel = () => {
    const { config, setConfig, showLoading, hideLoading, showStatus } = useApp();

    useEffect(() => {
        loadConfig();
    }, []);

    const loadConfig = async () => {
        try {
            const data = await api.getConfig();
            if (data.success) {
                setConfig(data.config);
            }
        } catch (error) {
            console.error('Failed to load config:', error);
        }
    };

    const handleInputChange = (field, value) => {
        setConfig(prev => ({
            ...prev,
            [field]: value
        }));
    };

    const handleArrayInputChange = (field, value) => {
        const array = value.split(',').map(s => s.trim()).filter(s => s.length > 0);
        setConfig(prev => ({
            ...prev,
            [field]: array
        }));
    };

    const handleSaveConfig = async () => {
        try {
            showLoading('Saving configuration...');
            const data = await api.updateConfig(config);

            if (data.success) {
                showStatus('Configuration saved successfully!', 'success');
            } else {
                throw new Error(data.error || 'Failed to save configuration');
            }
        } catch (error) {
            console.error('Save config error:', error);
            showStatus(`Error: ${error.message}`, 'error');
        } finally {
            hideLoading();
        }
    };

    const handleResetConfig = async () => {
        try {
            showLoading('Resetting configuration...');
            const data = await api.resetConfig();

            if (data.success) {
                await loadConfig();
                showStatus('Configuration reset to defaults!', 'success');
            } else {
                throw new Error(data.error || 'Failed to reset configuration');
            }
        } catch (error) {
            console.error('Reset config error:', error);
            showStatus(`Error: ${error.message}`, 'error');
        } finally {
            hideLoading();
        }
    };

    return (
        <div className="configuration-card">
            <div className="directory-selection-header">
                <div className="selection-icon">
                    <i className="fas fa-cog"></i>
                </div>
                <h2>Processing Configuration</h2>
                <p>Customize how files are scanned and processed</p>
            </div>

            <div className="config-content-wrapper">
                <div className="config-section">
                    <h3><i className="fas fa-sliders-h"></i> Scanning Limits</h3>
                    <div className="config-grid">
                        <div className="config-item">
                            <label>Max Files per Directory Scan</label>
                            <input
                                type="number"
                                min="10"
                                max="1000"
                                value={config.MAX_FILES_PER_DIR_SCAN}
                                onChange={(e) => handleInputChange('MAX_FILES_PER_DIR_SCAN', parseInt(e.target.value))}
                            />
                            <small>Maximum files to scan per directory (default: 100)</small>
                        </div>

                        <div className="config-item">
                            <label>Max Initial Scan Depth</label>
                            <input
                                type="number"
                                min="1"
                                max="10"
                                value={config.MAX_INITIAL_SCAN_DEPTH}
                                onChange={(e) => handleInputChange('MAX_INITIAL_SCAN_DEPTH', parseInt(e.target.value))}
                            />
                            <small>Directory depth for initial scan (default: 3)</small>
                        </div>

                        <div className="config-item">
                            <label>Large Directory Threshold</label>
                            <input
                                type="number"
                                min="10"
                                max="500"
                                value={config.LARGE_DIR_THRESHOLD}
                                onChange={(e) => handleInputChange('LARGE_DIR_THRESHOLD', parseInt(e.target.value))}
                            />
                            <small>Files count to consider a directory "large" (default: 50)</small>
                        </div>

                        <div className="config-item">
                            <label>Max Files to Show All</label>
                            <input
                                type="number"
                                min="10"
                                max="500"
                                value={config.MAX_FILES_TO_SHOW_ALL}
                                onChange={(e) => handleInputChange('MAX_FILES_TO_SHOW_ALL', parseInt(e.target.value))}
                            />
                            <small>Maximum files to list individually (default: 100)</small>
                        </div>

                        <div className="config-item">
                            <label>Tree Show First Files</label>
                            <input
                                type="number"
                                min="1"
                                max="20"
                                value={config.TREE_SHOW_FIRST_FILES}
                                onChange={(e) => handleInputChange('TREE_SHOW_FIRST_FILES', parseInt(e.target.value))}
                            />
                            <small>Files to show at start of large directories (default: 5)</small>
                        </div>

                        <div className="config-item">
                            <label>Tree Show Last Files</label>
                            <input
                                type="number"
                                min="1"
                                max="20"
                                value={config.TREE_SHOW_LAST_FILES}
                                onChange={(e) => handleInputChange('TREE_SHOW_LAST_FILES', parseInt(e.target.value))}
                            />
                            <small>Files to show at end of large directories (default: 5)</small>
                        </div>
                    </div>
                </div>

                <div className="config-section">
                    <h3><i className="fas fa-filter"></i> Ignore Patterns</h3>
                    <div className="config-grid">
                        <div className="config-item">
                            <label>Ignored Directories</label>
                            <input
                                type="text"
                                value={config.IGNORED_DIRS?.join(', ') || ''}
                                onChange={(e) => handleArrayInputChange('IGNORED_DIRS', e.target.value)}
                                placeholder="e.g., node_modules, .git, dist"
                            />
                            <small>Comma-separated list of directory names to ignore</small>
                        </div>

                        <div className="config-item">
                            <label>Ignored Files</label>
                            <input
                                type="text"
                                value={config.IGNORED_FILES?.join(', ') || ''}
                                onChange={(e) => handleArrayInputChange('IGNORED_FILES', e.target.value)}
                                placeholder="e.g., .DS_Store, thumbs.db"
                            />
                            <small>Comma-separated list of file names to ignore</small>
                        </div>

                        <div className="config-item">
                            <label>Ignored Directory Prefixes</label>
                            <input
                                type="text"
                                value={config.IGNORED_DIR_PREFIXES?.join(', ') || ''}
                                onChange={(e) => handleArrayInputChange('IGNORED_DIR_PREFIXES', e.target.value)}
                                placeholder="e.g., ., __"
                            />
                            <small>Ignore directories starting with these prefixes</small>
                        </div>

                        <div className="config-item">
                            <label>Ignored File Prefixes</label>
                            <input
                                type="text"
                                value={config.IGNORED_FILE_PREFIXES?.join(', ') || ''}
                                onChange={(e) => handleArrayInputChange('IGNORED_FILE_PREFIXES', e.target.value)}
                                placeholder="e.g., ., ~"
                            />
                            <small>Ignore files starting with these prefixes</small>
                        </div>
                    </div>
                </div>

                <div className="config-actions">
                    <button className="btn btn-secondary" onClick={handleResetConfig}>
                        <i className="fas fa-undo"></i> Reset to Defaults
                    </button>
                    <button className="btn btn-primary" onClick={handleSaveConfig}>
                        <i className="fas fa-save"></i> Save Configuration
                    </button>
                </div>
            </div>
        </div>
    );
};

export default ConfigPanel;
