from bs4 import BeautifulSoup
import os
import re

# Function to flatten and rewrite local paths
def rewrite_html_paths(input_html_path, output_html_path, new_prefix='/assets/'):
    with open(input_html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    soup = BeautifulSoup(html_content, 'html.parser')

    # Find all <img> tags and rewrite src
    for img in soup.find_all('img'):
        if 'src' in img.attrs:
            src = img['src'].strip()
            # If it's local (no http/https), flatten to basename and add prefix
            if not (src.startswith('http://') or src.startswith('https://') or src.startswith('//')):
                basename = os.path.basename(src)
                img['src'] = new_prefix + basename

    # Find all <a> tags and rewrite href if it's a local media link
    for a in soup.find_all('a'):
        if 'href' in a.attrs:
            href = a['href'].strip()
            if not (href.startswith('http://') or href.startswith('https://') or href.startswith('//')):
                basename = os.path.basename(href)
                a['href'] = new_prefix + basename

    # Also handle any [Media] placeholders in text (replace with a generic or remove, but here we'll assume they're already in tags)
    # If needed, search and replace text patterns
    media_pattern = re.compile(r'\[Media\]', re.IGNORECASE)
    html_content = media_pattern.sub('', str(soup))  # Or replace with something else if desired

    # Write the modified HTML to output file
    with open(output_html_path, 'w', encoding='utf-8') as f:
        f.write(str(soup))

# Usage: Replace with your file paths
input_file = 'searchable_hybrid_chat45.html'
output_file = 'rendered_chat_searchable_modified.html'
rewrite_html_paths(input_file, output_file)

print(f"Modified HTML saved to '{output_file}'. All local paths flattened to '/assets/filename.ext'.")