# MIDIBrain
Prototype for a Brain-Computer-Interface that allows modulating MIDI-CC parameters.

This is the result of my Bachelor Thesis that I wrote back in 2018/2019.
The Goal of the Thesis was to explore the possibilites of using EEG (Electroencephalography) to modulate musical paramters in DAWs (Digital Audio Workstations).

In simpler terms: I wanted to build a tool that lets you perform music by using just your brain!

At it's core, MIDIBrain takes incoming EEG data in realtime using the [Fieldtrip buffer](https://github.com/fieldtrip/fieldtrip/tree/master), calaculates the power of Alpha and Beta waves and converts them into two separate streams of MIDI-CC Messages, respectively.
The outgoing MIDI-CCs can then be mapped onto any parameter inside of any DAW to modulate Audio Effects or Virtual Instruments.

This software uses the FieldTrip buffer open source library. See http:/www.fieldtriptoolbox.org for details.
The FieldTrip buffer is used under the GNU-GPL License, Version 3.

# Installation and usage
## Requirements
### Windows
In order for MIDIBrain to be able to send out MIDI messages into a DAW, an additional driver called [LoopBe1](https://nerds.de/en/loopbe1.html) is needed.
You can download it (free for personal use) here: https://nerds.de/en/download.html

### MacOS
So far, MIDIBrain has only been tested on Windows Machines. Hence, only `.exe`s are provided in this repository. You can check out the source code and try to get it to work on your MacOS device though!

### Install required packages
run `pip install -r requirements.txt`

### Running the program
- Start the FieldTrip buffer for your EEG System
- Run `python source/midibrain.py`
- MIDIBrain will try to conect to the FieldTrip buffer via localhost:1972 per default. You can change the hostname and port under *Configuration > FieldTrip connection*
- After successful connection to the buffer, the *Start* button will be enabled and you will be able to select the EEG channels that you want to use the data from.

![midibrain](https://github.com/user-attachments/assets/8766a2e1-7a26-4732-91f1-27ab6a7c7a80)

### Calibration
- In order for the Mapping of the wave power to MIDI values to work properly, a calibration is needed.
- In the bottom left corner, press *Calibrate*
- Follow the instructions on the second window
- The calibration takes one minute each, for the Alpha and the Beta waves
- During the calibration the minimum and maximum values of the wave powers are measured, and saved for the ongoing session (A new calibration will overwrite the previous values)

### MIDI mapping
- Make sure you have installed the LoopBe1 MIDI Driver and configured your DAW to receive MIDI Input from it
- On the right side of the screen there is a button for each band (Alpha and Beta) that starts the MIDI Mapping
- During Mapping, MIDIBrain will send continuous control change messages to be received by a DAW. Think of it as turning a control knob on a midi controller, to map it to a specific parameter.
- Channel 0, CC1 for Alphawaves and channel 0, CC2 for Betawaves
- Once the MIDI mapping is started, you can start the mapping in your DAW aswell and select one or multiple parameters you want to control with the respective brain waves
- Press the button again to end the mapping

### Adjusting the stepsize and moving average
- The stepsize tells by how many samples the calculation window is moved. The blocksize is always equal to the sampling frequency, so for a sample frequency of 512, a stepsize of 1/2 block means that after each calculation the window is moved by 256 samples.
The smaller the stepsize, the more values are calculated per second and the greater the time-resolution of the curve becomes. Depending on the computing power of you machine, a too small step-size might lead to higher latency.

- The moving average adjusts the smoothness of the output curve. The higher the moving average, the more resilient the curve is to outliers in the measurements. The raw calculated power values are represented by the gray line in the graphs, while the output values are represented by the colored line.
If the moving average is set to 1, the raw curve is equal to the smoothed curve.

### Demo (Playback mode)
Don't have an EEG? No problem. To see what MIDIBrain does, you can playback previously recorded EEG data.
For that you will first have to run the `FieldTrip/demobuffer.exe`.
Now in the MIDIBrain application, go to *File > Replay recording*.
For demo purposes you can open the file `example-eeg-data/eeg_rec.csv`.
Once the file has been successfully loaded into MIDIBrain, you can press *Start* and the playback will begin.
You can adjust the blocksize and the moving average, and map the Alpha and Beta channel to whatever MIDI-controllable parameter in your DAW that you like.
