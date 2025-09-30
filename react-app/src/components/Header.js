import { useApp } from '../context/AppContext';
import './Header.css';

const Header = () => {
    const { currentProject, setShowDirectorySelection } = useApp();

    const handleChangeProject = () => {
        setShowDirectorySelection(true);
    };

    return (
        <header className="app-header">
            <div className="header-content">
                <div className="header-left">
                    <i className="fas fa-code-branch"></i>
                    <h1>Codebase to Clipboard</h1>
                </div>
                <div className="header-right">
                    {currentProject && (
                        <div className="project-info">
                            <span className="project-label">Project:</span>
                            <span className="project-name">{currentProject.project_name}</span>
                            <button className="btn btn-secondary btn-sm" onClick={handleChangeProject}>
                                <i className="fas fa-folder-open"></i> Change Project
                            </button>
                        </div>
                    )}
                </div>
            </div>
        </header>
    );
};

export default Header;
