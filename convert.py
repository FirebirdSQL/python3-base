import os
import re

def convert_rst_to_md(filename, content):
    # Rule 6: Determine module name
    base_name = os.path.splitext(os.path.basename(filename))[0]
    module_name = f"firebird.base.{base_name}"
    
    # Overrides for some files
    if base_name in ['index', 'introduction', 'changelog', 'license', 'modules']:
        module_name = "firebird.base"
    
    lines = content.splitlines()
    new_lines = []
    i = 0
    
    def process_roles(text):
        def replace_role(match):
            role = match.group(1)
            content = match.group(2)
            display_content = content
            if display_content.startswith('~'):
                display_content = display_content[1:].split('.')[-1]
            
            if role == 'doc':
                return f"[{display_content.capitalize()}]({display_content}.md)"
            return f"`{display_content}`"
        
        return re.sub(r':(doc|ref|class|func|obj|mod|attr|exc):`([^`]+)`', replace_role, text)

    while i < len(lines):
        line = lines[i]
        
        # Skip module/synopsis
        if line.strip().startswith('.. module::') or line.strip().startswith(':synopsis:'):
            i += 1
            continue

        # Rule 1: Headers
        # Title with overline and underline
        if i + 2 < len(lines) and re.match(r'^[#*=+^"~-]+$', line.strip()) and \
           re.match(r'^[#*=+^"~-]+$', lines[i+2].strip()) and \
           len(line.strip()) >= len(lines[i+1].strip()) and len(lines[i+2].strip()) >= len(lines[i+1].strip()):
            new_lines.append(f"# {lines[i+1].strip()}")
            i += 3
            continue
        
        # Header with underline
        if i + 1 < len(lines) and re.match(r'^[#*=+^"~-]+$', lines[i+1].strip()) and \
           len(lines[i+1].strip()) >= len(line.strip()) and len(line.strip()) > 0:
            char = lines[i+1].strip()[0]
            level = 2
            if char == '#': level = 1
            elif char == '=': level = 2
            elif char == '-': level = 3
            elif char == '^': level = 4
            elif char == '"': level = 5
            elif char == '~': level = 6
            new_lines.append(f"{'#' * level} {line.strip()}")
            i += 2
            continue
        
        # Rule 2: code-block
        if line.strip().startswith('.. code-block::'):
            lang = line.split('::')[-1].strip()
            new_lines.append(f"```{lang}")
            i += 1
            # Skip empty lines until indented block
            while i < len(lines) and not lines[i].strip():
                i += 1
            # Find indentation
            if i < len(lines):
                indent = len(lines[i]) - len(lines[i].lstrip())
                while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) >= indent):
                    new_lines.append(lines[i][indent:])
                    i += 1
            new_lines.append("```")
            continue

        # Rule 3: Admonitions
        admonitions = ['note', 'tip', 'warning', 'important', 'caution', 'seealso', 'admonition', 'error', 'danger']
        match_adm = re.match(r'^\.\.\s+(' + '|'.join(admonitions) + r')::(.*)', line.strip())
        if match_adm:
            adm_type = match_adm.group(1)
            adm_text = match_adm.group(2).strip()
            
            if adm_type == 'admonition':
                new_lines.append(f"!!! {adm_text}")
                i += 1
            else:
                new_lines.append(f"!!! {adm_type}")
                if adm_text:
                    new_lines.append(f"    {process_roles(adm_text)}")
                i += 1
            
            # Skip empty lines
            while i < len(lines) and not lines[i].strip():
                i += 1
            if i < len(lines):
                curr_indent = len(lines[i]) - len(lines[i].lstrip())
                if curr_indent > 0:
                    indent = curr_indent
                    while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) >= indent):
                        content_line = lines[i][indent:]
                        content_line = process_roles(content_line)
                        content_line = re.sub(r'^\.\.\s+(' + '|'.join(admonitions) + r')::', r'!!! \1', content_line)
                        new_lines.append(f"    {content_line}")
                        i += 1
            continue

        # Rule 5: mkdocstrings
        match_auto = re.match(r'^\.\.\s+auto(class|function|exception|data)::\s+([\w\.]+)', line.strip())
        if match_auto:
            obj_type = match_auto.group(1)
            obj_name = match_auto.group(2)
            full_name = obj_name if '.' in obj_name else f"{module_name}.{obj_name}"
            new_lines.append(f"::: {full_name}")
            i += 1
            # Skip options
            while i < len(lines) and (not lines[i].strip() or (len(lines[i]) - len(lines[i].lstrip()) > 0 and lines[i].strip().startswith(':'))):
                i += 1
            continue
            
        # Rule 4 & 7: Sphinx roles and toctree
        line = process_roles(line)
        
        if line.strip().startswith('.. toctree::'):
            i += 1
            while i < len(lines) and (not lines[i].strip() or lines[i].strip().startswith(':')):
                i += 1
            while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith('.'):
                fname = lines[i].strip()
                new_lines.append(f"- [{fname.capitalize()}]({fname}.md)")
                i += 1
            continue

        # Rule 8: license include
        if line.strip().startswith('.. include::'):
            inc_path = line.split('::')[-1].strip()
            if 'LICENSE' in inc_path:
                try:
                    with open('LICENSE', 'r') as f:
                        new_lines.extend(f.read().splitlines())
                except:
                    new_lines.append(f"(Include {inc_path})")
            i += 1
            continue
            
        # Horizontal rules
        if re.match(r'^[#*=+^"~-]{3,}$', line.strip()):
            new_lines.append("---")
            i += 1
            continue

        # Handle simple links like `Firebird Project`_
        line = re.sub(r'`([^`]+)`_', r'\1', line)
        # Handle link definitions
        match_link_def = re.match(r'^\.\.\s+_([^:]+):\s+(.*)', line.strip())
        if match_link_def:
            new_lines.append(f"[{match_link_def.group(1)}]: {match_link_def.group(2)}")
            i += 1
            continue
            
        if line.strip().startswith('.. |'):
            i += 1
            continue
        
        if line.strip() == '|':
            new_lines.append("")
            i += 1
            continue

        new_lines.append(line)
        i += 1
        
    return "\n".join(new_lines)

files_to_convert = [
    'buffer.txt', 'changelog.txt', 'collections.txt', 'config.txt',
    'hooks.txt', 'index.txt', 'introduction.txt', 'license.txt',
    'logging.txt', 'modules.txt', 'protobuf.txt', 'signal.txt',
    'strconv.txt', 'trace.txt', 'types.txt'
]

for filename in files_to_convert:
    src_path = os.path.join('docs', filename)
    dest_path = os.path.join('zendocs/docs', filename.replace('.txt', '.md'))
    
    if os.path.exists(src_path):
        with open(src_path, 'r') as f:
            content = f.read()
        
        converted = convert_rst_to_md(filename, content)
        
        with open(dest_path, 'w') as f:
            f.write(converted)
        print(f"Converted {src_path} to {dest_path}")
    else:
        print(f"Skipping {src_path}, not found.")
