import re

# Assuming the HTML content is saved in a file named 'rendered_chat_searchable.html'.
# If the content is provided as a string, you can replace the file reading with content = """paste_html_here"""

def extract_local_links(html_content):
    links = set()

    # Regex to find href attributes
    href_matches = re.finditer(r'\bhref\s*=\s*"([^"]+)"', html_content, re.IGNORECASE)
    for match in href_matches:
        link = match.group(1).strip()
        # Check if it's local (doesn't start with http/https or // for protocol-relative)
        if not (link.startswith('http://') or link.startswith('https://') or link.startswith('//')):
            links.add(link)

    # Regex to find src attributes
    src_matches = re.finditer(r'\bsrc\s*=\s*"([^"]+)"', html_content, re.IGNORECASE)
    for match in src_matches:
        link = match.group(1).strip()
        if not (link.startswith('http://') or link.startswith('https://') or link.startswith('//')):
            links.add(link)

    # Optionally, find placeholder-like texts if they resemble links (e.g., [Media] or paths in text)
    # This is a broad regex for potential placeholders that look like file paths
    placeholder_matches = re.finditer(r'(\[Media\])|((?:[\w\-]+\/)*[\w\-@]+\.(?:jpg|png|gif|html|pdf))', html_content, re.IGNORECASE)
    for match in placeholder_matches:
        link = match.group(0).strip()
        if link and not (link.startswith('http://') or link.startswith('https://') or link.startswith('//')):
            links.add(link)

    return sorted(links)

# Read the HTML file
try:
    with open('rendered_chat_searchable.html', 'r', encoding='utf-8') as f:
        html_content = f.read()
except FileNotFoundError:
    print("Error: File 'rendered_chat_searchable.html' not found. Please save the HTML content to this file.")
    exit(1)

# Extract links
local_links = extract_local_links(html_content)

# Write to output file
output_file = 'extracted_local_links.txt'
with open(output_file, 'w', encoding='utf-8') as f:
    for link in local_links:
        f.write(link + '\n')

print(f"Extracted {len(local_links)} local links (including potential placeholders) to '{output_file}'.")