import gi
import pyaudio
import threading
import numpy as np
import time

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
        self.device_index = 3  # Device 4 is at index 3 (0-based index)

        # Start and Stop buttons
        self.start_button = Gtk.Button(label="Start")
        self.stop_button = Gtk.Button(label="Stop")
        
        # Output display
        self.output_textview = Gtk.TextView()
        self.output_textview.set_editable(False)

        # Layout
        grid = Gtk.Grid()
        grid.attach(self.start_button, 0, 1, 1, 1)
        grid.attach(self.stop_button, 1, 1, 1, 1)
        grid.attach(self.output_textview, 0, 2, 3, 1)

        self.start_button.connect("clicked", self.on_start_clicked)
        self.stop_button.connect("clicked", self.on_stop_clicked)

        self.add(grid)

        self.decoder_thread = None
        self.is_decoding = False

        # Goertzel parameters
        self.target_freq = 558  # Frequency for Morse code tone (Hz)
        self.sample_rate = 48000  # Sample rate
        self.num_samples = 205  # Number of samples to process
        self.goertzel = Goertzel(self.target_freq, self.sample_rate, self.num_samples)
        self.morse_decoder = MorseDecoder()
    	
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
        num_channels = self.device_channels[device_index] # Get the number of channels for the selected device

        # Ensure we use a valid number of channels (1 or 2)
        if num_channels < 1:
            num_channels = 1
        elif num_channels > 2:
            num_channels = 2

        print(f"Using {num_channels} channels for the audio stream.")

        try:
            stream = p.open(format=pyaudio.paInt16,
                            channels=num_channels,
                            rate=self.sample_rate,
                            input=True,
                            input_device_index=self.device_index)

            while self.is_decoding:
                data = stream.read(self.num_samples)
                samples = np.frombuffer(data, dtype=np.int16)
                power = self.goertzel.process(samples)
                # Pass the power to the Morse decoder
                self.morse_decoder.add_signal(power)
            stream.stop_stream()
            tream.close()

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
