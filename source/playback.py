import time
import numpy as np
import pandas as pd
import FieldTrip
from events import Events

"""
Author: Edward Berndt
"""

class EEGPlayback:
    def __init__(self, csv_path, host='localhost', port=1972):
        self.csv_path = csv_path
        self.host = host
        self.port = port
        self.__ftc = FieldTrip.Client()
        self.playback_finished = Events()

    def load_data(self):
        with open(self.csv_path, 'r') as f:
            lines = f.readlines()

        # Parse sample rate from first line (e.g., "# 512.0")
        self.sample_rate = float(lines[0].strip().lstrip('#').strip())

        # Load EEG data (remaining lines)
        from io import StringIO
        data_str = ''.join(lines[1:])
        self.data = pd.read_csv(StringIO(data_str), header=None).values.astype(np.float32)
        self.n_samples, self.n_channels = self.data.shape

    def connect(self):
        print(f"Connecting to FieldTrip buffer at {self.host}:{self.port}...")
        self.__ftc.connect(self.host, self.port)

        print("Sending header...")
        labels = [f"chan{i+1}" for i in range(self.n_channels)]
        self.__ftc.putHeader(
            nChannels=self.n_channels,
            fSample=self.sample_rate,
            dataType=FieldTrip.DATATYPE_FLOAT32,
            labels=labels
        )

    def stream(self, running):
        block_size = int(self.sample_rate)
        total_blocks = self.n_samples // block_size
        print(f"Streaming {total_blocks} blocks of {block_size} samples...")

        for i in range(total_blocks):
            if running.is_set():
                block = self.data[i * block_size:(i + 1) * block_size, :]
                self.__ftc.putData(block)
                print(f"Block {i+1}/{total_blocks} sent.")
                time.sleep(1.0)  # Simulate real-time streaming
            else:
                print('Playback aborted')
                return

        print("All blocks sent.")
        self.playback_finished.on_change()

    def disconnect(self):
        self.__ftc.disconnect()
        print("Disconnected from FieldTrip buffer.")

    def getAllData(self):
        return self.data

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python playback.py <eeg_csv_file> [hostname] [port]")
        sys.exit(1)

    csv_path = sys.argv[1]
    hostname = sys.argv[2] if len(sys.argv) > 2 else 'localhost'
    port = int(sys.argv[3]) if len(sys.argv) > 3 else 1972

    player = EEGPlayback(csv_path, hostname, port)
    player.load_data()
    player.connect()
    player.stream()
    player.disconnect()
