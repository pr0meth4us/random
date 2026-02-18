import os
import sys
try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: Please run 'pip install beautifulsoup4' first.")
    exit()

# File naming matching your hybrid output
INPUT_FILE = "hybrid_chat.html"
OUTPUT_FILE = "searchable_hybrid_chat45.html"

if not os.path.exists(INPUT_FILE):
    print(f"Error: Could not find '{INPUT_FILE}' in the current directory.")
    exit()

print("1. Loading HTML file...")
with open(INPUT_FILE, 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f, 'html.parser')

print("2. Injecting Improved Styles...")
style_tag = soup.find('style')
if style_tag:
    # Overriding the body's flex behavior and fixing the padding
    # We use !important to make sure we kill the old 'display: flex' that's ruining the layout
    style_tag.append("""
    body { 
        display: block !important; 
        padding: 0 !important; 
        margin: 0 !important; 
        background-color: #f0f2f5;
    }
    
    #custom-search-container { 
        padding: 12px 20px; 
        background: rgba(240, 242, 245, 0.95); 
        backdrop-filter: blur(10px);
        border-bottom: 1px solid #ddd; 
        position: sticky; 
        top: 0; 
        z-index: 1000; 
        width: 100%;
        display: flex;
        justify-content: center;
        box-sizing: border-box;
    }

    #chat-search { 
        width: 100%; 
        max-width: 700px;
        padding: 12px 16px; 
        border: 1px solid #ccc; 
        border-radius: 12px; 
        font-size: 16px; 
        outline: none;
        box-shadow: 0 2px 8px rgba(0,0,0,0.05);
        background: white;
    }

    /* Centering the visible chat area and giving it the padding it needs */
    #visible-chat {
        margin: 20px auto; 
        padding: 0 15px; /* Outside padding so text isn't squeezed against edges */
        box-sizing: border-box;
    }

    .message { 
        content-visibility: auto; 
        contain-intrinsic-size: 0 80px; 
        margin-bottom: 10px;
    }
    
    @media (max-width: 700px) {
        #chat-search { width: 100%; }
        #visible-chat { width: 100%; padding: 0 10px; }
    }
    """)

print("3. Re-structuring for Search...")
chat_container = soup.find('div', class_='chat-container')

if chat_container:
    # 1. Add Search Bar at the very top of body
    search_container = soup.new_tag('div', id='custom-search-container')
    search_input = soup.new_tag('input', type='text', id='chat-search',
                                placeholder='Search messages...')
    search_container.append(search_input)
    soup.body.insert(0, search_container)

    # 2. Create the Centered Display Area
    new_visible_area = soup.new_tag('div', id='visible-chat')
    # We keep the original class so bubbles still look like iOS
    new_visible_area['class'] = 'chat-container'
    chat_container.insert_before(new_visible_area)

    # 3. Move messages into the hidden template
    chat_container.name = 'template'
    chat_container.attrs = {'id': 'message-data'}
else:
    print("❌ Error: Could not find <div class='chat-container'>.")
    exit()

print("4. Injecting Optimized Search Logic...")
script = soup.new_tag('script')
script.string = """
document.addEventListener("DOMContentLoaded", function() {
    const template = document.getElementById('message-data');
    const chatDisplay = document.getElementById('visible-chat');
    const searchInput = document.getElementById('chat-search');
    
    if (!template || !chatDisplay) return;
    
    const messages = Array.from(template.content.querySelectorAll('.message'));
    let currentIndex = 0;
    const batchSize = 100; 
    let isSearching = false;

    function loadMore() {
        if (isSearching || currentIndex >= messages.length) return;
        const fragment = document.createDocumentFragment();
        const end = Math.min(currentIndex + batchSize, messages.length);
        for (let i = currentIndex; i < end; i++) {
            fragment.appendChild(messages[i].cloneNode(true));
        }
        chatDisplay.appendChild(fragment);
        currentIndex = end;
    }

    loadMore();

    window.addEventListener('scroll', () => {
        if (!isSearching && (window.innerHeight + window.scrollY) >= document.body.offsetHeight - 1200) {
            loadMore();
        }
    });

    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase().trim();
        chatDisplay.innerHTML = '';
        
        if (query === '') {
            isSearching = false;
            currentIndex = 0;
            loadMore();
            return;
        }

        isSearching = true;
        const fragment = document.createDocumentFragment();
        let matchCount = 0;

        for (let i = 0; i < messages.length; i++) {
            if (messages[i].textContent.toLowerCase().includes(query)) {
                fragment.appendChild(messages[i].cloneNode(true));
                matchCount++;
                if (matchCount >= 500) break; // Limit search results for speed
            }
        }
        
        if (matchCount === 0) {
            chatDisplay.innerHTML = '<div style="padding: 40px; text-align: center; color: #888;">No results found.</div>';
        } else {
            chatDisplay.appendChild(fragment);
        }
    });
});
"""
soup.body.append(script)

print(f"5. Saving to {OUTPUT_FILE}...")
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.write(str(soup))

print(f"✅ Fixed! Header is sticky/full-width and chat bubbles have proper padding.")