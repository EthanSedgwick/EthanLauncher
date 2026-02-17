# Code Review: Python Standards, Readability & UI

## 1. Python coding standards (PEP 8 & best practices)

### Imports
- **Wildcard imports** (`from scr.configWindow import *`, `from scr.mainWindow import *` in launcher.py): Avoid `import *`. It hides dependencies and can cause name collisions. Use explicit imports (e.g. `from scr.configWindow import ConfigDialog`).
- **Duplicate/conflicting modules**: `SettingsManager` is defined in both `configWindow.py` (flat key=value for game `settings.txt`) and `settingsmanager.py` (category-based). Nothing imports `settingsmanager.py`; it’s effectively dead code and can confuse future changes. Prefer a single, clearly named module (e.g. keep game settings logic next to config, or move to one shared module).

### Naming
- **Inconsistent method names**: Mix of `snake_case` and `camelCase` (e.g. `load_mods` vs `loadSettings`, `saveCheckedmods`). PEP 8 recommends `snake_case` for functions/methods. Use `load_settings`, `save_checked_mods` (and update all call sites).
- **Shadowing built-ins**: In `configWindow.py`, `update(self, value)` shadows `QWidget.update()`. Rename to e.g. `on_update_time_changed` to avoid confusion and bugs.

### File handling
- **Encoding**: Many `open(..., 'r')` / `open(..., 'w')` calls don’t specify `encoding='utf-8'`. On Windows this can lead to platform-dependent behavior. Use `encoding='utf-8'` (and `errors='replace'` or `errors='ignore'` where appropriate) for text files.

### Error handling & debugging
- **Bare `except` / broad `except Exception`**: Several `except Exception` blocks swallow errors (e.g. in `refresh_mods`, `preset_manager`). Prefer catching specific exceptions or logging and re-raising where appropriate.
- **Debug prints**: Remove or replace with logging (e.g. `logging.debug`) in: `mainWindow.py` (application path, “Checking:”, “Found game root”, “User directory”, “Starting game…”), `configWindow.py` (user_dir, cache_path, “Cache cleared”), `presetmanagerWindow.py` (“Loaded preset”, “Deleted preset”, “Saved new preset”).

### Other
- **Typo**: In `mainWindow.py`, error message has “Pleaase” → “Please”.
- **Deprecation**: In `updatesWindow.py`, `datetime.utcfromtimestamp()` is deprecated in Python 3.12+. Prefer `datetime.fromtimestamp(ts, tz=timezone.utc)`.

---

## 2. Readability

- **Long methods**: `load_mods()` and `start_game()` in `mainWindow.py` are long and do many things. Consider extracting helpers (e.g. “build mod tree”, “write merged event_modifiers”, “build game command”) to improve readability and testability.
- **Magic numbers/strings**: Repeated paths like `"mod"`, `"Documents"`, `"Paradox Interactive"`, `"Victoria II"` could be named constants or a small config helper.
- **Comments**: Some logic (e.g. event modifier merge, load order) would benefit from short comments or docstrings at the block level.
- **Unused code**: `icon_button_style` in `mainWindow.py` is defined but never applied (buttons are `QPushButton`, not `QToolButton`). Either use it or remove it.

---

## 3. UI and Qt usage

### Bugs
- **configWindow.py line 222**:  
  `layout.addRow(layout.addRow("Update Time:", self.update_time_slider), self.update_time_slider_label)`  
  `addRow()` returns `None`, so the outer call is `addRow(None, self.update_time_slider_label)`, which produces a wrong row (missing label for “Update Time”). Fix by adding two separate rows: one for the slider, one for the label, or use a single row with a layout containing both.
- **configWindow.py**: `self.update_time_slider.toolTip = "..."` assigns to an attribute; the tooltip is never shown. Use `self.update_time_slider.setToolTip("...")`.
- **configWindow.py save_settings**: The keys for resolution are `'\tx'` and `'\ty'` (literal tab in the string) instead of `'x'` and `'y'`. That breaks matching when updating the settings file (e.g. `lines[i].startswith(key)` never matches `"x="`). Use `'x'` and `'y'`.

### Design / robustness
- **Dialog dependency**: In `mainWindow.open_about_dialog()`, `QDialog` is used but only available via `from scr.configWindow import *`. This is fragile. Import `QDialog` explicitly (e.g. from `PyQt6.QtWidgets`) in `mainWindow.py`.
- **Parent assumption**: In `presetmanagerWindow.py`, `self.parent().set_checked_mods(self.checked_mods)` assumes the parent has `set_checked_mods`. If the dialog is ever reparented or used elsewhere, this can break. Prefer a signal/slot or a callback passed in by the parent.
- **launcher_config types**: In `mainWindow.start_game()`, `priority = 'realtime' if launcher_config['realtime'] == '1'` assumes a string; JSON may store an integer. Handle both (e.g. `str(launcher_config.get('realtime', 0)) == '1'`) for robustness.
- **Missing file/directory**: In `start_game()`, the code reads/writes `settings_path` under the user’s Documents folder without checking existence. If the directory or file doesn’t exist (e.g. first run, or wrong `user_dir`), it can raise. Add existence checks or create directories as needed.

### Layout / UX
- **Config dialog**: `QVBoxLayout(self)` and later `self.setLayout(main_layout)` is redundant; passing `self` to the layout constructor is enough in Qt. Single `setLayout` is clearer.
- **Icon path**: In `launcher.py`, `QIcon("../scr/icon.ico")` depends on the current working directory. Prefer a path relative to the application (e.g. based on `sys.argv[0]` or `__file__`) so the icon loads regardless of CWD.

---

## Summary of recommended fixes (priority)

1. **Critical (bugs)**  
   - Fix config “Update Time” row (addRow usage).  
   - Use `setToolTip` for the update time slider.  
   - Fix resolution keys `'x'` and `'y'` (no leading tab) in `configWindow.save_settings`.

2. **High (standards / robustness)**  
   - Replace wildcard imports with explicit imports; import `QDialog` in `mainWindow.py`.  
   - Use `save_checked_mods` (snake_case) and update all references.  
   - Specify `encoding='utf-8'` for text file I/O.  
   - Fix “Pleaase” typo.  
   - Rename `ConfigDialog.update` to e.g. `on_update_time_changed` and connect accordingly.

3. **Medium (readability / maintenance)**  
   - Remove or replace debug `print` with logging.  
   - Remove unused `icon_button_style` or use it.  
   - Normalize `launcher_config['realtime']` type handling.  
   - Consider extracting long methods and centralizing path constants.

4. **Low**  
   - Remove or repurpose unused `settingsmanager.py` to avoid two different `SettingsManager` concepts.  
   - Use `datetime.fromtimestamp(..., timezone.utc)` in `updatesWindow.py`.  
   - Harden preset dialog parent assumption (signal or callback).
