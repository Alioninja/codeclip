import { useApp } from '../context/AppContext';
import './StatusBar.css';

const StatusBar = () => {
    const { status, clearStatus } = useApp();

    if (!status.message) return null;

    const getIcon = () => {
        switch (status.type) {
            case 'success':
                return 'fa-check-circle';
            case 'error':
                return 'fa-exclamation-circle';
            case 'warning':
                return 'fa-exclamation-triangle';
            default:
                return 'fa-info-circle';
        }
    };

    return (
        <div className={`status-message ${status.type}`}>
            <i className={`fas ${getIcon()}`}></i>
            <span>{status.message}</span>
            <button className="status-close" onClick={clearStatus}>
                <i className="fas fa-times"></i>
            </button>
        </div>
    );
};

export default StatusBar;
