import { useEffect } from 'react';
import './App.css';
import DirectorySelection from './components/DirectorySelection';
import Header from './components/Header';
import LoadingOverlay from './components/LoadingOverlay';
import MainContent from './components/MainContent';
import { AppProvider, useApp } from './context/AppContext';

const AppContent = () => {
    const { showDirectorySelection } = useApp();

    useEffect(() => {
        // Add keyboard shortcuts
        const handleKeyDown = (e) => {
            if (e.ctrlKey && e.key === 'Enter') {
                // Trigger process files
                const processBtn = document.querySelector('[data-action="process"]');
                if (processBtn && !processBtn.disabled) {
                    processBtn.click();
                }
            }
        };

        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, []);

    return (
        <div className="app-container">
            <Header />
            {showDirectorySelection ? <DirectorySelection /> : <MainContent />}
            <LoadingOverlay />
        </div>
    );
};

function App() {
    return (
        <AppProvider>
            <AppContent />
        </AppProvider>
    );
}

export default App;
