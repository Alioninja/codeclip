import { useApp } from '../context/AppContext';
import './LoadingOverlay.css';

const LoadingOverlay = () => {
    const { loading, loadingText, loadingCancelable, loadingOnCancel, hideLoading, loadingProgress } = useApp();

    if (!loading) return null;

    const handleCancel = () => {
        if (loadingOnCancel) {
            loadingOnCancel();
        }
        hideLoading();
    };

    return (
        <div className="loading-overlay">
            <div className="loading-content">
                <div className="loading-spinner">
                    <i className="fas fa-circle-notch fa-spin"></i>
                </div>
                <div className="loading-text">{loadingText}</div>
                {loadingProgress !== undefined && loadingProgress >= 0 && (
                    <div className="loading-progress-container">
                        <div className="loading-progress-bar" style={{ width: `${loadingProgress}%` }}></div>
                    </div>
                )}
                {loadingCancelable && (
                    <button className="cancel-btn" onClick={handleCancel}>
                        <i className="fas fa-times"></i>
                        <span>Cancel</span>
                    </button>
                )}
            </div>
        </div>
    );
};

export default LoadingOverlay;
