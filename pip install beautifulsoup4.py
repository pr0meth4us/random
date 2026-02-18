import os
import sys

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: Please run 'pip install beautifulsoup4' first.")
    exit()

INPUT_FILE = "hybrid_chat.html"
OUTPUT_FILE = "searchable_hybrid_chat14.html"

if not os.path.exists(INPUT_FILE):
    print(f"Error: Could not find '{INPUT_FILE}' in the current directory.")
    exit()

print("1. Loading HTML file...")
with open(INPUT_FILE, 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f, 'html.parser')

print("2. Injecting Search Styles...")
style_tag = soup.find('style')
if style_tag:
    style_tag.append("""
    /* ── Reset body/html so nothing squishes ── */
    html, body {
        margin: 0;
        padding: 0;
        width: 100%;
        box-sizing: border-box;
    }

    /* ── Sticky full-width search bar ── */
    #custom-search-container {
        position: sticky;
        top: 0;
        z-index: 1000;
        width: 100%;
        box-sizing: border-box;
        background: #f0f2f5;
        border-bottom: 1px solid #ddd;
        padding: 12px 20px;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 6px;
    }

    #chat-search {
        width: 100%;
        max-width: 900px;
        padding: 12px 16px;
        border: 1px solid #ccc;
        border-radius: 22px;
        font-size: 15px;
        outline: none;
        background: #fff;
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
        box-sizing: border-box;
    }

    #search-count {
        font-size: 13px;
        color: #888;
        display: none;
    }

    /* ── Make the visible chat fill the page properly ── */
    #visible-chat {
        width: 100%;
        max-width: 900px;
        margin: 0 auto;
        padding: 20px 24px;
        box-sizing: border-box;
    }

    /* ── Individual message breathing room ── */
    .message {
        margin-bottom: 6px;
        content-visibility: auto;
        contain-intrinsic-size: 0 80px;
    }

    /* ── No-results notice ── */
    #no-results {
        text-align: center;
        color: #999;
        padding: 40px 0;
        font-size: 15px;
    }
    """)

print("3. Re-structuring for Search (Targeting .chat-container)...")
chat_container = soup.find('div', class_='chat-container')

if chat_container:
    # 1. Build search bar
    search_container = soup.new_tag('div', id='custom-search-container')
    search_input = soup.new_tag(
        'input', type='text', id='chat-search',
        placeholder='Search messages...'
    )
    search_count = soup.new_tag('span', id='search-count')
    search_container.append(search_input)
    search_container.append(search_count)
    soup.body.insert(0, search_container)

    # 2. Visible display area — inherits chat-container styles but gets our id too
    new_visible_area = soup.new_tag('div', id='visible-chat')
    new_visible_area['class'] = 'chat-container'
    chat_container.insert_before(new_visible_area)

    # 3. Hide original messages in a <template>
    chat_container.name = 'template'
    chat_container.attrs = {'id': 'message-data'}
else:
    print("❌ Error: Could not find <div class='chat-container'>. Check your hybrid_chat.html structure.")
    exit()

print("4. Injecting Search Logic...")
script = soup.new_tag('script')
script.string = """
document.addEventListener("DOMContentLoaded", function () {
    const template    = document.getElementById('message-data');
    const chatDisplay = document.getElementById('visible-chat');
    const searchInput = document.getElementById('chat-search');
    const searchCount = document.getElementById('search-count');

    if (!template || !chatDisplay) return;

    const messages  = Array.from(template.content.querySelectorAll('.message'));
    let currentIndex = 0;
    const BATCH      = 100;
    let isSearching  = false;

    /* ── Show total message count in placeholder ── */
    searchInput.placeholder = `Search ${messages.length.toLocaleString()} messages...`;

    function loadBatch() {
        if (isSearching || currentIndex >= messages.length) return;
        const frag = document.createDocumentFragment();
        const end  = Math.min(currentIndex + BATCH, messages.length);
        for (let i = currentIndex; i < end; i++) {
            frag.appendChild(messages[i].cloneNode(true));
        }
        chatDisplay.appendChild(frag);
        currentIndex = end;
    }

    loadBatch();

    window.addEventListener('scroll', () => {
        if (!isSearching &&
            window.innerHeight + window.scrollY >= document.body.offsetHeight - 1000) {
            loadBatch();
        }
    });

    searchInput.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase().trim();
        chatDisplay.innerHTML = '';

        if (query === '') {
            isSearching  = false;
            currentIndex = 0;
            searchCount.style.display = 'none';
            loadBatch();
            return;
        }

        isSearching = true;
        const frag  = document.createDocumentFragment();
        const MAX   = 1000;
        let   count = 0;

        for (let i = 0; i < messages.length; i++) {
            if (messages[i].textContent.toLowerCase().includes(query)) {
                frag.appendChild(messages[i].cloneNode(true));
                if (++count >= MAX) break;
            }
        }

        if (count === 0) {
            chatDisplay.innerHTML = '<div id="no-results">No messages found.</div>';
            searchCount.style.display = 'none';
        } else {
            chatDisplay.appendChild(frag);
            searchCount.textContent   = count >= MAX
                ? `Showing first ${MAX} of many results`
                : `${count} result${count !== 1 ? 's' : ''}`;
            searchCount.style.display = 'block';
        }
    });
});
"""
soup.body.append(script)

print(f"5. Saving to {OUTPUT_FILE}...")
with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
    f.write(str(soup))

msg_count = len(chat_container.find_all(class_='message')) if chat_container else 0
print(f"✅ Done! Messages indexed: {msg_count}")