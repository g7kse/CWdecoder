import gi
import pyaudio
import threading
import numpy as np
import time

from gi.repository import GLib

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

class MorseDecoder:
    MORSE_CODE_DICT = {
        'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 
        'F': '..-.', 'G': '--.', 'H': '....', 'I': '..', 'J': '.---', 
        'K': '-.-', 'L': '.-..', 'M': '--', 'N': '-.', 'O': '---', 
        'P': '.--.', 'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-', 
        'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-', 'Y': '-.--', 
        'Z': '--..', '1': '.----', '2': '..---', '3': '...--', 
        '4': '....-', '5': '.....', '6': '-....', '7': '--...', 
        '8': '---..', '9': '----.', '0': '-----', ' ': '/'
    }

    def __init__(self):
        self.current_code = ""
        self.last_time = time.time()
        self.dash_duration = 0.2
        self.dot_duration = 0.1
        self.space_duration = 0.3

    def add_signal(self, power):
        current_time = time.time()
        duration = current_time - self.last_time

        if power > 100000:  # Detected tone
            if duration < self.dot_duration:  # Dot
                self.current_code += '.'
            elif duration < self.dash_duration:  # Dash
                self.current_code += '-'
        else:  # Detected silence
            if duration >= self.space_duration:  # Space between letters
                if self.current_code:
                    self.decode_current_code()
                    self.current_code = ""

        self.last_time = current_time

    def decode_current_code(self):
        for letter, morse in self.MORSE_CODE_DICT.items():
            if self.current_code == morse:
                print(f"Detected letter: {letter}")  # Here you can update the GUI instead
                break



class AudioDecoderApp(Gtk.Window):
    def __init__(self):
        super().__init__(title="CW Decoder")
        self.set_border_width(10)
        self.set_default_size(400, 200)

        # Audio input selection
        self.audio_input_combo = Gtk.ComboBoxText()  # Create a combo box for audio devices
        self.populate_audio_devices()

        # Start and Stop buttons
        self.start_button = Gtk.Button(label="Start")
        self.stop_button = Gtk.Button(label="Stop")

        # Output display
        self.output_textview = Gtk.TextView()
        self.output_textview.set_editable(False)

        # Layout
        grid = Gtk.Grid()
        grid.attach(self.audio_input_combo, 0, 0, 2, 1)
        grid.attach(self.start_button, 0, 1, 1, 1)
        grid.attach(self.stop_button, 1, 1, 1, 1)
        grid.attach(self.output_textview, 0, 2, 3, 1)

        self.start_button.connect("clicked", self.on_start_clicked)
        self.stop_button.connect("clicked", self.on_stop_clicked)

        self.add(grid)

        self.decoder_thread = None
        self.is_decoding = False
        self.lock = threading.Lock()  # Lock for thread safety

        # Goertzel parameters
        self.target_freq = 558  # Frequency for Morse code tone (Hz)
        self.sample_rate = 48000  # Sample rate
        self.num_samples = 205  # Number of samples to process
        self.goertzel = Goertzel(self.target_freq, self.sample_rate, self.num_samples)
        self.morse_decoder = MorseDecoder()

    def populate_audio_devices(self):
        p = pyaudio.PyAudio()
        self.device_channels = []  # Store the number of channels for each device
        for i in range(p.get_device_count()):
            device_info = p.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:  # Only add input devices
                self.audio_input_combo.append_text(device_info['name'])
                self.device_channels.append(device_info['maxInputChannels'])
        p.terminate()

    def decode_audio(self):
        p = pyaudio.PyAudio()
        device_index = self.audio_input_combo.get_active()  # Get selected device index
        if device_index == -1 or device_index >= len(self.device_channels):
            self.update_output("Invalid audio device selected.\n")
            return

        num_channels = self.device_channels[device_index]  # Get the number of channels for the selected device
        num_channels = min(max(num_channels, 1), 2)  # Ensure channels are 1 or 2

        stream = None
        try:
            # Open the audio stream with PipeWire (via PyAudio)
            stream = p.open(format=pyaudio.paInt16,
                            channels=num_channels,
                            rate=self.sample_rate,
                            input=True,
                            input_device_index=device_index)

            while True:
                with self.lock:
                    if not self.is_decoding:
                        break
                data = stream.read(self.num_samples)
                samples = np.frombuffer(data, dtype=np.int16)
                power = self.goertzel.process(samples)
                self.morse_decoder.add_signal(power)

        except Exception as e:
            GLib.idle_add(self.update_output, f"Error: {str(e)}\n")
        finally:
            if stream is not None:
                stream.stop_stream()
                stream.close()
            p.terminate()

    def on_start_clicked(self, widget):
        with self.lock:
            self.is_decoding = True
        self.decoder_thread = threading.Thread(target=self.decode_audio)
        self.decoder_thread.start()
        self.update_output("Decoding started...\n")

    def on_stop_clicked(self, widget):
        with self.lock:
            self.is_decoding = False
        if self.decoder_thread:
            self.decoder_thread.join()  # Ensure the thread has finished before proceeding
        self.update_output("Decoding stopped.\n")

    def update_output(self, message):
        GLib.idle_add(self.append_text, message)

    def append_text(self, message):
        buffer = self.output_textview.get_buffer()
        buffer.insert(buffer.get_end_iter(), message)

def main():
    app = AudioDecoderApp()
    app.connect("destroy", Gtk.main_quit)
    app.show_all()
    Gtk.main()

if __name__ == "__main__":
    main()
