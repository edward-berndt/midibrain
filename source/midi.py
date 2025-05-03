import time
import rtmidi
from rtmidi._rtmidi import InvalidPortError

"""
Author: Edward Berndt
"""

midi_out = rtmidi.MidiOut()
cc_statusbyte = 0xB0
is_mapping = False


def open_midi_port(port_nr=1):
    """
    opens a midi port. if not available opens a virtual port
    :param port_nr:
    :return:
    """
    available_ports = midi_out.get_ports()
    try:
        if available_ports:
            midi_out.open_port(port_nr)
            print("MIDI port opened")
        else:
            midi_out.open_virtual_port("My virtual output")
    except InvalidPortError:
        raise


def send_control_change(value, control_number=1):
    """sends a MIDI control change message with the given value from 0-127"""
    cchange = [cc_statusbyte, control_number, value]  # controlchange message
    midi_out.send_message(cchange)


def to_midi(x, min_, max_):
    """
    Converts the value x into the given range from min_ to max_
    """
    if x > max_:
        x = max_
    if x < min_:
        x = min_
    return int(x * 127 / (max_ - min_))


def start_mapping(control_number):
    """
    sends CC messages with the specified controller number until stop_mapping is called
    :param control_number:
    :return:
    """
    global is_mapping
    is_mapping = True
    while is_mapping:
        send_control_change(0, control_number)
        time.sleep(0.1)


def stop_mapping():
    """
    stops the mapping process initiated by start_mapping
    :return:
    """
    global is_mapping
    is_mapping = False
