# utils/file_diff.py

import os
import difflib
import pyperclip

def generate_diff(old_content: str, new_content: str, filename: str) -> str:
    """
    Generate a unified diff string from old_content to new_content for display.
    The 'filename' is used in the from/to lines, e.g. 'filename (old)' vs 'filename (new)'.
    """
    old_lines = old_content.splitlines(keepends=True)
    new_lines = new_content.splitlines(keepends=True)

    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=filename + " (old)",
        tofile=filename + " (new)",
        lineterm=""
    )
    return "".join(diff)

def prompt_and_write_file(final_path: str, new_content: str, diff_text: str) -> bool:
    """
    Display a diff, prompt the user if they want to write to 'final_path'.
    Return True if file was created/overwritten, False otherwise.
    """
    file_exists = os.path.isfile(final_path)
    if not diff_text:
        print(f"No changes for {final_path}, skipping.")
        return False

    print(f"\n--- Diff for {final_path} ---")
    print(diff_text, end="")  # diff_text includes line breaks
    print("\n--- End of diff ---")

    if file_exists:
        user_input = input(f"Overwrite file '{final_path}'? (y/N) ").strip().lower()
    else:
        user_input = input(f"File '{final_path}' does not exist. Create it? (y/N) ").strip().lower()

    if user_input == 'y':
        os.makedirs(os.path.dirname(final_path), exist_ok=True)
        try:
            with open(final_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            action = "Overwritten" if file_exists else "Created"
            print(f"{action} '{final_path}'.\n")
            return True
        except Exception as e:
            print(f"Error writing '{final_path}': {e}")
            return False
    elif user_input == 'c':
        pyperclip.copy(new_content)
        return False
    else:
        print(f"Skipped writing '{final_path}'.\n")
        return False
