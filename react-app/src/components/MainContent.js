import { useRef } from 'react';
import { useApp } from '../context/AppContext';
import api from '../utils/api';
import FileTree from './FileTree';
import FileTypes from './FileTypes';
import './MainContent.css';
import PreviewSection from './PreviewSection';
import StatusBar from './StatusBar';

const MainContent = () => {
    const {
        currentProject,
        selectedFiles,
        selectedExtensions,
        setPreviewContent,
        showLoading,
        hideLoading,
        updateLoadingProgress,
        showStatus
    } = useApp();

    const processCancelledRef = useRef(false);
    const progressIntervalRef = useRef(null);

    const handleProcessFiles = async () => {
        if (selectedFiles.size === 0) {
            showStatus('Please select files to process', 'error');
            return;
        }

        if (selectedExtensions.size === 0) {
            showStatus('Please select file types to process', 'error');
            return;
        }

        try {
            processCancelledRef.current = false;

            // Calculate actual file count based on selected extensions
            const selectedFilesArray = Array.from(selectedFiles);
            const filteredFileCount = selectedFilesArray.filter(filePath => {
                const fileExt = '.' + filePath.split('.').pop().toLowerCase();
                return selectedExtensions.has(fileExt);
            }).length;

            showLoading(`Processing ${filteredFileCount} file${filteredFileCount !== 1 ? 's' : ''}...`, true, () => {
                processCancelledRef.current = true;
                // Clear progress interval if cancelled
                if (progressIntervalRef.current) {
                    clearInterval(progressIntervalRef.current);
                    progressIntervalRef.current = null;
                }
            }, 0);

            // Start polling for progress
            progressIntervalRef.current = setInterval(async () => {
                try {
                    const progressData = await api.getProgress();
                    if (progressData.progress !== undefined) {
                        updateLoadingProgress(progressData.progress);
                    }
                } catch (error) {
                    console.error('Error fetching progress:', error);
                }
            }, 300); // Poll every 300ms

            // Convert Set to Array and build full paths
            const separator = currentProject.path.includes('\\') ? '\\' : '/';
            const fullPathFiles = selectedFilesArray.map(path => {
                return currentProject.path + separator + path.replace(/[/\\]/g, separator);
            });

            const data = await api.processFiles(
                fullPathFiles,
                Array.from(selectedExtensions)
            );

            // Stop progress polling
            if (progressIntervalRef.current) {
                clearInterval(progressIntervalRef.current);
                progressIntervalRef.current = null;
            }

            // Check if cancelled after API call completes
            if (processCancelledRef.current) {
                showStatus('Processing cancelled', 'info');
                return;
            }

            if (data.success) {
                // Copy to clipboard
                await navigator.clipboard.writeText(data.content);

                // Show preview
                setPreviewContent(data.content);

                showStatus(
                    `Copied ${data.file_count} files (${data.size_display}) in ${data.duration.toFixed(2)}s`,
                    'success'
                );

                if (data.errors && data.errors.length > 0) {
                    console.warn('Processing errors:', data.errors);
                }
            } else {
                throw new Error(data.error || 'Processing failed');
            }
        } catch (error) {
            // Clear progress interval on error
            if (progressIntervalRef.current) {
                clearInterval(progressIntervalRef.current);
                progressIntervalRef.current = null;
            }

            if (processCancelledRef.current) {
                showStatus('Processing cancelled', 'info');
                return;
            }
            console.error('Process files error:', error);
            showStatus(`Error: ${error.message}`, 'error');
        } finally {
            // Clear progress interval in finally block
            if (progressIntervalRef.current) {
                clearInterval(progressIntervalRef.current);
                progressIntervalRef.current = null;
            }

            if (!processCancelledRef.current) {
                hideLoading();
            }
        }
    };

    const isProcessDisabled = selectedFiles.size === 0 || selectedExtensions.size === 0;

    return (
        <main className="main-content">
            <div className="app-main">
                <div className="content-left">
                    <StatusBar />
                    <FileTree />
                </div>

                <div className="content-center">
                    <FileTypes />
                    <div className="process-section">
                        <button
                            className="btn btn-primary btn-large process-btn"
                            onClick={handleProcessFiles}
                            disabled={isProcessDisabled}
                            data-action="process"
                        >
                            <i className="fas fa-cog"></i>
                            Process Files & Copy to Clipboard
                        </button>
                        <p className="process-hint">
                            <i className="fas fa-info-circle"></i>
                            Select files and types above, then click to process
                            <span className="keyboard-shortcut">Ctrl + Enter</span>
                        </p>
                    </div>
                </div>

                <div className="content-right">
                    <PreviewSection />
                </div>
            </div>
        </main>
    );
};

export default MainContent;
