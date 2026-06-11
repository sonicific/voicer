import asyncio
import importlib
import os
import queue
import re
import sys
import threading
import tkinter as tk
import wave
from dataclasses import dataclass
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


APP_DIR = Path(__file__).resolve().parent
DEFAULT_TEXT = (
    "Xin chao, day la cong cu tao giong noi da provider. "
    "Ban co the chon provider, dieu chinh giong doc, toc do va xuat file audio."
)


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def split_text(text: str, max_chars: int = 200) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", clean_text(text))
    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if not current:
            current = sentence
        elif len(current) + len(sentence) + 1 <= max_chars:
            current = f"{current} {sentence}"
        else:
            chunks.append(current)
            current = sentence
    if current:
        chunks.append(current)
    return chunks


def import_external(module_name: str):
    script_dir = str(APP_DIR).lower()
    removed = []
    for index, item in reversed(list(enumerate(sys.path))):
        item_path = str(Path(item or ".").resolve()).lower()
        if item == "" or item_path == script_dir:
            removed.append((index, item))
            sys.path.pop(index)
    try:
        return importlib.import_module(module_name)
    finally:
        for index, item in sorted(removed):
            sys.path.insert(index, item)


@dataclass
class Field:
    key: str
    label: str
    kind: str
    default: object
    values: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None


class Provider:
    name = "Provider"
    extension = ".wav"
    fields: tuple[Field, ...] = ()

    def synthesize(self, text: str, output: Path, options: dict[str, object]) -> None:
        raise NotImplementedError


class EdgeProvider(Provider):
    name = "Microsoft Edge TTS"
    extension = ".mp3"
    fields = (
        Field(
            "voice",
            "Voice",
            "choice",
            "vi-VN-HoaiMyNeural",
            (
                "vi-VN-HoaiMyNeural",
                "vi-VN-NamMinhNeural",
                "en-US-AriaNeural",
                "en-US-JennyNeural",
                "en-US-GuyNeural",
                "en-US-DavisNeural",
                "en-GB-SoniaNeural",
                "en-GB-RyanNeural",
                "en-AU-NatashaNeural",
                "en-AU-WilliamNeural",
                "ja-JP-NanamiNeural",
                "ja-JP-KeitaNeural",
                "ko-KR-SunHiNeural",
                "ko-KR-InJoonNeural",
                "zh-CN-XiaoxiaoNeural",
                "zh-CN-YunxiNeural",
                "fr-FR-DeniseNeural",
                "fr-FR-HenriNeural",
                "de-DE-KatjaNeural",
                "de-DE-ConradNeural",
                "es-ES-ElviraNeural",
                "es-ES-AlvaroNeural",
                "id-ID-GadisNeural",
                "id-ID-ArdiNeural",
                "th-TH-PremwadeeNeural",
                "th-TH-NiwatNeural",
            ),
        ),
        Field("rate", "Rate", "choice", "+0%", ("-30%", "-15%", "+0%", "+15%", "+30%")),
        Field("volume", "Volume", "choice", "+0%", ("-30%", "-10%", "+0%", "+10%", "+30%")),
        Field("pitch", "Pitch", "choice", "+0Hz", ("-50Hz", "-25Hz", "+0Hz", "+25Hz", "+50Hz")),
    )

    def synthesize(self, text: str, output: Path, options: dict[str, object]) -> None:
        edge_tts = import_external("edge_tts")

        async def run() -> None:
            communicate = edge_tts.Communicate(
                text=text,
                voice=str(options["voice"]),
                rate=str(options["rate"]),
                volume=str(options["volume"]),
                pitch=str(options["pitch"]),
            )
            await communicate.save(str(output))

        asyncio.run(run())


class GTTSProvider(Provider):
    name = "Google gTTS"
    extension = ".mp3"
    fields = (
        Field("lang", "Language", "choice", "vi", ("vi", "en", "ja", "ko", "zh-CN", "fr", "de")),
        Field("tld", "Accent domain", "choice", "com", ("com", "com.vn", "us", "co.uk", "com.au", "ca", "co.in")),
        Field("slow", "Slow voice", "bool", False),
        Field("lang_check", "Validate language", "bool", True),
        Field("timeout", "Timeout seconds", "float", 20.0, minimum=1.0, maximum=120.0),
        Field("chunk_size", "Chunk size", "int", 200, minimum=80, maximum=500),
    )

    def synthesize(self, text: str, output: Path, options: dict[str, object]) -> None:
        gtts_module = import_external("gtts")
        chunks = split_text(text, int(options["chunk_size"]))
        temp_files: list[Path] = []
        try:
            for index, chunk in enumerate(chunks):
                temp_file = output.with_name(f"{output.stem}.part{index}.mp3")
                tts = gtts_module.gTTS(
                    text=chunk,
                    lang=str(options["lang"]),
                    tld=str(options["tld"]),
                    slow=bool(options["slow"]),
                    lang_check=bool(options["lang_check"]),
                    timeout=float(options["timeout"]),
                )
                tts.save(str(temp_file))
                temp_files.append(temp_file)
            with output.open("wb") as final_file:
                for temp_file in temp_files:
                    final_file.write(temp_file.read_bytes())
        finally:
            for temp_file in temp_files:
                temp_file.unlink(missing_ok=True)


class PiperProvider(Provider):
    name = "Piper Local"
    extension = ".wav"
    fields = (
        Field("model", "ONNX model", "file", str(APP_DIR / "en_US-lessac-medium.onnx")),
        Field("config", "Config JSON", "file", ""),
        Field("speaker_id", "Speaker ID", "int", 0, minimum=0, maximum=999),
        Field("length_scale", "Length scale", "float", 1.0, minimum=0.2, maximum=3.0),
        Field("noise_scale", "Noise scale", "float", 0.667, minimum=0.0, maximum=2.0),
        Field("noise_w", "Noise width", "float", 0.8, minimum=0.0, maximum=2.0),
        Field("sentence_silence", "Sentence silence", "float", 0.2, minimum=0.0, maximum=3.0),
        Field("use_cuda", "Use CUDA", "bool", False),
    )

    def synthesize(self, text: str, output: Path, options: dict[str, object]) -> None:
        piper = import_external("piper")
        model_path = Path(str(options["model"]))
        if not model_path.exists():
            raise FileNotFoundError(f"Khong tim thay model Piper: {model_path}")
        config_value = str(options["config"]).strip()
        config_path = config_value if config_value else None
        voice = piper.PiperVoice.load(str(model_path), config_path=config_path, use_cuda=bool(options["use_cuda"]))
        with wave.open(str(output), "wb") as file:
            voice.synthesize(
                text,
                file,
                speaker_id=int(options["speaker_id"]),
                length_scale=float(options["length_scale"]),
                noise_scale=float(options["noise_scale"]),
                noise_w=float(options["noise_w"]),
                sentence_silence=float(options["sentence_silence"]),
            )


class CoquiProvider(Provider):
    name = "Coqui TTS"
    extension = ".wav"
    fields = (
        Field(
            "model_name",
            "Model",
            "choice",
            "tts_models/en/ljspeech/tacotron2-DDC",
            (
                "tts_models/en/ljspeech/tacotron2-DDC",
                "tts_models/en/vctk/vits",
                "tts_models/multilingual/multi-dataset/xtts_v2",
            ),
        ),
        Field("vocoder_name", "Vocoder", "text", ""),
        Field("speaker_idx", "Speaker ID/name", "text", ""),
        Field("speaker_wav", "Clone speaker wav", "file", ""),
        Field("language", "Language", "choice", "", ("", "vi", "en", "ja", "ko", "fr", "de", "pt", "es")),
        Field("device", "Device", "choice", "auto", ("auto", "cpu", "cuda")),
    )

    def synthesize(self, text: str, output: Path, options: dict[str, object]) -> None:
        coqui = import_external("TTS.api")
        init_kwargs: dict[str, object] = {"model_name": str(options["model_name"]), "progress_bar": False}
        vocoder_name = str(options["vocoder_name"]).strip()
        if vocoder_name:
            init_kwargs["vocoder_name"] = vocoder_name
        tts = coqui.TTS(**init_kwargs)
        device = str(options["device"])
        if device != "cpu":
            torch = import_external("torch")
            resolved = "cuda" if device == "cuda" or (device == "auto" and torch.cuda.is_available()) else "cpu"
            tts = tts.to(resolved)
        call_kwargs: dict[str, object] = {"text": text, "file_path": str(output)}
        speaker_idx = str(options["speaker_idx"]).strip()
        speaker_wav = str(options["speaker_wav"]).strip()
        language = str(options["language"]).strip()
        if speaker_idx:
            call_kwargs["speaker"] = speaker_idx
            call_kwargs["speaker_idx"] = speaker_idx
        if speaker_wav:
            call_kwargs["speaker_wav"] = speaker_wav
        if language:
            call_kwargs["language"] = language
        try:
            tts.tts_to_file(**call_kwargs)
        except TypeError:
            call_kwargs.pop("speaker_idx", None)
            tts.tts_to_file(**call_kwargs)


class PyttsxProvider(Provider):
    name = "System pyttsx3"
    extension = ".wav"
    fields = (
        Field("voice", "Voice index", "int", 0, minimum=0, maximum=100),
        Field("rate", "Rate", "int", 150, minimum=80, maximum=300),
        Field("volume", "Volume", "float", 1.0, minimum=0.0, maximum=1.0),
        Field("driver", "Driver", "choice", "", ("", "sapi5", "nsss", "espeak")),
    )

    def synthesize(self, text: str, output: Path, options: dict[str, object]) -> None:
        pyttsx3 = import_external("pyttsx3")
        driver = str(options["driver"]).strip() or None
        engine = pyttsx3.init(driverName=driver)
        voices = engine.getProperty("voices")
        if voices:
            index = min(int(options["voice"]), len(voices) - 1)
            engine.setProperty("voice", voices[index].id)
        engine.setProperty("rate", int(options["rate"]))
        engine.setProperty("volume", float(options["volume"]))
        engine.save_to_file(text, str(output))
        engine.runAndWait()


class SupertonicProvider(Provider):
    name = "Supertonic"
    extension = ".wav"
    fields = (
        Field("voice_name", "Voice", "choice", "M1", ("M1", "M2", "M3", "M4", "M5", "F1", "F2", "F3", "F4", "F5")),
        Field(
            "lang",
            "Language",
            "choice",
            "ja",
            (
                "na",
                "vi",
                "en",
                "ja",
                "ko",
                "zh",
                "fr",
                "de",
                "es",
                "pt",
                "it",
                "ru",
                "id",
                "hi",
                "ar",
                "tr",
                "uk",
            ),
        ),
        Field("steps", "Quality steps", "int", 8, minimum=5, maximum=12),
        Field("speed", "Speed", "float", 1.05, minimum=0.7, maximum=2.0),
        Field("prefix_tag", "Expression tag", "choice", "", ("", "<breath>", "<laugh>", "<sigh>")),
    )

    def synthesize(self, text: str, output: Path, options: dict[str, object]) -> None:
        supertonic = import_external("supertonic")
        tts = supertonic.TTS(auto_download=True)
        style = tts.get_voice_style(voice_name=str(options["voice_name"]))
        prefix = str(options["prefix_tag"]).strip()
        wav, _duration = tts.synthesize(
            text=f"{prefix} {text}".strip(),
            lang=str(options["lang"]),
            voice_style=style,
            total_steps=int(options["steps"]),
            speed=float(options["speed"]),
        )
        tts.save_audio(wav, str(output))


PROVIDERS: tuple[Provider, ...] = (
    EdgeProvider(),
    GTTSProvider(),
    PiperProvider(),
    CoquiProvider(),
    PyttsxProvider(),
    SupertonicProvider(),
)


class VoiceStudio(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Voice Studio")
        self.geometry("980x680")
        self.minsize(860, 600)
        self.configure(bg="#f6f7f9")

        self.provider_by_name = {provider.name: provider for provider in PROVIDERS}
        self.provider_var = tk.StringVar(value=PROVIDERS[0].name)
        self.output_var = tk.StringVar(value=str(APP_DIR / f"voice_output{PROVIDERS[0].extension}"))
        self.status_var = tk.StringVar(value="Ready")
        self.auto_play_var = tk.BooleanVar(value=True)
        self.option_vars: dict[str, tk.Variable] = {}
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.last_output: Path | None = None

        self._configure_style()
        self._build()
        self._render_options()
        self.after(150, self._drain_log_queue)

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#f6f7f9")
        style.configure("Panel.TFrame", background="#ffffff", relief="flat")
        style.configure("TLabel", background="#f6f7f9", foreground="#20242a", font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background="#ffffff", foreground="#20242a", font=("Segoe UI", 10))
        style.configure("Title.TLabel", background="#f6f7f9", foreground="#111827", font=("Segoe UI Semibold", 20))
        style.configure("Hint.TLabel", background="#f6f7f9", foreground="#5b6472", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI Semibold", 10), padding=(14, 8))
        style.configure("Accent.TButton", background="#2563eb", foreground="#ffffff")
        style.map("Accent.TButton", background=[("active", "#1d4ed8"), ("disabled", "#9ca3af")])
        style.configure("TCombobox", padding=5)

    def _build(self) -> None:
        header = ttk.Frame(self, padding=(24, 20, 24, 12))
        header.pack(fill="x")
        ttk.Label(header, text="Voice Studio", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="Tao voice tu Edge TTS, gTTS, Piper, Coqui, pyttsx3 va Supertonic trong mot giao dien.",
            style="Hint.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        body = ttk.Frame(self, padding=(24, 8, 24, 20))
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=2)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        left = ttk.Frame(body, style="Panel.TFrame", padding=16)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        ttk.Label(left, text="Text input", style="Panel.TLabel", font=("Segoe UI Semibold", 11)).grid(
            row=0, column=0, sticky="w"
        )
        self.text_input = tk.Text(
            left,
            wrap="word",
            height=18,
            bg="#fbfdff",
            fg="#111827",
            insertbackground="#111827",
            relief="solid",
            bd=1,
            padx=12,
            pady=10,
            font=("Segoe UI", 11),
        )
        self.text_input.grid(row=1, column=0, sticky="nsew", pady=(8, 12))
        self.text_input.insert("1.0", DEFAULT_TEXT)

        output_row = ttk.Frame(left, style="Panel.TFrame")
        output_row.grid(row=2, column=0, sticky="ew")
        output_row.columnconfigure(1, weight=1)
        ttk.Label(output_row, text="Output", style="Panel.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(output_row, textvariable=self.output_var).grid(row=0, column=1, sticky="ew")
        ttk.Button(output_row, text="Browse", command=self._browse_output).grid(row=0, column=2, padx=(8, 0))

        action_row = ttk.Frame(left, style="Panel.TFrame")
        action_row.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        action_row.columnconfigure(0, weight=1)
        ttk.Checkbutton(action_row, text="Auto play", variable=self.auto_play_var).grid(row=0, column=0, sticky="w")
        self.play_button = ttk.Button(action_row, text="Play", command=self._play_output)
        self.play_button.grid(row=0, column=1, sticky="e", padx=(0, 8))
        self.open_folder_button = ttk.Button(action_row, text="Open Folder", command=self._open_output_folder)
        self.open_folder_button.grid(row=0, column=2, sticky="e", padx=(0, 8))
        self.generate_button = ttk.Button(
            action_row, text="Generate Voice", style="Accent.TButton", command=self._start_generate
        )
        self.generate_button.grid(row=0, column=3, sticky="e")

        right = ttk.Frame(body, style="Panel.TFrame", padding=16)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)

        ttk.Label(right, text="Provider", style="Panel.TLabel", font=("Segoe UI Semibold", 11)).grid(
            row=0, column=0, sticky="w"
        )
        provider_select = ttk.Combobox(
            right,
            textvariable=self.provider_var,
            values=tuple(self.provider_by_name),
            state="readonly",
        )
        provider_select.grid(row=1, column=0, sticky="ew", pady=(8, 14))
        provider_select.bind("<<ComboboxSelected>>", lambda _event: self._on_provider_changed())

        self.options_frame = ttk.Frame(right, style="Panel.TFrame")
        self.options_frame.grid(row=2, column=0, sticky="ew")
        self.options_frame.columnconfigure(1, weight=1)

        ttk.Label(right, text="Status", style="Panel.TLabel", font=("Segoe UI Semibold", 11)).grid(
            row=3, column=0, sticky="w", pady=(18, 8)
        )
        ttk.Label(right, textvariable=self.status_var, style="Panel.TLabel", wraplength=300).grid(
            row=4, column=0, sticky="ew"
        )

        self.log = tk.Text(
            right,
            height=12,
            wrap="word",
            state="disabled",
            bg="#111827",
            fg="#e5e7eb",
            relief="flat",
            padx=10,
            pady=10,
            font=("Consolas", 9),
        )
        self.log.grid(row=5, column=0, sticky="nsew", pady=(12, 0))
        right.rowconfigure(5, weight=1)

    def _current_provider(self) -> Provider:
        return self.provider_by_name[self.provider_var.get()]

    def _on_provider_changed(self) -> None:
        provider = self._current_provider()
        current = Path(self.output_var.get())
        self.output_var.set(str(current.with_suffix(provider.extension)))
        self._render_options()

    def _render_options(self) -> None:
        for child in self.options_frame.winfo_children():
            child.destroy()
        self.option_vars = {}
        provider = self._current_provider()
        for row, field in enumerate(provider.fields):
            ttk.Label(self.options_frame, text=field.label, style="Panel.TLabel").grid(
                row=row, column=0, sticky="w", pady=6, padx=(0, 8)
            )
            variable = self._create_variable(field)
            self.option_vars[field.key] = variable
            widget = self._create_field_widget(field, variable)
            widget.grid(row=row, column=1, sticky="ew", pady=6)

    def _create_variable(self, field: Field) -> tk.Variable:
        if field.kind == "bool":
            return tk.BooleanVar(value=bool(field.default))
        if field.kind == "int":
            return tk.IntVar(value=int(field.default))
        if field.kind == "float":
            return tk.DoubleVar(value=float(field.default))
        return tk.StringVar(value=str(field.default))

    def _create_field_widget(self, field: Field, variable: tk.Variable) -> ttk.Widget:
        if field.kind == "choice":
            return ttk.Combobox(self.options_frame, textvariable=variable, values=field.values, state="normal")
        if field.kind == "bool":
            return ttk.Checkbutton(self.options_frame, variable=variable)
        if field.kind == "file":
            frame = ttk.Frame(self.options_frame, style="Panel.TFrame")
            frame.columnconfigure(0, weight=1)
            ttk.Entry(frame, textvariable=variable).grid(row=0, column=0, sticky="ew")
            ttk.Button(frame, text="...", width=3, command=lambda: self._browse_file(variable)).grid(
                row=0, column=1, padx=(6, 0)
            )
            return frame
        return ttk.Entry(self.options_frame, textvariable=variable)

    def _browse_file(self, variable: tk.Variable) -> None:
        path = filedialog.askopenfilename(initialdir=APP_DIR)
        if path:
            variable.set(path)

    def _browse_output(self) -> None:
        provider = self._current_provider()
        path = filedialog.asksaveasfilename(
            initialdir=APP_DIR,
            defaultextension=provider.extension,
            filetypes=(("Audio", f"*{provider.extension}"), ("All files", "*.*")),
        )
        if path:
            self.output_var.set(path)

    def _collect_options(self) -> dict[str, object]:
        return {key: variable.get() for key, variable in self.option_vars.items()}

    def _start_generate(self) -> None:
        text = clean_text(self.text_input.get("1.0", "end"))
        if not text:
            messagebox.showwarning("Missing text", "Nhap noi dung can tao voice.")
            return
        output = Path(self.output_var.get()).expanduser()
        if not output.parent.exists():
            messagebox.showwarning("Invalid output", "Thu muc output khong ton tai.")
            return
        provider = self._current_provider()
        options = self._collect_options()
        self.generate_button.configure(state="disabled")
        self.status_var.set(f"Generating with {provider.name}...")
        self._append_log(f"Start: {provider.name} -> {output}")
        thread = threading.Thread(target=self._generate_worker, args=(provider, text, output, options), daemon=True)
        thread.start()

    def _generate_worker(self, provider: Provider, text: str, output: Path, options: dict[str, object]) -> None:
        try:
            provider.synthesize(text, output, options)
            self.last_output = output
            self.log_queue.put(f"Done: {output}")
            self.log_queue.put("__DONE__")
        except Exception as exc:
            self.log_queue.put(f"Error: {exc}")
            self.log_queue.put("__ERROR__")

    def _drain_log_queue(self) -> None:
        try:
            while True:
                message = self.log_queue.get_nowait()
                if message == "__DONE__":
                    self.generate_button.configure(state="normal")
                    self.status_var.set("Finished")
                    if self.auto_play_var.get():
                        self._play_output(show_error=False)
                    messagebox.showinfo("Done", "Da tao voice xong.")
                elif message == "__ERROR__":
                    self.generate_button.configure(state="normal")
                    self.status_var.set("Failed")
                    messagebox.showerror("Failed", "Khong tao duoc voice. Xem log de biet chi tiet.")
                else:
                    self._append_log(message)
        except queue.Empty:
            pass
        self.after(150, self._drain_log_queue)

    def _append_log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", f"{message}\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _output_path_for_actions(self) -> Path:
        return self.last_output or Path(self.output_var.get()).expanduser()

    def _play_output(self, show_error: bool = True) -> None:
        output = self._output_path_for_actions()
        if not output.exists():
            if show_error:
                messagebox.showwarning("Missing audio", "Chua co file audio de phat.")
            return
        try:
            os.startfile(str(output))
            self._append_log(f"Play: {output}")
        except OSError as exc:
            if show_error:
                messagebox.showerror("Play failed", str(exc))
            self._append_log(f"Play error: {exc}")

    def _open_output_folder(self) -> None:
        output = self._output_path_for_actions()
        folder = output.parent
        if not folder.exists():
            messagebox.showwarning("Missing folder", "Thu muc output khong ton tai.")
            return
        try:
            os.startfile(str(folder))
        except OSError as exc:
            messagebox.showerror("Open folder failed", str(exc))


if __name__ == "__main__":
    try:
        from voice_studio_qt import main as qt_main

        raise SystemExit(qt_main())
    except ImportError:
        app = VoiceStudio()
        app.mainloop()
