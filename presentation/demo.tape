# aprx-tools demo — merge conflict workflow
# Run `bash setup-demo.sh` first to create ~/aprx-demo
#
# To render:  vhs demo.tape
# Install:    go install github.com/charmbracelet/vhs@latest
#             (also requires ffmpeg: pacman -S ffmpeg)
#             (also requires ttyd:   yay -S ttyd)

Output demo.gif

Set Theme "Dracula"
Set FontSize 16
Set Width 1200
Set Height 650
Set PlaybackSpeed 0.85
Set CursorBlink false
Set TypingSpeed 40ms

# ── Show the starting state ────────────────────────────────────────────────────

Sleep 500ms
Type "cd ~/aprx-demo"
Enter
Sleep 1s

Type "git log --oneline --graph --all"
Enter
Sleep 10s

# ── Merge the first feature branch (succeeds) ──────────────────────────────────

Type "git merge feature/add-properties-layer"
Enter
Sleep 10s

# ── Try the second branch — conflict! ─────────────────────────────────────────

Type "git merge feature/update-symbology"
Enter
Sleep 10s

# ── Show what conflicted ───────────────────────────────────────────────────────

Type "git status"
Enter
Sleep 10s

# ── Show the conflict is readable JSON ────────────────────────────────────────

Type "cat map.aprx.src/GISProject.json"
Enter
Sleep 10s

# ── Highlight just the conflict markers ───────────────────────────────────────

Type "grep --color=always -n -E '<<<<<<|======|>>>>>>' map.aprx.src/GISProject.json"
Enter
Sleep 10s

# ── Open in nano and resolve ──────────────────────────────────────────────────

Type "nano map.aprx.src/GISProject.json"
Enter
Sleep 2s

# Conflict is at line 4. Cursor starts at line 1 — navigate down 3 lines.
Down
Down
Down
Sleep 1s

# Delete: <<<<<<< HEAD
Ctrl+K
Sleep 500ms

# Delete: "title": "Acme Site Analysis — New Layers"  (the version we don't want)
Ctrl+K
Sleep 500ms

# Delete: =======
Ctrl+K
Sleep 500ms

# "title": "Acme Site Analysis — Q2 2026" is now current line — keep it, skip over
Down
Sleep 500ms

# Delete: >>>>>>> feature/update-symbology
Ctrl+K
Sleep 3s

# Save and exit
Ctrl+X
Sleep 1s
y
Sleep 500ms
Enter
Sleep 1s

# ── Show the resolved file ────────────────────────────────────────────────────

Type "cat map.aprx.src/GISProject.json"
Enter
Sleep 10s

# ── Stage and commit — hook fires automatically ───────────────────────────────

Type "git add map.aprx.src/ map.aprx"
Enter
Sleep 1s

Type "git commit -m 'Merge: Q2 title + boundaries + properties layers'"
Enter
Sleep 10s

# ── Clean history ─────────────────────────────────────────────────────────────

Type "git log --oneline --graph"
Enter
Sleep 10s
