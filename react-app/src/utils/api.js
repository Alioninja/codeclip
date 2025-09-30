// API utility functions for making requests to the Flask backend

const API_BASE = process.env.REACT_APP_API_URL || '';

class ApiError extends Error {
    constructor(message, status) {
        super(message);
        this.status = status;
        this.name = 'ApiError';
    }
}

const handleResponse = async (response) => {
    const data = await response.json();

    if (!response.ok) {
        throw new ApiError(data.error || 'Request failed', response.status);
    }

    return data;
};

export const api = {
    // Directory browsing
    async getCurrentDirectory() {
        const response = await fetch(`${API_BASE}/api/get-current-directory`);
        return handleResponse(response);
    },

    async browseDirectory(path) {
        const response = await fetch(`${API_BASE}/api/browse-directory`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        });
        return handleResponse(response);
    },

    async selectDirectory(path) {
        const response = await fetch(`${API_BASE}/api/select-directory`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        });
        return handleResponse(response);
    },

    async browseNative() {
        const response = await fetch(`${API_BASE}/api/browse-native`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        return handleResponse(response);
    },

    async getCommonDirectories() {
        const response = await fetch(`${API_BASE}/api/get-common-directories`);
        return handleResponse(response);
    },

    async findDirectory(name) {
        const response = await fetch(`${API_BASE}/api/find-directory`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        return handleResponse(response);
    },

    // File processing
    async processFiles(selectedFiles, selectedExtensions) {
        const response = await fetch(`${API_BASE}/api/process`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                selected_files: selectedFiles,
                selected_extensions: selectedExtensions
            })
        });
        return handleResponse(response);
    },

    async getProgress() {
        const response = await fetch(`${API_BASE}/api/progress`);
        return handleResponse(response);
    },

    async processDirectoryStructure(directoryStructure, rootName) {
        const response = await fetch(`${API_BASE}/api/process-directory-structure`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                directoryStructure,
                rootName
            })
        });
        return handleResponse(response);
    },

    // Configuration
    async getConfig() {
        const response = await fetch(`${API_BASE}/api/get-config`);
        return handleResponse(response);
    },

    async updateConfig(config) {
        const response = await fetch(`${API_BASE}/api/update-config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ config })
        });
        return handleResponse(response);
    },

    async resetConfig() {
        const response = await fetch(`${API_BASE}/api/reset-config`, {
            method: 'POST'
        });
        return handleResponse(response);
    }
};

export default api;
