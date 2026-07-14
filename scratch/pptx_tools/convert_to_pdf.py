import subprocess
import os

pptx_path = "/Users/nicksng/code/random/EGD_Slide Presentaton_DA5.pptx"
pdf_path = "/Users/nicksng/code/random/EGD_Slide Presentaton_DA5.pdf"

if not os.path.exists(pptx_path):
    print(f"Error: {pptx_path} does not exist.")
    exit(1)

applescript = f'''
with timeout of 1200 seconds
    tell application "Microsoft PowerPoint"
        activate
        -- Close all open presentations without saving to ensure clean state
        repeat while (count of presentations) > 0
            close active presentation saving no
        end repeat
        
        open POSIX file "{pptx_path}"
        delay 5
        set activePres to active presentation
        save activePres in POSIX file "{pdf_path}" as save as PDF
        delay 2
        close activePres saving no
    end tell
end timeout
'''

print("Running AppleScript with 20-minute timeout to convert PPTX to PDF via PowerPoint...")
process = subprocess.Popen(['osascript', '-e', applescript], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
stdout, stderr = process.communicate()

if process.returncode == 0:
    print(f"Success! PDF created at {pdf_path}")
else:
    print("Failed to convert presentation to PDF.")
    print(f"Error: {stderr.decode('utf-8')}")
    print(f"Output: {stdout.decode('utf-8')}")
