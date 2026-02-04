import os
import requests
import re
import shutil
import tempfile
import zipfile
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
)
from PyQt6.QtCore import Qt, QObject, QThread, pyqtSignal
from datetime import datetime
import webbrowser


class _UpdateWorker(QObject):
    status = pyqtSignal(str)
    success = pyqtSignal(str)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, dialog: "UpdateCheckerDialog", mod_name: str, zipball_url: str, latest_tag: str):
        super().__init__()
        self._dialog = dialog
        self._mod_name = mod_name
        self._zipball_url = zipball_url
        self._latest_tag = latest_tag

    def run(self):
        try:
            self.status.emit(f"Downloading source for {self._mod_name} {self._latest_tag}...")
            with tempfile.TemporaryDirectory(prefix="tglauncher_mod_update_") as td:
                zip_path = os.path.join(td, "release.zip")
                self._dialog._download_to_file(self._zipball_url, zip_path)

                self.status.emit(f"Extracting {self._mod_name} {self._latest_tag}...")
                with zipfile.ZipFile(zip_path, "r") as zf:
                    root = self._dialog._get_zip_root_folder(zf)
                    zf.extractall(td)

                extracted_root = os.path.join(td, root)
                if not os.path.isdir(extracted_root):
                    raise RuntimeError("Extracted zip root folder not found.")

                self.status.emit(f"Installing {self._mod_name} {self._latest_tag}...")
                copied_mod_files = self._dialog._copy_root_contents_to_mod_folder(extracted_root)

                # Write back version to any newly installed .mod files (top-level ones)
                if self._latest_tag:
                    for mod_file_path in copied_mod_files:
                        self._dialog._update_mod_version_field(mod_file_path, self._latest_tag)

            self.success.emit(f"Installed {self._mod_name} {self._latest_tag}.")
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


class UpdateCheckerDialog(QDialog):
    def __init__(self, mod_files, mod_folder, parent=None):
        super().__init__(parent)
        self.mod_files = mod_files
        self.mod_folder = mod_folder
        # row -> {"mod_name","github_url","release_info","zipball_url","latest_tag"}
        self._updates_by_row = {}
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Mod Update Checker")
        self.setFixedSize(680, 320)
        layout = QVBoxLayout()

        self.status_label = QLabel("Checking for updates...")
        layout.addWidget(self.status_label)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.mod_list = QListWidget()
        layout.addWidget(self.mod_list)

        buttons = QHBoxLayout()

        self.update_selected_button = QPushButton("Update selected")
        self.update_selected_button.clicked.connect(self.update_selected)
        self.update_selected_button.setEnabled(False)
        buttons.addWidget(self.update_selected_button)

        self.open_github_button = QPushButton("Open GitHub page")
        self.open_github_button.clicked.connect(self.open_selected_github)
        self.open_github_button.setEnabled(False)
        buttons.addWidget(self.open_github_button)

        buttons.addStretch()

        self.ok_button = QPushButton("Close")
        self.ok_button.clicked.connect(self.close)
        buttons.addWidget(self.ok_button)

        layout.addLayout(buttons)

        self.setLayout(layout)

        self.mod_list.itemSelectionChanged.connect(self.on_selection_changed)
        self.mod_list.itemDoubleClicked.connect(self.on_item_double_clicked)

        self.check_for_updates()

    def _set_busy(self, busy: bool):
        # 0..0 makes an indeterminate (marquee) progress bar
        self.progress.setVisible(busy)
        self.progress.setRange(0, 0 if busy else 1)
        if not busy:
            self.progress.setValue(0)

        self.update_selected_button.setEnabled(not busy and self.mod_list.currentRow() >= 0)
        self.open_github_button.setEnabled(not busy and self.mod_list.currentRow() >= 0)
        self.ok_button.setEnabled(not busy)
        self.mod_list.setEnabled(not busy)

    def _repo_from_github_url(self, github_url: str) -> str | None:
        m = re.match(r"^https?://github\.com/([^/]+)/([^/#?]+)", (github_url or "").strip())
        if not m:
            return None
        return f"{m.group(1)}/{m.group(2)}"

    def _api_json(self, url: str):
        resp = requests.get(url, headers={"User-Agent": "TGLauncher"}, timeout=25)
        if resp.status_code != 200:
            return None
        return resp.json()

    def _download_to_file(self, url: str, out_path: str) -> None:
        with requests.get(url, headers={"User-Agent": "TGLauncher"}, stream=True, timeout=90) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)

    def _get_zip_root_folder(self, zf: zipfile.ZipFile) -> str:
        # GitHub zipballs contain a single root folder like owner-repo-sha/
        roots = set()
        for name in zf.namelist():
            if not name or name.endswith("/") is False and "/" not in name:
                # ignore any weird top-level file; still compute roots via split
                pass
            first = name.split("/", 1)[0]
            if first:
                roots.add(first)
        if len(roots) != 1:
            raise RuntimeError(f"Expected 1 root folder in zip, found: {sorted(roots)}")
        return next(iter(roots))

    def _update_mod_version_field(self, mod_file_path: str, new_version: str) -> None:
        try:
            with open(mod_file_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except FileNotFoundError:
            return

        out = []
        replaced = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("version") and "=" in stripped:
                out.append(f'version="{new_version}"\n')
                replaced = True
            else:
                out.append(line)

        if not replaced:
            if out and not out[-1].endswith("\n"):
                out[-1] += "\n"
            out.append(f'version="{new_version}"\n')

        with open(mod_file_path, "w", encoding="utf-8", errors="ignore") as f:
            f.writelines(out)

    def _copy_root_contents_to_mod_folder(self, extracted_root_dir: str) -> list[str]:
        copied_mod_files = []
        for entry in os.listdir(extracted_root_dir):
            src_path = os.path.join(extracted_root_dir, entry)
            dest_path = os.path.join(self.mod_folder, entry)

            if os.path.isdir(src_path):
                # Allow overwrites by merging trees and overwriting conflicts
                shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
            elif os.path.isfile(src_path):
                # allow overwriting files (including .mod)
                shutil.copy2(src_path, dest_path)
                if entry.lower().endswith(".mod"):
                    copied_mod_files.append(dest_path)
        return copied_mod_files

    def check_for_updates(self):
        mods_with_updates = []  # [(displayText, githubUrl, modName, releaseInfo, zipballUrl, latestTag)]
        for mod_name, mod_info in self.mod_files.items():
            github_url = mod_info.get('github')
            version = mod_info.get('version')
            mod_file_path = os.path.join(self.mod_folder, mod_info['file'])

            if github_url:
                try:
                    repo = self._repo_from_github_url(github_url)
                    if not repo:
                        continue

                    # Latest release
                    release_api_url = f"https://api.github.com/repos/{repo}/releases/latest"
                    latest_release_info = self._api_json(release_api_url) or {}
                    latest_release_tag = latest_release_info.get("tag_name")
                    latest_release_date = latest_release_info.get("published_at")
                    zipball_url = latest_release_info.get("zipball_url")

                    # Latest commit (informational)
                    commit_api_url = f"https://api.github.com/repos/{repo}/commits"
                    commit_response = requests.get(commit_api_url, headers={"User-Agent": "TGLauncher"}, timeout=25)
                    latest_commit_date = None
                    if commit_response.status_code == 200:
                        latest_commit_info = commit_response.json()
                        latest_commit_date = latest_commit_info[0]['commit']['committer']['date']

                    # Check modification date of local mod file
                    mod_last_modified_timestamp = os.path.getmtime(mod_file_path)
                    mod_last_modified_date = datetime.utcfromtimestamp(mod_last_modified_timestamp)

                    has_new_release = False
                    has_new_commit = False
                    # Compare release date
                    if latest_release_date:
                        latest_release_date = datetime.strptime(latest_release_date, "%Y-%m-%dT%H:%M:%SZ")
                        # Prefer tag compare; fallback to timestamp if version missing
                        if (latest_release_tag and version and latest_release_tag != version) or (not version and latest_release_date > mod_last_modified_date):
                            has_new_release = True
                        elif latest_release_tag and not version:
                            # If local version missing, any tagged release newer than file timestamp counts
                            if latest_release_date > mod_last_modified_date:
                                has_new_release = True
                    
                    # Compare commit date
                    if latest_commit_date:
                        latest_commit_date = datetime.strptime(latest_commit_date, "%Y-%m-%dT%H:%M:%SZ")
                        if latest_commit_date > mod_last_modified_date:
                            has_new_commit = True

                    if has_new_release and has_new_commit:
                        mods_with_updates.append((f"{mod_name} - New release {latest_release_tag} and new commits available.", github_url, mod_name, latest_release_info, zipball_url, latest_release_tag))
                    elif has_new_release:
                        mods_with_updates.append((f"{mod_name} - New release available: {latest_release_tag}", github_url, mod_name, latest_release_info, zipball_url, latest_release_tag))
                    elif has_new_commit:
                        mods_with_updates.append((f"{mod_name} - New commits available (no new release).", github_url, mod_name, None, None, None))

                except Exception as e:
                    self.status_label.setText(f"An error occurred while displaying the updates, report it to Wyrm on the discord server: {e}")

        if mods_with_updates:
            try:
                self.mod_list.clear()
                self._updates_by_row = {}
                for update_text, url, mod_name, release_info, zipball_url, latest_tag in mods_with_updates:
                    item = QListWidgetItem(update_text)
                    if url:
                        item.setData(Qt.ItemDataRole.UserRole, url)
                    self.mod_list.addItem(item)
                    row = self.mod_list.row(item)
                    self._updates_by_row[row] = {
                        "mod_name": mod_name,
                        "github_url": url,
                        "release_info": release_info,
                        "zipball_url": zipball_url,
                        "latest_tag": latest_tag,
                    }
                self.status_label.setText("Updates found. Select a mod to update; double-click opens GitHub.")
            except Exception as e:
                self.status_label.setText(f"An error occurred while displaying the updates, report it to Wyrm on the discord server: {e}")
        else:
            self.status_label.setText("All mods are up to date.")

        self.on_selection_changed()

    def on_selection_changed(self):
        row = self.mod_list.currentRow()
        has_selection = row >= 0
        self.update_selected_button.setEnabled(has_selection)
        self.open_github_button.setEnabled(has_selection)

    def on_item_double_clicked(self, item):
        url = item.data(Qt.ItemDataRole.UserRole)
        if url:
            webbrowser.open(url)

    def open_selected_github(self):
        row = self.mod_list.currentRow()
        if row < 0:
            return
        info = self._updates_by_row.get(row) or {}
        url = info.get("github_url")
        if url:
            webbrowser.open(url)

    def update_selected(self):
        row = self.mod_list.currentRow()
        if row < 0:
            return
        info = self._updates_by_row.get(row)
        if not info:
            return

        mod_name = info.get("mod_name") or "Mod"
        zipball_url = info.get("zipball_url")
        latest_tag = info.get("latest_tag") or ""

        if not zipball_url:
            QMessageBox.information(self, "No release to install", "This entry does not have a GitHub Release zipball to install.")
            return

        self._set_busy(True)

        # Run update in background so UI stays responsive
        self._thread = QThread(self)
        self._worker = _UpdateWorker(self, mod_name, zipball_url, latest_tag)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)

        def on_status(msg: str):
            self.status_label.setText(msg)

        def on_success(msg: str):
            self.status_label.setText(msg)
            QMessageBox.information(self, "Update complete", msg)
            # Refresh mods + metadata (re-read .mod files) and then refresh this dialog list
            parent = self.parent()
            if parent is not None and hasattr(parent, "load_mods"):
                try:
                    parent.load_mods()
                except Exception:
                    pass
            self.mod_files = getattr(parent, "mod_files", self.mod_files)
            self.check_for_updates()

        def on_error(err: str):
            QMessageBox.critical(self, "Update failed", f"Failed to update {mod_name}.\n\n{err}")
            self.status_label.setText(f"Update failed for {mod_name}: {err}")

        def on_finished():
            self._set_busy(False)
            self._thread.quit()
            self._thread.wait(2000)
            self._worker.deleteLater()
            self._thread.deleteLater()

        self._worker.status.connect(on_status)
        self._worker.success.connect(on_success)
        self._worker.error.connect(on_error)
        self._worker.finished.connect(on_finished)

        self._thread.start()