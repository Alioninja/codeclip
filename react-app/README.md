# CodeClip React Application

A modern React-based code aggregation tool that allows you to browse directories, select files, and copy their contents to the clipboard in a formatted structure. This is a refactored version of the original vanilla JavaScript application using React best practices.

## Features

- 🗂️ **Directory Browsing**: Navigate through your file system with an intuitive interface
- 🌳 **File Tree**: Hierarchical view of all files and folders with checkboxes
- 🏷️ **File Type Filtering**: Select files by extension with visual counts
- ⚙️ **Configuration**: Customize scanning limits and ignore patterns
- 📋 **Copy to Clipboard**: Process and copy selected files with one click
- 👁️ **Preview**: View the formatted output before copying
- 💾 **Persistent Config**: Settings saved across sessions
- ⌨️ **Keyboard Shortcuts**: Ctrl+Enter to process files quickly

## Technology Stack

- **React 18.2.0**: Modern functional components with hooks
- **Context API**: Global state management
- **CSS3**: Custom properties for theming
- **Font Awesome 6.0.0**: Icon library
- **File System Access API**: Native directory browsing
- **Flask Backend**: Python API server (see main repository)

## Prerequisites

- Node.js 14.0 or higher
- npm or yarn
- Python 3.8+ (for Flask backend)
- Modern browser (Chrome, Edge, Firefox, Safari)

## Installation

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Ensure Flask backend is running**:
   The React app proxies API requests to `http://localhost:5000`. Make sure the Flask server is running before starting the React development server.

   In the parent directory:
   ```bash
   # Install Python dependencies
   pip install -r requirements.txt
   
   # Run Flask server
   python app.py
   ```

## Running the Application

### Development Mode

Start the React development server:
```bash
npm start
```

The application will open at `http://localhost:3000` and automatically reload when you make changes.

### Production Build

Create an optimized production build:
```bash
npm run build
```

The build artifacts will be in the `build/` directory.

## Project Structure

```
react-app/
├── public/
│   ├── index.html          # HTML entry point
│   └── favicon.ico         # App icon
├── src/
│   ├── components/         # React components
│   │   ├── Header.js       # Top navigation bar
│   │   ├── LoadingOverlay.js   # Loading spinner
│   │   ├── DirectoryBrowser.js # Directory navigation
│   │   ├── DirectorySelection.js   # Initial directory picker
│   │   ├── ConfigPanel.js  # Configuration settings
│   │   ├── FileTree.js     # Hierarchical file tree
│   │   ├── FileTypes.js    # File extension filters
│   │   ├── StatusBar.js    # Status messages
│   │   ├── PreviewSection.js   # Output preview
│   │   └── MainContent.js  # Main application view
│   ├── context/
│   │   └── AppContext.js   # Global state management
│   ├── utils/
│   │   └── api.js          # API utility functions
│   ├── App.js              # Root component
│   ├── App.css             # Global app styles
│   ├── index.js            # React entry point
│   └── index.css           # CSS variables and reset
├── package.json            # Dependencies and scripts
└── README.md               # This file
```

## Component Architecture

### Context API (AppContext)

The application uses React Context for global state management. The `AppContext` provides:

- **Project State**: Current directory, files, and extensions
- **Selection State**: Selected files and file types
- **UI State**: Loading status, messages, and view mode
- **Configuration State**: User preferences and settings
- **Action Functions**: State updaters and API interaction methods

### Main Components

1. **Header**: Displays project info and navigation
2. **DirectorySelection**: Initial screen for choosing a directory
3. **MainContent**: Main application interface with three columns:
   - **Left**: FileTree with file/folder hierarchy
   - **Center**: FileTypes grid and process button
   - **Right**: PreviewSection with output
4. **ConfigPanel**: Settings for scan limits and ignore patterns
5. **StatusBar**: User feedback messages

### API Integration

All backend communication is handled through `src/utils/api.js`, which provides:

- `getCurrentDirectory()`: Get initial directory
- `browseDirectory(path)`: Navigate to a directory
- `selectDirectory(path)`: Select a directory to work with
- `processFiles(files, extensions)`: Process selected files
- `getConfig()`: Fetch configuration
- `updateConfig(config)`: Save configuration
- `resetConfig()`: Reset to defaults

## Usage

1. **Select a Directory**:
   - Click "Browse" to navigate through directories
   - Or use "Choose with Browser Picker" for native file dialog
   - Click "Select This Directory" when you find your target

2. **Configure Settings** (optional):
   - Adjust scan limits and depth
   - Add directories or files to ignore
   - Click "Save Configuration" to persist changes

3. **Select Files**:
   - Check/uncheck files in the file tree
   - Folders can be expanded/collapsed
   - Use folder checkboxes to select all children

4. **Filter by Type**:
   - Click file extension badges to include/exclude types
   - Use "Select All" or "Deselect All" for bulk actions
   - Badge shows count of files for each extension

5. **Process Files**:
   - Click "Process Files & Copy to Clipboard"
   - Or press **Ctrl+Enter**
   - View the formatted output in the preview section
   - Content is automatically copied to clipboard

## Keyboard Shortcuts

- **Ctrl+Enter**: Process selected files and copy to clipboard

## Configuration Options

### Scan Settings

- **MAX_FILES_PER_DIR_SCAN**: Maximum files to scan per directory (default: 5000)
- **MAX_INITIAL_SCAN_DEPTH**: How deep to scan initially (default: 3)
- **LARGE_DIR_THRESHOLD**: Threshold for warning about large directories (default: 1000)

### Ignore Patterns

- **Ignored Directories**: Directories to skip (e.g., `node_modules`, `.git`)
- **Ignored Files**: File patterns to exclude (e.g., `*.pyc`, `.DS_Store`)

Configuration is saved to `config.json` in the backend.

## Styling

The application uses CSS custom properties for theming. Key variables are defined in `src/index.css`:

```css
--primary-color: #007bff
--bg-primary: #1a1a1a
--bg-secondary: #242424
--text-primary: #e0e0e0
--border-color: #333
/* ... and more */
```

Each component has its own CSS file following a consistent naming convention.

## Browser Compatibility

- **Chrome/Edge**: Full support including File System Access API
- **Firefox**: Supported with directory input fallback
- **Safari**: Supported with directory input fallback

## Development Tips

### Adding a New Component

1. Create `ComponentName.js` and `ComponentName.css` in `src/components/`
2. Import and use the `useApp` hook for accessing global state:
   ```javascript
   import { useApp } from '../context/AppContext';
   
   const ComponentName = () => {
     const { state, actions } = useApp();
     // Component logic
   };
   ```
3. Import CSS: `import './ComponentName.css';`

### Updating Global State

Add new state or actions in `src/context/AppContext.js`:

```javascript
const [newState, setNewState] = useState(initialValue);

const contextValue = {
  // ... existing state
  newState,
  setNewState,
  // ... existing actions
};
```

### API Requests

Add new endpoints in `src/utils/api.js`:

```javascript
export const newApiFunction = async (params) => {
  const response = await fetch('/api/endpoint', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  return handleResponse(response);
};
```

## Troubleshooting

### React app can't connect to backend

- Ensure Flask is running on port 5000
- Check the proxy configuration in `package.json`
- Verify CORS settings in Flask if needed

### Files not loading

- Check browser console for errors
- Verify directory permissions
- Check ignored patterns in configuration

### Build fails

- Clear node_modules: `rm -rf node_modules && npm install`
- Clear cache: `npm cache clean --force`
- Update dependencies: `npm update`

## Available Scripts

- `npm start`: Start development server
- `npm test`: Run tests (if configured)
- `npm run build`: Create production build
- `npm run eject`: Eject from Create React App (irreversible)

## License

See the LICENSE file in the parent repository.

## Contributing

This is a refactored version of the original CodeClip application. For contributions, please refer to the main repository guidelines.

## Acknowledgments

- Original vanilla JavaScript version by [original author]
- Refactored to React with modern best practices
- Font Awesome for icons
- Create React App for build tooling
