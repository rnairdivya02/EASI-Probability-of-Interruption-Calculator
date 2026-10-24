# Physical Protection System (PPS) Evaluation Tool

A desktop application for evaluating the effectiveness of a physical
protection system against defined attack paths, using the **EASI**
(Estimate of Adversary Sequence Interruption) model. It computes each
path's **Probability of Interruption (PI)**, ranks the most vulnerable and
most secure paths, and visualises the results with charts.

The app is built with **Python + Tkinter** (GUI), **NumPy**, and
**Matplotlib**.

---

## Table of contents
1. [Quick start — how to run the app](#quick-start--how-to-run-the-app)
2. [Requirements](#requirements)
3. [Directory structure](#directory-structure)
4. ["Where do I change X?" — a map for developers](#where-do-i-change-x--a-map-for-developers)
5. [How the app works](#how-the-app-works)
6. [How your work is saved (important)](#how-your-work-is-saved-important)
7. [Project file format](#project-file-format)
8. [FAQ / troubleshooting](#faq--troubleshooting)
9. [For maintainers](#for-maintainers)

---

## Quick start — how to run the app

**Recommended** (checks/installs dependencies first, then launches):

```bash
python "run_pps_tool.py"
```

This launcher reports which dependencies you have and which are missing,
asks permission before installing anything with `pip`, and then starts the
GUI.

**Direct** (if you already have the dependencies installed):

```bash
python GUI.py
```

Both do the same thing in the end — `GUI.py` is a tiny launcher that starts
the real application inside the `pps/` package.

---

## Requirements

| Requirement | Notes |
|---|---|
| **Python 3.8+** | Includes **Tkinter** (the GUI toolkit). On Windows, make sure "tcl/tk and IDLE" was ticked during Python install. |
| **numpy** | Installed automatically by `run_pps_tool.py`, or manually: `pip install numpy` |
| **matplotlib** | Installed automatically by `run_pps_tool.py`, or manually: `pip install matplotlib` |

Manual install of both at once:

```bash
pip install numpy matplotlib
```

---

## Directory structure

```
Divya's Project/
├─ GUI.py              # Launcher shim. Starts the app (from pps.app import main).
│                      #   Kept so run_pps_tool.py can keep launching "GUI.py".
├─ run_pps_tool.py     # Pre-flight dependency checker + launcher (the recommended entry point).
│
├─ pps/                # The actual application, split into focused modules.
│  ├─ __init__.py      #   Marks pps/ as a Python package (intentionally empty).
│  ├─ app.py           #   The GUI: window, pages, dialogs, charts, buttons, event handlers.
│  ├─ model.py         #   The EASI math (pure calculation, no UI).
│  ├─ storage.py       #   Reading/writing/listing project files on disk (pure, no UI).
│  ├─ theme.py         #   Fonts and the light/dark colour themes.
│  ├─ text.py          #   The in-app Guide page text.
│  └─ paths.py         #   Defines where the projects/ folder lives.
│
├─ projects/           # Your saved projects, one .json file each. Created automatically.
│
└─ archive/            # Old / backup files, reference only — not used by the app.
   ├─ GUI_backup_pre_modularize.py   # The original single-file version, pre-refactor.
   └─ README.md
```

> **Why split into `pps/`?** The whole app used to be one 1769-line `GUI.py`.
> It was split into small modules so it is easier to read, debug, and extend.
> Behaviour is identical — only the file organisation changed.

---

## "Where do I change X?" — a map for developers

Use this to jump straight to the right file. **Most UI work happens in
`pps/app.py`**; the other modules hold the pieces that don't depend on the
GUI.

| I want to change… | Go to | Look for |
|---|---|---|
| The **calculation** (PI, Pd, CDP, Gaussian) | `pps/model.py` | `EASIModel`, `gaussian_cdf` |
| **Colours / dark mode / fonts** | `pps/theme.py` | `THEMES`, `FONT` |
| The **Guide page** wording | `pps/text.py` | `GUIDE_TEXT` |
| How projects are **saved / loaded / listed / renamed / duplicated / deleted** | `pps/storage.py` | `write_atomic`, `read_project`, `list_projects`, … |
| **Where** the `projects/` folder is created | `pps/paths.py` | `PROJECTS_DIR` |
| A **page's layout** (Inputs, Results, Projects, Guide) | `pps/app.py` | `_build_inputs_page`, `_build_results_page`, `_build_projects_page`, `_build_guide_page` |
| **Buttons / the sidebar / the header** | `pps/app.py` | `_build_layout` |
| Adding/editing/deleting **tasks and paths** | `pps/app.py` | `add_task`, `add_path`, `edit_path_name`, `view_path_details` |
| **Running an evaluation** and filling the results | `pps/app.py` | `calculate` |
| The **charts** | `pps/app.py` | `show_pi_chart`, `show_gaussian_graph` |
| **Sample/fabricated data** generation | `pps/app.py` | `generate_sample_data`, `_apply_sample_data` |
| **New / Open / Save / Save As** and the unsaved-changes prompts | `pps/app.py` | `new_project`, `open_project`, `save_project`, `_confirm_discard` |
| The **dependency check / launcher** | `run_pps_tool.py` | `scan_dependencies`, `launch_gui` |

---

## How the app works

The app has four pages, reachable from the sidebar:

1. **📝 Inputs** — set Global Parameters (delay/Pd uncertainty, response time,
   alarm probability) and build attack paths. Each path is a named list of
   tasks; each task has a name, a detection probability **Pd (0–1)**, and a
   **delay** in seconds. "🎲 Generate Sample Data" fills a fresh document with
   realistic random paths so you can explore quickly.
2. **📊 Results** — "▶ Run Evaluation" computes each path's PI with the EASI
   model, shows summary cards, a colour-coded table, a PI bar chart, and a
   Gaussian time-analysis chart for the most vulnerable path.
3. **🗂 Projects** — lists every saved project (name, number of paths, last
   modified). Double-click to open; Rename / Duplicate / Delete act on the
   selected one; "Open Folder" reveals the `projects/` folder.
4. **❓ Guide** — the built-in help text (`pps/text.py`).

The header button toggles **Light / Dark** mode.

---

## How your work is saved (important)

The app behaves like a word processor — **your work is NOT saved
automatically**:

- Work lives in memory as a **document** until you save it. Use **Save**
  (`Ctrl+S`) to write it to disk, and **Save As…** (`Ctrl+Shift+S`) to save
  under a new name.
- The header shows the current document name and a **`●` dot** whenever there
  are **unsaved changes**.
- **New Project** and **Generate Sample Data** both open a fresh document *in
  memory* — they never overwrite the project you had open.
- If you have unsaved changes and try to start a new document, open another
  project, generate sample data, or close the app, you are asked
  **Save / Don't Save / Cancel** — so work is never lost or overwritten by
  accident.
- Saves are **atomic** (written to a temporary file then swapped in), so a
  crash or full disk cannot corrupt an existing project file.

---

## Project file format

Each project is a plain JSON file in `projects/`. Structure:

```json
{
    "meta": {
        "name": "Site A",
        "created": "2026-08-10T14:30:00",
        "modified": "2026-08-10T14:35:00"
    },
    "global_inputs": {
        "delay_uncertainty": "10",
        "pd_uncertainty": "10",
        "response_time": "180",
        "alarm_probability": "0.9"
    },
    "paths": [
        {
            "name": "Attack Path A",
            "tasks": [
                { "name": "Breach Gate", "pd": 0.5, "delay": 30.0 }
            ]
        }
    ]
}
```

- `meta.created` / `meta.modified` use ISO-8601 timestamps (`YYYY-MM-DDTHH:MM:SS`).
- `global_inputs` values are stored as strings (they come from text fields).
- These files are safe to back up or copy; dropping a valid `.json` into
  `projects/` makes it appear in the Projects list.

---

## FAQ / troubleshooting

**How do I start the app?**
Run `python "run_pps_tool.py"` (recommended) or `python GUI.py`.

**The app won't start — it says `tkinter` is missing.**
Tkinter ships with Python but must be selected at install time. On Windows,
re-run the Python installer and tick "tcl/tk and IDLE". Then try again.

**It says numpy or matplotlib is missing.**
Run `python "run_pps_tool.py"` and let it install them, or run
`pip install numpy matplotlib` yourself.

**Where are my projects stored?**
In the `projects/` folder next to the app. In the app, the Projects page has
an "Open Folder" button that opens it directly.

**I renamed/deleted a project file directly on disk — is that ok?**
Yes. Use the Projects page "Refresh" button (or reopen the app) to see the
change.

**Can I move the app to another folder?**
Yes — keep the whole folder together (`GUI.py`, `run_pps_tool.py`, `pps/`,
`projects/`). The `projects/` folder always stays next to the app.

**What is the `archive/` folder?**
Old backups kept for reference only. The running app never uses it.

**Where's the old single-file version?**
`archive/GUI_backup_pre_modularize.py` — the original app before it was split
into the `pps/` package.

---

## For maintainers

- **Entry point:** `GUI.py` → `pps.app.main()` starts the Tkinter loop.
  `run_pps_tool.py` launches `GUI.py` as a subprocess after a dependency
  check, so keep `GUI.py` present and runnable.
- **Design principle:** UI code lives in `pps/app.py`; everything that does
  *not* need the GUI (math, disk I/O, theme data, guide text, paths) lives in
  its own module so it can be changed and reasoned about independently.
- **`projects/` location** is anchored to the project root in `pps/paths.py`
  (one level above the `pps/` package), so it does not matter which module is
  the entry point — the folder always resolves to `<root>/projects`.
- **No automated test suite yet.** After changes, verify by launching the app
  and clicking through all four pages, running an evaluation, and exercising
  New / Open / Save / Generate Sample Data. A pre-refactor backup is kept in
  `archive/` as a fallback.
- **Dependencies** the launcher checks: `numpy`, `matplotlib` (pip) and the
  stdlib `math`, `json`, `tkinter`. Update the lists in `run_pps_tool.py` if
  the imports change.
