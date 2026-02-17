
import os
import json
import sys
import string
import time
from collections import deque
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QMessageBox, QLabel, QFileDialog,
    QPushButton, QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator,
    QSizePolicy, QDialog,
)
from PyQt6.QtCore import Qt
import subprocess
import threading

from PyQt6.QtGui import QIcon

from scr.configWindow import ConfigDialog
from scr.presetmanagerWindow import PresetManagerDialog
from scr.updatesWindow import UpdateCheckerDialog

Z_LAUNCHER_NAME = "z_launcher"
EVENT_MODIFIERS_FILE = "event_modifiers.txt"


class GameLauncher(QWidget):

    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon('scr/icon.ico'))

        self.mod_files = {}  # Dictionary to store {display_name: filename}
        self.mod_dependencies = {}  # Dictionary to store {mod_name: [dependencies]}
        
        # Get the directory of the running executable
        application_path = os.path.dirname(sys.argv[0])
        self._bootstrap_config_path = os.path.join(application_path, "launcher_configs.json")

        self.game_root = self._load_game_root_from_settings()
        if self.game_root and not self._game_root_has_executable(self.game_root):
            self.game_root = None

        if not self.game_root:
            self.default_game_roots = self._build_default_game_roots(application_path)
            for candidate in self.default_game_roots:
                if self._game_root_has_executable(candidate):
                    self.game_root = candidate
                    break

        while not self.game_root:
            QMessageBox.critical(
                self,
                "Game not found",
                "Victoria II (v2game.exe) was not found in the usual Steam/GOG locations. Please select your Victoria II installation folder.",
            )
            root, user_cancelled = self.get_game_root_from_user()
            if user_cancelled:
                sys.exit(1)
            if root:
                self.game_root = root
                break

        self._save_game_root_to_settings(self.game_root)
        self.config_file = "launcher_configs.json"
        self.settings_file = os.path.join(self.game_root, "mod", self.config_file)
        if not os.path.exists(self.settings_file):
            with open(self.settings_file, "w", encoding="utf-8") as file:
                json.dump({
                    "checked_mods": [],
                    "game_root": self.game_root,
                    "update_time": 1,
                    "realtime": 0,
                    "skipintro": 0,
                    "presets": {},
                    "merge_event_modifiers": 1
                }, file, indent=4)
        self.initUI()
        self.load_mods()
        self.loadSettings()

    def _game_root_has_executable(self, path):
        """Return True if path contains v2game.exe."""
        return path and os.path.exists(os.path.join(path, "v2game.exe"))

    def _load_game_root_from_settings(self):
        """Load stored game_root from bootstrap config (next to executable). Returns None if missing or invalid."""
        if not os.path.exists(self._bootstrap_config_path):
            return None
        try:
            with open(self._bootstrap_config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("game_root") or None
        except Exception:
            return None

    def _save_game_root_to_settings(self, game_root):
        """Persist game_root to bootstrap config so we can find the game next launch."""
        try:
            data = {}
            if os.path.exists(self._bootstrap_config_path):
                try:
                    with open(self._bootstrap_config_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    pass
            data["game_root"] = game_root
            with open(self._bootstrap_config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception:
            pass

    def get_game_root_from_user(self):
        """
        Ask the user to select the Victoria II installation folder.
        Returns (game_root or None, user_cancelled: bool).
        If user cancels the dialog, returns (None, True). If user picks a folder without v2game.exe, shows a warning and returns (None, False).
        """
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        folder = QFileDialog.getExistingDirectory(self, "Select Victoria II Installation Folder", options=options)
        if not folder or not folder.strip():
            return None, True
        if self._game_root_has_executable(folder):
            return folder, False
        QMessageBox.warning(
            self,
            "Invalid folder",
            "The selected folder does not contain v2game.exe. Please choose your Victoria II installation folder (the one that contains v2game.exe).",
        )
        return None, False

    def _get_available_drives(self):
        drives = []
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                drives.append(drive)
        return drives

    def _build_default_game_roots(self, application_path):
        roots = [
            application_path,
            os.path.dirname(application_path),
        ]

        for drive in self._get_available_drives():
            roots.append(os.path.join(drive, r"Program Files (x86)\Steam\steamapps\common\Victoria 2"))
            roots.append(os.path.join(drive, r"GOG Games\Victoria II"))

        # Preserve order but avoid duplicates.
        seen = set()
        deduped = []
        for root in roots:
            if root not in seen:
                seen.add(root)
                deduped.append(root)
        return deduped

    def initUI(self):
        self.setWindowTitle('The Greater Launcher')
        self.setGeometry(300, 300, 300, 400)

        layout = QVBoxLayout()
        
        
        # Mod tree structure
        self.mod_tree = QTreeWidget()
        self.mod_tree.setHeaderLabels(['Mods'])
        self.mod_tree.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self.mod_tree.itemChanged.connect(self.on_item_changed)

        # Top bar with mod-folder + refresh icons
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(0, 0, 0, 0)
        top_bar.setSpacing(4)

        # Open mod folder button (left)
        self.open_mod_folder_button = QPushButton("Open Mods Folder")
        self.open_mod_folder_button.setToolTip("Open mod directory")
        self.open_mod_folder_button.clicked.connect(self.open_mod_folder)
        self.open_mod_folder_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        top_bar.addWidget(self.open_mod_folder_button)

        # Refresh button (right)
        self.refresh_mods_button = QPushButton("Refresh")
        self.refresh_mods_button.setToolTip("Refresh mods list")
        self.refresh_mods_button.clicked.connect(self.refresh_mods)
        self.refresh_mods_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        top_bar.addWidget(self.refresh_mods_button)
        layout.addLayout(top_bar)

        layout.addWidget(self.mod_tree)

        # Buttons
        buttons_layout = QHBoxLayout()


        # Start button
        self.start_button = QPushButton('Start Game')
        self.start_button.clicked.connect(self.start_game)
        self.start_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        buttons_layout.addWidget(self.start_button)

        # Preset manager button
        self.preset_manager_button = QPushButton('Manage Pre-Sets')
        self.preset_manager_button.clicked.connect(self.preset_manager)
        self.preset_manager_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        buttons_layout.addWidget(self.preset_manager_button)

        # Configuration button to open config dialog
        self.config_button = QPushButton('Settings')
        self.config_button.clicked.connect(self.open_config_dialog)
        self.config_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        buttons_layout.addWidget(self.config_button)

        layout.addLayout(buttons_layout)

        buttons_layout2 = QHBoxLayout()

        # Check for Updates button
        self.update_button = QPushButton('Check for Updates')
        self.update_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.update_button.clicked.connect(self.check_for_updates)
        buttons_layout2.addWidget(self.update_button)

        # About button
        self.about_button = QPushButton('About')
        self.about_button.clicked.connect(self.open_about_dialog)
        self.about_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        buttons_layout2.addWidget(self.about_button)

        # Quit button
        self.quit_button = QPushButton('Quit')
        self.quit_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.quit_button.clicked.connect(self.close)
        buttons_layout2.addWidget(self.quit_button)

#        buttons_layout2.addStretch()

        layout.addLayout(buttons_layout2)

        self.setLayout(layout)

    def refresh_mods(self):
        """Re-scan the mod folder and refresh metadata, preserving checked mods when possible."""
        try:
            checked = self.get_checked_mods()
        except Exception:
            checked = []

        self.load_mods()

        try:
            self.set_checked_mods(checked)
        except Exception:
            pass

    def open_mod_folder(self):
        """Open the Victoria 2 mod directory in the system file explorer."""
        try:
            mod_folder = os.path.join(self.game_root, "mod")
            if not os.path.isdir(mod_folder):
                QMessageBox.warning(self, "Mod folder not found", f"Could not find mod folder:\n{mod_folder}")
                return
            # On Windows, os.startfile will open Explorer
            os.startfile(mod_folder)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open mod folder: {e}")

    def _get_mod_folder(self):
        """Return the Victoria 2 mod directory path."""
        return os.path.join(self.game_root, "mod")

    def _ensure_z_launcher_setup(self, mod_folder):
        """Create z_launcher folder, .mod file, common/event_modifiers.txt, and readme. Idempotent."""
        z_dir = os.path.join(mod_folder, Z_LAUNCHER_NAME)
        common_dir = os.path.join(z_dir, "common")
        os.makedirs(common_dir, exist_ok=True)
        mod_file_path = os.path.join(mod_folder, f"{Z_LAUNCHER_NAME}.mod")
        if not os.path.exists(mod_file_path):
            with open(mod_file_path, "w", encoding="utf-8") as f:
                f.write('name = "z_launcher"\n')
                f.write('path = "mod/z_launcher"\n')
                f.write('user_dir = "z_launcher"\n')
        em_path = os.path.join(common_dir, EVENT_MODIFIERS_FILE)
        if not os.path.exists(em_path):
            with open(em_path, "w", encoding="utf-8") as f:
                f.write("")
        readme_path = os.path.join(z_dir, "readme.txt")
        if not os.path.exists(readme_path):
            with open(readme_path, "w", encoding="utf-8") as f:
                f.write("This folder and mod is used to fix conflicts with event_modifiers and is hidden by default.\n")

    def _get_mods_with_event_modifiers(self, selected_mods, mod_folder):
        """Return list of selected mod names that have common/event_modifiers.txt."""
        result = []
        for mod_name in selected_mods:
            if mod_name not in self.mod_files:
                continue
            folder = self.mod_files[mod_name].get("folder")
            if not folder:
                continue
            path = os.path.join(mod_folder, folder, "common", EVENT_MODIFIERS_FILE)
            if os.path.isfile(path):
                result.append(mod_name)
        return result

    def _resolve_event_modifiers_load_order(self, mod_names):
        """
        Resolve load order for mods: alphanumeric by default, with dependencies forcing
        depended-on mods to load first. On cycle/error, fall back to a-z and print error.
        Returns list of mod names in load order (first = loaded first).
        """
        if not mod_names:
            return []
        # Build graph: dep -> mod for each (mod depends on dep) so dep must come before mod
        deps_map = {}
        for mod in mod_names:
            deps_map[mod] = [d for d in self.mod_dependencies.get(mod, []) if d in mod_names]
        # Topological sort (Kahn). If cycle, fall back to sorted.
        in_degree = {m: 0 for m in mod_names}
        for mod in mod_names:
            for dep in deps_map[mod]:
                in_degree[mod] += 1
        queue = deque(m for m in mod_names if in_degree[m] == 0)
        order = []
        # Reverse deps_map for "who depends on me"
        rev = {m: [] for m in mod_names}
        for mod in mod_names:
            for dep in deps_map[mod]:
                rev[dep].append(mod)
        while queue:
            m = queue.popleft()
            order.append(m)
            for other in rev[m]:
                in_degree[other] -= 1
                if in_degree[other] == 0:
                    queue.append(other)
        if len(order) != len(mod_names):
            print("Event modifiers load order: dependency cycle or missing dependency detected. Using alphanumeric order.")
            return sorted(mod_names)
        return order

    def _parse_event_modifiers_content(self, content):
        """
        Parse event_modifiers.txt: key=value lines, # is comment. Values can be multi-line
        if they contain { ; keep reading until matching }.
        Returns list of (key, value) in order; value may contain newlines.
        """
        pairs = []
        lines = content.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            s = line.strip()
            if not s or s.startswith("#"):
                i += 1
                continue
            if "=" not in s:
                i += 1
                continue
            key, value = s.split("=", 1)
            key = key.strip()
            value = value.strip()
            if "{" in value:
                depth = value.count("{") - value.count("}")
                while depth > 0 and i + 1 < len(lines):
                    i += 1
                    next_line = lines[i]
                    value += "\n" + next_line
                    depth += next_line.count("{") - next_line.count("}")
                value = value.strip()
            pairs.append((key, value))
            i += 1
        return pairs

    def _merge_event_modifiers_from_paths(self, mod_folder, ordered_mod_names):
        """
        Merge event_modifiers from the given mods in load order into z_launcher's file.
        First mod's content is used as base; then for each next: same key+value skip,
        same key different value overwrite (later mod wins), new key append to bottom.
        """
        merged_values = {}  # key -> value (last writer wins)
        merged_order = []   # keys in order of first appearance
        for mod_name in ordered_mod_names:
            folder = self.mod_files[mod_name]["folder"]
            path = os.path.join(mod_folder, folder, "common", EVENT_MODIFIERS_FILE)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception as e:
                print(f"Could not read {path}: {e}")
                continue
            for key, value in self._parse_event_modifiers_content(content):
                merged_values[key] = value
                if key not in merged_order:
                    merged_order.append(key)
        output_lines = []
        for key in merged_order:
            val = merged_values[key]
            output_lines.append(f"{key}={val}\n")
        return "".join(output_lines)

    def set_checked_mods(self, checked_mods):
        """Set the checked state of mods in the tree based on the provided list."""
        try:
            iterator = QTreeWidgetItemIterator(self.mod_tree, QTreeWidgetItemIterator.IteratorFlag.All)
            self.mod_tree.blockSignals(True)  # Prevent signals during setup
            while iterator.value():
                item = iterator.value()
                mod_name = item.text(0)
                if mod_name in checked_mods:
                    item.setCheckState(0, Qt.CheckState.Checked)
                else:
                    item.setCheckState(0, Qt.CheckState.Unchecked)
                iterator += 1
            self.mod_tree.blockSignals(False)  # Re-enable signals
        except Exception as e:
            QMessageBox.warning(self, 'Error', f"Error occurred when setting checked mods: {e}")

    def preset_manager(self):
        """Opens the preset manager dialog."""
        try:
            dialog = PresetManagerDialog(self.get_checked_mods(), self.settings_file, parent=self)
            
            if dialog.exec():
                self.checked_mods = dialog.checked_mods
                self.set_checked_mods(self.checked_mods)  # Apply the preset to the tree
                
                # Update the user_dir based on the newly checked mods
                self.get_checked_mods()  # This will update the user_dir based on the checked mods
                
                self.save_checked_mods()  # Save the new preset
        except Exception as e:
            QMessageBox.warning(self, 'Error', f"Error occurred in preset manager: {e}")

    def open_about_dialog(self):
        """Opens the about dialog with GitHub and Discord links."""
        try:
            about_dialog = QDialog(self)
            about_dialog.setWindowTitle("About TGLauncher")

            main_layout = QVBoxLayout(about_dialog)

            about_text = QLabel(
                "<h3 style='text-align: center;'>The Ethan Launcher</h3>"
                "<p style='text-align: center;'>A fork of The Greater Launcher originally created by The TGC Modding Team. This is the premiere Vic2 MP Launcher.</p>"
                "<p style='text-align: center;'>v1.0.0</p>"
                "<p style='text-align: center;'><a href='https://github.com/The-Grand-Combination/TGLauncher'>GitHub Repository</a><br>"
                "<a href='https://discord.gg/the-grand-combination-689466155978588176'>Support TGC for the original project by joining their Discord</a></p>"
            )
            about_text.setTextFormat(Qt.TextFormat.RichText)
            about_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            about_text.setOpenExternalLinks(True)
            about_text.setAlignment(Qt.AlignmentFlag.AlignCenter)

            main_layout.addWidget(about_text)

            button_layout = QHBoxLayout()
            close_button = QPushButton("OK")
            close_button.setFixedSize(80, 30)
            close_button.clicked.connect(about_dialog.accept)

            button_layout.addStretch()
            button_layout.addWidget(close_button)
            button_layout.addStretch()

            main_layout.addLayout(button_layout)

            about_dialog.exec()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error occurred trying to open the about tab: {e}")

    def check_for_updates(self):
        dialog = UpdateCheckerDialog(self.mod_files, os.path.join(self.game_root, "mod"))
        dialog.exec()

    def open_config_dialog(self):
        """Opens the configuration dialog."""
        try:
            dialog = ConfigDialog(self.game_root, self, self.user_dir)
            dialog.exec()
        except Exception as e:
            print(e)
            QMessageBox.warning(self, "Error", f"Error occurred in the configuration tab: {e}")

    def load_mods(self):
        mod_folder = os.path.join(self.game_root, "mod")
        
        if not os.path.exists(mod_folder):
            print(f"Mod folder does not exist: {mod_folder}")
            self.mod_tree.clear()
            return

        self.mod_files.clear()
        self.mod_dependencies.clear()
        self.mod_user_dirs = {}

        def _parse_mod_kv(line: str) -> tuple[str, str] | None:
            # Supports formats like: key="value" or key = "value"
            s = (line or "").strip()
            if not s or s.startswith("#") or s.startswith("//"):
                return None
            if "=" not in s:
                return None
            key, value = s.split("=", 1)
            key = key.strip()
            value = value.strip()
            if value.startswith('"') and value.endswith('"') and len(value) >= 2:
                value = value[1:-1]
            return key, value

        for file in os.listdir(mod_folder):
            if file.endswith(".mod"):
                try:
                    with open(os.path.join(mod_folder, file), 'r', encoding='utf-8', errors='ignore') as mod_file:
                        content = mod_file.read()
                        name = ""
                        dependencies = []
                        user_dir = ""
                        github = ""
                        version = ""
                        mod_path = ""  # e.g. "mod/ModFolder"
                        for line in content.split('\n'):
                            parsed = _parse_mod_kv(line)
                            if not parsed:
                                continue
                            key, value = parsed

                            if key == "name":
                                name = value
                            elif key == "dependencies":
                                deps_str = value.strip().strip("{}")
                                dependencies = [dep.strip().strip('"') for dep in deps_str.split(",") if dep.strip()]
                            elif key == "path":
                                mod_path = value
                            elif key == "user_dir":
                                user_dir = value
                            elif key == "github":
                                github = value
                            elif key == "version":
                                version = value

                        if name:
                            # Path is typically "mod/FolderName" -> folder name is after "mod/"
                            mod_folder_name = mod_path.split("/")[-1] if mod_path else ""
                            self.mod_files[name] = {
                                'file': file,
                                'path': mod_path,
                                'folder': mod_folder_name,
                                'github': github if github else None,
                                'version': version if version else None
                            }
                            self.mod_dependencies[name] = dependencies
                            self.mod_user_dirs[name] = user_dir
                except Exception as e:
                    print(f"An error reading the mod file {file}: {e}")

        self.mod_tree.blockSignals(True)
        self.mod_tree.clear()
        mod_items = {}

        for mod_name in self.mod_files.keys():
            if mod_name == "z_launcher":
                continue  # Hide launcher merge mod from list
            item = QTreeWidgetItem()
            item.setText(0, mod_name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            item.setCheckState(0, Qt.CheckState.Unchecked)
            mod_items[mod_name] = item

        for mod_name, dependencies in self.mod_dependencies.items():
            if mod_name == "z_launcher":
                continue
            if mod_name not in mod_items:
                continue
            if dependencies:
                for dep in dependencies:
                    if dep in mod_items:
                        mod_items[dep].addChild(mod_items[mod_name])
                        break
                else:
                    self.mod_tree.addTopLevelItem(mod_items[mod_name])
            else:
                self.mod_tree.addTopLevelItem(mod_items[mod_name])

        self.mod_tree.expandAll()
        self.mod_tree.blockSignals(False)

    def get_checked_mods(self):
        checked_mods = []
        last_user_dir_mod = None
        try:
            iterator = QTreeWidgetItemIterator(self.mod_tree, QTreeWidgetItemIterator.IteratorFlag.All)
            while iterator.value():
                item = iterator.value()
                if item.checkState(0) == Qt.CheckState.Checked:
                    mod_name = item.text(0)
                    if mod_name in self.mod_files:
                        checked_mods.append(mod_name)
                        if self.mod_user_dirs[mod_name]:
                            last_user_dir_mod = mod_name
                iterator += 1
            if last_user_dir_mod:
                self.user_dir = self.mod_user_dirs[last_user_dir_mod]
                print(f"User directory: {self.user_dir}")
            else:
                self.user_dir = ""
        except Exception as e:
            QMessageBox.warning(self, 'Error', f"An error occurred when getting the active mods: {e}")

        return checked_mods

    def start_game(self):
        selected_mods = self.get_checked_mods()

        with open(self.settings_file, "r", encoding="utf-8") as file:
            launcher_config = json.load(file)

        settings_path = os.path.join(
            os.path.expanduser("~"),
            "Documents",
            "Paradox Interactive",
            "Victoria II",
            self.user_dir,
            "settings.txt"
        )

        with open(settings_path, "r", encoding="utf-8") as file:
            lines = file.readlines()

        with open(settings_path, "w", encoding="utf-8") as file:
            for i in range(len(lines)):
                if lines[i].startswith("update_time"):
                    lines[i] = f"update_time={float(launcher_config['update_time']):.6f}\n"

            file.writelines(lines)

        mods_to_load = list(selected_mods)
        merge_event_modifiers = bool(int(launcher_config.get("merge_event_modifiers", 1)))
        if merge_event_modifiers and selected_mods:
            mod_folder = self._get_mod_folder()
            z_launcher_dir = os.path.join(mod_folder, Z_LAUNCHER_NAME)
            if not os.path.isdir(z_launcher_dir):
                self._ensure_z_launcher_setup(mod_folder)
            mods_with_em = self._get_mods_with_event_modifiers(selected_mods, mod_folder)
            if len(mods_with_em) > 1:
                t0 = time.perf_counter()
                order = self._resolve_event_modifiers_load_order(mods_with_em)
                merged_content = self._merge_event_modifiers_from_paths(mod_folder, order)
                z_launcher_common = os.path.join(mod_folder, Z_LAUNCHER_NAME, "common", EVENT_MODIFIERS_FILE)
                with open(z_launcher_common, "w", encoding="utf-8") as f:
                    f.write(merged_content)
                mods_to_load.append(Z_LAUNCHER_NAME)
                elapsed = time.perf_counter() - t0
                print(f"Event modifiers merge completed in {elapsed:.3f}s")

        if mods_to_load:
            mod_file_args = []
            for mod in mods_to_load:
                if mod == Z_LAUNCHER_NAME:
                    mod_file_args.append("-mod=mod/z_launcher.mod")
                else:
                    mod_file_args.append(f"-mod=mod/{self.mod_files[mod]['file']}")
            mods_argument = " ".join(mod_file_args)
            game_command = f'v2game.exe {mods_argument}'
            print(f"Starting game with mods: {game_command}")
        else:
            game_command = 'v2game.exe'
            print("Starting game without mods.")

        priority = "realtime" if str(launcher_config.get("realtime", 0)) == "1" else "high"
        full_command = (
            f'cd /d "{self.game_root}" && '
            f'start "Victoria II" /{priority} /affinity 1 /node 0 '
            f'{game_command}'
        )

        print(full_command)

        try:
            thread = threading.Thread(target=subprocess.run, args=(full_command,), kwargs={'shell': True})
            thread.start()
            if selected_mods:
                self.save_checked_mods()
            self.close()
        except Exception as e:
            QMessageBox.warning(self, 'Error', f"An error occurred when starting the game: {e}")


    def on_item_changed(self, item, column):
        if column == 0:
            try:
                check_state = item.checkState(0)
                self.mod_tree.blockSignals(True)
                self.save_checked_mods()
                self.mod_tree.blockSignals(False)
            except Exception as e:
                QMessageBox.warning(self, 'Error', f"An error occurred when changing the mod state: {e}")
    def loadSettings(self):
        checked_mods = []
        
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    checked_mods = settings.get("checked_mods", [])
                    self.game_root = settings.get('game_root', self.game_root)
        except Exception as e:
            QMessageBox.warning(self, 'Error', f"Error loading settings: {e}")
        
        self.load_mods()
        
        iterator = QTreeWidgetItemIterator(self.mod_tree, QTreeWidgetItemIterator.IteratorFlag.All)
        self.mod_tree.blockSignals(True)
        while iterator.value():
            item = iterator.value()
            mod_name = item.text(0)
            if mod_name in checked_mods:
                item.setCheckState(0, Qt.CheckState.Checked)
            else:
                item.setCheckState(0, Qt.CheckState.Unchecked)
            iterator += 1
        self.mod_tree.blockSignals(False)
        
        try:
            self.get_checked_mods()
        except Exception as e:
            QMessageBox.warning(self, 'Error', f"Error setting user directory: {e}")

    def save_checked_mods(self):
        checked_mods = self.get_checked_mods()
        settings = {}

        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            settings["checked_mods"] = checked_mods
            settings["game_root"] = self.game_root
            mod_folder = os.path.join(self.game_root, "mod")
            os.makedirs(mod_folder, exist_ok=True)
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=4)
        except Exception as e:
            QMessageBox.warning(self, 'Error', f"Error saving settings: {e}")
