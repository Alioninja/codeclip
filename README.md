# 📂 Code Clip for AI

Don't have premium access to GitHub Copilot, Cursor, or another AI-powered IDE? Tired of manually copying each file's code, managing filenames, and structuring your directories just so AI chatbots understand?

**Code Clip for AI** streamlines this entire process with a beautiful, modern React interface!

## 🚀 What does it do?

This powerful web application offers an advanced React-based GUI with professional directory selection to:

![Code Clip for AI Screenshot](screenshot.png)

- **🎨 Modern React interface** with beautiful dark theme
- **📁 Advanced directory browser** with native OS integration
- **🔄 Project switching** — easily change between different projects
- **📋 Smart file selection** with visual directory trees
- **⚡ One-click clipboard copy** with automatic formatting
- **⚙️ Configurable settings** for scan limits and ignore patterns

Just paste into your favorite AI chatbot and ask your question!

## 🛠️ Features

### 🎯 **Core Features**
- ✅ **Modern React UI** with functional components and hooks
- ✅ **Smart project selection** — beautiful directory picker
- ✅ **Easy file selection** — hierarchical tree with checkboxes
- ✅ **Instant clipboard copy** with properly formatted output
- ✅ **Perfect for AI chatbots** — free and premium alike

### 🎨 **Advanced Interface**
- ✅ **Native directory browser** integration (Windows/Mac/Linux)
- ✅ **Interactive navigation** with clickable folders and path input
- ✅ **Tri-state checkboxes** — visual feedback for folder selection states
- ✅ **Real-time file counting** and extension detection
- ✅ **Responsive design** that adapts to any screen size
- ✅ **Enhanced path navigation** — type paths directly with Go button

### 🔄 **Project Management**
- ✅ **Project switching** — change directories anytime
- ✅ **Dynamic file type detection** — automatic categorization
- ✅ **Smart filtering** — select specific file types or entire directories
- ✅ **Configuration panel** — customize scan limits and ignore patterns

### 🚀 **User Experience**
- ✅ **Intuitive navigation** with up/back buttons
- ✅ **Clean, modern interface** — professional React design
- ✅ **Keyboard shortcuts** — Ctrl+Enter to process files
- ✅ **Cancelable operations** — cancel loading or processing anytime
- ✅ **Progress indicators** — visual progress bar for long operations
- ✅ **Loading states** — visual feedback for all operations
- ✅ **Status messages** — clear success/error notifications

## ⚙️ Installation

### Prerequisites
- Python 3.8+
- Node.js 14.0+
- npm or yarn

### Clone and Install

Clone the repository:

```bash
git clone https://github.com/Alioninja/codeclip.git
cd codeclip
```

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Install React dependencies:

```bash
cd react-app
npm install
cd ..
```

## 🎯 Usage

### 🚀 **Development Mode** (Recommended for Development)

**Terminal 1 - Start Flask Backend:**
```bash
python app.py
```
Server runs at: http://localhost:5000

**Terminal 2 - Start React Dev Server:**
```bash
cd react-app
npm start
```
App opens at: http://localhost:3000 (with hot reload)

### 📦 **Production Mode** (Single Server)

1. **Build the React app:**
```bash
# Windows
build-react.bat

# Mac/Linux
chmod +x build-react.sh
./build-react.sh
```

2. **Run the server:**
```bash
python app.py
```
Visit: http://localhost:5000

The Flask server automatically serves the React build when available.

### 🎯 **Using the Application**

1. **Select a directory:**
   - Use the "Browse" button for native OS directory picker
   - Or navigate manually through the directory tree
   - Click "Select This Directory" when ready

2. **Configure settings (optional):**
   - Adjust scan limits and depth
   - Add directories or files to ignore
   - Save configuration for future use

3. **Select your content:**
   - Browse directories with the hierarchical file tree
   - Use checkboxes to select specific files or entire folders
   - Filter by file types with the smart extension grid
   - Expand/collapse folders to navigate the structure

4. **Process and copy:**
   - Click **"Process Files & Copy to Clipboard"** or press **Ctrl+Enter**
   - Properly formatted content is copied instantly
   - View the output in the preview section
   - Paste directly into any AI chatbot

5. **Ask your questions!**
   - Content includes file paths and directory structure
   - Perfect for AI code analysis, debugging, and enhancement

### 💡 **Pro Tips**

- **🔄 Project Switching**: Use "Change Project" to work with multiple codebases
- **📁 Smart Navigation**: Click folders or use "Up Directory" button
- **⌨️ Keyboard Shortcuts**: Press **Ctrl+Enter** to process files quickly
- **🎯 Path Input**: Type or paste paths directly in the address bar
- **⚙️ Configuration**: Customize scan limits and ignore patterns in settings
- **🎯 File Filtering**: Uncheck file types you don't need for focused analysis
- **📏 Efficient Browsing**: Compact folder items show more directories at once
- **⚡ Quick Selection**: "Select All" and "Deselect All" buttons for bulk operations
- **☑️ Tri-State Checkboxes**: Folder checkboxes show ✓ (all selected), − (some selected), or ☐ (none selected)
- **🎯 Smart Folder Selection**: Click folder checkboxes to select/deselect all contents at once

## 🎨 **Interface Highlights**

### **Directory Selection Dialog**
- 🚀 Welcome screen with project selection
- ⌨️ **Smart editable address bar** with path autocompletion and validation
- 🎯 **Visual feedback** with color-coded borders (green=valid, orange=suggestions, red=error)
- ⚡ **Keyboard shortcuts** - Ctrl+L to focus, Tab to complete, Enter to navigate, Esc to reset
- 🔙 Reliable "Up Directory" navigation
- 📄 File count display in footer
- 🎨 Consistent dark theme matching main application

### **Main Application**  
- 🗂️ Visual directory tree with expand/collapse
- ☑️ Smart file type detection and filtering
- 📊 Real-time file counting and statistics
- 🔄 Seamless project switching without restart

## 🔧 **Technical Features**

- **🎯 Smart Directory Scanning**: Automatically detects and categorizes all file types
- **📦 Optimized Performance**: Efficient scanning with limits for large directories
- **🛡️ Robust Error Handling**: Graceful handling of permission errors and invalid paths
- **💾 Memory Efficient**: Proper cleanup and resource management
- **🖥️ Cross-Platform**: Works on Windows, macOS, and Linux
- **⚡ Responsive UI**: Smooth interactions and proper window management

## 📋 **Requirements**

- **Python 3.7+**
- **customtkinter** - Modern UI framework
- **Pillow** - Image processing for UI elements

All dependencies are listed in `requirements.txt` for easy installation.

## 📝 Contributing

Pull requests are welcome! Please open an issue first to discuss changes.

## 📜 License

[MIT](LICENSE)

---

Happy coding! 🚀

