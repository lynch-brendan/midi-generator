#include "GmSynth.h"

#include <fluidsynth.h>
#include <iostream>

namespace nasty {

GmSynth::GmSynth()
    : juce::AudioProcessor(BusesProperties().withOutput("Output", juce::AudioChannelSet::stereo(), true))
{
    settings = new_fluid_settings();
    // Small buffer + reasonable defaults for a real-time DAW context.
    fluid_settings_setnum(settings, "synth.sample-rate", 44100.0);
    fluid_settings_setint(settings, "synth.polyphony", 256);
    // We drive the render loop ourselves — no audio driver inside FluidSynth.
    fluid_settings_setstr(settings, "audio.driver", "file");
    synth = new_fluid_synth(settings);
}

GmSynth::~GmSynth() {
    if (synth)    delete_fluid_synth(synth);
    if (settings) delete_fluid_settings(settings);
}

bool GmSynth::loadSoundFont(const juce::String& sf2Path) {
    std::lock_guard<std::mutex> lock(mutex);
    if (!synth) return false;
    sfFontId = fluid_synth_sfload(synth, sf2Path.toRawUTF8(), /*resetPresets*/ 1);
    if (sfFontId < 0) {
        std::cerr << "[GmSynth] failed to load soundfont: " << sf2Path << std::endl;
        return false;
    }
    // Bind default program (0 = Acoustic Grand Piano) on MIDI channel 0.
    fluid_synth_program_select(synth, 0, sfFontId, /*bank*/ 0, /*preset*/ 0);
    return true;
}

void GmSynth::setProgram(int programNumber) {
    std::lock_guard<std::mutex> lock(mutex);
    // 0-127 = melodic GM programs. 128 = drum kit (bank 128 preset 0).
    // Clamp only when the value is out of the extended 0-128 range.
    currentProgram = juce::jlimit(0, 128, programNumber);
    if (!synth || sfFontId < 0) return;
    if (currentProgram == 128) {
        fluid_synth_program_select(synth, 0, sfFontId, 128, 0);
        isDrumChannel = true;
    } else {
        fluid_synth_program_select(synth, 0, sfFontId, 0, currentProgram);
        isDrumChannel = false;
    }
}

void GmSynth::prepareToPlay(double sampleRate, int /*blockSize*/) {
    std::lock_guard<std::mutex> lock(mutex);
    curSampleRate = sampleRate;
    if (settings) fluid_settings_setnum(settings, "synth.sample-rate", sampleRate);
    if (synth) fluid_synth_all_notes_off(synth, -1);
}

void GmSynth::processBlock(juce::AudioBuffer<float>& buf, juce::MidiBuffer& midi) {
    if (!synth) { buf.clear(); return; }

    // Deliver MIDI events at their sample offsets. FluidSynth handles them
    // immediately; sample-accurate scheduling isn't perfect but good enough
    // for typing-keyboard + hardware note-in latency.
    for (const auto meta : midi) {
        const auto& m = meta.getMessage();
        const int ch = 0; // We route all channels to fluid channel 0.
        if (m.isNoteOn()) {
            fluid_synth_noteon(synth, ch, m.getNoteNumber(), m.getVelocity());
        } else if (m.isNoteOff()) {
            fluid_synth_noteoff(synth, ch, m.getNoteNumber());
        } else if (m.isAllNotesOff() || m.isAllSoundOff()) {
            fluid_synth_all_notes_off(synth, ch);
        } else if (m.isController()) {
            fluid_synth_cc(synth, ch, m.getControllerNumber(), m.getControllerValue());
        } else if (m.isPitchWheel()) {
            fluid_synth_pitch_bend(synth, ch, m.getPitchWheelValue());
        }
    }

    const int numSamples = buf.getNumSamples();
    if (buf.getNumChannels() < 2) {
        buf.setSize(2, numSamples, false, true, true);
    }
    float* left  = buf.getWritePointer(0);
    float* right = buf.getWritePointer(1);
    fluid_synth_write_float(synth, numSamples, left, 0, 1, right, 0, 1);
}

} // namespace nasty
