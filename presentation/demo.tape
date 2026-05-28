# aprx-tools demo — merge conflict workflow
# Run `bash setup-demo.sh` first to create ~/aprx-demo
#
# To render:  vhs demo.tape
# Install:    go install github.com/charmbracelet/vhs@latest
#             (also requires ffmpeg: pacman -S ffmpeg)

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
Sleep 300ms

Type "git log --oneline --graph --all"
Enter
Sleep 3s

# ── Merge the first feature branch ────────────────────────────────────────────

Type "git merge feature/add-properties-layer"
Enter
Sleep 2.5s

# ── Try the second branch — conflict! ─────────────────────────────────────────

Type "git merge feature/update-symbology"
Enter
Sleep 3s

# ── Show the conflicted files ──────────────────────────────────────────────────

Type "git status"
Enter
Sleep 2s

# ── The key moment: the conflict is human-readable ────────────────────────────

Type "cat map.aprx.src/GISProject.json"
Enter
Sleep 4s

# ── Resolve: accept both branches' meaningful changes ─────────────────────────

Type "python3 resolve.py"
Enter
Sleep 1.5s

Type "cat map.aprx.src/GISProject.json"
Enter
Sleep 3.5s

# ── Stage and commit — watch the hook fire automatically ─────────────────────

Type "git add map.aprx.src/ map.aprx"
Enter
Sleep 500ms

Type "git commit -m 'Merge: Q2 title + boundaries + properties layers'"
Enter
Sleep 3.5s

# ── Clean history ─────────────────────────────────────────────────────────────

Type "git log --oneline --graph"
Enter
Sleep 3s
