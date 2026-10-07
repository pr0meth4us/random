set inFile to POSIX file "/Users/nicksng/code/random/bkd/Presentation4.pptx"
set outFile to POSIX file "/Users/nicksng/code/random/bkd/Presentation4.pdf"

tell application "Microsoft PowerPoint"
    -- Launch if not open, open without UI if possible (might still show UI)
    open inFile
    delay 2
    save active presentation in outFile as save as PDF
    close active presentation saving no
end tell
