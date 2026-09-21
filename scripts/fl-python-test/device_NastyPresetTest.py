# name=Nasty Preset Test

import plugins
import ui

TEST_CHANNEL = 0


def OnInit():
    plugins.nextPreset(TEST_CHANNEL)
    ui.setHintMsg(f"Nasty Preset Test: called plugins.nextPreset({TEST_CHANNEL})")


def OnDeInit():
    ui.setHintMsg("Nasty Preset Test: unloaded")
