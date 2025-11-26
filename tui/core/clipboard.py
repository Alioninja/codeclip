import platform
import subprocess
from pathlib import Path

def copy_to_clipboard(text: str) -> tuple[bool, str]:
    """Copy text to clipboard using native OS mechanisms."""
    system = platform.system()
    
    try:
        if system == "Linux":
            for cmd in [['xclip', '-selection', 'clipboard'],
                        ['xsel', '--clipboard', '--input'],
                        ['wl-copy']]:
                try:
                    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
                    process.communicate(text.encode('utf-8'), timeout=2)
                    if process.returncode == 0:
                        return True, f"✓ Copied ({cmd[0]})"
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue
        
        elif system == "Darwin":
            process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
            process.communicate(text.encode('utf-8'), timeout=2)
            if process.returncode == 0:
                return True, "✓ Copied (pbcopy)"
        
        elif system == "Windows":
            process = subprocess.Popen(
                ['powershell', '-Command', 'Set-Clipboard -Value $input'],
                stdin=subprocess.PIPE, stderr=subprocess.PIPE
            )
            process.communicate(text.encode('utf-8'), timeout=2)
            if process.returncode == 0:
                return True, "✓ Copied (PowerShell)"
    except Exception:
        pass
    
    # Fallback: save to file
    try:
        clipboard_file = Path.home() / ".codeclip_clipboard"
        clipboard_file.write_text(text, encoding='utf-8')
        return True, f"✓ Saved to {clipboard_file}"
    except Exception as e:
        return False, f"✗ Failed: {e}"
