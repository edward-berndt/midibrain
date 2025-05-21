# MIDIBrain
Prototype for a Brain-Computer-Interface that allows modulating MIDI-CC parameters.

This is the result of my Bachelor Thesis that I wrote back in 2018/2019.
The Goal of the Thesis was to explore the possibilites of using EEG (Electroencephalography) to modulate musical paramters in DAWs (Digital Audio Workstations).

In simpler terms: I wanted to build a tool that lets you perform music by using just your brain!

At it's core, MIDIBrain takes incoming EEG data in realtime using the [Fieldtrip buffer](https://github.com/fieldtrip/fieldtrip/tree/master), calaculates the power of Alpha and Beta waves and converts them into two separate streams of MIDI-CC Messages, respectively.
The outgoing MIDI-CCs can then be mapped onto any parameter inside of any DAW to modulate Audio Effects or Virtual Instruments.

# Installation and usage
## Requirements
### Windows
In order for MIDIBrain to be able to send out MIDI messages into a DAW, an additional driver called [LoopBe1](https://nerds.de/en/loopbe1.html) is needed.
You can download it (free for personal use) here: https://nerds.de/en/download.html

### MacOS
So far, MIDIBrain has only been tested on Windows Machines. Hence, only `.exe`s are provided in this repository. You can check out the source code and try to get it to work on your MacOS device though!

This software uses the FieldTrip buffer open source library. See http:/www.fieldtriptoolbox.org for details.
The FieldTrip buffer is used under the GNU-GPL License, Version 3.

### Install required packages
run `pip install -r requirements.txt`

### Run the program
1. Run `FieldTrip/demobuffer.exe`
2. Run python `source/midibrain.py`

### Demo (Playback mode)
Don't have an EEG? No problem. To see what MIDIBrain does, you can playback previously recorded EEG data.
For that you will first have to run the `FieldTrip/demobuffer.exe`.
Now in the MIDIBrain application, go to *File > Replay recording*.
For demo purposes you can open the file `example-eeg-data/eeg_rec.csv`.
Once the file has been successfully loaded into MIDIBrain, you can press *Start* and the playback will begin.
You can adjust the blocksize and the moving average, and map the Alpha and Beta channel to whatever MIDI-controllable parameter in your DAW that you like.