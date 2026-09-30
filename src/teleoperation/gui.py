from __future__ import annotations

import queue
import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from .config import AppConfig
from .controller import CommandResult, TeleoperationController
from .models import AXES, Pose
from .protocol import ProtocolError
from .tcp_client import TCPClient
from .telemetry import parse_telemetry


class TeleoperationGUI:
    POLL_MS = 75

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Teleoperation & Compensation — Simulator Demo")
        self.root.geometry("1160x760")
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.client = TCPClient(log=self.log)
        self.config = AppConfig()
        self.controller = TeleoperationController(self.config, sender=self.client)

        self.host = tk.StringVar(value=self.config.network.host)
        self.port = tk.StringVar(value=str(self.config.network.port))
        self.status = tk.StringVar(value="Disconnected")
        self.commanded_text = tk.StringVar()
        self.measured_text = tk.StringVar()
        self.preview_text = tk.StringVar(value="No command sent")
        self.origin_text = tk.StringVar(value="Origin: X0=0.00, Y0=0.00")
        self.step_vars = {
            "x": tk.DoubleVar(value=10.0),
            "y": tk.DoubleVar(value=10.0),
            "z": tk.DoubleVar(value=10.0),
            "r": tk.DoubleVar(value=5.0),
            "p": tk.DoubleVar(value=5.0),
            "w": tk.DoubleVar(value=5.0),
            "g": tk.DoubleVar(value=5.0),
        }
        self.absolute_vars = {axis: tk.DoubleVar(value=0.0) for axis in AXES}
        self.delta_vars = {axis: tk.DoubleVar(value=0.0) for axis in ("x", "y", "z")}
        self._create_setting_variables()
        self._configure_style()
        self._build_layout()
        self._refresh_state_labels()
        self._set_controls_enabled(False)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.after(self.POLL_MS, self._poll)

    def _create_setting_variables(self) -> None:
        mapping = self.config.mapping
        compensation = self.config.compensation
        safety = self.config.safety
        self.settings: dict[str, tk.Variable] = {
            "swap_xy": tk.BooleanVar(value=mapping.swap_xy),
            "x_sign": tk.IntVar(value=mapping.x_sign),
            "y_sign": tk.IntVar(value=mapping.y_sign),
            "rotation": tk.DoubleVar(value=mapping.rotation_degrees),
            "swap_yz": tk.BooleanVar(value=mapping.swap_yz),
            "swap_rw": tk.BooleanVar(value=mapping.swap_rw),
            "z_enabled": tk.BooleanVar(value=compensation.z_enabled),
            "z_kx": tk.DoubleVar(value=compensation.z_kx),
            "z_ky": tk.DoubleVar(value=compensation.z_ky),
            "z_sign": tk.IntVar(value=compensation.z_sign),
            "r_enabled": tk.BooleanVar(value=compensation.r_enabled),
            "r_kx": tk.DoubleVar(value=compensation.r_kx),
            "r_ky": tk.DoubleVar(value=compensation.r_ky),
            "r_sign": tk.IntVar(value=compensation.r_sign),
            "limits_enabled": tk.BooleanVar(value=safety.enabled),
            "x_min": tk.DoubleVar(value=safety.x_min),
            "x_max": tk.DoubleVar(value=safety.x_max),
            "y_min": tk.DoubleVar(value=safety.y_min),
            "y_max": tk.DoubleVar(value=safety.y_max),
            "fixed_z_enabled": tk.BooleanVar(value=safety.fixed_z_enabled),
            "fixed_z": tk.DoubleVar(value=safety.fixed_z),
        }

    def _configure_style(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        background, ink, accent = "#f6f7fb", "#182033", "#2563eb"
        self.root.configure(bg=background)
        style.configure(".", background=background, foreground=ink, font=("Segoe UI", 10))
        style.configure("TFrame", background=background)
        style.configure("TLabelframe", background=background)
        style.configure("TLabelframe.Label", background=background, font=("Segoe UI", 10, "bold"))
        style.configure("TLabel", background=background)
        style.configure("Accent.TButton", background=accent, foreground="white", padding=(12, 7))
        style.map("Accent.TButton", background=[("active", "#1d4ed8")])

    def _build_layout(self) -> None:
        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)
        left = ttk.Frame(self.root, padding=12)
        right = ttk.Frame(self.root, padding=12)
        left.grid(row=0, column=0, sticky="nsw")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)

        self._build_connection(left)
        notebook = ttk.Notebook(left)
        notebook.grid(row=1, column=0, sticky="nsew")
        for title, builder in (
            ("Jog", self._build_jog_tab),
            ("Absolute / Delta", self._build_pose_tab),
            ("Mapping", self._build_mapping_tab),
            ("Compensation", self._build_compensation_tab),
            ("Safety", self._build_safety_tab),
        ):
            tab = ttk.Frame(notebook, padding=10)
            notebook.add(tab, text=title)
            builder(tab)
        self._build_status(right)
        self._build_log(right)

    def _build_connection(self, parent: ttk.Frame) -> None:
        frame = ttk.Labelframe(parent, text="Local simulator connection", padding=8)
        frame.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(frame, text="Host").grid(row=0, column=0, padx=4, pady=3)
        ttk.Entry(frame, textvariable=self.host, width=14).grid(row=0, column=1, padx=4, pady=3)
        ttk.Label(frame, text="Port").grid(row=1, column=0, padx=4, pady=3)
        ttk.Entry(frame, textvariable=self.port, width=14).grid(row=1, column=1, padx=4, pady=3)
        self.connect_button = ttk.Button(
            frame, text="Connect", style="Accent.TButton", command=self.toggle_connection
        )
        self.connect_button.grid(row=0, column=2, rowspan=2, padx=8, sticky="ns")

    def _build_jog_tab(self, parent: ttk.Frame) -> None:
        self.command_buttons: list[ttk.Button] = []
        for row, axis in enumerate(AXES):
            ttk.Label(parent, text=axis.upper(), width=4).grid(row=row, column=0, pady=4)
            entry = ttk.Entry(parent, textvariable=self.step_vars[axis], width=8)
            entry.grid(row=row, column=1, padx=4)
            for column, direction in ((2, -1), (3, 1)):
                button = ttk.Button(
                    parent,
                    text="−" if direction < 0 else "+",
                    command=lambda a=axis, d=direction: self.jog(a, d),
                    width=5,
                )
                button.grid(row=row, column=column, padx=3)
                self.command_buttons.append(button)
        ttk.Label(parent, text="Linear: mm · Orientation/gripper: degrees").grid(
            row=len(AXES), column=0, columnspan=4, pady=(8, 0)
        )

    def _build_pose_tab(self, parent: ttk.Frame) -> None:
        for row, axis in enumerate(AXES):
            ttk.Label(parent, text=f"{axis.upper()}:").grid(row=row, column=0, sticky="e", pady=2)
            ttk.Entry(parent, textvariable=self.absolute_vars[axis], width=11).grid(
                row=row, column=1, padx=5, pady=2
            )
        absolute = ttk.Button(
            parent, text="Send absolute pose", style="Accent.TButton", command=self.send_absolute
        )
        absolute.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(8, 12))
        self.command_buttons.append(absolute)

        ttk.Separator(parent).grid(row=8, column=0, columnspan=2, sticky="ew", pady=6)
        for row, axis in enumerate(("x", "y", "z"), start=9):
            ttk.Label(parent, text=f"Δ{axis.upper()}:").grid(row=row, column=0, sticky="e", pady=2)
            ttk.Entry(parent, textvariable=self.delta_vars[axis], width=11).grid(
                row=row, column=1, padx=5, pady=2
            )
        delta = ttk.Button(parent, text="Apply delta", command=self.send_delta)
        delta.grid(row=12, column=0, columnspan=2, sticky="ew", pady=6)
        self.command_buttons.append(delta)

        origin = ttk.Button(parent, text="Set compensation origin", command=self.set_origin)
        origin.grid(row=13, column=0, columnspan=2, sticky="ew", pady=(14, 4))
        ttk.Label(parent, textvariable=self.origin_text).grid(row=14, column=0, columnspan=2)
        zero = ttk.Button(parent, text="Send synthetic zero pose", command=self.send_zero)
        zero.grid(row=15, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        self.command_buttons.append(zero)

    def _build_mapping_tab(self, parent: ttk.Frame) -> None:
        self._check(parent, "Swap X/Y before rotation", "swap_xy", 0)
        self._check(parent, "Swap Y/Z output channels", "swap_yz", 1)
        self._check(parent, "Swap R/W output channels", "swap_rw", 2)
        self._entry(parent, "Rotation [deg]", "rotation", 3)
        self._choice(parent, "X sign", "x_sign", 4, (-1, 1))
        self._choice(parent, "Y sign", "y_sign", 5, (-1, 1))

    def _build_compensation_tab(self, parent: ttk.Frame) -> None:
        self._check(parent, "Enable Z tilt compensation", "z_enabled", 0)
        self._entry(parent, "Z kx", "z_kx", 1)
        self._entry(parent, "Z ky", "z_ky", 2)
        self._choice(parent, "Z sign", "z_sign", 3, (-1, 1))
        ttk.Separator(parent).grid(row=4, column=0, columnspan=2, sticky="ew", pady=8)
        self._check(parent, "Enable R compensation", "r_enabled", 5)
        self._entry(parent, "R kx", "r_kx", 6)
        self._entry(parent, "R ky", "r_ky", 7)
        self._choice(parent, "R sign", "r_sign", 8, (-1, 1))

    def _build_safety_tab(self, parent: ttk.Frame) -> None:
        self._check(parent, "Enable X/Y soft limits", "limits_enabled", 0)
        self._entry(parent, "X min", "x_min", 1)
        self._entry(parent, "X max", "x_max", 2)
        self._entry(parent, "Y min", "y_min", 3)
        self._entry(parent, "Y max", "y_max", 4)
        self._check(parent, "Force a fixed Z plane", "fixed_z_enabled", 5)
        self._entry(parent, "Fixed Z", "fixed_z", 6)
        ttk.Label(parent, text="Defaults are synthetic demo values.", wraplength=220).grid(
            row=7, column=0, columnspan=2, pady=(10, 0)
        )

    def _build_status(self, parent: ttk.Frame) -> None:
        state = ttk.Labelframe(parent, text="Commanded vs measured pose", padding=8)
        state.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(state, textvariable=self.status).grid(row=0, column=0, sticky="w")
        ttk.Label(state, text="Commanded", font=("Segoe UI", 10, "bold")).grid(
            row=1, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Label(state, textvariable=self.commanded_text, font=("Consolas", 10)).grid(
            row=2, column=0, sticky="w"
        )
        ttk.Label(state, text="Measured", font=("Segoe UI", 10, "bold")).grid(
            row=3, column=0, sticky="w", pady=(8, 0)
        )
        ttk.Label(state, textvariable=self.measured_text, font=("Consolas", 10)).grid(
            row=4, column=0, sticky="w"
        )
        preview = ttk.Labelframe(parent, text="Last control pipeline result", padding=8)
        preview.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        ttk.Label(
            preview,
            textvariable=self.preview_text,
            font=("Consolas", 9),
            wraplength=690,
        ).grid(row=0, column=0, sticky="w")

    def _build_log(self, parent: ttk.Frame) -> None:
        frame = ttk.Labelframe(parent, text="Event log", padding=6)
        frame.grid(row=2, column=0, sticky="nsew")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.log_widget = tk.Text(frame, state="disabled", height=18, wrap="word", bg="white")
        self.log_widget.grid(row=0, column=0, sticky="nsew")

    def _check(self, parent: ttk.Frame, label: str, key: str, row: int) -> None:
        ttk.Checkbutton(parent, text=label, variable=self.settings[key]).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=3
        )

    def _entry(self, parent: ttk.Frame, label: str, key: str, row: int) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="e", pady=3)
        ttk.Entry(parent, textvariable=self.settings[key], width=12).grid(
            row=row, column=1, sticky="w", padx=5, pady=3
        )

    def _choice(
        self, parent: ttk.Frame, label: str, key: str, row: int, values: tuple[int, ...]
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="e", pady=3)
        ttk.Combobox(
            parent, textvariable=self.settings[key], values=values, state="readonly", width=9
        ).grid(row=row, column=1, sticky="w", padx=5, pady=3)

    def toggle_connection(self) -> None:
        if self.client.connected:
            self.client.disconnect("manual")
            self.status.set("Disconnected")
            self.connect_button.configure(text="Connect")
            self._set_controls_enabled(False)
            return
        host = self.host.get().strip()
        if host not in {"127.0.0.1", "localhost"}:
            messagebox.showerror("Local demo only", "Use 127.0.0.1 or localhost.")
            return
        try:
            self.client.connect(host, int(self.port.get()), self.config.network.timeout_seconds)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Connection failed", str(exc))
            return
        self.status.set(f"Connected to synthetic simulator at {host}:{self.port.get()}")
        self.connect_button.configure(text="Disconnect")
        self._set_controls_enabled(True)

    def jog(self, axis: str, direction: int) -> None:
        self._run_command(lambda: self.controller.jog(axis, direction * self.step_vars[axis].get()))

    def send_absolute(self) -> None:
        pose = Pose(**{axis: variable.get() for axis, variable in self.absolute_vars.items()})
        self._run_command(lambda: self.controller.set_absolute(pose))

    def send_delta(self) -> None:
        deltas = {axis: variable.get() for axis, variable in self.delta_vars.items()}
        self._run_command(lambda: self.controller.apply_delta(**deltas))

    def set_origin(self) -> None:
        self._apply_settings()
        origin = self.controller.set_compensation_origin()
        self.origin_text.set(f"Origin: X0={origin.x:.2f}, Y0={origin.y:.2f}")
        self.log("Compensation origin captured; no movement command was sent")

    def send_zero(self) -> None:
        confirmed = messagebox.askyesno(
            "Synthetic zero pose", "Send an explicit zero pose to the simulator?"
        )
        if confirmed:
            self._run_command(self.controller.send_zero_command)

    def _run_command(self, operation: Callable[[], CommandResult]) -> None:
        if not self.client.connected:
            messagebox.showwarning("Not connected", "Start the local simulator and connect first.")
            return
        try:
            self._apply_settings()
            result = operation()
        except (OSError, RuntimeError, ValueError, tk.TclError) as exc:
            messagebox.showerror("Command failed", str(exc))
            return
        self._show_result(result)

    def _apply_settings(self) -> None:
        values = {key: variable.get() for key, variable in self.settings.items()}
        mapping = self.config.mapping
        mapping.swap_xy = bool(values["swap_xy"])
        mapping.x_sign = int(values["x_sign"])
        mapping.y_sign = int(values["y_sign"])
        mapping.rotation_degrees = float(values["rotation"])
        mapping.swap_yz = bool(values["swap_yz"])
        mapping.swap_rw = bool(values["swap_rw"])
        compensation = self.config.compensation
        compensation.z_enabled = bool(values["z_enabled"])
        compensation.z_kx = float(values["z_kx"])
        compensation.z_ky = float(values["z_ky"])
        compensation.z_sign = int(values["z_sign"])
        compensation.r_enabled = bool(values["r_enabled"])
        compensation.r_kx = float(values["r_kx"])
        compensation.r_ky = float(values["r_ky"])
        compensation.r_sign = int(values["r_sign"])
        safety = self.config.safety
        safety.enabled = bool(values["limits_enabled"])
        safety.x_min = float(values["x_min"])
        safety.x_max = float(values["x_max"])
        safety.y_min = float(values["y_min"])
        safety.y_max = float(values["y_max"])
        safety.fixed_z_enabled = bool(values["fixed_z_enabled"])
        safety.fixed_z = float(values["fixed_z"])

    def _show_result(self, result: CommandResult) -> None:
        self._refresh_state_labels()
        for axis, variable in self.absolute_vars.items():
            variable.set(getattr(self.controller.commanded_pose, axis))
        clamp = ",".join(result.clamped_axes) or "none"
        self.preview_text.set(
            f"safe={_format_pose(result.safe_scene_pose)}\n"
            f"robot={_format_pose(result.robot_pose)}\nclamped={clamp}"
        )
        self.log(f"Command sent; clamped axes: {clamp}")

    def _poll(self) -> None:
        for line in self.client.drain_received():
            try:
                sample = parse_telemetry(line, self.controller.measured_pose)
            except ProtocolError as exc:
                self.log(f"Ignored telemetry: {exc}")
                continue
            self.controller.update_measured_pose(sample.pose)
            self.log("Telemetry updated measured pose")
        if not self.client.connected and self.status.get().startswith("Connected"):
            self.status.set("Disconnected")
            self.connect_button.configure(text="Connect")
            self._set_controls_enabled(False)
        self._refresh_state_labels()
        self._flush_log()
        self.root.after(self.POLL_MS, self._poll)

    def _refresh_state_labels(self) -> None:
        self.commanded_text.set(_format_pose(self.controller.commanded_pose))
        self.measured_text.set(_format_pose(self.controller.measured_pose))

    def _set_controls_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in self.command_buttons:
            button.configure(state=state)

    def log(self, message: str) -> None:
        self.log_queue.put(message)

    def _flush_log(self) -> None:
        lines: list[str] = []
        while True:
            try:
                lines.append(self.log_queue.get_nowait())
            except queue.Empty:
                break
        if not lines:
            return
        self.log_widget.configure(state="normal")
        self.log_widget.insert("end", "\n".join(lines) + "\n")
        self.log_widget.see("end")
        self.log_widget.configure(state="disabled")

    def close(self) -> None:
        self.client.disconnect("application closed")
        self.root.destroy()


def _format_pose(pose: Pose) -> str:
    return "  ".join(f"{axis.upper()}={getattr(pose, axis):.2f}" for axis in AXES)


def main() -> None:
    root = tk.Tk()
    TeleoperationGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
