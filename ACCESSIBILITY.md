# Accessibility Permissions Guide

## Why Accessibility Permissions Are Needed

Open Whisper uses global keyboard shortcuts that work even when the app is not focused. macOS requires **Accessibility** permissions for apps to:

1. **Monitor keyboard input** - Detect when you press `Cmd+Shift+V` or `Cmd+Shift+R`
2. **Simulate keyboard events** - Paste text using `Cmd+V`

## What Files Need Permission

When you run Open Whisper, you need to grant permission to **2 executables**:

### 1. Your Terminal App

**Why:** The terminal spawns the Python process
**Which one:** Depends on what you use:
- `Terminal.app` (default macOS terminal)
- `iTerm.app` (if you use iTerm2)
- `Alacritty`, `Kitty`, etc.

**Location:**
- Terminal: `/System/Applications/Utilities/Terminal.app`
- iTerm: `/Applications/iTerm.app`

### 2. Python Executable

**Why:** Python runs the actual code that listens for hotkeys
**Which one:** The Python inside your project's virtual environment

**Find it:**
```bash
# Run this to see the exact path:
uv run python -c "import sys; print(sys.executable)"
```

**Typical path:**
```
/Users/YOUR_USERNAME/src/github.com/dalasnoin/open_whisper/.venv/bin/python3
```

## How to Add to Accessibility

### Step 1: Open Accessibility Settings

1. Click **Apple menu ()**
2. **System Settings**
3. **Privacy & Security**
4. Click **Accessibility** in the list

### Step 2: Unlock Settings

Click the **🔒 lock icon** at bottom left and enter your password

### Step 3: Add Terminal App

**Option A: Already listed?**
- Look for **Terminal** or **iTerm** in the list
- Toggle it **ON** (make sure it's checked/blue)

**Option B: Not listed?**
- Let the app request permission (see "Automatic Method" below)

### Step 4: Add Python Executable

**Option A: Let macOS prompt you (Easiest)**
1. Start the app
2. Press `Cmd+Shift+R` or `Cmd+Shift+V`
3. macOS shows permission dialog
4. Click **"Open System Settings"**
5. Toggle the permission **ON**

**Option B: Add manually**
1. Find Python path: `uv run python -c "import sys; print(sys.executable)"`
2. Open Finder, press `Cmd+Shift+G`
3. Paste the path
4. Drag `python3` into Accessibility settings window

### Step 5: Restart the App

```bash
# Kill the app
pkill -f main.py

# Restart
./start_app.sh          # Menu bar version
# OR
./start_desktop.sh      # Desktop window version
```

## Verification

After granting permissions:

1. Start the app
2. You should **NOT** see: `"This process is not trusted!"`
3. Test hotkeys:
   - Press `Cmd+Shift+R` → Should start/stop recording
   - Press `Cmd+Shift+V` → Should paste transcripts

## Troubleshooting

### Still seeing "not trusted" error?

1. **Check both are enabled:** Terminal AND Python must BOTH be toggled ON
2. **Restart Mac:** Permissions sometimes don't apply until reboot
3. **Reset TCC database:**
   ```bash
   tccutil reset Accessibility
   # Then re-add permissions
   ```

### Can't find (+) button?

The macOS Accessibility UI has changed. Instead:
- Click the 🔒 lock first
- Press `Cmd+Shift+R` to trigger permission request
- macOS will show you what to add

### Multiple Python entries?

If you see several Python executables, add the one from your `.venv`:
```
✅ /Users/.../open_whisper/.venv/bin/python3  (THIS ONE)
❌ /usr/bin/python3
❌ /usr/local/bin/python3
```

## What The Code Actually Does

You can verify the code is safe by reading:

**Hotkey listener** (`backend/service.py:90-139`):
```python
def on_toggle_recording():
    self.listening = not self.listening  # Toggle on/off
    if not self.listening:
        pyperclip.copy(text)  # Copy to clipboard

def on_paste():
    pyperclip.copy(text)      # Copy to clipboard
    pyautogui.hotkey('cmd', 'v')  # Simulate Cmd+V
```

That's it! The code:
- ✅ Toggles recording on/off
- ✅ Copies text to clipboard
- ✅ Simulates paste command
- ❌ Does NOT log keystrokes
- ❌ Does NOT send data anywhere
- ❌ Does NOT do anything else with accessibility permissions

## Security Best Practices

1. **Review the code** - You have full source access
2. **Only grant to your own .venv Python** - Not system Python
3. **Revoke when not using** - Remove permissions if you uninstall
4. **Monitor what's listed** - Regularly check Accessibility settings

## Alternative: No Accessibility Permissions

If you're uncomfortable granting permissions, you can:

1. **Skip the global hotkeys** - Don't grant permissions
2. **Use menu bar paste** - Click 🎤 → "Paste Transcripts"
3. **Use in-app buttons** - Open window and click paste button
4. **Manually copy** - Select text and `Cmd+C`

Everything works except `Cmd+Shift+V` and `Cmd+Shift+R` global hotkeys.
