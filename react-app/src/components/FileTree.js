import { useEffect, useRef, useState } from 'react';
import { useApp } from '../context/AppContext';
import './FileTree.css';

const TreeItem = ({ name, type, path, hasChildren, children, level = 0 }) => {
    const { selectedFiles, toggleFile, toggleFolder, getFolderSelectionState } = useApp();
    const [isExpanded, setIsExpanded] = useState(false);
    const checkboxRef = useRef(null);

    const isFileChecked = type === 'file' ? selectedFiles.has(path) : false;
    const folderState = type === 'folder' ? getFolderSelectionState(path) : 'unchecked';
    const isFolderChecked = folderState === 'checked';
    const isFolderIndeterminate = folderState === 'indeterminate';

    // Set indeterminate property on checkbox element
    useEffect(() => {
        if (checkboxRef.current && type === 'folder') {
            checkboxRef.current.indeterminate = isFolderIndeterminate;
        }
    }, [isFolderIndeterminate, type]);

    const handleToggle = (e) => {
        e.stopPropagation();
        setIsExpanded(!isExpanded);
    };

    const handleCheckboxChange = (e) => {
        e.stopPropagation();
        if (type === 'file') {
            toggleFile(path);
        } else {
            // For folders: if checked or indeterminate, uncheck all; if unchecked, check all
            const shouldCheck = folderState === 'unchecked';
            toggleFolder(path, shouldCheck);
        }
    };

    const handleLabelDoubleClick = (e) => {
        e.stopPropagation();
        if (hasChildren) {
            setIsExpanded(!isExpanded);
        }
    };

    const isChecked = type === 'file' ? isFileChecked : isFolderChecked;

    return (
        <div className="tree-item" style={{ '--level': level }}>
            <div className="tree-item-header">
                <div className="tree-toggle" onClick={handleToggle}>
                    {hasChildren && (
                        <i className={`fas fa-chevron-${isExpanded ? 'down' : 'right'}`}></i>
                    )}
                </div>
                <div className="tree-icon">
                    <i className={`fas fa-${type === 'folder' ? 'folder' : 'file'}`}></i>
                </div>
                <label className="checkbox">
                    <input
                        ref={checkboxRef}
                        type="checkbox"
                        checked={isChecked}
                        onChange={handleCheckboxChange}
                    />
                    <div className={`checkbox-icon ${isFolderIndeterminate ? 'indeterminate' : ''}`}>
                        {isFolderIndeterminate ? (
                            <i className="fas fa-minus" style={{ fontSize: '10px' }}></i>
                        ) : (
                            <i className="fas fa-check" style={{ fontSize: '10px' }}></i>
                        )}
                    </div>
                </label>
                <div className="tree-label" onDoubleClick={handleLabelDoubleClick}>
                    {name}
                </div>
            </div>
            {hasChildren && isExpanded && (
                <div className="tree-children">
                    {children}
                </div>
            )}
        </div>
    );
};

const FileTree = () => {
    const { currentProject, selectAllFiles, deselectAllFiles } = useApp();

    const renderTree = (tree, path = '', level = 0) => {
        const items = [];

        // Render folders
        Object.entries(tree.subfolders || {}).forEach(([folderName, subTree]) => {
            const folderPath = path ? `${path}/${folderName}` : folderName;
            const hasChildren =
                Object.keys(subTree.subfolders || {}).length > 0 ||
                (subTree.files || []).length > 0;

            const children = hasChildren ? renderTree(subTree, folderPath, level + 1) : null;

            items.push(
                <TreeItem
                    key={folderPath}
                    name={folderName}
                    type="folder"
                    path={folderPath}
                    hasChildren={hasChildren}
                    level={level}
                >
                    {children}
                </TreeItem>
            );
        });

        // Render files
        (tree.files || []).forEach((fileName) => {
            const filePath = path ? `${path}/${fileName}` : fileName;
            items.push(
                <TreeItem
                    key={filePath}
                    name={fileName}
                    type="file"
                    path={filePath}
                    hasChildren={false}
                    level={level}
                />
            );
        });

        return items;
    };

    if (!currentProject?.tree) {
        return (
            <div className="file-tree-container">
                <div className="file-tree-header">
                    <h3><i className="fas fa-folder-tree"></i> File Structure</h3>
                </div>
                <div className="file-tree-empty">
                    <i className="fas fa-folder-open"></i>
                    <p>No project loaded</p>
                </div>
            </div>
        );
    }

    return (
        <div className="file-tree-container">
            <div className="file-tree-header">
                <h3><i className="fas fa-folder-tree"></i> File Structure</h3>
                <div className="file-tree-actions">
                    <button className="btn btn-sm btn-outline" onClick={selectAllFiles}>
                        <i className="fas fa-check-square"></i> Select All
                    </button>
                    <button className="btn btn-sm btn-outline" onClick={deselectAllFiles}>
                        <i className="fas fa-square"></i> Deselect All
                    </button>
                </div>
            </div>
            <div className="file-tree">
                {renderTree(currentProject.tree)}
            </div>
        </div>
    );
};

export default FileTree;
