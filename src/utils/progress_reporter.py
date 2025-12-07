"""Progress reporter with periodic updates."""

import threading
import time
from datetime import datetime
from typing import Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich.live import Live

from ..config.settings import ProcessingStep


@dataclass
class StepStatus:
    """Status of a processing step."""
    name: str
    status: str = "pending"  # pending, in_progress, completed, failed
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    message: str = ""
    sub_steps: list[str] = field(default_factory=list)
    current_sub_step: int = 0


class ProgressReporter:
    """
    Progress reporter that updates every 15 seconds.

    Tracks the current step, overall progress, and provides
    periodic console updates.
    """

    def __init__(
        self,
        update_interval: int = 15,
        console: Optional[Console] = None,
        on_update: Optional[Callable[[dict], None]] = None
    ):
        self.update_interval = update_interval
        self.console = console or Console()
        self.on_update = on_update

        self._steps: dict[str, StepStatus] = {}
        self._current_step: Optional[str] = None
        self._start_time: Optional[datetime] = None
        self._is_running = False
        self._update_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Initialize all steps
        for step in ProcessingStep.ORDERED_STEPS:
            self._steps[step] = StepStatus(name=step)

    def start(self):
        """Start the progress reporter."""
        self._start_time = datetime.now()
        self._is_running = True

        # Start update thread
        self._update_thread = threading.Thread(target=self._update_loop, daemon=True)
        self._update_thread.start()

        self.console.print("\n[bold green]Starting NotebookLM Generation Process[/bold green]\n")

    def stop(self):
        """Stop the progress reporter."""
        self._is_running = False
        if self._update_thread:
            self._update_thread.join(timeout=2)

        self._print_final_summary()

    def set_step(self, step: str, message: str = ""):
        """Set the current processing step."""
        with self._lock:
            # Complete previous step if exists
            if self._current_step and self._current_step != step:
                prev_status = self._steps.get(self._current_step)
                if prev_status and prev_status.status == "in_progress":
                    prev_status.status = "completed"
                    prev_status.end_time = datetime.now()

            # Start new step
            self._current_step = step
            if step in self._steps:
                self._steps[step].status = "in_progress"
                self._steps[step].start_time = datetime.now()
                self._steps[step].message = message

    def update_message(self, message: str):
        """Update the message for the current step."""
        with self._lock:
            if self._current_step and self._current_step in self._steps:
                self._steps[self._current_step].message = message

    def set_sub_steps(self, sub_steps: list[str]):
        """Set sub-steps for the current step."""
        with self._lock:
            if self._current_step and self._current_step in self._steps:
                self._steps[self._current_step].sub_steps = sub_steps
                self._steps[self._current_step].current_sub_step = 0

    def advance_sub_step(self):
        """Advance to the next sub-step."""
        with self._lock:
            if self._current_step and self._current_step in self._steps:
                status = self._steps[self._current_step]
                if status.current_sub_step < len(status.sub_steps):
                    status.current_sub_step += 1

    def fail_step(self, step: str, error_message: str):
        """Mark a step as failed."""
        with self._lock:
            if step in self._steps:
                self._steps[step].status = "failed"
                self._steps[step].end_time = datetime.now()
                self._steps[step].message = f"Error: {error_message}"

    def complete_step(self, step: str):
        """Mark a step as completed."""
        with self._lock:
            if step in self._steps:
                self._steps[step].status = "completed"
                self._steps[step].end_time = datetime.now()

    def get_progress(self) -> dict:
        """Get current progress information."""
        with self._lock:
            completed = sum(1 for s in self._steps.values() if s.status == "completed")
            failed = sum(1 for s in self._steps.values() if s.status == "failed")
            total = len(self._steps)

            elapsed = None
            if self._start_time:
                elapsed = (datetime.now() - self._start_time).total_seconds()

            return {
                "current_step": self._current_step,
                "completed_steps": completed,
                "failed_steps": failed,
                "total_steps": total,
                "progress_percent": (completed / total) * 100 if total > 0 else 0,
                "elapsed_seconds": elapsed,
                "steps": {k: {
                    "name": v.name,
                    "status": v.status,
                    "message": v.message
                } for k, v in self._steps.items()}
            }

    def _update_loop(self):
        """Background thread that prints updates every interval."""
        while self._is_running:
            self._print_progress()
            time.sleep(self.update_interval)

    def _print_progress(self):
        """Print current progress to console."""
        progress = self.get_progress()

        # Create progress table
        table = Table(title="Progress Update", show_header=True, header_style="bold cyan")
        table.add_column("Step", style="dim")
        table.add_column("Status")
        table.add_column("Details")

        status_icons = {
            "pending": "[dim]○[/dim]",
            "in_progress": "[yellow]●[/yellow]",
            "completed": "[green]✓[/green]",
            "failed": "[red]✗[/red]"
        }

        for step_name in ProcessingStep.ORDERED_STEPS:
            status = self._steps.get(step_name)
            if status:
                icon = status_icons.get(status.status, "○")
                status_text = status.status.replace("_", " ").title()

                # Add sub-step progress if available
                details = status.message
                if status.sub_steps and status.status == "in_progress":
                    details = f"{status.current_sub_step}/{len(status.sub_steps)} - {details}"

                table.add_row(
                    step_name.replace("_", " ").title(),
                    f"{icon} {status_text}",
                    details[:50] + "..." if len(details) > 50 else details
                )

        self.console.print(table)

        # Print summary line
        elapsed_str = ""
        if progress["elapsed_seconds"]:
            minutes = int(progress["elapsed_seconds"] // 60)
            seconds = int(progress["elapsed_seconds"] % 60)
            elapsed_str = f" | Elapsed: {minutes}m {seconds}s"

        self.console.print(
            f"\n[bold]Progress: {progress['completed_steps']}/{progress['total_steps']} "
            f"({progress['progress_percent']:.1f}%){elapsed_str}[/bold]\n"
        )

        # Callback if provided
        if self.on_update:
            self.on_update(progress)

    def _print_final_summary(self):
        """Print final summary when processing completes."""
        progress = self.get_progress()

        self.console.print("\n" + "=" * 60)
        self.console.print("[bold]Final Summary[/bold]")
        self.console.print("=" * 60)

        for step_name in ProcessingStep.ORDERED_STEPS:
            status = self._steps.get(step_name)
            if status:
                if status.status == "completed":
                    self.console.print(f"[green]✓[/green] {step_name.replace('_', ' ').title()}")
                elif status.status == "failed":
                    self.console.print(f"[red]✗[/red] {step_name.replace('_', ' ').title()}: {status.message}")
                else:
                    self.console.print(f"[dim]○[/dim] {step_name.replace('_', ' ').title()}: Skipped")

        if progress["elapsed_seconds"]:
            minutes = int(progress["elapsed_seconds"] // 60)
            seconds = int(progress["elapsed_seconds"] % 60)
            self.console.print(f"\n[bold]Total time: {minutes}m {seconds}s[/bold]")

        self.console.print("=" * 60 + "\n")
