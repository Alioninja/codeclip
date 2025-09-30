import { useApp } from '../context/AppContext';
import './FileTypes.css';

const FileTypes = () => {
    const {
        currentProject,
        selectedExtensions,
        toggleExtension,
        selectAllExtensions,
        deselectAllExtensions
    } = useApp();

    if (!currentProject?.extensions) {
        return (
            <div className="file-types-container">
                <div className="file-types-header">
                    <h3><i className="fas fa-file-code"></i> File Types</h3>
                </div>
                <div className="file-types-empty">
                    <i className="fas fa-file"></i>
                    <p>No file types available</p>
                </div>
            </div>
        );
    }

    const extensions = Object.entries(currentProject.extensions);

    return (
        <div className="file-types-container">
            <div className="file-types-header">
                <h3><i className="fas fa-file-code"></i> File Types</h3>
                <div className="file-types-actions">
                    <button className="btn btn-sm btn-outline" onClick={selectAllExtensions}>
                        <i className="fas fa-check-square"></i> Select All
                    </button>
                    <button className="btn btn-sm btn-outline" onClick={deselectAllExtensions}>
                        <i className="fas fa-square"></i> Deselect All
                    </button>
                </div>
            </div>
            <div className="file-types-grid">
                {extensions.map(([ext, count]) => (
                    <label key={ext} className="file-type-item checkbox">
                        <input
                            type="checkbox"
                            checked={selectedExtensions.has(ext)}
                            onChange={() => toggleExtension(ext)}
                        />
                        <div className="checkbox-icon">
                            <i className="fas fa-check" style={{ fontSize: '10px' }}></i>
                        </div>
                        <span>{ext} files ({count})</span>
                    </label>
                ))}
            </div>
        </div>
    );
};

export default FileTypes;
