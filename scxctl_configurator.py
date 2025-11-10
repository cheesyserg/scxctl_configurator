import sys
import re
import subprocess
from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QComboBox, QVBoxLayout, QHBoxLayout, QPushButton, QGroupBox, QLineEdit,
    QWidget as ContainerWidget
)
from PySide6.QtCore import Qt

# --- 1. Import Data ---
from scheduler_data import SCHEDULER_OPTIONS

class SchedulerSelector(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SCXCTL Scheduler Configurator")
        self.setGeometry(100, 100, 500, 500)

        self.dynamic_widgets_group = QGroupBox("Configuration Options")
        self.dynamic_layout = QVBoxLayout()
        self.dynamic_widgets_group.setLayout(self.dynamic_layout)

        # Class variables to hold dynamic widgets
        self.mode_layout_widget = None
        self.args_layout_widget = None
        self.mode_combo = None
        self.args_textbox = None
        self.description_label = None

        self.current_status_text = ""
        self.setup_ui()
        self.populate_dropdown_from_scxctl()
        self.update_status()

    def setup_ui(self):
        """Initializes all static widgets and the main layout."""
        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        # 0. Scheduler Status Indicator
        self.status_indicator = QLabel("Checking status...", self)
        self.status_indicator.setAlignment(Qt.AlignCenter)
        self.status_indicator.setStyleSheet(
            """
            QLabel {
                padding: 8px;
                border: 1px solid #333;
                border-radius: 4px;
                font-weight: bold;
            }
            """
        )
        self.main_layout.addWidget(self.status_indicator)

        # 1. Main Scheduler Dropdown
        self.main_layout.addWidget(QLabel("Select an Available Scheduler:"))
        self.scheduler_combo = QComboBox(self)
        self.scheduler_combo.currentIndexChanged.connect(self.update_dynamic_options)
        self.main_layout.addWidget(self.scheduler_combo)

        # 2. Dynamic Options Group Box (Modes/Flags, Description, Custom Args)
        self.main_layout.addWidget(self.dynamic_widgets_group)

        # 3. Action Buttons (Combined Switch/Start and Stop)
        self.select_button = QPushButton("Confirm Selection (Switch or Start Scheduler)")
        self.select_button.clicked.connect(self.confirm_selection)
        self.main_layout.addWidget(self.select_button)

        # Stop Button
        self.mgmt_layout = QHBoxLayout()
        self.disable_button = QPushButton("Stop Scheduler")
        self.disable_button.clicked.connect(self.disable_scheduler)
        self.mgmt_layout.addWidget(self.disable_button)
        self.main_layout.addLayout(self.mgmt_layout)

        # 4. Feedback Label
        self.feedback_label = QLabel("Waiting for action...", self)
        self.feedback_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.feedback_label)

        self.update_dynamic_options()

    def clear_layout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                sub_layout = item.layout()
                if sub_layout is not None:
                    self.clear_layout(sub_layout)

    def autofill_arguments(self, mode_flags):
        """Autofills the custom arguments textbox with the selected mode's flags."""
        if self.args_textbox:
            # Clear the textbox if mode_flags is empty (i.e., Default selected)
            # Otherwise, set the flags
            self.args_textbox.setText(mode_flags)

    def update_description(self):
        """Updates the description label and triggers autofill based on the selected mode."""

        selected_scheduler = self.scheduler_combo.currentText()

        if not self.mode_combo or self.mode_combo.currentIndex() == 0:
            self.description_label.setText("<small>Select a mode above to view its description and flags.</small>")
            self.autofill_arguments("") # Clear the arguments if default is selected
            return

        mode_name = self.mode_combo.currentText()

        mode_data = SCHEDULER_OPTIONS.get(selected_scheduler, {}).get("Modes", {}).get(mode_name, {})

        description = mode_data.get("Description", "No description available.")
        flags = mode_data.get("Flags", "No flags.")

        # Format the description
        formatted_text = f"<b>Flags:</b> <code>{flags}</code><br>"
        formatted_text += f"<b>Description:</b> {description}"

        self.description_label.setText(formatted_text)

        # Trigger autofill with the extracted flags
        self.autofill_arguments(flags)


    def update_dynamic_options(self):
        """
        Clears old options and rebuilds all dynamic widgets, including the static custom arguments.
        """
        selected_scheduler = self.scheduler_combo.currentText()
        options = SCHEDULER_OPTIONS.get(selected_scheduler, {"Modes": {}, "Flags": {}})

        self.clear_layout(self.dynamic_layout)

        modes = options["Modes"]
        flags = options["Flags"]

        # Reset dynamic widget trackers
        self.mode_layout_widget = None
        self.args_layout_widget = None
        self.mode_combo = None
        self.args_textbox = None
        self.description_label = None


        # 1. Mode Dropdown Widgets
        if modes:
            mode_layout = QHBoxLayout()
            mode_layout.addWidget(QLabel("Scheduler Mode:"))

            self.mode_combo = QComboBox(self)
            self.mode_combo.addItem("Default (No Mode Flags)")
            for mode_name in modes.keys():
                self.mode_combo.addItem(mode_name)

            # Connect to update description (which now also triggers autofill)
            self.mode_combo.currentIndexChanged.connect(self.update_description)

            mode_layout.addWidget(self.mode_combo)

            self.mode_layout_widget = ContainerWidget()
            self.mode_layout_widget.setLayout(mode_layout)
            self.dynamic_layout.addWidget(self.mode_layout_widget)
        else:
            self.dynamic_layout.addWidget(QLabel("No specific Modes available for this scheduler."))


        # 2. Description Label
        self.description_label = QLabel()
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet(
            """
            QLabel {
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
            }
            """
        )
        self.dynamic_layout.addWidget(self.description_label)


        # 3. Custom Arguments Text Box (Static and visible)
        args_layout = QHBoxLayout()
        args_layout.addWidget(QLabel("Custom Arguments (Overrides Mode):"))
        self.args_textbox = QLineEdit(self)
        self.args_textbox.setPlaceholderText('e.g., -m performance -w -C 0')
        args_layout.addWidget(self.args_textbox)

        self.args_layout_widget = ContainerWidget()
        self.args_layout_widget.setLayout(args_layout)
        self.dynamic_layout.addWidget(self.args_layout_widget)

        # 4. Placeholder/Flags
        if flags:
            self.dynamic_layout.addWidget(QLabel("Individual flags not implemented for this scheduler."))
            self.flag_checkboxes = []
        else:
            self.flag_checkboxes = []

        self.dynamic_layout.addStretch()

        # Initial call
        self.update_description()

    # --- STATUS CHECK METHODS (No Changes) ---

    def check_scheduler_status(self):
        """Runs 'scxctl get' and returns the raw output and formatted status."""
        try:
            result = subprocess.run(
                ['scxctl', 'get'],
                capture_output=True,
                text=True,
                check=True,
                encoding='utf-8'
            )
            output = result.stdout.strip()
            self.current_status_text = output.lower()

            if self.current_status_text == "no scx scheduler running":
                return "Scheduler Status: DISABLED", output

            if output:
                scheduler_name = output.strip()
                return f"Scheduler Status: {scheduler_name.upper()}", output

            return "Scheduler Status: Status Unknown (Empty Output)", output

        except FileNotFoundError:
            return "ERROR: scxctl command not found.", "ERROR"
        except subprocess.CalledProcessError:
            return "ERROR: scxctl get failed.", "ERROR"
        except Exception as e:
            return f"An unexpected error occurred: {e}", "ERROR"

    def update_status(self):
        status_text, _ = self.check_scheduler_status()
        self.status_indicator.setText(status_text)

    # --- ENABLE/DISABLE HANDLERS (No Changes) ---

    def run_mgmt_command(self, action, command_list):
        command_str = " ".join(command_list)
        self.feedback_label.setText(f"Attempting command: {command_str}")
        QApplication.processEvents()

        try:
            subprocess.run(
                command_list,
                capture_output=True,
                text=True,
                check=True,
                encoding='utf-8',
            )
            self.feedback_label.setText(f"Scheduler successfully {action}d.")
            self.update_status()
        except subprocess.CalledProcessError as e:
            error_message = f"Failed to {action} scheduler. Error: {e.stderr.strip()}"
            self.feedback_label.setText(f"ERROR: {error_message}")
        except Exception as e:
            error_message = f"An unexpected error occurred: {e}"
            self.feedback_label.setText(f"ERROR: {error_message}")

    def disable_scheduler(self):
        self.run_mgmt_command("stop", ['scxctl', 'stop'])

    # --- CONFIRM/START/SWITCH ACTION (Argument source logic updated) ---

    def confirm_selection(self):
        """
        Pulls arguments from EITHER the textbox (if filled) OR the dropdown (if textbox is empty).
        """
        selected_scheduler = self.scheduler_combo.currentText()

        if selected_scheduler.startswith("--- ERROR ---"):
            self.feedback_label.setText("ERROR: Please select a valid scheduler.")
            return

        # Determine if we need to START or SWITCH
        if self.current_status_text == "no scx scheduler running":
            action_verb = "start"
            base_command = ['scxctl', 'start', '--sched', selected_scheduler]
        else:
            action_verb = "switch"
            base_command = ['scxctl', 'switch', '--sched', selected_scheduler]

        # 1. Prepare Arguments: Custom textbox takes precedence
        # We always use the text currently in the box, whether it was typed or autofilled.
        final_args = self.args_textbox.text().strip()

        if not final_args:
            # If textbox is empty, and a mode is selected, we should still use the mode flags
            # (The autofill logic should prevent this, but this serves as a robust fallback)
            if self.mode_combo and self.mode_combo.currentIndex() > 0:
                selected_mode_name = self.mode_combo.currentText()
                mode_data = SCHEDULER_OPTIONS.get(selected_scheduler, {}).get("Modes", {}).get(selected_mode_name, {})
                final_args = mode_data.get("Flags", "")

        final_args = final_args.strip()

        # 2. Build the Final Command
        final_command = list(base_command)

        if final_args:
            final_command.append('--args')
            # The args must be passed as a single string argument, hence the quotes
            final_command.append(f'"{final_args}"')

        # 3. Execute
        self.feedback_label.setText(f"Attempting command: {' '.join(final_command)}")
        QApplication.processEvents()

        try:
            subprocess.run(
                final_command,
                capture_output=True,
                text=True,
                check=True,
                encoding='utf-8',
            )
            self.feedback_label.setText(f"Scheduler successfully {action_verb}ed to: {selected_scheduler}")
            self.update_status()
        except subprocess.CalledProcessError as e:
            error_message = f"Failed to {action_verb} scheduler: {e.stderr.strip()}"
            self.feedback_label.setText(f"ERROR: {error_message}")
        except Exception as e:
            error_message = f"An unexpected error occurred: {e}"
            self.feedback_label.setText(f"ERROR: {error_message}")

    # --- LIST SCHEDULERS METHODS (No Changes) ---

    def run_scxctl_list(self):
        try:
            result = subprocess.run(
                ['scxctl', 'list'],
                capture_output=True,
                text=True,
                check=True,
                encoding='utf-8'
            )
            return result.stdout
        except FileNotFoundError:
            return "scxctl command not found. Install scxctl."
        except subprocess.CalledProcessError as e:
            return f"scxctl failed. Stderr: {e.stderr.strip()}"
        except Exception as e:
            return f"An unexpected error occurred: {e}"

    def extract_schedulers(self, output_string):
        match = re.search(r'supported schedulers: \[(.*?)\]', output_string, re.DOTALL)
        if match:
            list_content = match.group(1)
            schedulers = re.findall(r'"(.*?)"', list_content)
            return schedulers
        return []

    def populate_dropdown_from_scxctl(self):
        self.feedback_label.setText("Running 'scxctl list' to detect schedulers...")
        QApplication.processEvents()

        output = self.run_scxctl_list()

        if output.startswith("ERROR:"):
            self.scheduler_combo.addItem("--- ERROR ---")
            self.feedback_label.setText(f"ERROR: {output}")
            self.select_button.setEnabled(False)
            return

        scheduler_list = self.extract_schedulers(output)

        for scheduler in scheduler_list:
             self.scheduler_combo.addItem(scheduler)

        if scheduler_list:
            self.feedback_label.setText("Schedulers loaded. Ready to configure.")
        else:
            self.scheduler_combo.addItem("--- ERROR ---")
            self.feedback_label.setText("Error: Could not parse schedulers from command output.")
            self.select_button.setEnabled(False)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SchedulerSelector()
    window.show()
    sys.exit(app.exec())
