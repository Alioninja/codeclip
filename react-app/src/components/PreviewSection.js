import { useApp } from '../context/AppContext';
import './PreviewSection.css';

const PreviewSection = () => {
    const { previewContent, showStatus } = useApp();

    const handleCopyToClipboard = async () => {
        try {
            await navigator.clipboard.writeText(previewContent);
            showStatus('Copied to clipboard!', 'success');
        } catch (error) {
            console.error('Copy to clipboard error:', error);
            showStatus('Failed to copy to clipboard', 'error');
        }
    };

    if (!previewContent) return null;

    return (
        <div className="preview-section">
            <div className="preview-header">
                <h3><i className="fas fa-eye"></i> Preview</h3>
                <button className="btn btn-primary btn-sm" onClick={handleCopyToClipboard}>
                    <i className="fas fa-copy"></i> Copy to Clipboard
                </button>
            </div>
            <div className="preview-content">
                <textarea
                    readOnly
                    value={previewContent}
                    className="preview-text"
                />
            </div>
        </div>
    );
};

export default PreviewSection;
