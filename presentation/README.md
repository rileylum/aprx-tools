# Presentation

5–10 minute team demo covering the aprx-tools problem and solution.

## Files

| File | Purpose |
|---|---|
| `slides.md` | Marp slide deck source |
| `slide.html` | Compiled presentation (open in browser) |
| `demo.tape` | VHS screenplay for the terminal animation |
| `setup-demo.sh` | Creates the `~/aprx-demo` git repo used by the tape |

## Slides

Requires [Marp CLI](https://github.com/marp-team/marp-cli) (via npx — no install needed):

```bash
npx @marp-team/marp-cli slides.md --html -o slide.html
```

Open `slide.html` in a browser. Navigate with arrow keys.

## Terminal animation

Requires [VHS](https://github.com/charmbracelet/vhs) and `ffmpeg`:

```bash
# Arch
sudo pacman -S ffmpeg
go install github.com/charmbracelet/vhs@latest

# macOS
brew install vhs
```

Set up the demo repo, then record:

```bash
bash setup-demo.sh          # creates ~/aprx-demo (safe to re-run)
vhs demo.tape               # produces demo.gif
```

Embed the result in the final slide by placing `demo.gif` alongside `slide.html` — the last slide already references it as `![](demo.gif)` once you add that line, or present it separately in a terminal.
