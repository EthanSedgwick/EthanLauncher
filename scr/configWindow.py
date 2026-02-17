import os
import shutil
import json

class SettingsManager:
    def __init__(self, settings_file):
        self.settings_file = settings_file
        self.settings = {}
        self.load_settings()

    def load_settings(self):
        """Loads settings from the file into a dictionary."""
        if not os.path.exists(self.settings_file):
            self.create_default_settings()

        self.settings = {}
        
        with open(self.settings_file, "r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                # Skip empty lines and lines with braces
                if not line or line.startswith("{") or line.startswith("}"):
                    continue
                
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"')  # Remove surrounding quotes if present
                    self.settings[key] = value

    def save_settings(self):
        """Saves the current settings to the file."""
        with open(self.settings_file, "w", encoding="utf-8") as file:
            for key, value in self.settings.items():
                file.write(f"{key}={value}\n")

    def get_setting(self, key, default=None):
        """Returns the value of a specific setting, or a default if not found."""
        return self.settings.get(key, default)

    def create_default_settings(self):
        default_settings = """gui=
            {
            language=l_english
            }
            graphics=
            {
            size=
            {
                x=1920
                y=1080
            }

            refreshRate=60
            fullScreen=no
            borderless=yes
            shadows=no
            shadowSize=2048
            multi_sampling=0
            anisotropic_filtering=0
            gamma=50.000000
            }
            sound_fx_volume=100.000000
            music_volume=100.000000
            scroll_speed=50.000000
            camera_rotation_speed=50.000000
            zoom_speed=50.000000
            mouse_speed=50.000000
            master_volume=100.000000
            ambient_volume=50.000000
            mapRenderingOptions=
            {
            renderTrees=yes
            onmap=yes
            simpleWater=no
            counter_distance=300.000000
            text_height=300.000000
            sea_text_alpha=120
            details=1.000
            }
            lastplayer="Player"
            lasthost=""
            serveradress="diplomacy.valkyrienet.com"
            debug_saves=0
            autosave="YEARLY"
            simple=no
            categories=
            {
            1 1 1 1 1 1 }
            update_time=1.000000
            shortcut=yes
            """
        with open(self.settings_file, "w", encoding="utf-8") as file:
            file.write(default_settings)

from PyQt6.QtWidgets import (
    QHBoxLayout, QLabel, QVBoxLayout, QDialog, QFormLayout, QLineEdit, QSlider,
    QPushButton, QMessageBox, QCheckBox, QComboBox, QFileDialog
)
from PyQt6.QtCore import Qt
import os

class ConfigDialog(QDialog):
    def __init__(self, current_root, parent, user_dir):
        super().__init__(parent)
        self.setWindowTitle("Configuration")
        self.setGeometry(400, 400, 400, 400)
        self.user_dir = user_dir
        self.settings_path = os.path.join(
            os.path.expanduser("~"),
            "Documents",
            "Paradox Interactive",
            "Victoria II",
            self.user_dir,
            "settings.txt"
        )
        self.game_root = current_root
        self.launcher_settings_file = os.path.join(self.game_root, "mod", "launcher_configs.json")
        self.settings_manager = SettingsManager(self.settings_path)
        self.initUI()

    def _game_root_has_executable(self, path):
        """Return True if path contains v2game.exe."""
        return path and os.path.exists(os.path.join(path, "v2game.exe"))

    def _browse_game_directory(self):
        """Let user pick Victoria II folder; update line edit if valid."""
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        folder = QFileDialog.getExistingDirectory(
            self, "Select Victoria II Installation Folder", self.game_root or "", options=options
        )
        if not folder or not folder.strip():
            return
        if not self._game_root_has_executable(folder):
            QMessageBox.warning(
                self,
                "Invalid folder",
                "The selected folder does not contain v2game.exe. Please choose your Victoria II installation folder.",
            )
            return
        self.game_directory_input.setText(folder)
        self._new_game_root = folder

    def initUI(self):
        self._new_game_root = None  # Set when user picks a new path via Browse
        main_layout = QVBoxLayout(self)
        layout = QFormLayout()

        with open(self.launcher_settings_file, "r", encoding="utf-8") as file:
            launcher_config = json.load(file)

        # Game directory (path to Victoria II install)
        self.game_directory_input = QLineEdit(self.game_root or "")
        self.game_directory_input.setReadOnly(True)
        self.game_directory_input.setPlaceholderText("Path to folder containing v2game.exe")
        game_dir_layout = QHBoxLayout()
        game_dir_layout.addWidget(self.game_directory_input)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_game_directory)
        game_dir_layout.addWidget(browse_btn)
        layout.addRow("Game directory:", game_dir_layout)

        # Screen Resolution
        self.resolution_input = QComboBox()
        self.resolution_input.addItem("3840x2160")
        self.resolution_input.addItem("2560x1440")
        self.resolution_input.addItem("1920x1080")
        self.resolution_input.addItem("1600x900")
        self.resolution_input.addItem("1366x768")
        self.resolution_input.addItem("1280x720")
        self.resolution_input.addItem("1024x600")
        self.resolution_input.addItem("800x600")

        self.resolution_input.setCurrentText(f"{self.settings_manager.get_setting('x')}x{self.settings_manager.get_setting('y')}")
        layout.addRow("Screen Resolution:", self.resolution_input)


        # Fullscreen and Borderless
        self.fullscreen_checkbox = QCheckBox("Fullscreen")
        self.fullscreen_checkbox.setChecked(self.settings_manager.get_setting("fullScreen") == "yes")
        self.borderless_checkbox = QCheckBox("Borderless")
        self.borderless_checkbox.setChecked(self.settings_manager.get_setting("borderless") == "yes")
        layout.addRow(self.fullscreen_checkbox)
        layout.addRow(self.borderless_checkbox)

        #Intro
        self.skip_intro_checkbox = QCheckBox("Skip Intro")
        self.skip_intro_checkbox.setChecked(int(launcher_config["skipintro"]))
        layout.addRow(self.skip_intro_checkbox)

        # Sound Volume
        self.master_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.master_volume_slider.setMinimum(0)
        self.master_volume_slider.setMaximum(100)
        self.master_volume_slider.setValue(int(float(self.settings_manager.get_setting("master_volume"))))
        layout.addRow("Master Volume:", self.master_volume_slider)

        self.music_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.music_volume_slider.setMinimum(0)
        self.music_volume_slider.setMaximum(100)
        self.music_volume_slider.setValue(int(float(self.settings_manager.get_setting("music_volume"))))
        layout.addRow("Music Volume:", self.music_volume_slider)

        self.sound_fx_slider = QSlider(Qt.Orientation.Horizontal)
        self.sound_fx_slider.setMinimum(0)
        self.sound_fx_slider.setMaximum(100)
        self.sound_fx_slider.setValue(int(float(self.settings_manager.get_setting("sound_fx_volume"))))
        layout.addRow("Sound FX Volume:", self.sound_fx_slider)

        self.ambient_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.ambient_volume_slider.setMinimum(0)
        self.ambient_volume_slider.setMaximum(100)
        self.ambient_volume_slider.setValue(int(float(self.settings_manager.get_setting("ambient_volume"))))
        layout.addRow("Ambient Volume:", self.ambient_volume_slider)

        # Last Player
        self.lastplayer_input = QLineEdit(self.settings_manager.get_setting("lastplayer"))
        layout.addRow("Player Name:", self.lastplayer_input)

        # Autosave
        self.autosave_input = QComboBox()
        self.autosave_input.addItem("FIVE_YEAR")
        self.autosave_input.addItem("YEARLY")
        self.autosave_input.addItem("HALFYEAR")
        self.autosave_input.addItem("MONTHLY")
        self.autosave_input.setCurrentText(self.settings_manager.get_setting("autosave", "YEARLY"))
        layout.addRow("Autosave Frequency:", self.autosave_input)

        # Debug Saves
        self.debug_saves_checkbox = QCheckBox("Enable Debug Saves")
        self.debug_saves_checkbox.setChecked(self.settings_manager.get_setting("debug_saves", "0") == "1")
        layout.addRow(self.debug_saves_checkbox)

        self.realtime_mode_checkbox = QCheckBox("Realtime Priority Mode")
        self.realtime_mode_checkbox.setChecked(int(launcher_config["realtime"]))
        self.realtime_mode_checkbox.setToolTip("Enables realtime priority mode in task manager. If unchecked, uses high priority instead.")
        layout.addRow(self.realtime_mode_checkbox)

        self.merge_event_modifiers_checkbox = QCheckBox("Automatically merge event_modifiers between mods")
        self.merge_event_modifiers_checkbox.setChecked(bool(int(launcher_config.get("merge_event_modifiers", 1))))
        self.merge_event_modifiers_checkbox.setToolTip("Ticking this box loads the z_launcher mod.")
        layout.addRow(self.merge_event_modifiers_checkbox)

        self.update_time_slider = QSlider(Qt.Orientation.Horizontal)
        self.update_time_slider.setMinimum(1)
        self.update_time_slider.setMaximum(100)
        self.update_time_slider.setValue(int(float(launcher_config["update_time"])))
        self.update_time_slider.setToolTip("Increases game speed at the cost of higher input lag. Higher is faster, with more input lag.")

        self.update_time_slider.valueChanged.connect(self.on_update_time_changed)
        self.update_time_slider_label = QLabel(f"{self.update_time_slider.value()}")
        layout.addRow(layout.addRow("Update Time:", self.update_time_slider), self.update_time_slider_label)

        # Clean Cache
        self.clean_cache_button = QPushButton("Clear Cache")
        self.clean_cache_button.clicked.connect(self.clear_cache)
        layout.addRow(self.clean_cache_button)

        self.open_saves_button = QPushButton("Open Save Folder")
        self.open_saves_button.clicked.connect(self.open_saves)
        layout.addRow(self.open_saves_button)

        # Buttons (OK, Cancel)
        button_layout = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.save_settings)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        layout.addRow(button_layout)
        main_layout.addLayout(layout)
        self.setLayout(main_layout)    

    def on_update_time_changed(self, value):
        self.update_time_slider_label.setText(f"{value}")    

    def save_settings(self):
        parent = self.parent()
        if self._new_game_root and self._game_root_has_executable(self._new_game_root):
            parent.game_root = self._new_game_root
            parent.settings_file = os.path.join(self._new_game_root, "mod", "launcher_configs.json")
            if hasattr(parent, "_save_game_root_to_settings"):
                parent._save_game_root_to_settings(self._new_game_root)
            mod_folder = os.path.join(self._new_game_root, "mod")
            os.makedirs(mod_folder, exist_ok=True)
            if not os.path.exists(parent.settings_file):
                with open(parent.settings_file, "w", encoding="utf-8") as f:
                    json.dump({
                        "checked_mods": [],
                        "game_root": self._new_game_root,
                        "update_time": 1,
                        "realtime": 0,
                        "skipintro": 0,
                        "presets": {},
                        "merge_event_modifiers": 1,
                    }, f, indent=4)
            self.game_root = self._new_game_root
            self.launcher_settings_file = parent.settings_file
            if hasattr(parent, "load_mods"):
                parent.load_mods()

        updated_settings = {
            'fullScreen': "yes" if self.fullscreen_checkbox.isChecked() else "no",
            'borderless': "yes" if self.borderless_checkbox.isChecked() else "no",
            'sound_fx_volume': f"{self.sound_fx_slider.value():.6f}",
            'music_volume': f"{self.music_volume_slider.value():.6f}",
            'master_volume': f"{self.master_volume_slider.value():.6f}",
            'ambient_volume': f"{self.ambient_volume_slider.value():.6f}",
            'lastplayer': self.lastplayer_input.text(),
            'autosave': self.autosave_input.currentText(),
            'debug_saves': "1" if self.debug_saves_checkbox.isChecked() else "0",
            'x': self.resolution_input.currentText().split('x')[0],
            'y': self.resolution_input.currentText().split('x')[1],
        }

        # Read the existing settings
        with open(self.settings_path, "r", encoding="utf-8") as file:
            lines = file.readlines()

        # Replace or update lines that start with the keys
        for key, value in updated_settings.items():
            for i in range(len(lines)):
                if lines[i].startswith(key):
                    lines[i] = f"{key}={value}\n"
                    break

        # Write the updated lines back to the file
        with open(self.settings_path, "w", encoding="utf-8") as file:
            file.writelines(lines)

        # Update the update_time in the launcher config file
        with open(self.launcher_settings_file, "r", encoding="utf-8") as file:
            launcher_config = json.load(file)

        launcher_config["game_root"] = self.game_root
        launcher_config["update_time"] = f"{self.update_time_slider.value()}"
        launcher_config["realtime"] = "1" if self.realtime_mode_checkbox.isChecked() else "0"
        launcher_config["skipintro"] = "1" if self.skip_intro_checkbox.isChecked() else "0"
        launcher_config["merge_event_modifiers"] = "1" if self.merge_event_modifiers_checkbox.isChecked() else "0"
        with open(self.launcher_settings_file, "w", encoding="utf-8") as file:
            json.dump(launcher_config, file, indent=4)

        self.skip_intro_change(self.skip_intro_checkbox.isChecked())

        self.accept()

    def clear_cache(self):
        cache_path = os.path.join(
            os.path.expanduser("~"),
            "Documents",
            "Paradox Interactive",
            "Victoria II",
            self.user_dir
        )
        map_folder = os.path.join(cache_path, "map")
        gfx_folder = os.path.join(cache_path, "gfx")
        music_folder = os.path.join(cache_path, "music")

        # Confirm deletion
        confirm_msg = QMessageBox.question(
            self,
            "Clear Cache",
            "Are you sure you want to delete the map, gfx, and music folders? This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if confirm_msg == QMessageBox.StandardButton.Yes:
            for folder in [map_folder, gfx_folder, music_folder]:
                if os.path.exists(folder):
                    shutil.rmtree(folder)
            pass  # Cache cleared
        else:
            pass  # User cancelled

    def open_saves(self):
        saves_folder = os.path.join(
            os.path.expanduser("~"),
            "Documents",
            "Paradox Interactive",
            "Victoria II",
            self.user_dir,
            "save games"
        )
        if not os.path.exists(saves_folder):
            os.mkdir(saves_folder)
        else:
            os.startfile(saves_folder)

    def skip_intro_change(self, checked):
        movie_folder = os.path.join(self.game_root, "movies")
        disabled_folder = os.path.join(self.game_root, "moviesdisabled")
        if checked:
            if os.path.exists(movie_folder):
                os.rename(movie_folder, disabled_folder)
        else:
            if os.path.exists(disabled_folder):
                os.rename(disabled_folder, movie_folder)


