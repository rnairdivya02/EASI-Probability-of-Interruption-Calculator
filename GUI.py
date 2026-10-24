import os
import re
import math
import json
import random
import shutil
import datetime
import numpy as np
import tkinter as tk

from tkinter import filedialog
from tkinter import ttk, messagebox
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure


# ===========================================================================
#  DESIGN SYSTEM
# ===========================================================================

FONT = "Segoe UI"

THEMES = {
    "light": {
        "bg": "#eef2f7",
        "surface": "#ffffff",
        "surface_alt": "#f8fafc",
        "border": "#dbe3ec",
        "text": "#0f172a",
        "muted": "#64748b",
        "primary": "#2563eb",
        "primary_hover": "#1d4ed8",
        "success": "#16a34a",
        "success_hover": "#15803d",
        "danger": "#dc2626",
        "danger_hover": "#b91c1c",
        "warning": "#d97706",
        "sidebar": "#111827",
        "sidebar_text": "#cbd5e1",
        "sidebar_active": "#2563eb",
        "sidebar_active_text": "#ffffff",
        "header": "#111827",
        "header_text": "#f8fafc",
        "heading": "#eef2f7",
        "selected": "#dbeafe",
        "entry": "#ffffff",
        # result row tints (bg, fg)
        "row_excellent": ("#dcfce7", "#14532d"),
        "row_secure": ("#d1fae5", "#065f46"),
        "row_acceptable": ("#fef3c7", "#78350f"),
        "row_needs": ("#ffedd5", "#7c2d12"),
        "row_critical": ("#fee2e2", "#7f1d1d"),
    },
    "dark": {
        "bg": "#0b1220",
        "surface": "#131c2e",
        "surface_alt": "#0f1626",
        "border": "#28344a",
        "text": "#e5edf7",
        "muted": "#93a4bc",
        "primary": "#3b82f6",
        "primary_hover": "#60a5fa",
        "success": "#22c55e",
        "success_hover": "#4ade80",
        "danger": "#ef4444",
        "danger_hover": "#f87171",
        "warning": "#f59e0b",
        "sidebar": "#080d18",
        "sidebar_text": "#94a3b8",
        "sidebar_active": "#3b82f6",
        "sidebar_active_text": "#ffffff",
        "header": "#080d18",
        "header_text": "#e5edf7",
        "heading": "#1c273c",
        "selected": "#1e3a8a",
        "entry": "#0f1626",
        "row_excellent": ("#14532d", "#dcfce7"),
        "row_secure": ("#065f46", "#d1fae5"),
        "row_acceptable": ("#78350f", "#fef3c7"),
        "row_needs": ("#7c2d12", "#ffedd5"),
        "row_critical": ("#7f1d1d", "#fee2e2"),
    },
}


GUIDE_TEXT = """PHYSICAL PROTECTION SYSTEM — EVALUATION TOOL
A quick guide to the workflow and the newer features.

────────────────────────────────────────
1. PROJECTS  (🗂 sidebar)
────────────────────────────────────────
• All work lives inside a project. Projects are plain .json files stored
  in a "projects" folder kept right next to the application.
• "New Project" asks for a name and creates the file immediately — there is
  no risk of losing work because you forgot to save.
• The Projects page lists every saved project (name, number of paths, last
  modified). Double-click a row to open it.
• Rename / Duplicate / Delete act on the selected project.
• "Open Folder" reveals the projects folder in File Explorer.

────────────────────────────────────────
2. AUTOSAVE
────────────────────────────────────────
• Once a project is open, changes are saved automatically: adding or editing
  a path, running an evaluation, or leaving a Global Parameter field.
• The header always shows the current project name, so you can tell at a
  glance what you are editing.
• "Save" and "Save As…" remain in the sidebar and are available on EVERY
  page, including the Results page. (Earlier the save controls could vanish
  after viewing results — the persistent sidebar fixes that.)

────────────────────────────────────────
3. SAMPLE / FABRICATED DATA  (🎲)
────────────────────────────────────────
• On the Inputs page, "Generate Sample Data" fills the tool with realistic,
  randomly generated attack paths so you can explore the app instantly.
• You control the ranges: number of paths, tasks per path, Pd range,
  delay range, response time, uncertainties and alarm probability.
• Generating replaces the current paths, then autosaves into the open project.

────────────────────────────────────────
4. BUILDING PATHS  (📝 Inputs)
────────────────────────────────────────
• Global Parameters apply to every path (uncertainties, response time,
  alarm probability).
• Build a path: name it, add tasks (name, Pd 0–1, delay seconds), then
  "Add Path". Use "View Details" to add/edit/delete tasks inside a path.

────────────────────────────────────────
5. RESULTS  (📊)
────────────────────────────────────────
• "Run Evaluation" computes each path's PI using the EASI model and jumps
  to the Results page: summary cards, a color-coded table, a PI bar chart
  and a Gaussian time-analysis chart for the most vulnerable path.

────────────────────────────────────────
6. THEME
────────────────────────────────────────
• The header button toggles Light / Dark mode. Every panel, table and chart
  re-colors to match.
"""


# ===========================================================================
#  MODEL  (unchanged logic)
# ===========================================================================

def gaussian_cdf(z):
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


class Task:
    def __init__(self, name, pd, pd_std, delay_mean, delay_std):
        self.name = name
        self.pd = pd
        self.pd_std = pd_std
        self.delay_mean = delay_mean
        self.delay_std = delay_std


class ResponseForce:
    def __init__(self, mean, std):
        self.mean = mean
        self.std = std


class EASIModel:
    def __init__(self, tasks, response_force, p_alarm):
        self.tasks = tasks
        self.response_force = response_force
        self.p_alarm = p_alarm

    def calculate_pd(self):
        undetected_probability = 1.0
        for task in self.tasks:
            undetected_probability *= (1 - task.pd)
        pd_total = 1 - undetected_probability
        pd_total *= self.p_alarm
        return pd_total

    def calculate_adversary_mean(self):
        return sum(task.delay_mean for task in self.tasks)

    def calculate_combined_std(self):
        variance_sum = sum(task.delay_std ** 2 for task in self.tasks)
        variance_sum += self.response_force.std ** 2
        return math.sqrt(variance_sum)

    def calculate_pi(self):
        pd_total = self.calculate_pd()
        adversary_mean = self.calculate_adversary_mean()
        combined_std = self.calculate_combined_std()

        if combined_std == 0:
            z = 0
        else:
            z = (adversary_mean - self.response_force.mean) / combined_std

        cdf_value = gaussian_cdf(z)
        pi = pd_total * cdf_value
        return (pi, pd_total, adversary_mean, combined_std, cdf_value, z)

    def calculate_cdp(self):
        total_time = self.calculate_adversary_mean()
        response_time = self.response_force.mean

        cumulative_time = 0
        cdp_task = None
        remaining_time = 0
        interruption_margin = 0

        for task in self.tasks:
            cumulative_time += task.delay_mean
            remaining_time = total_time - cumulative_time
            if remaining_time >= response_time:
                cdp_task = task.name
                interruption_margin = remaining_time - response_time

        return (cdp_task, remaining_time, interruption_margin)


# ===========================================================================
#  APPLICATION
# ===========================================================================

class PPSApp:

    def __init__(self, root):
        self.root = root
        self.theme_name = "light"

        # state
        self.paths = []
        self.latest_results = []
        self.mvp_result = None
        self.chart_canvas = None
        self.gaussian_canvas = None

        # project storage
        self.projects_dir = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "projects")
        os.makedirs(self.projects_dir, exist_ok=True)
        self.current_project = None
        self.project_name = None
        self._meta_created = None
        self._projects_index = {}

        root.title("Physical Protection System Evaluation Tool")
        root.state("zoomed")
        root.minsize(1100, 700)

        self.style = ttk.Style()
        self.style.theme_use("clam")

        self._build_layout()
        self.apply_theme()
        self._refresh_projects_list()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.set_page("projects")

    # -- convenience -------------------------------------------------------
    @property
    def t(self):
        return THEMES[self.theme_name]

    # =====================================================================
    #  LAYOUT
    # =====================================================================
    def _build_layout(self):
        self.header = tk.Frame(self.root, height=64)
        self.header.pack(fill="x", side="top")
        self.header.pack_propagate(False)

        self.header_title = tk.Label(
            self.header,
            text="  🛡  Physical Protection System — Evaluation Tool",
            font=(FONT, 16, "bold"),
        )
        self.header_title.pack(side="left", padx=18)

        self.theme_btn = ttk.Button(
            self.header, text="Dark mode", style="Ghost.TButton",
            command=self.toggle_theme, takefocus=False,
        )
        self.theme_btn.pack(side="right", padx=16)

        self.current_label = tk.Label(self.header, text="No project open",
                                      font=(FONT, 10, "italic"))
        self.current_label.pack(side="right", padx=8)

        # body: sidebar + content
        self.body = tk.Frame(self.root)
        self.body.pack(fill="both", expand=True)

        self.sidebar = tk.Frame(self.body, width=210)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        self.nav_inputs = ttk.Button(
            self.sidebar, text="   📝  Inputs", style="Nav.TButton",
            command=lambda: self.set_page("inputs"), takefocus=False,
        )
        self.nav_inputs.pack(fill="x", padx=12, pady=(20, 4))

        self.nav_results = ttk.Button(
            self.sidebar, text="   📊  Results", style="Nav.TButton",
            command=lambda: self.set_page("results"), takefocus=False,
        )
        self.nav_results.pack(fill="x", padx=12, pady=4)

        self.nav_projects = ttk.Button(
            self.sidebar, text="   🗂  Projects", style="Nav.TButton",
            command=lambda: self.set_page("projects"), takefocus=False,
        )
        self.nav_projects.pack(fill="x", padx=12, pady=4)

        self.nav_guide = ttk.Button(
            self.sidebar, text="   ❓  Guide", style="Nav.TButton",
            command=lambda: self.set_page("guide"), takefocus=False,
        )
        self.nav_guide.pack(fill="x", padx=12, pady=4)

        ttk.Separator(self.sidebar).pack(fill="x", padx=12, pady=14)

        self.nav_new = ttk.Button(
            self.sidebar, text="   ✚  New Project", style="Nav.TButton",
            command=self.new_project, takefocus=False,
        )
        self.nav_new.pack(fill="x", padx=12, pady=4)

        self.nav_open = ttk.Button(
            self.sidebar, text="   📂  Open Project", style="Nav.TButton",
            command=self.open_project, takefocus=False,
        )
        self.nav_open.pack(fill="x", padx=12, pady=4)

        self.nav_save = ttk.Button(
            self.sidebar, text="   💾  Save", style="Nav.TButton",
            command=self.save_project, takefocus=False,
        )
        self.nav_save.pack(fill="x", padx=12, pady=4)

        self.nav_save_as = ttk.Button(
            self.sidebar, text="   💾  Save As…", style="Nav.TButton",
            command=lambda: self.save_project(True), takefocus=False,
        )
        self.nav_save_as.pack(fill="x", padx=12, pady=4)

        self.sidebar_hint = tk.Label(
            self.sidebar,
            text="EASI model\nAttack-path analysis",
            font=(FONT, 8), justify="left",
        )
        self.sidebar_hint.pack(side="bottom", anchor="w", padx=18, pady=16)

        # content area holds stacked pages
        self.content = tk.Frame(self.body)
        self.content.pack(side="left", fill="both", expand=True)

        self.pages = {}
        self.pages["projects"] = ttk.Frame(self.content, style="App.TFrame")
        self.pages["inputs"] = ttk.Frame(self.content, style="App.TFrame")
        self.pages["results"] = ttk.Frame(self.content, style="App.TFrame")
        self.pages["guide"] = ttk.Frame(self.content, style="App.TFrame")
        for page in self.pages.values():
            page.place(relx=0, rely=0, relwidth=1, relheight=1)

        self._build_projects_page(self.pages["projects"])
        self._build_inputs_page(self.pages["inputs"])
        self._build_results_page(self.pages["results"])
        self._build_guide_page(self.pages["guide"])

    # ---------------------------------------------------------------------
    #  INPUTS PAGE
    # ---------------------------------------------------------------------
    def _build_inputs_page(self, page):
        wrap = ttk.Frame(page, style="App.TFrame", padding=18)
        wrap.pack(fill="both", expand=True)

        # -- Global parameters card
        gp = ttk.LabelFrame(wrap, text="Global Parameters",
                            style="Card.TLabelframe", padding=16)
        gp.pack(fill="x")

        def field(parent, label, r, c):
            ttk.Label(parent, text=label, style="Card.TLabel").grid(
                row=r, column=c, padx=(6, 8), pady=8, sticky="w")
            e = ttk.Entry(parent, width=18)
            e.grid(row=r, column=c + 1, padx=(0, 24), pady=8, sticky="w")
            return e

        self.delay_unc_entry = field(gp, "Delay Uncertainty (%)", 0, 0)
        self.pd_unc_entry = field(gp, "Pd Uncertainty (%)", 1, 0)
        self.response_entry = field(gp, "Response Time (sec)", 0, 2)
        self.alarm_entry = field(gp, "Alarm Probability (0–1)", 1, 2)

        for _e in (self.delay_unc_entry, self.pd_unc_entry,
                   self.response_entry, self.alarm_entry):
            _e.bind("<FocusOut>", lambda ev: self._autosave())

        # -- two columns: path builder + path list
        row = ttk.Frame(wrap, style="App.TFrame")
        row.pack(fill="both", expand=True, pady=(16, 0))

        # ---- build attack path
        build = ttk.LabelFrame(row, text="Build Attack Path",
                               style="Card.TLabelframe", padding=16)
        build.pack(side="left", fill="both", expand=True, padx=(0, 8))

        ttk.Label(build, text="Path Name", style="Card.TLabel").grid(
            row=0, column=0, padx=6, pady=6, sticky="w")
        self.path_name_entry = ttk.Entry(build, width=26)
        self.path_name_entry.grid(row=0, column=1, columnspan=3,
                                  pady=6, sticky="w")

        columns = ("Task", "Pd (0-1)", "Delay(sec)")
        self.task_tree = ttk.Treeview(build, columns=columns,
                                      show="headings", height=5)
        for col in columns:
            self.task_tree.heading(col, text=col)
            self.task_tree.column(col, width=130, anchor="center")
        self.task_tree.grid(row=1, column=0, columnspan=4, pady=12, sticky="ew")

        ttk.Label(build, text="Task", style="Card.TLabel").grid(
            row=2, column=0, padx=6, pady=6, sticky="w")
        self.task_name_entry = ttk.Entry(build, width=18)
        self.task_name_entry.grid(row=2, column=1, pady=6, sticky="w")

        ttk.Label(build, text="Pd (0-1)", style="Card.TLabel").grid(
            row=2, column=2, padx=6, pady=6, sticky="w")
        self.task_pd_entry = ttk.Entry(build, width=18)
        self.task_pd_entry.grid(row=2, column=3, pady=6, sticky="w")

        ttk.Label(build, text="Delay (sec)", style="Card.TLabel").grid(
            row=3, column=0, padx=6, pady=6, sticky="w")
        self.task_delay_entry = ttk.Entry(build, width=18)
        self.task_delay_entry.grid(row=3, column=1, pady=6, sticky="w")

        btns = ttk.Frame(build, style="Card.TFrame")
        btns.grid(row=4, column=0, columnspan=4, pady=(12, 0), sticky="w")
        ttk.Button(btns, text="Add Task", style="Primary.TButton",
                   command=self.add_task).pack(side="left", padx=(0, 8))
        ttk.Button(btns, text="Delete Task", style="Danger.TButton",
                   command=self.delete_task).pack(side="left", padx=8)
        ttk.Button(btns, text="Add Path", style="Success.TButton",
                   command=self.add_path).pack(side="left", padx=8)

        # ---- added paths
        listcard = ttk.LabelFrame(row, text="Attack Paths",
                                  style="Card.TLabelframe", padding=16)
        listcard.pack(side="left", fill="both", expand=True, padx=(8, 0))

        path_columns = ("Path Name", "Tasks", "Status")
        self.path_tree = ttk.Treeview(listcard, columns=path_columns,
                                      show="headings", height=8)
        self.path_tree.heading("Path Name", text="Path Name")
        self.path_tree.heading("Tasks", text="Tasks")
        self.path_tree.heading("Status", text="Status")
        self.path_tree.column("Path Name", width=200)
        self.path_tree.column("Tasks", width=70, anchor="center")
        self.path_tree.column("Status", width=100, anchor="center")
        self.path_tree.pack(fill="both", expand=True, pady=(0, 12))

        pbtns = ttk.Frame(listcard, style="Card.TFrame")
        pbtns.pack(anchor="w")
        ttk.Button(pbtns, text="Edit Name", style="Primary.TButton",
                   command=self.edit_path_name).pack(side="left", padx=(0, 8))
        ttk.Button(pbtns, text="Delete Path", style="Danger.TButton",
                   command=self.delete_path).pack(side="left", padx=8)
        ttk.Button(pbtns, text="View Details", style="Primary.TButton",
                   command=self.view_path_details).pack(side="left", padx=8)

        # -- run evaluation
        run = ttk.Frame(wrap, style="App.TFrame")
        run.pack(fill="x", pady=(16, 0))
        ttk.Button(run, text="🎲  Generate Sample Data", style="Primary.TButton",
                   command=self.generate_sample_data).pack(side="left")
        ttk.Button(run, text="▶   RUN EVALUATION", style="Success.TButton",
                   command=self.calculate).pack(side="right")

    # ---------------------------------------------------------------------
    #  RESULTS PAGE
    # ---------------------------------------------------------------------
    def _build_results_page(self, page):
        wrap = ttk.Frame(page, style="App.TFrame", padding=18)
        wrap.pack(fill="both", expand=True)

        # summary detail lines
        summary = ttk.Frame(wrap, style="App.TFrame")
        summary.pack(fill="x")
        self.mvp_label = ttk.Label(summary, text="Most Vulnerable Path: -",
                                   style="MVP.TLabel")
        self.mvp_label.pack(side="left", fill="x", expand=True)
        self.msp_label = ttk.Label(summary, text="Most Secure Path: -",
                                   style="MSP.TLabel")
        self.msp_label.pack(side="left", fill="x", expand=True)

        # stat cards
        cards = ttk.Frame(wrap, style="App.TFrame")
        cards.pack(fill="x", pady=14)
        self.card_paths = self._stat_card(cards, "TOTAL PATHS")
        self.card_mvp = self._stat_card(cards, "MOST VULNERABLE")
        self.card_msp = self._stat_card(cards, "MOST SECURE")
        self.card_avg = self._stat_card(cards, "AVERAGE PI")
        self.card_risk = self._stat_card(cards, "HIGH RISK")

        # results table
        table = ttk.LabelFrame(wrap, text="Evaluation Results",
                               style="Card.TLabelframe", padding=12)
        table.pack(fill="both", expand=True)

        cols = ("Path", "PI", "Security %", "Risk %", "Status", "CDP", "Risk")
        self.result_tree = ttk.Treeview(table, columns=cols,
                                        show="headings", height=6)
        widths = {"Path": 280, "PI": 70, "Security %": 110, "Risk %": 100,
                  "Status": 130, "CDP": 170, "Risk": 90}
        headings = {"Path": "Path", "PI": "PI", "Security %": "Security Score",
                    "Risk %": "Risk Score", "Status": "Status",
                    "CDP": "Critical Detection Point", "Risk": "Risk"}
        for c in cols:
            self.result_tree.heading(c, text=headings[c])
            anchor = "w" if c == "Path" else "center"
            self.result_tree.column(c, width=widths[c], anchor=anchor)

        vsb = ttk.Scrollbar(table, orient="vertical",
                            command=self.result_tree.yview)
        self.result_tree.configure(yscrollcommand=vsb.set)
        self.result_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # charts
        charts = ttk.Frame(wrap, style="App.TFrame")
        charts.pack(fill="both", expand=True, pady=(14, 0))
        self.chart_frame = ttk.LabelFrame(charts, text="PI by Attack Path",
                                          style="Card.TLabelframe", padding=8)
        self.chart_frame.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.gaussian_frame = ttk.LabelFrame(
            charts, text="Gaussian Time Analysis — Most Vulnerable Path",
            style="Card.TLabelframe", padding=8)
        self.gaussian_frame.pack(side="left", fill="both", expand=True,
                                 padx=(8, 0))

    def _stat_card(self, parent, caption):
        card = ttk.Frame(parent, style="Card.TFrame", padding=(16, 12))
        card.pack(side="left", fill="x", expand=True, padx=5)
        ttk.Label(card, text=caption, style="Caption.TLabel").pack(anchor="w")
        value = ttk.Label(card, text="-", style="Stat.TLabel")
        value.pack(anchor="w", pady=(4, 0))
        return value

    # ---------------------------------------------------------------------
    #  PROJECTS PAGE
    # ---------------------------------------------------------------------
    def _build_projects_page(self, page):
        wrap = ttk.Frame(page, style="App.TFrame", padding=18)
        wrap.pack(fill="both", expand=True)

        top = ttk.Frame(wrap, style="App.TFrame")
        top.pack(fill="x")
        ttk.Label(top, text="Projects", style="H1.TLabel").pack(side="left")
        ttk.Button(top, text="✚ New Project", style="Primary.TButton",
                   command=self.new_project).pack(side="right")
        ttk.Button(top, text="Open Folder", style="Primary.TButton",
                   command=self._open_projects_folder).pack(
                       side="right", padx=8)

        ttk.Label(wrap, text=self.projects_dir, style="PathHint.TLabel").pack(
            anchor="w", pady=(4, 12))

        card = ttk.LabelFrame(wrap, text="Saved Projects",
                              style="Card.TLabelframe", padding=12)
        card.pack(fill="both", expand=True)

        cols = ("Name", "Paths", "Modified")
        self.projects_tree = ttk.Treeview(card, columns=cols,
                                          show="headings", height=12)
        for c, w, a in (("Name", 340, "w"), ("Paths", 90, "center"),
                        ("Modified", 200, "center")):
            self.projects_tree.heading(c, text=c)
            self.projects_tree.column(c, width=w, anchor=a)
        vsb = ttk.Scrollbar(card, orient="vertical",
                            command=self.projects_tree.yview)
        self.projects_tree.configure(yscrollcommand=vsb.set)
        self.projects_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.projects_tree.bind(
            "<Double-1>", lambda e: self._open_selected_project())

        bar = ttk.Frame(wrap, style="App.TFrame")
        bar.pack(fill="x", pady=(12, 0))
        for text, style, cmd in (
                ("Open", "Primary.TButton", self._open_selected_project),
                ("Rename", "Primary.TButton", self._rename_selected_project),
                ("Duplicate", "Primary.TButton",
                 self._duplicate_selected_project),
                ("Delete", "Danger.TButton", self._delete_selected_project),
                ("Refresh", "Primary.TButton", self._refresh_projects_list)):
            ttk.Button(bar, text=text, style=style, command=cmd).pack(
                side="left", padx=(0, 8))

    # ---------------------------------------------------------------------
    #  GUIDE PAGE
    # ---------------------------------------------------------------------
    def _build_guide_page(self, page):
        wrap = ttk.Frame(page, style="App.TFrame", padding=18)
        wrap.pack(fill="both", expand=True)
        ttk.Label(wrap, text="Guide & Feature Reference",
                  style="H1.TLabel").pack(anchor="w", pady=(0, 12))

        card = ttk.LabelFrame(wrap, text="How to use this tool",
                              style="Card.TLabelframe", padding=12)
        card.pack(fill="both", expand=True)

        self.guide_text = tk.Text(card, wrap="word", relief="flat",
                                  font=(FONT, 10), padx=12, pady=12,
                                  borderwidth=0, height=10)
        vsb = ttk.Scrollbar(card, orient="vertical",
                            command=self.guide_text.yview)
        self.guide_text.configure(yscrollcommand=vsb.set)
        self.guide_text.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.guide_text.insert("1.0", GUIDE_TEXT)
        self.guide_text.configure(state="disabled")

    # ---------------------------------------------------------------------
    #  SAMPLE / FABRICATED DATA
    # ---------------------------------------------------------------------
    def generate_sample_data(self):
        win = self._themed_toplevel("Generate Sample Data", "440x560")
        win.grab_set()
        ttk.Label(win, text="Fabricated data — parameter ranges",
                  style="Card.TLabel").pack(padx=16, pady=(16, 4), anchor="w")

        form = ttk.Frame(win, style="Card.TFrame")
        form.pack(fill="x", padx=16, pady=8)

        defaults = [
            ("Number of paths", "num_paths", "4"),
            ("Min tasks / path", "min_tasks", "3"),
            ("Max tasks / path", "max_tasks", "6"),
            ("Pd min (0-1)", "pd_min", "0.2"),
            ("Pd max (0-1)", "pd_max", "0.9"),
            ("Delay min (sec)", "delay_min", "10"),
            ("Delay max (sec)", "delay_max", "120"),
            ("Response time (sec)", "response", "180"),
            ("Delay uncertainty (%)", "delay_unc", "10"),
            ("Pd uncertainty (%)", "pd_unc", "10"),
            ("Alarm probability (0-1)", "alarm", "0.9"),
        ]
        entries = {}
        for i, (label, key, dv) in enumerate(defaults):
            ttk.Label(form, text=label, style="Card.TLabel").grid(
                row=i, column=0, sticky="w", padx=6, pady=4)
            e = ttk.Entry(form, width=12)
            e.grid(row=i, column=1, padx=6, pady=4)
            e.insert(0, dv)
            entries[key] = e

        def generate():
            try:
                num_paths = int(float(entries["num_paths"].get()))
                min_tasks = int(float(entries["min_tasks"].get()))
                max_tasks = int(float(entries["max_tasks"].get()))
                pd_min = float(entries["pd_min"].get())
                pd_max = float(entries["pd_max"].get())
                delay_min = float(entries["delay_min"].get())
                delay_max = float(entries["delay_max"].get())
                response = float(entries["response"].get())
                delay_unc = float(entries["delay_unc"].get())
                pd_unc = float(entries["pd_unc"].get())
                alarm = float(entries["alarm"].get())
            except ValueError:
                messagebox.showerror("Error", "All fields must be numeric.")
                return

            if num_paths < 1:
                messagebox.showerror("Error", "Need at least one path.")
                return
            if min_tasks < 1 or max_tasks < min_tasks:
                messagebox.showerror("Error",
                                     "Check the tasks-per-path range.")
                return
            if not (0 <= pd_min <= pd_max <= 1):
                messagebox.showerror("Error", "Pd range must be within 0-1.")
                return
            if delay_min <= 0 or delay_max < delay_min:
                messagebox.showerror("Error", "Check the delay range.")
                return
            if not 0 <= alarm <= 1:
                messagebox.showerror("Error",
                                     "Alarm probability must be 0-1.")
                return

            self._apply_sample_data(num_paths, min_tasks, max_tasks, pd_min,
                                    pd_max, delay_min, delay_max, response,
                                    delay_unc, pd_unc, alarm)
            win.destroy()

        bar = ttk.Frame(win, style="Card.TFrame")
        bar.pack(pady=14)
        ttk.Button(bar, text="Generate", style="Success.TButton",
                   command=generate).pack(side="left", padx=6)
        ttk.Button(bar, text="Cancel", style="Danger.TButton",
                   command=win.destroy).pack(side="left", padx=6)

    def _apply_sample_data(self, num_paths, min_tasks, max_tasks, pd_min,
                           pd_max, delay_min, delay_max, response, delay_unc,
                           pd_unc, alarm):
        task_pool = ["Cut Perimeter Fence", "Cross Open Yard", "Breach Gate",
                     "Force Exterior Door", "Defeat Door Lock",
                     "Bypass Motion Sensor", "Traverse Corridor",
                     "Breach Vault Door", "Disable Camera",
                     "Access Control Room", "Reach Target Asset"]

        self.paths.clear()
        self.path_tree.delete(*self.path_tree.get_children())
        self.task_tree.delete(*self.task_tree.get_children())
        self.result_tree.delete(*self.result_tree.get_children())
        self._clear_charts()
        self._reset_cards()

        for entry, val in ((self.delay_unc_entry, delay_unc),
                           (self.pd_unc_entry, pd_unc),
                           (self.response_entry, response),
                           (self.alarm_entry, alarm)):
            entry.delete(0, tk.END)
            entry.insert(0, str(val))

        for p in range(num_paths):
            n_tasks = random.randint(min_tasks, max_tasks)
            names = random.sample(task_pool, min(n_tasks, len(task_pool)))
            while len(names) < n_tasks:
                names.append(f"Task {len(names) + 1}")
            tasks = [{
                "name": nm,
                "pd": round(random.uniform(pd_min, pd_max), 2),
                "delay": round(random.uniform(delay_min, delay_max), 1),
            } for nm in names]
            name = f"Attack Path {chr(65 + p)}" if p < 26 \
                else f"Attack Path {p + 1}"
            self.paths.append({"name": name, "tasks": tasks})
            self.path_tree.insert("", "end",
                                  values=(name, len(tasks), "Pending"))

        self._autosave()
        self.set_page("inputs")
        messagebox.showinfo(
            "Sample Data",
            f"Generated {num_paths} attack paths with fabricated data.")

    # =====================================================================
    #  THEMING
    # =====================================================================
    def toggle_theme(self):
        self.theme_name = "dark" if self.theme_name == "light" else "light"
        self.apply_theme()

    def apply_theme(self):
        t = self.t
        self.root.configure(bg=t["bg"])
        self._configure_styles()

        # plain tk widgets
        self.header.configure(bg=t["header"])
        self.header_title.configure(bg=t["header"], fg=t["header_text"])
        self.current_label.configure(bg=t["header"], fg=t["muted"])
        self.body.configure(bg=t["bg"])
        self.sidebar.configure(bg=t["sidebar"])
        self.sidebar_hint.configure(bg=t["sidebar"], fg=t["muted"])
        self.content.configure(bg=t["bg"])
        if hasattr(self, "guide_text"):
            self.guide_text.configure(bg=t["surface"], fg=t["text"],
                                      insertbackground=t["text"])

        self.theme_btn.configure(
            text="Light mode" if self.theme_name == "dark" else "Dark mode")

        self._configure_result_tags()
        self._refresh_nav()

        # redraw charts in the new theme
        if self.latest_results:
            self.show_pi_chart(self.latest_results)
            if self.mvp_result:
                self.show_gaussian_graph(self.mvp_result)

    def _configure_styles(self):
        t = self.t
        s = self.style

        s.configure("App.TFrame", background=t["bg"])
        s.configure("Card.TFrame", background=t["surface"])
        s.configure("TSeparator", background=t["border"])

        s.configure("Card.TLabelframe", background=t["surface"],
                    bordercolor=t["border"], relief="solid", borderwidth=1)
        s.configure("Card.TLabelframe.Label", background=t["surface"],
                    foreground=t["text"], font=(FONT, 11, "bold"))

        s.configure("TLabel", background=t["bg"], foreground=t["text"],
                    font=(FONT, 10))
        s.configure("Card.TLabel", background=t["surface"],
                    foreground=t["text"], font=(FONT, 10))
        s.configure("Caption.TLabel", background=t["surface"],
                    foreground=t["muted"], font=(FONT, 8, "bold"))
        s.configure("Stat.TLabel", background=t["surface"],
                    foreground=t["text"], font=(FONT, 15, "bold"))
        s.configure("MVP.TLabel", background=t["bg"], foreground=t["danger"],
                    font=(FONT, 11, "bold"))
        s.configure("MSP.TLabel", background=t["bg"], foreground=t["success"],
                    font=(FONT, 11, "bold"))
        s.configure("H1.TLabel", background=t["bg"], foreground=t["text"],
                    font=(FONT, 16, "bold"))
        s.configure("PathHint.TLabel", background=t["bg"],
                    foreground=t["muted"], font=(FONT, 9))

        s.configure("TEntry", fieldbackground=t["entry"], foreground=t["text"],
                    bordercolor=t["border"], insertcolor=t["text"], padding=5)

        # tables
        s.configure("Treeview", background=t["surface"],
                    fieldbackground=t["surface"], foreground=t["text"],
                    rowheight=28, borderwidth=0, font=(FONT, 10))
        s.configure("Treeview.Heading", background=t["heading"],
                    foreground=t["text"], relief="flat",
                    font=(FONT, 10, "bold"))
        s.map("Treeview.Heading", background=[("active", t["heading"])])
        s.map("Treeview",
              background=[("selected", t["selected"])],
              foreground=[("selected", t["text"])])

        # scrollbar
        s.configure("Vertical.TScrollbar", background=t["border"],
                    troughcolor=t["surface_alt"], bordercolor=t["surface_alt"],
                    arrowcolor=t["muted"])

        # buttons
        def button(name, bg, hover, fg="#ffffff", font=(FONT, 10, "bold"),
                   pad=(14, 8)):
            s.configure(name, background=bg, foreground=fg, font=font,
                        borderwidth=0, focuscolor=bg, padding=pad)
            s.map(name, background=[("active", hover), ("pressed", hover)])

        button("Primary.TButton", t["primary"], t["primary_hover"])
        button("Success.TButton", t["success"], t["success_hover"],
               font=(FONT, 12, "bold"), pad=(22, 11))
        button("Danger.TButton", t["danger"], t["danger_hover"])

        s.configure("Ghost.TButton", background=t["header"],
                    foreground=t["header_text"], borderwidth=1,
                    bordercolor=t["muted"], font=(FONT, 9, "bold"),
                    padding=(12, 6), focuscolor=t["header"])
        s.map("Ghost.TButton", background=[("active", t["header"])])

        # sidebar nav
        s.configure("Nav.TButton", background=t["sidebar"],
                    foreground=t["sidebar_text"], borderwidth=0,
                    font=(FONT, 10), anchor="w", padding=(14, 10),
                    focuscolor=t["sidebar"])
        s.map("Nav.TButton", background=[("active", t["surface_alt"])],
              foreground=[("active", t["text"])])
        s.configure("NavActive.TButton", background=t["sidebar_active"],
                    foreground=t["sidebar_active_text"], borderwidth=0,
                    font=(FONT, 10, "bold"), anchor="w", padding=(14, 10),
                    focuscolor=t["sidebar_active"])
        s.map("NavActive.TButton",
              background=[("active", t["sidebar_active"])])

    def _configure_result_tags(self):
        t = self.t
        mapping = {
            "Excellent": "row_excellent",
            "Secure": "row_secure",
            "Acceptable": "row_acceptable",
            "Needs Improvement": "row_needs",
            "Critical": "row_critical",
        }
        for tag, key in mapping.items():
            bg, fg = t[key]
            self.result_tree.tag_configure(tag, background=bg, foreground=fg)

    def _refresh_nav(self):
        active = getattr(self, "_page", "inputs")
        self.nav_inputs.configure(
            style="NavActive.TButton" if active == "inputs" else "Nav.TButton")
        self.nav_results.configure(
            style="NavActive.TButton" if active == "results" else "Nav.TButton")
        self.nav_projects.configure(
            style="NavActive.TButton" if active == "projects" else "Nav.TButton")
        self.nav_guide.configure(
            style="NavActive.TButton" if active == "guide" else "Nav.TButton")

    def set_page(self, name):
        self._page = name
        self.pages[name].tkraise()
        self._refresh_nav()

    # =====================================================================
    #  TASK / PATH ACTIONS
    # =====================================================================
    def add_task(self):
        task = self.task_name_entry.get().strip()
        try:
            pd = float(self.task_pd_entry.get())
            delay = float(self.task_delay_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Pd and Delay must be numeric.")
            return

        if not 0 <= pd <= 1:
            messagebox.showerror("Error", "Pd must be between 0 and 1.")
            return
        if not task:
            return

        self.task_tree.insert("", "end", values=(task, pd, delay))
        self.task_name_entry.delete(0, tk.END)
        self.task_pd_entry.delete(0, tk.END)
        self.task_delay_entry.delete(0, tk.END)

    def delete_task(self):
        selected = self.task_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Select a task first.")
            return
        if messagebox.askyesno("Delete Task",
                               "Are you sure you want to delete this task?"):
            self.task_tree.delete(selected[0])

    def add_path(self):
        path_name = self.path_name_entry.get().strip()
        if not path_name:
            messagebox.showerror("Error", "Enter Path Name")
            return

        tasks = []
        for row in self.task_tree.get_children():
            values = self.task_tree.item(row)["values"]
            if len(values) != 3:
                continue
            tasks.append({"name": values[0], "pd": float(values[1]),
                          "delay": float(values[2])})

        if len(tasks) == 0:
            messagebox.showerror("Error", "Please add at least one task.")
            return
        if any(p["name"] == path_name for p in self.paths):
            messagebox.showerror("Error",
                                 "A path with this name already exists.")
            return

        self.paths.append({"name": path_name, "tasks": tasks})
        self.path_tree.insert("", "end",
                              values=(path_name, len(tasks), "Pending"))
        self.path_name_entry.delete(0, tk.END)
        self.task_tree.delete(*self.task_tree.get_children())
        self._autosave()
        messagebox.showinfo("Success", "Path Added")

    def delete_path(self):
        selected = self.path_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Select a path first.")
            return
        index = self.path_tree.index(selected[0])
        if messagebox.askyesno("Delete Path",
                               "Are you sure you want to delete this path?"):
            self.path_tree.delete(selected[0])
            self.paths.pop(index)
            self._autosave()

    def edit_path_name(self):
        selected = self.path_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Select a path first.")
            return
        index = self.path_tree.index(selected[0])
        current_name = self.paths[index]["name"]

        win = self._themed_toplevel("Edit Path Name", "360x160")
        ttk.Label(win, text="Path Name", style="Card.TLabel").pack(
            padx=16, pady=(18, 6), anchor="w")
        entry = ttk.Entry(win, width=36)
        entry.pack(padx=16)
        entry.insert(0, current_name)

        def save():
            new_name = entry.get().strip()
            if not new_name:
                messagebox.showerror("Error", "Path name cannot be empty.")
                return
            self.paths[index]["name"] = new_name
            values = list(self.path_tree.item(selected[0])["values"])
            values[0] = new_name
            self.path_tree.item(selected[0], values=values)
            self._autosave()
            win.destroy()

        ttk.Button(win, text="Save", style="Primary.TButton",
                   command=save).pack(pady=16)

    def view_path_details(self):
        selected = self.path_tree.selection()
        if not selected:
            messagebox.showwarning("Warning", "Please select a path.")
            return

        path_index = self.path_tree.index(selected[0])
        selected_path = self.paths[path_index]

        win = self._themed_toplevel(
            f"Path Details — {selected_path['name']}", "720x520")

        summary = ttk.Label(win, style="Card.TLabel", font=(FONT, 11, "bold"))
        summary.pack(pady=12)

        tree = ttk.Treeview(win, columns=("Task", "Pd", "Delay"),
                            show="headings", height=10)
        tree.heading("Task", text="Task")
        tree.heading("Pd", text="Pd")
        tree.heading("Delay", text="Delay (sec)")
        tree.column("Task", width=250)
        tree.column("Pd", width=100, anchor="center")
        tree.column("Delay", width=120, anchor="center")
        tree.pack(fill="both", expand=True, padx=12)

        def refresh_tree():
            tree.delete(*tree.get_children())
            total_delay = 0
            total_pd = 0
            for task in selected_path["tasks"]:
                tree.insert("", "end",
                            values=(task["name"], task["pd"], task["delay"]))
                total_delay += task["delay"]
                total_pd += task["pd"]
            avg_pd = total_pd / len(selected_path["tasks"]) \
                if selected_path["tasks"] else 0
            summary.config(
                text=f"Tasks: {len(selected_path['tasks'])}      "
                     f"Total Delay: {total_delay:.1f} sec      "
                     f"Average Pd: {avg_pd:.3f}")
            self.path_tree.item(
                selected[0],
                values=(selected_path["name"],
                        len(selected_path["tasks"]), "Pending"))
            self._autosave()

        def edit_selected_task(event=None):
            item = tree.focus()
            if not item:
                return
            index = tree.index(item)
            task = selected_path["tasks"][index]

            edit = self._themed_toplevel("Edit Task", "320x260")
            ttk.Label(edit, text="Task", style="Card.TLabel").pack(pady=(14, 2))
            task_entry = ttk.Entry(edit)
            task_entry.pack()
            task_entry.insert(0, task["name"])
            ttk.Label(edit, text="Pd", style="Card.TLabel").pack(pady=(10, 2))
            pd_entry = ttk.Entry(edit)
            pd_entry.pack()
            pd_entry.insert(0, str(task["pd"]))
            ttk.Label(edit, text="Delay", style="Card.TLabel").pack(pady=(10, 2))
            delay_entry = ttk.Entry(edit)
            delay_entry.pack()
            delay_entry.insert(0, str(task["delay"]))

            def save():
                try:
                    pd = float(pd_entry.get())
                    delay = float(delay_entry.get())
                except ValueError:
                    messagebox.showerror("Error", "Enter numeric values.")
                    return
                task["name"] = task_entry.get()
                task["pd"] = pd
                task["delay"] = delay
                refresh_tree()
                edit.destroy()

            ttk.Button(edit, text="Save", style="Primary.TButton",
                       command=save).pack(pady=14)

        def delete_selected_task():
            item = tree.focus()
            if not item:
                return
            selected_path["tasks"].pop(tree.index(item))
            refresh_tree()

        def add_new_task():
            add = self._themed_toplevel("Add Task", "320x260")
            ttk.Label(add, text="Task", style="Card.TLabel").pack(pady=(14, 2))
            task_entry = ttk.Entry(add)
            task_entry.pack()
            ttk.Label(add, text="Pd", style="Card.TLabel").pack(pady=(10, 2))
            pd_entry = ttk.Entry(add)
            pd_entry.pack()
            ttk.Label(add, text="Delay", style="Card.TLabel").pack(pady=(10, 2))
            delay_entry = ttk.Entry(add)
            delay_entry.pack()

            def save():
                try:
                    pd = float(pd_entry.get())
                    delay = float(delay_entry.get())
                except ValueError:
                    messagebox.showerror("Error", "Enter numeric values.")
                    return
                selected_path["tasks"].append(
                    {"name": task_entry.get(), "pd": pd, "delay": delay})
                refresh_tree()
                add.destroy()

            ttk.Button(add, text="Add", style="Primary.TButton",
                       command=save).pack(pady=14)

        bar = ttk.Frame(win, style="Card.TFrame")
        bar.pack(pady=12)
        ttk.Button(bar, text="Add Task", style="Primary.TButton",
                   command=add_new_task).pack(side="left", padx=5)
        ttk.Button(bar, text="Edit Task", style="Primary.TButton",
                   command=edit_selected_task).pack(side="left", padx=5)
        ttk.Button(bar, text="Delete Task", style="Danger.TButton",
                   command=delete_selected_task).pack(side="left", padx=5)
        ttk.Button(bar, text="Close", style="Primary.TButton",
                   command=win.destroy).pack(side="left", padx=5)

        tree.bind("<Double-1>", edit_selected_task)
        refresh_tree()

    def _themed_toplevel(self, title, geometry):
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry(geometry)
        win.configure(bg=self.t["surface"])
        win.transient(self.root)
        return win

    # =====================================================================
    #  CHARTS
    # =====================================================================
    def _style_axes(self, figure, axis):
        t = self.t
        figure.patch.set_facecolor(t["surface"])
        axis.set_facecolor(t["surface"])
        axis.title.set_color(t["text"])
        axis.xaxis.label.set_color(t["text"])
        axis.yaxis.label.set_color(t["text"])
        axis.tick_params(colors=t["text"])
        for spine in axis.spines.values():
            spine.set_color(t["border"])
        axis.grid(True, alpha=0.25, color=t["muted"])

    def show_pi_chart(self, results):
        if self.chart_canvas is not None:
            self.chart_canvas.get_tk_widget().destroy()

        path_names = [r["name"] for r in results]
        pi_values = [r["pi"] for r in results]
        min_pi = min(pi_values)

        colors = []
        for pi in pi_values:
            if pi == min_pi:
                colors.append("#dc2626")
            elif pi < 0.40:
                colors.append("#ef4444")
            elif pi < 0.70:
                colors.append("#f59e0b")
            else:
                colors.append("#16a34a")

        figure = Figure(figsize=(6, 3.4), dpi=100)
        axis = figure.add_subplot(111)
        self._style_axes(figure, axis)
        axis.bar(path_names, pi_values, color=colors, width=0.5)
        axis.set_title("Probability of Interruption by Attack Path")
        axis.set_xlabel("Attack Path")
        axis.set_ylabel("PI")
        axis.set_ylim(0, 1)
        axis.tick_params(axis="x", rotation=20, colors=self.t["text"])
        figure.tight_layout()

        self.chart_canvas = FigureCanvasTkAgg(figure, master=self.chart_frame)
        self.chart_canvas.draw()
        self.chart_canvas.get_tk_widget().pack(fill="both", expand=True)

    def show_gaussian_graph(self, result):
        if self.gaussian_canvas is not None:
            self.gaussian_canvas.get_tk_widget().destroy()

        adv_mean = result["adversary_mean"]
        adv_std = max(result["combined_std"], 0.0001)
        resp_mean = result["response_mean"]
        resp_std = max(result["response_std"], 0.0001)
        spread = max(adv_std, resp_std, 1)

        x_min = max(0, min(adv_mean, resp_mean) - 4 * spread)
        x_max = max(adv_mean, resp_mean) + 4 * spread
        x = np.linspace(x_min, x_max, 500)

        adv_y = (1 / (adv_std * np.sqrt(2 * np.pi))) * \
            np.exp(-0.5 * ((x - adv_mean) / adv_std) ** 2)
        resp_y = (1 / (resp_std * np.sqrt(2 * np.pi))) * \
            np.exp(-0.5 * ((x - resp_mean) / resp_std) ** 2)

        figure = Figure(figsize=(6, 3.4), dpi=100)
        axis = figure.add_subplot(111)
        self._style_axes(figure, axis)
        axis.plot(x, adv_y, color="#2563eb", label="Adversary Time")
        axis.plot(x, resp_y, color="#dc2626", label="Response Time")
        axis.axvline(adv_mean, color="#2563eb", linestyle="--")
        axis.axvline(resp_mean, color="#dc2626", linestyle="--")
        axis.set_title(f"Gaussian Time Analysis — {result['name']}")
        axis.set_xlabel("Time (seconds)")
        axis.set_ylabel("Probability Density")

        legend = axis.legend()
        legend.get_frame().set_facecolor(self.t["surface"])
        legend.get_frame().set_edgecolor(self.t["border"])
        for text in legend.get_texts():
            text.set_color(self.t["text"])
        figure.tight_layout()

        self.gaussian_canvas = FigureCanvasTkAgg(figure,
                                                 master=self.gaussian_frame)
        self.gaussian_canvas.draw()
        self.gaussian_canvas.get_tk_widget().pack(fill="both", expand=True)

    # =====================================================================
    #  CALCULATE
    # =====================================================================
    def calculate(self):
        self.result_tree.delete(*self.result_tree.get_children())
        self.mvp_label.config(text="Most Vulnerable Path: -")
        self.msp_label.config(text="Most Secure Path: -")

        if len(self.paths) == 0:
            messagebox.showerror("Error", "Please add at least one path.")
            return

        try:
            delay_uncertainty = float(self.delay_unc_entry.get())
            pd_uncertainty = float(self.pd_unc_entry.get())
            response_mean = float(self.response_entry.get())
            p_alarm = float(self.alarm_entry.get())
        except ValueError:
            messagebox.showerror("Error",
                                 "Please enter valid numeric global inputs.")
            return

        if p_alarm < 0 or p_alarm > 1:
            messagebox.showerror("Error",
                                 "Alarm Probability must be between 0 and 1.")
            return

        delay_factor = delay_uncertainty / 100
        pd_factor = pd_uncertainty / 100
        response_force = ResponseForce(mean=response_mean,
                                       std=delay_factor * response_mean)

        results = []
        for path in self.paths:
            model_tasks = []
            for task in path["tasks"]:
                model_tasks.append(Task(
                    name=task["name"], pd=task["pd"],
                    pd_std=pd_factor * task["pd"],
                    delay_mean=task["delay"],
                    delay_std=delay_factor * task["delay"]))

            model = EASIModel(tasks=model_tasks,
                              response_force=response_force, p_alarm=p_alarm)
            (pi, pd_total, adversary_mean, combined_std,
             cdf_value, z) = model.calculate_pi()

            security_score = pi * 100
            risk_score = (1 - pi) * 100

            if pi >= 0.90:
                status, risk = "Excellent", "Very Low"
            elif pi >= 0.75:
                status, risk = "Secure", "Low"
            elif pi >= 0.60:
                status, risk = "Acceptable", "Medium"
            elif pi >= 0.40:
                status, risk = "Needs Improvement", "High"
            else:
                status, risk = "Critical", "Very High"

            cdp_task, remaining_time, interruption_margin = model.calculate_cdp()

            self.result_tree.insert(
                "", "end",
                values=(path["name"], f"{pi:.4f}", f"{security_score:.1f}%",
                        f"{risk_score:.1f}%", status,
                        cdp_task if cdp_task else "None", risk),
                tags=(status,))

            results.append({
                "name": path["name"], "pi": pi, "cdp": cdp_task,
                "security_score": security_score, "risk_score": risk_score,
                "status": status, "adversary_mean": adversary_mean,
                "combined_std": combined_std,
                "response_mean": response_force.mean,
                "response_std": response_force.std})

            for item in self.path_tree.get_children():
                if self.path_tree.item(item)["values"][0] == path["name"]:
                    current = list(self.path_tree.item(item)["values"])
                    current[2] = "Calculated"
                    self.path_tree.item(item, values=current)
                    break

        most_vulnerable = min(results, key=lambda r: r["pi"])
        most_secure = max(results, key=lambda r: r["pi"])
        average_pi = sum(r["pi"] for r in results) / len(results)
        high_risk_count = sum(
            1 for r in results
            if r["status"] in ["Critical", "Needs Improvement"])

        self.card_paths.config(text=str(len(results)))
        self.card_mvp.config(text=most_vulnerable["name"])
        self.card_msp.config(text=most_secure["name"])
        self.card_avg.config(text=f"{average_pi:.4f}")
        self.card_risk.config(text=str(high_risk_count))

        self.mvp_label.config(
            text=f"Most Vulnerable Path: {most_vulnerable['name']} "
                 f"| PI = {most_vulnerable['pi']:.4f} "
                 f"| Security = {most_vulnerable['security_score']:.1f}% "
                 f"| {most_vulnerable['status']}")
        self.msp_label.config(
            text=f"Most Secure Path: {most_secure['name']} "
                 f"| PI = {most_secure['pi']:.4f} "
                 f"| Security = {most_secure['security_score']:.1f}% "
                 f"| {most_secure['status']}")

        self.latest_results = results
        self.mvp_result = most_vulnerable
        self.show_pi_chart(results)
        self.show_gaussian_graph(most_vulnerable)
        self._autosave()
        self.set_page("results")

    # =====================================================================
    #  PROJECT I/O
    # =====================================================================
    def _reset_cards(self):
        self.mvp_label.config(text="Most Vulnerable Path: -")
        self.msp_label.config(text="Most Secure Path: -")
        for card in (self.card_paths, self.card_mvp, self.card_msp,
                     self.card_avg, self.card_risk):
            card.config(text="-")

    def _clear_charts(self):
        if self.chart_canvas:
            self.chart_canvas.get_tk_widget().destroy()
            self.chart_canvas = None
        if self.gaussian_canvas:
            self.gaussian_canvas.get_tk_widget().destroy()
            self.gaussian_canvas = None
        self.latest_results = []
        self.mvp_result = None

    # -- filename / path helpers -----------------------------------------
    def _sanitize_filename(self, name):
        safe = re.sub(r"[^A-Za-z0-9 _-]", "", name).strip()
        return re.sub(r"\s+", " ", safe)

    def _project_path(self, name):
        return os.path.join(self.projects_dir,
                            self._sanitize_filename(name) + ".json")

    def _update_current_label(self):
        self.current_label.config(
            text=f"Project: {self.project_name}" if self.project_name
            else "No project open")

    def _clear_workspace(self):
        self.paths.clear()
        self.path_tree.delete(*self.path_tree.get_children())
        self.task_tree.delete(*self.task_tree.get_children())
        self.result_tree.delete(*self.result_tree.get_children())
        self._clear_charts()
        for entry in (self.path_name_entry, self.delay_unc_entry,
                      self.pd_unc_entry, self.response_entry, self.alarm_entry):
            entry.delete(0, tk.END)
        self._reset_cards()

    # -- read / write -----------------------------------------------------
    def _write_project(self, path):
        now = datetime.datetime.now().isoformat(timespec="seconds")
        if not self._meta_created:
            self._meta_created = now
        data = {
            "meta": {
                "name": self.project_name or
                        os.path.splitext(os.path.basename(path))[0],
                "created": self._meta_created,
                "modified": now,
            },
            "global_inputs": {
                "delay_uncertainty": self.delay_unc_entry.get(),
                "pd_uncertainty": self.pd_unc_entry.get(),
                "response_time": self.response_entry.get(),
                "alarm_probability": self.alarm_entry.get(),
            },
            "paths": self.paths,
        }
        with open(path, "w") as file:
            json.dump(data, file, indent=4)

    def _autosave(self, *_):
        if not self.current_project:
            return
        try:
            self._write_project(self.current_project)
        except Exception as e:
            print("Autosave failed:", e)
        self._refresh_projects_list()

    def _prompt_name(self, title, label, initial=""):
        win = self._themed_toplevel(title, "400x180")
        win.grab_set()
        ttk.Label(win, text=label, style="Card.TLabel").pack(
            padx=18, pady=(22, 8), anchor="w")
        entry = ttk.Entry(win, width=40)
        entry.pack(padx=18)
        entry.insert(0, initial)
        entry.focus_set()

        result = {"value": None}

        def ok():
            result["value"] = entry.get().strip()
            win.destroy()

        bar = ttk.Frame(win, style="Card.TFrame")
        bar.pack(pady=18)
        ttk.Button(bar, text="OK", style="Primary.TButton",
                   command=ok).pack(side="left", padx=6)
        ttk.Button(bar, text="Cancel", style="Danger.TButton",
                   command=win.destroy).pack(side="left", padx=6)
        entry.bind("<Return>", lambda e: ok())
        win.wait_window()
        return result["value"]

    # -- create / open / save --------------------------------------------
    def new_project(self):
        name = self._prompt_name("New Project", "Project name:")
        if not name:
            return
        safe = self._sanitize_filename(name)
        if not safe:
            messagebox.showerror("Error", "Please enter a valid project name.")
            return
        path = self._project_path(safe)
        if os.path.exists(path):
            messagebox.showerror(
                "Error", f"A project named '{safe}' already exists.")
            return

        self._clear_workspace()
        self.current_project = path
        self.project_name = safe
        self._meta_created = None
        self._write_project(path)
        self._update_current_label()
        self._refresh_projects_list()
        self.set_page("inputs")

    def open_project(self, path=None):
        if path is None:
            path = filedialog.askopenfilename(
                initialdir=self.projects_dir,
                filetypes=[("JSON Files", "*.json")])
        if not path:
            return
        try:
            with open(path, "r") as file:
                project = json.load(file)
        except Exception as e:
            messagebox.showerror("Error", f"Could not open project:\n{e}")
            return

        self.current_project = path
        meta = project.get("meta", {})
        self.project_name = meta.get("name") or \
            os.path.splitext(os.path.basename(path))[0]
        self._meta_created = meta.get("created")

        self._clear_workspace()

        gi = project.get("global_inputs", {})
        for entry, key in ((self.delay_unc_entry, "delay_uncertainty"),
                           (self.pd_unc_entry, "pd_uncertainty"),
                           (self.response_entry, "response_time"),
                           (self.alarm_entry, "alarm_probability")):
            entry.insert(0, gi.get(key, ""))

        for path_ in project.get("paths", []):
            self.paths.append(path_)
            self.path_tree.insert(
                "", "end",
                values=(path_["name"], len(path_["tasks"]), "Pending"))

        self._update_current_label()
        self.set_page("inputs")

    def save_project(self, save_as=False):
        if save_as or not self.current_project:
            name = self._prompt_name("Save Project As", "Project name:",
                                     initial=self.project_name or "")
            if not name:
                return
            safe = self._sanitize_filename(name)
            if not safe:
                messagebox.showerror("Error",
                                     "Please enter a valid project name.")
                return
            path = self._project_path(safe)
            if os.path.exists(path) and path != self.current_project:
                if not messagebox.askyesno(
                        "Overwrite", f"'{safe}' already exists. Overwrite?"):
                    return
            self.current_project = path
            self.project_name = safe
            if save_as:
                self._meta_created = None
        try:
            self._write_project(self.current_project)
            self._update_current_label()
            self._refresh_projects_list()
            messagebox.showinfo("Saved", "Project saved successfully.")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # -- project manager (list) ------------------------------------------
    def _refresh_projects_list(self):
        if not hasattr(self, "projects_tree"):
            return
        self.projects_tree.delete(*self.projects_tree.get_children())
        try:
            files = [f for f in os.listdir(self.projects_dir)
                     if f.lower().endswith(".json")]
        except OSError:
            files = []

        items = []
        for f in files:
            full = os.path.join(self.projects_dir, f)
            name = os.path.splitext(f)[0]
            count = 0
            try:
                with open(full, "r") as fh:
                    data = json.load(fh)
                name = data.get("meta", {}).get("name", name)
                count = len(data.get("paths", []))
            except Exception:
                pass
            items.append((os.path.getmtime(full), name, count, full))

        items.sort(reverse=True)
        self._projects_index = {}
        for mtime, name, count, full in items:
            modified = datetime.datetime.fromtimestamp(mtime).strftime(
                "%Y-%m-%d %H:%M")
            iid = self.projects_tree.insert(
                "", "end", values=(name, count, modified))
            self._projects_index[iid] = full

    def _selected_project_file(self):
        sel = self.projects_tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Select a project first.")
            return None
        return self._projects_index.get(sel[0])

    def _open_selected_project(self):
        path = self._selected_project_file()
        if path:
            self.open_project(path)

    def _rename_selected_project(self):
        path = self._selected_project_file()
        if not path:
            return
        old = os.path.splitext(os.path.basename(path))[0]
        new = self._prompt_name("Rename Project", "New name:", initial=old)
        if not new:
            return
        safe = self._sanitize_filename(new)
        if not safe:
            messagebox.showerror("Error", "Please enter a valid name.")
            return
        new_path = self._project_path(safe)
        if os.path.exists(new_path) and new_path != path:
            messagebox.showerror("Error", f"'{safe}' already exists.")
            return
        try:
            with open(path, "r") as fh:
                data = json.load(fh)
        except Exception:
            data = {}
        data.setdefault("meta", {})["name"] = safe
        try:
            with open(path, "w") as fh:
                json.dump(data, fh, indent=4)
            os.replace(path, new_path)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        if self.current_project == path:
            self.current_project = new_path
            self.project_name = safe
            self._update_current_label()
        self._refresh_projects_list()

    def _duplicate_selected_project(self):
        path = self._selected_project_file()
        if not path:
            return
        base = os.path.splitext(os.path.basename(path))[0]
        candidate = f"{base} (copy)"
        new_path = self._project_path(candidate)
        i = 2
        while os.path.exists(new_path):
            candidate = f"{base} (copy {i})"
            new_path = self._project_path(candidate)
            i += 1
        try:
            shutil.copyfile(path, new_path)
            with open(new_path, "r") as fh:
                data = json.load(fh)
            data.setdefault("meta", {})["name"] = candidate
            with open(new_path, "w") as fh:
                json.dump(data, fh, indent=4)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self._refresh_projects_list()

    def _delete_selected_project(self):
        path = self._selected_project_file()
        if not path:
            return
        name = os.path.splitext(os.path.basename(path))[0]
        if not messagebox.askyesno(
                "Delete Project",
                f"Delete '{name}'?\nThis permanently removes the file."):
            return
        try:
            os.remove(path)
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        if self.current_project == path:
            self.current_project = None
            self.project_name = None
            self._update_current_label()
        self._refresh_projects_list()

    def _open_projects_folder(self):
        try:
            os.startfile(self.projects_dir)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_close(self):
        self._autosave()
        self.root.destroy()


# ===========================================================================
#  ENTRY POINT
# ===========================================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = PPSApp(root)
    root.mainloop()
