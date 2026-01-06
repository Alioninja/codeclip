import platform
import subprocess
import tempfile
import os
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
            # Method 1: Use Windows Clipboard API directly via ctypes
            try:
                import ctypes
                
                kernel32 = ctypes.windll.kernel32
                user32 = ctypes.windll.user32
                
                # Set up function signatures for proper 64-bit support
                kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
                kernel32.GlobalAlloc.restype = ctypes.c_void_p
                kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
                kernel32.GlobalLock.restype = ctypes.c_void_p
                kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
                kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
                user32.OpenClipboard.argtypes = [ctypes.c_void_p]
                user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
                user32.SetClipboardData.restype = ctypes.c_void_p
                
                # Constants
                CF_UNICODETEXT = 13
                GMEM_MOVEABLE = 0x0002
                
                # Convert text to UTF-16LE (Windows native Unicode) with null terminator
                text_bytes = text.encode('utf-16-le') + b'\x00\x00'
                
                # Allocate global memory
                h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(text_bytes))
                if not h_mem:
                    raise Exception("GlobalAlloc failed")
                
                # Lock and copy data
                p_mem = kernel32.GlobalLock(h_mem)
                if not p_mem:
                    kernel32.GlobalFree(h_mem)
                    raise Exception("GlobalLock failed")
                
                ctypes.memmove(p_mem, text_bytes, len(text_bytes))
                kernel32.GlobalUnlock(h_mem)
                
                # Open clipboard, empty it, set data, close
                if not user32.OpenClipboard(None):
                    kernel32.GlobalFree(h_mem)
                    raise Exception("OpenClipboard failed")
                
                user32.EmptyClipboard()
                result = user32.SetClipboardData(CF_UNICODETEXT, h_mem)
                user32.CloseClipboard()
                
                if result:
                    return True, "✓ Copied (Windows API)"
                else:
                    raise Exception("SetClipboardData failed")
                    
            except Exception as e:
                # Method 2: Fall back to PowerShell with temp file (handles Unicode properly)
                try:
                    # Write to temp file with UTF-8 BOM so PowerShell reads it correctly
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, 
                                                      encoding='utf-8-sig') as f:
                        f.write(text)
                        temp_path = f.name
                    
                    try:
                        # Use PowerShell to read the file and set clipboard
                        ps_cmd = f'Get-Content -Path "{temp_path}" -Raw -Encoding UTF8 | Set-Clipboard'
                        result = subprocess.run(
                            ['powershell', '-NoProfile', '-Command', ps_cmd],
                            capture_output=True,
                            timeout=10
                        )
                        if result.returncode == 0:
                            return True, "✓ Copied (PowerShell)"
                    finally:
                        # Clean up temp file
                        try:
                            os.unlink(temp_path)
                        except:
                            pass
                except Exception:
                    pass
                    
    except Exception:
        pass
    
    # Fallback: save to file
    try:
        clipboard_file = Path.home() / ".codeclip_clipboard"
        clipboard_file.write_text(text, encoding='utf-8')
        return True, f"✓ Saved to {clipboard_file}"
    except Exception as e:
        return False, f"✗ Failed: {e}"
