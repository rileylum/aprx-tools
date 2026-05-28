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

# ── Show the conflict — bat syntax-highlights the markers ─────────────────────

Type "bat --paging=never map.aprx.src/GISProject.json"
Enter
Sleep 10s

# ── Open in nvim and resolve ──────────────────────────────────────────────────

Type "nvim map.aprx.src/GISProject.json"
Enter
Sleep 2s

# Jump straight to the conflict at line 4
Type "4G"
Sleep 1s

# Delete: <<<<<<< HEAD
Type "dd"
Sleep 500ms

# Delete: "title": "Acme Site Analysis — New Layers"  (the version we don't want)
Type "dd"
Sleep 500ms

# Delete: =======
Type "dd"
Sleep 500ms

# "title": "Acme Site Analysis — Q2 2026" is now current line — keep it, skip over
Type "j"
Sleep 500ms

# Delete: >>>>>>> feature/update-symbology
Type "dd"
Sleep 3s

# Save and quit
Type ":wq"
Enter
Sleep 1s

# ── Show the resolved file ────────────────────────────────────────────────────

Type "bat --paging=never map.aprx.src/GISProject.json"
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
