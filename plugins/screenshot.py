import os
import subprocess
import shutil
from datetime import datetime
from typing import List, Dict
from plugins import llt
from utils import Colors, path_input
from message import Message
import time

def _check_dependencies() -> tuple[str, List[str]]:
    """Check for available screenshot tools and return the best available option."""
    if os.name == 'nt':  # Windows
        if shutil.which('ffmpeg'):
            return 'ffmpeg', ['gdigrab', 'desktop']
        raise RuntimeError("ffmpeg is required for screenshots on Windows")
        
    if os.uname().sysname == 'Darwin':  # macOS
        if shutil.which('ffmpeg'):
            return 'ffmpeg', ['avfoundation', '1:none']
        raise RuntimeError("ffmpeg is required for screenshots on macOS")
        
    # Linux
    desktop = os.getenv("XDG_CURRENT_DESKTOP", "").lower()
    session = os.getenv("DESKTOP_SESSION", "").lower()
    
    # Check for GNOME/Unity environments first
    if "gnome" in desktop or "unity" in desktop or "gnome" in session or "ubuntu" in session:
        if shutil.which('gnome-screenshot'):
            return 'gnome-screenshot', ['-f']  # -f for file output
        
    # Then check Wayland
    if os.getenv("WAYLAND_DISPLAY"):
        if shutil.which('grim'):
            return 'grim', []
            
    # Then check X11 tools
    if shutil.which('maim'):
        return 'maim', []
    if shutil.which('ffmpeg'):
        return 'ffmpeg', ['x11grab']
        
    # If we get here and we're in GNOME/Unity, try one more time with ffmpeg
    if "gnome" in desktop or "unity" in desktop or "gnome" in session or "ubuntu" in session:
        if shutil.which('ffmpeg'):
            return 'ffmpeg', ['x11grab']
            
    raise RuntimeError("No compatible screenshot tool found. Please install gnome-screenshot, grim (Wayland), maim (X11), or ffmpeg.")

@llt
def screenshot(messages: List[Message], args: Dict, index: int = -1) -> List[Message]:
    """
    Description: Capture a screenshot using ffmpeg
    Type: boolean
    Default: false
    flag: screenshot
    short: screen
    """
    # Default to screenshots directory in LLT_PATH
    screenshot_dir = os.path.join(os.getenv('LLT_PATH', ''), 'screenshots')
    os.makedirs(screenshot_dir, exist_ok=True)

    # Generate default filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    default_filename = f"screenshot_{timestamp}.png"
    
    if not args.get('non_interactive'):
        output_path = path_input(
            os.path.join(screenshot_dir, default_filename),
            screenshot_dir
        )
    else:
        output_path = os.path.join(screenshot_dir, args.get('screenshot') or default_filename)

    try:
        # Check dependencies and get appropriate tool and settings
        tool, tool_args = _check_dependencies()
        
        if tool == 'ffmpeg':
            if tool_args[0] == 'x11grab':
                # Get screen resolution for X11
                try:
                    xdpyinfo_output = subprocess.check_output("xdpyinfo | grep dimensions", shell=True).decode()
                    import re
                    match = re.search(r"dimensions:\s+(\d+x\d+)", xdpyinfo_output)
                    if match:
                        video_size = match.group(1)
                    else:
                        video_size = "1920x1080"
                except Exception:
                    video_size = "1920x1080"

                display = os.getenv("DISPLAY", ":0.0")
                cmd = [
                    "ffmpeg",
                    "-f", tool_args[0],
                    "-video_size", video_size,
                    "-framerate", "1",
                    "-i", f"{display}+0,0",  # Capture from top-left corner
                    "-frames:v", "1",
                    "-y",
                    output_path
                ]
            else:
                cmd = [
                    "ffmpeg",
                    "-f", tool_args[0],
                    "-i", tool_args[1],
                    "-frames:v", "1",
                    "-y",
                    "-draw_mouse", "1",
                    output_path
                ]
        elif tool == 'gnome-screenshot':
            cmd = [
                tool,
                '--file=' + output_path,  # Use file parameter
                '--display=' + os.getenv("DISPLAY", ":0.0"),  # Specify display
                '--include-pointer'  # Include mouse cursor
            ]
        else:
            cmd = [tool, output_path]

        # Brief delay to allow screen refresh before capturing screenshot
        time.sleep(2)  # Reduced delay since we're more efficient now
        
        # Execute screenshot command with timeout
        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10  # Add timeout to prevent hanging
            )
            
            if process.returncode == 0:
                Colors.print_colored(f"Screenshot saved to: {output_path}", Colors.GREEN)

                # alternative method to doing the same thing we do in file_include
                args['file'] = output_path
                args['prompt'] = "I've taken a screenshot of my screen. Please analyze this image and help me understand what's shown. Feel free to ask questions about specific parts you see."
                messages.append({"role": "llt", "content": "file-1"})
                
            else:
                error_msg = f"Screenshot failed: {process.stderr}"
                Colors.print_colored(error_msg, Colors.RED)
                messages.append({
                    "role": "user",
                    "content": error_msg
                })

        except subprocess.TimeoutExpired:
            error_msg = "Screenshot timed out"
            Colors.print_colored(error_msg, Colors.RED)
            messages.append({
                "role": "user",
                "content": error_msg
            })

    except Exception as e:
        error_msg = f"Error capturing screenshot: {str(e)}"
        Colors.print_colored(error_msg, Colors.RED)
        messages.append({
            "role": "user",
            "content": error_msg
        })

    return messages 