import gi
import pyaudio
import threading
import numpy as np

gi.require_version('Gtk', '3.0')
from gi.repository import Gtk

class Goertzel:
    def __init__(self, target_freq, sample_rate, num_samples):
        self.target_freq = target_freq
        self.sample_rate = sample_rate
        self.num_samples = num_samples
        self.coeff = 2 * np.cos(2 * np.pi * target_freq / sample_rate)
        self.s = [0] * 2
        self.power = 0

    def reset(self):
        self.s = [0] * 2
        self.power = 0

    def process(self, sample):
        self.s[0] = sample + self.coeff * self.s[1]
        self.power = self.s[0] * self.s[0] + self.s[1] * self.s[1]
        self.s[1] = self.s[0]
        return self.power

class AudioDecoderApp(Gtk.Window):
    def __init__(self):
        super().__init__(title="Audio Decoder")
        self.set_border_width(10)
        self.set_default_size(400, 200)

        # Audio input selection
        self.audio_input_combo = Gtk.ComboBoxText()
        self.device_channels = []  # Store the number of channels for each device
        self.populate_audio_inputs()
        
        # Start and Stop buttons
        self.start_button = Gtk.Button(label="Start")
        self.stop_button = Gtk.Button(label="Stop")
        
        # Output display
        self.output_textview = Gtk.TextView()
        self.output_textview.set_editable(False)

        # Layout
        grid = Gtk.Grid()
        grid.attach(Gtk.Label("Select Audio Input:"), 0, 0, 1, 1)
        grid.attach(self.audio_input_combo, 1, 0, 2, 1)
        grid.attach(self.start_button, 0, 1, 1, 1)
        grid.attach(self.stop_button, 1, 1, 1, 1)
        grid.attach(self.output_textview, 0, 2, 3, 1)

        self.start_button.connect("clicked", self.on_start_clicked)
        self.stop_button.connect("clicked", self.on_stop_clicked)

        self.add(grid)

        self.decoder_thread = None
        self.is_decoding = False

        # Goertzel parameters
        self.target_freq = 1000  # Frequency for Morse code tone (Hz)
        self.sample_rate = 44100  # Sample rate
        self.num_samples = 205  # Number of samples to process
        self.goertzel = Goertzel(self.target_freq, self.sample_rate, self.num_samples)

    def populate_audio_inputs(self):
        p = pyaudio.PyAudio()
        for i in range(p.get_device_count()):
            device_info = p.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:
                self.audio_input_combo.append_text(device_info['name'])
                self.device_channels.append(device_info['maxInputChannels'])  # Store channel count
        p.terminate()

    def on_start_clicked(self, widget):
        self.is_decoding = True
        self.decoder_thread = threading.Thread(target=self.decode_audio)
        self.decoder_thread.start()

    def on_stop_clicked(self, widget):
        self.is_decoding = False
        if self.decoder_thread:
            self.decoder_thread.join()

    def decode_audio(self):
    p = pyaudio.PyAudio()
    device_index = self.audio_input_combo.get_active()
    num_channels = self.device_channels[device_index]  # Get the number of channels for the selected device

    # If the number of channels is more than 2, fallback to 1 channel (mono)
    if num_channels > 2:
        num_channels = 1

    try:
        stream = p.open(format=pyaudio.paInt16,
                        channels=num_channels,
                        rate=self.sample_rate,
                        input=True,
                        input_device_index=device_index)

        while self.is_decoding:
            data = stream.read(self.num_samples)
            samples = np.frombuffer(data, dtype=np.int16)
            power = self.goertzel.process(samples)

            # Detect Morse code based on power threshold
            if power > 100000:  # Adjust threshold as necessary
                self.update_output("Detected Morse Tone\n")
            else:
                self.update_output("No Morse Tone\n")

        stream.stop_stream()
        stream.close()
    except Exception as e:
        self.update_output(f"Error: {str(e)}")
    finally:
        p.terminate()
    
    
    def update_output(self, message):
        buffer = self.output_textview.get_buffer()
        buffer.insert(buffer.get_end_iter(), message)

def main():

    app = AudioDecoderApp()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
