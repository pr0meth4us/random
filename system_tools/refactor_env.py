import os
import re

def refactor_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Match os.getenv(...) and os.environ.get(...)
    # We want to replace os.getenv("KEY") with get_config("KEY")
    new_content = re.sub(r'os\.getenv\(', 'get_config(', content)
    new_content = re.sub(r'os\.environ\.get\(', 'get_config(', new_content)

    if new_content != content:
        # We made a replacement, add the import at the top
        # Find where to add the import: after the last existing import, or just at the top.
        # But a safer approach is to just put it near the top (after shebang or docstring).
        # We can just insert it at line 2 if line 1 is a shebang, else line 1.
        
        lines = new_content.split('\n')
        import_stmt = "from utils.bifrost_config import get_config"
        
        if import_stmt not in new_content:
            insert_idx = 0
            for i, line in enumerate(lines):
                if line.startswith('#!'):
                    continue
                if line.startswith('import os') or line.startswith('import sys') or 'import' in line:
                    insert_idx = i + 1
                    continue
                if line.strip() == '' and insert_idx > 0:
                    continue
                # If we passed imports and reached actual code, break
                if insert_idx > 0 and not line.startswith('from') and not line.startswith('import'):
                    break
                    
            lines.insert(insert_idx, import_stmt)
            
        new_content = '\n'.join(lines)
        
        with open(filepath, 'w') as f:
            f.write(new_content)
        print(f"Refactored: {filepath}")

from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent

if __name__ == '__main__':
    for root, dirs, files in os.walk(PROJECT_DIR):
        if 'venv' in dirs:
            dirs.remove('venv')
        if '__pycache__' in dirs:
            dirs.remove('__pycache__')
            
        for file in files:
            if file.endswith('.py'):
                if file in ['bifrost_config.py', 'bifrost_secret_manager.py', 'refactor_env.py', 'bifrost_env_migrator.py']:
                    continue
                    
                filepath = os.path.join(root, file)
                refactor_file(filepath)
