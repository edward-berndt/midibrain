import sys
import threading
import winsound

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import pyqtSlot, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QApplication, QCheckBox, QMessageBox, QFileDialog
from PyQt5.uic import loadUi
from rtmidi._rtmidi import InvalidPortError

import midi
from Processing import Processing, CalibrationThread

"""
Author: Edward Berndt
"""

app = None
gui = None
cal_gui = None
ft_gui = None
proc = None

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
timer = QTimer()
processing_thread = None
proc_run = threading.Event()
cal_thread = None


def on_new_values(val_a, val_b):
    a = midi.to_midi(val_a, proc.alpha_min, proc.alpha_max)
    b = midi.to_midi(val_b, proc.beta_min, proc.beta_max)
    midi.send_control_change(a, 1)
    midi.send_control_change(b, 2)


def on_connection_changed(is_conn):
    if is_conn:
        gui.calibrate_button.setEnabled(True)
    else:
        gui.calibrate_button.setEnabled(False)
    update_labels()
    update_channel_boxes()
    update_spinboxes()


def show_dialog(text):
    box = QMessageBox()
    box.setText(text)
    box.setWindowTitle("BCI to MIDI")
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
    name = QFileDialog.getSaveFileName(gui, "Aufnahme speichern", filter='Text File (*.csv)',
                                       initialFilter='Text File (*.csv)')[0]
    if name:
        np.savetxt(name, data, header=str(proc.sfreq), delimiter=",")
    show_dialog('Erfolgreich gespeichert')


def load_data():
    # TODO: implement data loading
    pass


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
    alpha_graph.getPlotItem().setTitle("Alphastärke")
    beta_graph.getPlotItem().setTitle("Betastärke")
    alpha_plot["raw"] = alpha_graph.getPlotItem().plot(pen=QColor(155, 155, 155), width=10)
    alpha_plot["averaged"] = alpha_graph.getPlotItem().plot(pen='b', width=10)
    beta_plot["raw"] = beta_graph.getPlotItem().plot(pen=QColor(155, 155, 155), width=50)
    beta_plot["averaged"] = beta_graph.getPlotItem().plot(pen=QColor(234, 98, 0), width=50)
    alpha_graph.setYRange(proc.alpha_min, proc.alpha_max)
    beta_graph.setYRange(proc.beta_min, proc.beta_max)
    timer.timeout.connect(update_graph)
    timer.start(40)


def update_graph():
    global alpha_graph, beta_graph
    if proc.is_connected():
        alpha_plot["raw"].setData(proc.raw_alphas)
        alpha_plot["averaged"].setData(proc.av_alphas)
        beta_plot["raw"].setData(proc.raw_betas)
        beta_plot["averaged"].setData(proc.av_betas)
        alpha_graph.setYRange(proc.alpha_min - proc.alpha_min * 1.1, proc.alpha_max * 1.1)
        beta_graph.setYRange(proc.beta_min - proc.beta_min * 1.1, proc.beta_max * 1.1)
        app.processEvents()


def init_channel_boxes():
    global gui, proc
    gui.cb_channel_all.clicked.connect(on_all_channels_checked)
    check_all_channels(False)
    cont = gui.channel_cb_container
    cb_list = cont.findChildren(QCheckBox)
    for i in range(0, len(cb_list)):
        cb_list[i].stateChanged.connect(lambda checked, a=i: on_channel_checked(cb_list[a], a))
    update_channel_boxes()


def update_channel_boxes():
    global gui, proc
    cont = gui.channel_cb_container
    cb_list = cont.findChildren(QCheckBox)
    for i in range(0, len(cb_list)):
        if proc.n_channels > i:
            cb_list[i].setEnabled(True)
        else:
            cb_list[i].setChecked(False)
            cb_list[i].setEnabled(False)
    gui.cb_channel_all.setEnabled(proc.is_connected())
    gui.cb_channel_all.setChecked(False)


@pyqtSlot(QCheckBox, int)
def on_channel_checked(cb, chan_nr):
    global gui, proc
    if cb.isChecked():
        proc.activate_channel(chan_nr)
    else:
        proc.deactivate_channel(chan_nr)
        gui.cb_channel_all.setChecked(False)
    proc.recalibrate()


@pyqtSlot()
def on_all_channels_checked():
    global gui, proc
    cb_all = gui.cb_channel_all
    if cb_all.isChecked():
        check_all_channels(True)
    else:
        check_all_channels(False)


def check_all_channels(check):
    cont = gui.channel_cb_container
    cb_list = cont.findChildren(QCheckBox)
    for cb in cb_list:
        if cb.isEnabled():
            cb.setChecked(check)


def init_buttons():
    global gui, cal_gui
    gui.start_button.clicked.connect(on_start)
    gui.alpha_map_button.clicked.connect(on_alpha_map)
    gui.beta_map_button.clicked.connect(on_beta_map)
    gui.calibrate_button.clicked.connect(show_calibration)
    gui.apply_button.clicked.connect(update_spinboxes)
    cal_gui.a_calib_button.clicked.connect(lambda: calibrate(True, False))
    cal_gui.b_calib_button.clicked.connect(lambda: calibrate(False, True))
    ft_gui.connect_button.clicked.connect(on_connect)


@pyqtSlot()
def on_connect():
    global host_name, port_nr
    if proc.is_connected():
        proc.disconnect()
        ft_gui.connect_button.setText('Verbinden')
    else:
        host_name = ft_gui.hostname_input.text()
        port_nr = int(ft_gui.portnr_input.text())
        connect()


def connect():
    try:
        proc.connect(host_name, port_nr)
        ft_gui.connect_button.setText('Trennen')
    except IOError:
        show_dialog('Verbindung mit Fieldtrip gescheitert')


@pyqtSlot()
def on_start():
    global gui, proc, processing_thread
    if proc_run.isSet():
        stop_processing()
    else:
        start_processing()


def start_processing():
    global proc, processing_thread
    gui.start_button.setText('Stop')
    proc_run.set()
    processing_thread = threading.Thread(target=proc.start_processing, args=(proc_run,))
    processing_thread.daemon = True
    processing_thread.start()


def stop_processing():
    global processing_thread
    if processing_thread is not None:
        proc_run.clear()
        processing_thread.join()
        processing_thread = None
        gui.start_button.setText('Start')


@pyqtSlot()
def on_alpha_map():
    global gui
    mapping_thread = threading.Thread(target=midi.start_mapping, args=[alpha_control_nr])
    mapping_thread.daemon = True
    if gui.alpha_map_button.isChecked():
        gui.beta_map_button.setEnabled(False)
        mapping_thread.start()
    else:
        midi.stop_mapping()
        gui.beta_map_button.setEnabled(True)


@pyqtSlot()
def on_beta_map():
    global gui
    mapping_thread = threading.Thread(target=midi.start_mapping, args=[beta_control_nr])
    mapping_thread.daemon = True
    if gui.beta_map_button.isChecked():
        gui.alpha_map_button.setEnabled(False)
        mapping_thread.start()
    else:
        midi.stop_mapping()
        gui.alpha_map_button.setEnabled(True)


def update_labels():
    global gui, proc
    if proc.is_connected():
        gui.status_fieldtrip_label.setText('Verbunden')
        gui.status_sfreq_label.setText(str(int(proc.sfreq)))
        gui.status_channels_label.setText(str(proc.n_channels))
    else:
        gui.status_fieldtrip_label.setText('Nicht verbunden')
        gui.status_sfreq_label.setText('-')
        gui.status_channels_label.setText('-')
    gui.val_per_sec_label.setText(str(proc.get_vals_per_sec()))


def init_spinboxes():
    global gui
    update_spinboxes()


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


def main():
    global app, gui, cal_gui, ft_gui, proc
    app = QApplication(sys.argv)
    gui = loadUi("view/main.ui")
    cal_gui = loadUi("view/calibration.ui")
    ft_gui = loadUi("view/fieldtrip_dialog.ui")
    gui.show()
    proc = Processing()
    proc.new_values_event.on_change += on_new_values
    proc.connection_changed.on_change += on_connection_changed
    try:
        midi.open_midi_port()
    except InvalidPortError:
        show_dialog("Es konnte kein MIDI-Port geöffnet werden. Bitte installieren Sie den LoopBe1 MIDI-Treiber")
    init_buttons()
    init_menubar()
    init_channel_boxes()
    update_labels()
    init_spinboxes()
    init_graph()
    connect()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
