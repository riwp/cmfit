import os
import re
import sys

def split_combined_templates(file_path="combined_templates.txt", output_dir="templates"):
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found.")
        return

    os.makedirs(output_dir, exist_ok=True)

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Pattern matches "### FILE: templates/filename.html" or "### FILE: filename.html"
    # and handles optional markdown code fences ```html ... ```
    file_pattern = re.compile(
        r"### FILE:\s*(?:templates/)?([a-zA-Z0-9_\-]+\.html)\s*\n(?:```(?:html)?\n)?(.*?)(?=\n### FILE:|\n----------------------------------------|\Z)",
        re.DOTALL
    )

    matches = file_pattern.findall(content)

    if not matches:
        print(f"No template markers found in '{file_path}'.")
        return

    for filename, code in matches:
        # Strip trailing markdown fence if present
        clean_code = re.sub(r"\n```\s*$", "", code.strip())
        dest_path = os.path.join(output_dir, filename)
        
        with open(dest_path, "w", encoding="utf-8") as out_file:
            out_file.write(clean_code + "\n")
        print(f"Successfully extracted: {dest_path}")

    print(f"\nCompleted! Extracted {len(matches)} files into ./{output_dir}/")

if __name__ == "__main__":
    # Allow passing file path as command line argument
    target_file = sys.argv[1] if len(sys.argv) > 1 else "split.txt"
    split_combined_templates(target_file)