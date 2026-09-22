# name=Nasty Preset Test
# receiveFrom=Nasty Preset Test

import plugins
import ui
import midi

TEST_CHANNEL = 0


def OnInit():
    ui.setHintMsg(
        f"Nasty Preset Test loaded on ch{TEST_CHANNEL}. "
        f"Play any note to call plugins.nextPreset()."
    )
    plugins.nextPreset(TEST_CHANNEL)
    ui.setHintMsg(f"OnInit: called plugins.nextPreset({TEST_CHANNEL})")


def OnMidiMsg(event):
    if event.midiId == midi.MIDI_NOTEON and event.data2 > 0:
        plugins.nextPreset(TEST_CHANNEL)
        ui.setHintMsg(f"MIDI note: called plugins.nextPreset({TEST_CHANNEL})")
        event.handled = True


def OnDeInit():
    ui.setHintMsg("Nasty Preset Test unloaded")
