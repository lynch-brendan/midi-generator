# Test A — does FL Studio's Python door change presets?

**Mission this serves:** AI loads any FL preset by name.
**Question this answers:** Can code (not a click) actually change the loaded preset AND make it stick when the project is saved/reloaded?

## Install (one time)

```
mkdir -p ~/Documents/Image-Line/FL\ Studio/Settings/Hardware/Nasty\ Preset\ Test
cp device_NastyPresetTest.py ~/Documents/Image-Line/FL\ Studio/Settings/Hardware/Nasty\ Preset\ Test/
```

## Run the test

1. Open **FL Studio the app** (not through Nasty).
2. Load **FLEX** on the very first channel (channel 0). Note the current preset name shown in FLEX's title bar — call this "Preset A".
3. Options menu → MIDI Settings. In the Input list, find **"Nasty Preset Test"**, click it, enable it, and set Controller Type to **"Nasty Preset Test (user)"**.
4. Enable **Typing to piano** (or connect any MIDI keyboard).
5. Press a key. FL's status bar should show `Called plugins.nextPreset(0)` and FLEX's preset should visibly advance to "Preset B".
6. Press it 3 more times → should land on "Preset E".
7. **The definitive check:** save the project. Close it. Reopen it. Does FLEX show "Preset E" (state bridge crossed → mission door is real) or "Preset A" (same wall as MIDI PC → door is a mirage)?

## Report back

- Did steps 5–6 change FLEX visibly? (Y/N)
- Did the sound change when you played FLEX? (Y/N)
- After save+close+reopen, which preset was loaded? (A or E)
