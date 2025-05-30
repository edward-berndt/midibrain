import sys
import threading
import winsound
import os

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import pyqtSlot, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication, QCheckBox, QMessageBox, QFileDialog
from PyQt5.uic import loadUi
from rtmidi._rtmidi import InvalidPortError

import midi
from Processing import *
from Playback import EEGPlayback

"""
Author: Edward Berndt
"""

app = None
gui = None
cal_gui = None
ft_gui = None
proc = None
playback = None

# for connection to FieldTrip
host_name = 'localhost'
port_nr = 1972

# will hold plotlines for both raw and averaged alpha/beta values
alpha_graph = None
beta_graph = None
alpha_plot = dict()
beta_plot = dict()

# midi control numbers
alpha_control_nr = 1
beta_control_nr = 2

# Threading related
# timer = QTimer()
connection_thread = None
processing_thread = None
cal_thread = None
playback_thread = None
connect_run = threading.Event()
proc_run = threading.Event()
playback_run = threading.Event()

def show_dialog(text):
    box = QMessageBox()
    box.setText(text)
    box.setWindowTitle("MIDIBrain")
    box.setStandardButtons(QMessageBox.Ok)
    box.exec_()


def show_calibration():
    stop_processing()
    cal_gui.show()


def show_ft_config():
    ft_gui.show()


def calibrate(alpha, beta):
    global cal_thread
    cal_gui.a_calib_button.setEnabled(False)
    cal_gui.b_calib_button.setEnabled(False)
    cal_gui.cal_progbar.setEnabled(True)
    cal_thread = CalibrationThread(proc, alpha, beta)
    cal_thread.sig_calibration_progress.connect(update_progbar)
    cal_thread.start()

@pyqtSlot(int)
def on_connection_changed(status):
    print(f'[on_connection_changed] connection status: {status}')
    update_buttons()
    update_labels()
    update_channel_boxes()
    update_spinboxes()

@pyqtSlot(PowerValues)
def on_new_values(new_values):
    print(f'received new power values: {new_values}')
    a = midi.to_midi(new_values.av_alpha, proc.alpha_min, proc.alpha_max)
    b = midi.to_midi(new_values.av_beta, proc.beta_min, proc.beta_max)
    midi.send_control_change(a, 1)
    midi.send_control_change(b, 2)
    update_graph()

@pyqtSlot(int)
def update_progbar(val):
    cal_gui.cal_progbar.setValue(val)
    if val == 100:
        cal_gui.cal_progbar.setEnabled(False)
        cal_gui.a_calib_button.setEnabled(True)
        cal_gui.b_calib_button.setEnabled(True)
        winsound.MessageBeep(winsound.MB_OK)

def save_data():
    stop_processing()
    data = proc.raw_data
    name = QFileDialog.getSaveFileName(gui, "Save recorded EEG data", filter='Text File (*.csv)',
                                       initialFilter='Text File (*.csv)')[0]
    if name:
        np.savetxt(name, data, header=str(proc.sfreq), delimiter=",")
    show_dialog('Successfully saved!')


def load_data():
    global playback, proc, host_name, port_nr, gui
    stop_processing()
    file_name = QFileDialog.getOpenFileName(gui, "Open recorded EEG data", filter='Text File (*.csv)', initialFilter='Text File (*.csv)')[0]
    playback = EEGPlayback(file_name, host_name, port_nr)
    playback.load_data()
    playback.connect()
    playback.playback_finished.on_change += stop_playback
    data = playback.getAllData()
    proc.clear_vals()
    proc.reset_fieldtrip_vars()
    proc.calibrate_from_recording(data)
    connect()

    gui.input_label_value.setText(f'playback from {os.path.basename(file_name)}')
    gui.unload_data_button.setVisible(True)

    show_dialog('EEG recording loaded. To start playback, press Start.')
    
def unload_data():
    global playback, gui
    stop_processing()
    playback.disconnect()
    playback = None

    gui.input_label_value.setText('live EEG data')
    gui.unload_data_button.setVisible(False)


def init_graph():
    global gui, proc, timer, alpha_graph, beta_graph

    pg.setConfigOptions(antialias=True)
    alpha_graph = pg.PlotWidget(name="alpha plot")
    beta_graph = pg.PlotWidget(name="beta plot")
    al = gui.alpha_horizontalLayout
    bl = gui.beta_horizontalLayout
    alpha_graph.setBackground('w')
    beta_graph.setBackground('w')
    al.insertWidget(0, alpha_graph, 8)
    bl.insertWidget(0, beta_graph, 8)
    alpha_graph.getPlotItem().setTitle("Alpha waves")
    alpha_graph.getPlotItem().vb.setLimits(xMin=0, yMin=0)
    beta_graph.getPlotItem().setTitle("Beta waves")
    beta_graph.getPlotItem().vb.setLimits(xMin=0, yMin=0)
    alpha_plot["raw"] = alpha_graph.getPlotItem().plot(pen=QColor(155, 155, 155), width=10)
    alpha_plot["averaged"] = alpha_graph.getPlotItem().plot(pen='b', width=10)
    beta_plot["raw"] = beta_graph.getPlotItem().plot(pen=QColor(155, 155, 155), width=50)
    beta_plot["averaged"] = beta_graph.getPlotItem().plot(pen=QColor(234, 98, 0), width=50)
    alpha_graph.setYRange(proc.alpha_min, proc.alpha_max)
    beta_graph.setYRange(proc.beta_min, proc.beta_max)


def update_graph():
    global alpha_graph, beta_graph
    if proc.connection_status == ConnectionStatus.CONNECTED:
        alpha_plot["raw"].setData(proc.power_values.raw_alpha)
        alpha_plot["averaged"].setData(proc.power_values.av_alpha)
        beta_plot["raw"].setData(proc.power_values.raw_beta)
        beta_plot["averaged"].setData(proc.power_values.av_beta)
        alpha_graph.setYRange(proc.alpha_min - proc.alpha_min * 1.1, proc.alpha_max * 1.1)
        beta_graph.setYRange(proc.beta_min - proc.beta_min * 1.1, proc.beta_max * 1.1)
        app.processEvents()


def init_channel_boxes():
    global gui, proc
    gui.cb_channel_all.clicked.connect(on_all_channels_checked)
    connect_channel_boxes()
    update_channel_boxes()


def connect_channel_boxes():
    cont = gui.channel_cb_container
    cb_list = cont.findChildren(QCheckBox)
    for i in range(0, len(cb_list)):
        cb_list[i].stateChanged.connect(lambda checked, a=i: on_channel_checked(cb_list[a], a))

def disconnect_channel_boxes():
    cont = gui.channel_cb_container
    cb_list = cont.findChildren(QCheckBox)
    for i in range(0, len(cb_list)):
        cb_list[i].stateChanged.disconnect()


def update_channel_boxes():
    global gui, proc
    cont = gui.channel_cb_container
    cb_list = cont.findChildren(QCheckBox)
    for i in range(0, len(cb_list)):
        if proc.n_channels > i:
            cb_list[i].setEnabled(True)
            cb_list[i].setChecked(i in proc.active_channels)
        else:
            cb_list[i].setChecked(False)
            cb_list[i].setEnabled(False)
    gui.cb_channel_all.setEnabled(proc.connection_status == ConnectionStatus.CONNECTED)
    gui.cb_channel_all.setChecked(len(proc.active_channels) == proc.n_channels)


@pyqtSlot(QCheckBox, int)
def on_channel_checked(cb, chan_nr):
    global gui, proc
    if cb.isChecked():
        proc.activate_channel(chan_nr)
    else:
        proc.deactivate_channel(chan_nr)
        gui.cb_channel_all.setChecked(False)


@pyqtSlot()
def on_all_channels_checked():
    global gui, proc
    cb_all = gui.cb_channel_all
    if cb_all.isChecked():
        proc.set_active_channels(np.arange(proc.n_channels))
    else:
        proc.set_active_channels([])


@pyqtSlot()
def on_connect_button_pressed():
    global host_name, port_nr
    if proc.connection_status == ConnectionStatus.CONNECTED or proc.connection_status == ConnectionStatus.WAIT_FOR_HEADER:
        disconnect()
    else:
        host_name = ft_gui.hostname_input.text()
        port_nr = int(ft_gui.portnr_input.text())
        connect()


def connect():
    global connection_thread, host_name, port_nr
    if connection_thread is not None and connection_thread.isRunning():
        connect_run.clear()
        connection_thread.wait()
    connect_run.set()
    connection_thread = ConnectionThread(proc, host_name, port_nr, connect_run)
    connection_thread.sig_connection_status.connect(on_connection_changed)
    connection_thread.start()

def disconnect():
    if connection_thread is not None and connection_thread.isRunning():
        connect_run.clear()
        connection_thread.wait()
    if processing_thread is not None and processing_thread.isRunning():
        stop_processing()
    proc.disconnect()
    on_connection_changed(proc.connection_status)

def on_connection_error():
    show_dialog('Connection to FieldTrip failed')

@pyqtSlot()
def on_start():
    global gui, proc
    if proc_run.is_set():
        stop_playback()
        stop_processing()
        return
    
    if playback is not None:
        start_playback()
    else:
        start_processing()


def start_processing():
    global proc, processing_thread, proc_run
    gui.start_button.setText('Stop')
    proc_run.set()
    processing_thread = ProcessingThread(proc, proc_run)
    processing_thread.sig_calculated_values.connect(on_new_values)
    processing_thread.start()


def stop_processing():
    global processing_thread
    if processing_thread is not None:
        proc_run.clear()
        processing_thread.wait()
        processing_thread = None
        gui.start_button.setText('Start') 

def start_playback():
    global playback, playback_thread
    playback_run.set()
    playback_thread = threading.Thread(target=playback.stream, args=(playback_run,))
    playback_thread.daemon = True
    playback_thread.start()
    start_processing()

def stop_playback():
    global playback_thread
    if playback_thread is not None:
        playback_run.clear()
        playback_thread = None
        stop_processing()

@pyqtSlot()
def on_alpha_map_pressed():
    global gui
    mapping_thread = threading.Thread(target=midi.start_mapping, args=[alpha_control_nr], daemon=True)
    if gui.alpha_map_button.isChecked():
        gui.beta_map_button.setEnabled(False)
        mapping_thread.start()
    else:
        midi.stop_mapping()
        gui.beta_map_button.setEnabled(True)


@pyqtSlot()
def on_beta_map_pressed():
    global gui
    mapping_thread = threading.Thread(target=midi.start_mapping, args=[beta_control_nr])
    mapping_thread.daemon = True
    if gui.beta_map_button.isChecked():
        gui.alpha_map_button.setEnabled(False)
        mapping_thread.start()
    else:
        midi.stop_mapping()
        gui.alpha_map_button.setEnabled(True)

def on_header_changed():
    gui.status_sfreq_label.setText(str(int(proc.sfreq)))
    gui.status_channels_label.setText(str(proc.n_channels))
    update_channel_boxes()

def update_buttons():
    if proc.connection_status == ConnectionStatus.CONNECTED:
        gui.start_button.setEnabled(True)
        gui.calibrate_button.setEnabled(True)
    else:
        gui.start_button.setEnabled(False)
        gui.calibrate_button.setEnabled(False)

def update_labels():
    global gui, proc
    if proc.connection_status == ConnectionStatus.CONNECTED:
        gui.status_fieldtrip_label.setText('Connected')
        gui.status_sfreq_label.setText(str(int(proc.sfreq)))
        gui.status_channels_label.setText(str(proc.n_channels))
        ft_gui.connect_button.setText('Disconnect')
        if not playback_run.is_set():
            gui.input_label_value.setText('live EEG data')
    if proc.connection_status == ConnectionStatus.WAIT_FOR_HEADER:
        gui.status_fieldtrip_label.setText('Waiting for input')
        gui.status_sfreq_label.setText('-')
        gui.status_channels_label.setText('-')
        gui.input_label_value.setText('No input')
        ft_gui.connect_button.setText('Disconnect')
    if proc.connection_status == ConnectionStatus.NOT_CONNECTED:
        gui.status_fieldtrip_label.setText('Not Connected')
        gui.status_sfreq_label.setText('-')
        gui.status_channels_label.setText('-')
        gui.input_label_value.setText('No input')
        ft_gui.connect_button.setText('Connect')
    gui.val_per_sec_label.setText(str(proc.get_vals_per_sec()))


def update_spinboxes():
    cont = False
    if proc_run.is_set():
        stop_processing()
        cont = True
    glide = gui.glide_spinBox.value()
    av = gui.average_spinBox.value()
    proc.set_glide(glide)
    proc.set_average(av)
    proc.recalibrate()
    update_labels()
    if cont:
        start_processing()


@pyqtSlot(int)
def change_average(av):
    global proc
    t = threading.Thread(target=proc.set_average, args=(av,))
    t.daemon = True
    t.start()


def init_menubar():
    gui.ft_item.triggered.connect(show_ft_config)
    gui.item_save.triggered.connect(save_data)
    gui.item_open.triggered.connect(load_data)

def init_buttons():
    global gui, cal_gui, ft_gui, proc
    gui.start_button.clicked.connect(on_start)
    gui.start_button.setEnabled(False)
    gui.alpha_map_button.clicked.connect(on_alpha_map_pressed)
    gui.beta_map_button.clicked.connect(on_beta_map_pressed)
    gui.calibrate_button.clicked.connect(show_calibration)
    gui.calibrate_button.setEnabled(False)
    gui.apply_button.clicked.connect(update_spinboxes)
    gui.unload_data_button.clicked.connect(unload_data)
    gui.unload_data_button.setVisible(False)

    cal_gui.a_calib_button.clicked.connect(lambda: calibrate(True, False))
    cal_gui.b_calib_button.clicked.connect(lambda: calibrate(False, True))
    ft_gui.connect_button.clicked.connect(on_connect_button_pressed)


def main():
    global app, gui, cal_gui, ft_gui, proc

    #dirname = os.path.dirname(__file__)
    #demo_buffer_path = os.path.join(dirname, '../FieldTrip/demo_buffer.exe')
    #os.startfile(demo_buffer_path)

    app = QApplication(sys.argv)
    dir_path = os.path.dirname(os.path.realpath(__file__))
    gui = loadUi(dir_path + "/view/main.ui")
    cal_gui = loadUi(dir_path + "/view/calibration.ui")
    ft_gui = loadUi(dir_path + "/view/fieldtrip_dialog.ui")
    gui.show()
    proc = Processing()
    proc.header_changed.on_change += lambda header: on_header_changed()
    proc.channels_changed.on_change += lambda chans: update_channel_boxes()

    try:
        midi.open_midi_port()
    except InvalidPortError:
        show_dialog("MIDI port could not be opened. Please install the LoopBe1 MIDI driver.")

    init_buttons()
    init_menubar()
    init_channel_boxes()
    update_labels()
    update_spinboxes()
    init_graph()
    connect()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
