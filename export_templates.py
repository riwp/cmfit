import os


def export_templates(
    templates_dir="templates", output_file="combined_templates.txt"
):
    if not os.path.exists(templates_dir):
        print(f"Error: Directory '{templates_dir}' not found.")
        return

    output_lines = [
        "Here are my HTML/Jinja template files for review:\n",
        "=" * 60 + "\n",
    ]
    file_count = 0

    for root, _, files in os.walk(templates_dir):
        for file in sorted(files):
            if file.endswith((".html", ".jinja", ".jinja2", ".j2", ".htm")):
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path)

                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    output_lines.append(f"### FILE: {rel_path}\n")
                    output_lines.append("```html\n")
                    output_lines.append(content)
                    if not content.endswith("\n"):
                        output_lines.append("\n")
                    output_lines.append("```\n")
                    output_lines.append("\n" + "-" * 40 + "\n\n")
                    file_count += 1
                except Exception as e:
                    print(f"Warning: Could not read {rel_path} ({e})")

    final_output = "".join(output_lines)

    with open(output_file, "w", encoding="utf-8") as out:
        out.write(final_output)

    print(
        f"Success: Processed {file_count} template file(s) into '{output_file}'."
    )

    try:
        import pyperclip

        pyperclip.copy(final_output)
        print("Clipboard: Output successfully copied to your clipboard!")
    except Exception:
        print(
            "Note: Saved to file. Use 'cat combined_templates.txt' to view and copy."
        )


if __name__ == "__main__":
    export_templates()