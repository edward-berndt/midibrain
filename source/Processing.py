import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from events import Events
from scipy import signal
from scipy.integrate import simpson

import FieldTrip


class Processing:
    """
    Provides methods for the EEG signal processing
    Author: Edward Berndt
    """

    def __init__(self):
        # FieldTrip related variables
        self.__ftc = FieldTrip.Client()
        self.sfreq = 0
        self.block_size = 512
        self.sample_n = 0
        self.n_channels = 0
        self.picked_channels = np.array([], dtype=int)

        # general Processing variables
        self._glide = 1
        self._average = 20

        # data arrays
        self.raw_data = np.array([])
        self.raw_alphas = np.array([])
        self.raw_betas = np.array([])
        self.av_alphas = np.array([])
        self.av_betas = np.array([])

        # raw data from the calibration gets saved here and can be used for recalibration
        self.cal_alpha = np.array([])
        self.cal_beta = np.array([])

        # min and max values of the alpha and beta power due to calibration
        self.alpha_min = 0
        self.alpha_max = 1
        self.beta_min = 0
        self.beta_max = 1

        # gets raised if new alpha/beta values are calculated
        self.new_values_event = Events()
        self.connection_changed = Events()
        self.calibration_progress_changed = Events()

    def reset_fieldtrip_vars(self):
        self.sfreq = 0
        self.block_size = 512
        self.sample_n = 0
        self.n_channels = 0
        self.picked_channels = np.array([], dtype=int)

    def clear_vals(self):
        self.raw_alphas = np.array([])
        self.raw_betas = np.array([])
        self.av_alphas = np.array([])
        self.av_betas = np.array([])

    def connect(self, name, port):
        """
        Connects the FieldTrip Client to given hostname and port
        :param name: name of the host
        :param port: port number
        :return: True if connection was successful, False if not
        """
        connected = False
        try:
            self.__ftc.connect(name, port)  # might throw IOError
        except IOError:
            raise
        header = self.__ftc.getHeader()
        if header is None:
            raise IOError("Connection to FieldTrip failed: no Header")
        self.sfreq = header.fSample
        self.block_size = self.sfreq
        self.n_channels = header.nChannels
        if self.raw_data.size == 0:
            self.raw_data = self.raw_data.reshape((0, self.n_channels))
        self.connection_changed.on_change(self.is_connected())
        print("connected to FieldTrip")

    def disconnect(self):
        """
        Disconnects the FieldTrip Client
        :return:
        """
        self.__ftc.disconnect()
        self.reset_fieldtrip_vars()
        self.connection_changed.on_change(self.is_connected())
        print("disconnected from FieldTrip")

    def set_glide(self, glide):
        self._glide = glide

    def set_average(self, av):
        self._average = av

    def set_active_channels(self, chans):
        """
        Specifies the channels that should be included in the calculation of the powers
        :param chans: list-like with the channel numbers from 0 to n_channels
        :return:
        """
        if len(chans) > self.n_channels:
            raise ValueError('There are only ' + str(self.n_channels) + ' channels')
        elif len(chans) == 0:
            self.picked_channels = chans
        elif max(chans) >= self.n_channels or min(chans) < 0:
            raise ValueError('Values for chans must be within range from 0 to ' + str(self.n_channels - 1))
        else:
            self.picked_channels = chans

    def activate_channel(self, chan_nr):
        if chan_nr >= self.n_channels or chan_nr < 0:
            raise ValueError('Values for chans must be within range from 0 to ' + str(self.n_channels - 1))
        else:
            chans = np.append(self.picked_channels, int(chan_nr))
            chans = np.unique(chans)
            self.set_active_channels(chans)

    def deactivate_channel(self, chan_nr):
        i = np.argwhere(self.picked_channels == chan_nr)
        chans = np.delete(self.picked_channels, i)
        self.set_active_channels(chans)

    def is_connected(self):
        return self.__ftc.isConnected

    def get_vals_per_sec(self):
        """
        :return: the amount of calculated A/B values per second,
                    depending on the current samplerate, blocksize and glide
        """
        val_per_sec = int(self.sfreq / (self.block_size / self._glide))
        return val_per_sec

    def get_data(self):
        """
        retrieves the next block of data from the FieldTrip Client
        :return: array of data with the length of set blocksize
        """
        if not self.__ftc.isConnected:
            return [], False

        header = self.__ftc.getHeader()
        if header.nSamples >= self.sample_n + self.block_size:
            stop = self.sample_n + self.block_size - 1
            d = self.__ftc.getData([self.sample_n, stop])
            return d, True
        else:
            return [], False

    def get_psd(self, x):
        """
        calculates the frequency spectrum of the given block x with the sampling rate sf
        :param x: array of values
        :return: freqs the frequency indices and psd the power of each frequency
        """
        freqs, psd = signal.welch(x, self.sfreq, nperseg=x.size)
        return freqs, psd

    def get_band_power(self, x, lo, up):
        """
        calculates the bandpower of the given data within the given band
        :param x: array of values. If x is multidimensional, the mean of the power of each dimension is calculated
        :param lo: lower limit of the band
        :param up: upper limit of the band
        :return: the band power
        """
        if len(self.picked_channels) == 0:
            return np.array([])
        powers = np.array([])
        for i in self.picked_channels:
            freq_res = x[:, i].size / self.sfreq
            freqs, psd = self.get_psd(x[:, i])
            band = np.logical_and(freqs >= lo, freqs <= up)
            power = simpson(y=psd[band], dx=freq_res, axis=0)
            powers = np.append(powers, power)
        mean_power = np.mean(powers)
        return mean_power

    def set_latest_sample(self):
        """
        sets the current sample_n to the latest sample of the FieldTrip Client
        :return:
        """
        self.sample_n = self.__ftc.getHeader().nSamples

    def get_next_block(self):
        """
        retrieves the next block from the buffer, if available. stores it in the self.raw_data array
        :return: the block of data + True if new data was available, False if not
        """
        d, has_new = self.get_data()
        if has_new:
            step = int(self.block_size / self._glide)
            self.sample_n += step
            new_samples = d[-step:, :]
            self.raw_data = np.concatenate((self.raw_data, new_samples), axis=0)
        return d, has_new

    def process_block(self, d, raw_alphas, raw_betas):
        """
        processes the given block d. calculates its alpha and beta power raw as well as averaged
        and stores it in the given arrays
        :param raw_betas: an array with the last raw beta powers to calculate the average power from
        :param raw_alphas: an array with the last raw alpha powers to calculate the average power from
        :param d: (data) the block
        :return: the averaged alpha and beta value
        """
        raw_alpha_power = None
        raw_beta_power = None
        av_alpha_power = None
        av_beta_power = None
        if len(self.picked_channels) != 0 and len(d[:, 0]) >= self.block_size:
            raw_alpha_power = self.get_band_power(d, 8, 13)
            raw_beta_power = self.get_band_power(d, 14, 27)

            raw_alphas = np.append(raw_alphas, raw_alpha_power)
            raw_betas = np.append(raw_betas, raw_beta_power)

            av_alpha_power = np.mean(raw_alphas[-self._average:])
            av_beta_power = np.mean(raw_betas[-self._average:])
        return raw_alpha_power, raw_beta_power, av_alpha_power, av_beta_power

    def start_processing(self, running):
        """
        starts retrieving data from the buffer and calculating the alpha and beta power.
        Raises the new_values event for every calculated value.
        :param running: requestflag for stopping the processing while running on another Thread
        :return:
        """
        self.set_latest_sample()
        print("processing started")
        while running.is_set():
            d, has_new = self.get_next_block()
            if has_new:
                raw_alpha, raw_beta, av_alpha, av_beta = self.process_block(d, self.raw_alphas, self.raw_betas)
                if av_alpha is not None:
                    self.raw_alphas = np.append(self.raw_alphas, raw_alpha)
                    self.raw_betas = np.append(self.raw_betas, raw_beta)
                    self.av_alphas = np.append(self.av_alphas, av_alpha)
                    self.av_betas = np.append(self.av_betas, av_beta)
                    self.new_values_event.on_change(av_alpha, av_beta)

        print("processing finished")

    def recalibrate(self):
        """
        uses the recorded calibration data to calculate the min and max values of alpha/beta power
        with the current glide and average settings
        :return:
        """

        av_alphas = []
        av_betas = []
        cals = [self.cal_alpha, self.cal_beta]
        for cal in cals:
            raw_alphas = []
            raw_betas = []
            if len(cal) > 0:
                for i in range(1, int(len(cal) * self._glide / self.block_size)):
                    start = int((self.block_size * (i - 1)) / self._glide)
                    stop = int(start + self.block_size)
                    block = cal[start:stop, :]
                    raw_alpha, raw_beta, av_alpha, av_beta = self.process_block(block, raw_alphas, raw_betas)
                    if raw_alpha is not None:
                        raw_alphas.append(raw_alpha)
                        raw_betas.append(raw_beta)
                        av_alphas.append(av_alpha)
                        av_betas.append(av_beta)
        if len(av_alphas) != 0:
            self.alpha_max = max(av_alphas)
            self.alpha_min = min(av_alphas)
        if len(av_betas) != 0:
            self.beta_max = max(av_betas)
            self.beta_min = min(av_betas)


class CalibrationThread(QThread):
    sig_calibration_progress = pyqtSignal(int)

    def __init__(self, processing, alpha, beta, parent=None):
        super(CalibrationThread, self).__init__(parent)
        self.processing = processing
        self.alpha = alpha
        self.beta = beta
        self.start()

    def run(self):
        self.calibrate(self.alpha, self.beta)

    def calibrate(self, cal_a, cal_b):
        """
        records one minute of raw data, that gets used to calibrate the min and max values of the alpha/beta power
        :param cal_a: if True, the recorded data gets used to calibrate alpha power
        :param cal_b: if True, the recorded data gets used to calibrate beta power
        :return:
        """
        if not cal_a and not cal_b:
            raise ValueError('at least one of both parameters must be True')
        proc = self.processing
        proc.set_latest_sample()
        val_sec = proc.get_vals_per_sec()
        duration = 60  # duration of the calibration in sec
        minute = val_sec * duration
        i = 1
        while i <= minute:
            d, has_new = proc.get_next_block()
            if has_new:
                progress = int(100 / minute * i)
                self.sig_calibration_progress.emit(progress)
                # self.calibration_progress_changed.on_change(int(100 / minute * i))  # calculate percentage
                i += 1

        cal_data = proc.raw_data[-int(minute * proc.block_size):, :]
        proc.raw_data = proc.raw_data[:-int(minute * proc.block_size), :]
        if cal_a:
            proc.cal_alpha = cal_data
        if cal_b:
            proc.cal_beta = cal_data
        proc.recalibrate()
