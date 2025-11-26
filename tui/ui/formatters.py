def format_output_markdown(project_name, tree_string, files_content):
    """Format output as Markdown."""
    output = f"# Project: {project_name}\n\n"
    output += "## Directory Structure\n\n```\n"
    output += f"{project_name}/\n{tree_string}\n```\n\n"
    output += "## File Contents\n\n"
    
    for rel_path, content, lang in files_content:
        output += f"### {rel_path}\n\n```{lang}\n{content}\n```\n\n"
    
    return output


def format_output_xml(project_name, tree_string, files_content):
    """Format output as XML."""
    output = '<?xml version="1.0" encoding="UTF-8"?>\n'
    output += f'<project name="{project_name}">\n'
    output += '  <structure>\n'
    output += f'    <![CDATA[\n{project_name}/\n{tree_string}\n]]>\n'
    output += '  </structure>\n'
    output += '  <files>\n'
    
    for rel_path, content, lang in files_content:
        # Escape CDATA end sequences in content
        safe_content = content.replace(']]>', ']]]]><![CDATA[>')
        output += f'    <file path="{rel_path}" language="{lang}">\n'
        output += f'      <![CDATA[{safe_content}]]>\n'
        output += '    </file>\n'
    
    output += '  </files>\n'
    output += '</project>\n'
    
    return output


def format_output_plain(project_name, tree_string, files_content):
    """Format output as plain text."""
    output = f"PROJECT: {project_name}\n"
    output += "=" * 60 + "\n\n"
    output += "DIRECTORY STRUCTURE:\n"
    output += "-" * 40 + "\n"
    output += f"{project_name}/\n{tree_string}\n\n"
    output += "=" * 60 + "\n"
    output += "FILE CONTENTS\n"
    output += "=" * 60 + "\n\n"
    
    for rel_path, content, lang in files_content:
        output += f">>> {rel_path} ({lang if lang else 'text'})\n"
        output += "-" * 40 + "\n"
        output += f"{content}\n"
        output += "-" * 40 + "\n\n"
    
    return output
