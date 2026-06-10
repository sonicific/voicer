import json
import os
import sys
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QAction, QDesktopServices, QFont
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from voice_studio import APP_DIR, DEFAULT_TEXT, PROVIDERS, Field, Provider, clean_text


HISTORY_FILE = APP_DIR / "voice_studio_history.json"
PRESET_FILE = APP_DIR / "voice_studio_presets.json"


PROVIDER_NOTES = {
    "Microsoft Edge TTS": "Online Microsoft neural voices. Best for natural Vietnamese and fast MP3 output.",
    "Google gTTS": "Simple online Google Translate TTS. Accent can change by Google domain.",
    "Piper Local": "Local ONNX voices. Needs a Piper .onnx model and matching .json config.",
    "Coqui TTS": "Neural TTS models, multi-speaker models, and speaker-wav cloning when supported.",
    "System pyttsx3": "Offline system voices via Windows SAPI, NSSpeechSynthesizer, or eSpeak.",
    "Supertonic": "Local multilingual ONNX TTS with quality, speed, style, and expression tags.",
}


class GenerateWorker(QThread):
    log = Signal(str)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, provider: Provider, text: str, output: Path, options: dict[str, object]) -> None:
        super().__init__()
        self.provider = provider
        self.text = text
        self.output = output
        self.options = options

    def run(self) -> None:
        try:
            self.log.emit(f"Start: {self.provider.name} -> {self.output}")
            self.provider.synthesize(self.text, self.output, self.options)
            self.finished_ok.emit(str(self.output))
        except Exception as exc:
            self.failed.emit(str(exc))


class VoiceStudioQt(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Voice Studio Pro")
        self.resize(1180, 760)
        self.setMinimumSize(980, 640)

        self.providers = {provider.name: provider for provider in PROVIDERS}
        self.field_widgets: dict[str, QWidget] = {}
        self.worker: GenerateWorker | None = None
        self.last_output: Path | None = None

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.audio_output.setVolume(0.9)
        self.player.setAudioOutput(self.audio_output)
        self.player.playbackStateChanged.connect(self._sync_player_buttons)

        self._build_ui()
        self._build_actions()
        self._apply_styles()
        self._load_history()
        self._render_provider_options()
        self._update_metrics()

    def _build_actions(self) -> None:
        clear_action = QAction("Clear Log", self)
        clear_action.triggered.connect(self.log.clear)
        self.addAction(clear_action)

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)
        main = QVBoxLayout(root)
        main.setContentsMargins(22, 18, 22, 18)
        main.setSpacing(14)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Voice Studio Pro")
        title.setObjectName("Title")
        subtitle = QLabel("Multi-provider voice generation workspace")
        subtitle.setObjectName("Subtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box, 1)

        self.provider_combo = QComboBox()
        self.provider_combo.addItems(self.providers.keys())
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        self.provider_combo.setMinimumWidth(290)
        header.addWidget(self.provider_combo)
        main.addLayout(header)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        main.addWidget(splitter, 1)

        left = self._panel()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(18, 16, 18, 16)
        left_layout.setSpacing(12)
        text_header = QHBoxLayout()
        text_label = QLabel("Text")
        text_label.setObjectName("SectionTitle")
        self.metrics_label = QLabel("")
        self.metrics_label.setObjectName("Muted")
        text_header.addWidget(text_label)
        text_header.addStretch()
        text_header.addWidget(self.metrics_label)
        left_layout.addLayout(text_header)

        self.text_edit = QTextEdit()
        self.text_edit.setPlainText(DEFAULT_TEXT)
        self.text_edit.textChanged.connect(self._update_metrics)
        self.text_edit.setAcceptRichText(False)
        self.text_edit.setPlaceholderText("Nhap noi dung can tao voice...")
        left_layout.addWidget(self.text_edit, 1)

        output_row = QHBoxLayout()
        self.output_edit = QLineEdit(str(APP_DIR / f"voice_output{self._current_provider().extension}"))
        browse_output = QPushButton("Browse")
        browse_output.clicked.connect(self._browse_output)
        output_row.addWidget(QLabel("Output"))
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(browse_output)
        left_layout.addLayout(output_row)

        controls = QHBoxLayout()
        self.auto_play_check = QCheckBox("Auto play")
        self.auto_play_check.setChecked(True)
        self.generate_button = QPushButton("Generate Voice")
        self.generate_button.setObjectName("PrimaryButton")
        self.generate_button.clicked.connect(self._start_generate)
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self._play_audio)
        self.pause_button = QPushButton("Pause")
        self.pause_button.clicked.connect(self.player.pause)
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.player.stop)
        self.open_folder_button = QPushButton("Open Folder")
        self.open_folder_button.clicked.connect(self._open_output_folder)
        controls.addWidget(self.auto_play_check)
        controls.addStretch()
        controls.addWidget(self.play_button)
        controls.addWidget(self.pause_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.open_folder_button)
        controls.addWidget(self.generate_button)
        left_layout.addLayout(controls)

        splitter.addWidget(left)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(12)

        provider_panel = self._panel()
        provider_layout = QVBoxLayout(provider_panel)
        provider_layout.setContentsMargins(16, 14, 16, 14)
        provider_layout.setSpacing(10)
        provider_header = QHBoxLayout()
        provider_title = QLabel("Provider Settings")
        provider_title.setObjectName("SectionTitle")
        save_preset = QToolButton()
        save_preset.setText("Save Preset")
        save_preset.clicked.connect(self._save_provider_preset)
        load_preset = QToolButton()
        load_preset.setText("Load Preset")
        load_preset.clicked.connect(self._load_provider_preset)
        provider_header.addWidget(provider_title)
        provider_header.addStretch()
        provider_header.addWidget(save_preset)
        provider_header.addWidget(load_preset)
        self.provider_note = QLabel("")
        self.provider_note.setObjectName("Muted")
        self.provider_note.setWordWrap(True)
        provider_layout.addLayout(provider_header)
        provider_layout.addWidget(self.provider_note)

        self.options_container = QWidget()
        self.options_grid = QGridLayout(self.options_container)
        self.options_grid.setContentsMargins(0, 8, 0, 0)
        self.options_grid.setHorizontalSpacing(10)
        self.options_grid.setVerticalSpacing(9)
        self.options_grid.setColumnStretch(1, 1)
        options_scroll = QScrollArea()
        options_scroll.setWidgetResizable(True)
        options_scroll.setFrameShape(QFrame.NoFrame)
        options_scroll.setWidget(self.options_container)
        provider_layout.addWidget(options_scroll, 1)
        right_layout.addWidget(provider_panel, 3)

        history_panel = self._panel()
        history_layout = QVBoxLayout(history_panel)
        history_layout.setContentsMargins(16, 14, 16, 14)
        history_title = QHBoxLayout()
        history_label = QLabel("History")
        history_label.setObjectName("SectionTitle")
        clear_history = QToolButton()
        clear_history.setText("Clear")
        clear_history.clicked.connect(self._clear_history)
        history_title.addWidget(history_label)
        history_title.addStretch()
        history_title.addWidget(clear_history)
        history_layout.addLayout(history_title)
        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self._open_history_item)
        history_layout.addWidget(self.history_list)
        right_layout.addWidget(history_panel, 2)

        splitter.addWidget(right)
        splitter.setSizes([720, 420])

        bottom = self._panel()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(14, 10, 14, 10)
        log_header = QHBoxLayout()
        log_label = QLabel("Log")
        log_label.setObjectName("SectionTitle")
        clear_log = QPushButton("Clear")
        clear_log.clicked.connect(lambda: self.log.clear())
        log_header.addWidget(log_label)
        log_header.addStretch()
        log_header.addWidget(clear_log)
        bottom_layout.addLayout(log_header)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(125)
        self.log.setObjectName("LogBox")
        bottom_layout.addWidget(self.log)
        main.addWidget(bottom)

        self.statusBar().showMessage("Ready")

    def _panel(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("Panel")
        frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        return frame

    def _apply_styles(self) -> None:
        QApplication.instance().setFont(QFont("Segoe UI", 10))
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f4f6f8;
                color: #172033;
            }
            #Title {
                font-size: 26px;
                font-weight: 700;
                letter-spacing: 0px;
            }
            #Subtitle, #Muted {
                color: #647084;
            }
            #SectionTitle {
                font-size: 13px;
                font-weight: 700;
                color: #111827;
            }
            #Panel {
                background: #ffffff;
                border: 1px solid #dfe5ee;
                border-radius: 8px;
            }
            QTextEdit, QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QListWidget {
                background: #fbfcfe;
                border: 1px solid #d9e1ec;
                border-radius: 6px;
                padding: 7px;
                selection-background-color: #2563eb;
            }
            QTextEdit:focus, QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #2563eb;
            }
            QPushButton, QToolButton {
                background: #eef2f7;
                border: 1px solid #d4dce8;
                border-radius: 6px;
                padding: 8px 12px;
                font-weight: 600;
            }
            QPushButton:hover, QToolButton:hover {
                background: #e3eaf3;
            }
            QPushButton:disabled {
                color: #8a94a6;
                background: #edf0f4;
            }
            #PrimaryButton {
                color: white;
                background: #2563eb;
                border: 1px solid #1d4ed8;
            }
            #PrimaryButton:hover {
                background: #1d4ed8;
            }
            QCheckBox {
                spacing: 8px;
            }
            #LogBox {
                background: #111827;
                color: #dbeafe;
                border: 0;
                font-family: Consolas;
                font-size: 9pt;
            }
            """
        )

    def _current_provider(self) -> Provider:
        return self.providers[self.provider_combo.currentText()]

    def _on_provider_changed(self) -> None:
        provider = self._current_provider()
        current = Path(self.output_edit.text() or str(APP_DIR / "voice_output.wav"))
        self.output_edit.setText(str(current.with_suffix(provider.extension)))
        self._render_provider_options()
        self.statusBar().showMessage(f"Selected {provider.name}")

    def _render_provider_options(self) -> None:
        while self.options_grid.count():
            item = self.options_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.field_widgets = {}
        provider = self._current_provider()
        self.provider_note.setText(PROVIDER_NOTES.get(provider.name, ""))
        for row, field in enumerate(provider.fields):
            label = QLabel(field.label)
            label.setObjectName("Muted")
            widget = self._field_widget(field)
            self.field_widgets[field.key] = widget
            self.options_grid.addWidget(label, row, 0)
            self.options_grid.addWidget(widget, row, 1)
        self.options_grid.setRowStretch(len(provider.fields), 1)

    def _field_widget(self, field: Field) -> QWidget:
        if field.kind == "choice":
            combo = QComboBox()
            combo.setEditable(True)
            combo.addItems(field.values)
            combo.setCurrentText(str(field.default))
            return combo
        if field.kind == "bool":
            check = QCheckBox()
            check.setChecked(bool(field.default))
            return check
        if field.kind == "int":
            spin = QSpinBox()
            spin.setRange(int(field.minimum or 0), int(field.maximum or 999999))
            spin.setValue(int(field.default))
            return spin
        if field.kind == "float":
            spin = QDoubleSpinBox()
            spin.setDecimals(3)
            spin.setSingleStep(0.05)
            spin.setRange(float(field.minimum if field.minimum is not None else -999999), float(field.maximum or 999999))
            spin.setValue(float(field.default))
            return spin
        if field.kind == "file":
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            edit = QLineEdit(str(field.default))
            button = QToolButton()
            button.setText("...")
            button.clicked.connect(lambda: self._browse_file(edit))
            layout.addWidget(edit, 1)
            layout.addWidget(button)
            row.setProperty("line_edit", edit)
            return row
        edit = QLineEdit(str(field.default))
        return edit

    def _field_value(self, widget: QWidget) -> object:
        if isinstance(widget, QComboBox):
            return widget.currentText()
        if isinstance(widget, QCheckBox):
            return widget.isChecked()
        if isinstance(widget, QDoubleSpinBox):
            return widget.value()
        if isinstance(widget, QSpinBox):
            return widget.value()
        if isinstance(widget, QLineEdit):
            return widget.text()
        edit = widget.property("line_edit")
        if isinstance(edit, QLineEdit):
            return edit.text()
        return ""

    def _set_field_value(self, widget: QWidget, value: object) -> None:
        if isinstance(widget, QComboBox):
            widget.setCurrentText(str(value))
        elif isinstance(widget, QCheckBox):
            widget.setChecked(bool(value))
        elif isinstance(widget, QDoubleSpinBox):
            widget.setValue(float(value))
        elif isinstance(widget, QSpinBox):
            widget.setValue(int(value))
        elif isinstance(widget, QLineEdit):
            widget.setText(str(value))
        else:
            edit = widget.property("line_edit")
            if isinstance(edit, QLineEdit):
                edit.setText(str(value))

    def _collect_options(self) -> dict[str, object]:
        return {key: self._field_value(widget) for key, widget in self.field_widgets.items()}

    def _save_provider_preset(self) -> None:
        presets = self._read_presets()
        provider_name = self._current_provider().name
        presets[provider_name] = self._collect_options()
        PRESET_FILE.write_text(json.dumps(presets, indent=2), encoding="utf-8")
        self._append_log(f"Saved preset: {provider_name}")
        self.statusBar().showMessage(f"Saved preset for {provider_name}")

    def _load_provider_preset(self) -> None:
        provider_name = self._current_provider().name
        presets = self._read_presets()
        options = presets.get(provider_name)
        if not options:
            QMessageBox.information(self, "No preset", "Provider nay chua co preset da luu.")
            return
        for key, value in options.items():
            widget = self.field_widgets.get(key)
            if widget is not None:
                self._set_field_value(widget, value)
        self._append_log(f"Loaded preset: {provider_name}")
        self.statusBar().showMessage(f"Loaded preset for {provider_name}")

    def _read_presets(self) -> dict[str, dict[str, object]]:
        if not PRESET_FILE.exists():
            return {}
        try:
            data = json.loads(PRESET_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _browse_file(self, edit: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Select file", str(APP_DIR))
        if path:
            edit.setText(path)

    def _browse_output(self) -> None:
        provider = self._current_provider()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save audio",
            self.output_edit.text(),
            f"Audio (*{provider.extension});;All files (*.*)",
        )
        if path:
            self.output_edit.setText(path)

    def _start_generate(self) -> None:
        text = clean_text(self.text_edit.toPlainText())
        if not text:
            QMessageBox.warning(self, "Missing text", "Nhap noi dung can tao voice.")
            return
        output = Path(self.output_edit.text()).expanduser()
        if not output.parent.exists():
            QMessageBox.warning(self, "Invalid output", "Thu muc output khong ton tai.")
            return
        provider = self._current_provider()
        self.generate_button.setEnabled(False)
        self.statusBar().showMessage(f"Generating with {provider.name}...")
        self.worker = GenerateWorker(provider, text, output, self._collect_options())
        self.worker.log.connect(self._append_log)
        self.worker.finished_ok.connect(self._on_generate_done)
        self.worker.failed.connect(self._on_generate_failed)
        self.worker.finished.connect(lambda: self.generate_button.setEnabled(True))
        self.worker.start()

    def _on_generate_done(self, output: str) -> None:
        self.last_output = Path(output)
        self._append_log(f"Done: {output}")
        self.statusBar().showMessage("Finished")
        self._add_history(self.last_output)
        if self.auto_play_check.isChecked():
            self._play_audio()

    def _on_generate_failed(self, error: str) -> None:
        self._append_log(f"Error: {error}")
        self.statusBar().showMessage("Failed")
        QMessageBox.critical(self, "Generate failed", error)

    def _play_audio(self) -> None:
        output = self._action_output()
        if not output.exists():
            QMessageBox.warning(self, "Missing audio", "Chua co file audio de phat.")
            return
        self.player.setSource(QUrl.fromLocalFile(str(output)))
        self.player.play()
        self._append_log(f"Play: {output}")

    def _open_output_folder(self) -> None:
        output = self._action_output()
        folder = output.parent
        if folder.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        else:
            QMessageBox.warning(self, "Missing folder", "Thu muc output khong ton tai.")

    def _action_output(self) -> Path:
        return self.last_output or Path(self.output_edit.text()).expanduser()

    def _sync_player_buttons(self, *_args: object) -> None:
        is_playing = self.player.playbackState() == QMediaPlayer.PlayingState
        self.play_button.setEnabled(not is_playing)
        self.pause_button.setEnabled(is_playing)

    def _update_metrics(self) -> None:
        text = clean_text(self.text_edit.toPlainText())
        words = len(text.split()) if text else 0
        self.metrics_label.setText(f"{len(text)} chars | {words} words")

    def _append_log(self, message: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log.append(f"[{stamp}] {message}")

    def _load_history(self) -> None:
        self.history_list.clear()
        if not HISTORY_FILE.exists():
            return
        try:
            items = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        for item in items[:30]:
            self._insert_history_item(Path(item["path"]), item.get("provider", ""), item.get("created_at", ""), save=False)

    def _add_history(self, output: Path) -> None:
        self._insert_history_item(output, self._current_provider().name, datetime.now().strftime("%Y-%m-%d %H:%M"), save=True)

    def _insert_history_item(self, output: Path, provider: str, created_at: str, save: bool) -> None:
        item = QListWidgetItem(f"{output.name}\n{provider} | {created_at}")
        item.setData(Qt.UserRole, str(output))
        self.history_list.insertItem(0, item)
        if self.history_list.count() > 30:
            self.history_list.takeItem(self.history_list.count() - 1)
        if save:
            self._save_history()

    def _save_history(self) -> None:
        items = []
        for index in range(self.history_list.count()):
            item = self.history_list.item(index)
            path = item.data(Qt.UserRole)
            meta = item.text().splitlines()[-1]
            provider, _, created_at = meta.partition(" | ")
            items.append({"path": path, "provider": provider, "created_at": created_at})
        HISTORY_FILE.write_text(json.dumps(items, indent=2), encoding="utf-8")

    def _clear_history(self) -> None:
        self.history_list.clear()
        HISTORY_FILE.unlink(missing_ok=True)

    def _open_history_item(self, item: QListWidgetItem) -> None:
        path = Path(item.data(Qt.UserRole))
        if path.exists():
            self.last_output = path
            self.output_edit.setText(str(path))
            self._play_audio()
        else:
            QMessageBox.warning(self, "Missing audio", "File audio trong history khong con ton tai.")


def main() -> int:
    app = QApplication(sys.argv)
    window = VoiceStudioQt()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
