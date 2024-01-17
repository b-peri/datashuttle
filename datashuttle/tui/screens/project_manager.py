from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import (
    Button,
    Header,
    TabbedContent,
    TabPane,
)

from datashuttle.tui import configs
from datashuttle.tui.tabs import create_folders, transfer
from watchdog.observers import Observer
import watchdog.events


class ProjectManagerScreen(Screen):
    """
    Screen containing the Create and Transfer tabs. This is
    the primary screen within which the user interacts with
    a pre-configured project.

    The 'Create' tab interacts with Datashuttle's `make_folders()`
    method to create new project folders.

    The 'Transfer' tab, XXX.

    The 'Configs' tab displays the current project's configurations
    and allows configs to be reset. This is an instantiation of the
    ConfigsContent window, which is also shared by `Make New Project`.
    See ConfigsContent for more information.

    Parameters
    ----------

    mainwindow : TuiApp
        The main application window used for coordinating screen display.

    project : DataShuttle
        An instantiated datashuttle project.
    """

    def __init__(self, mainwindow, project):
        super(ProjectManagerScreen, self).__init__()

        self.mainwindow = mainwindow
        self.project = project
        self.title = f"Project: {self.project.project_name}"

        self.event_handler = None  # TODO: init properly

    def compose(self) -> ComposeResult:
        yield Header()
        yield Button("Main Menu", id="all_main_menu_buttons")
        with TabbedContent(
            id="tabscreen_tabbed_content", initial="tabscreen_create_tab"
        ):
            yield create_folders.CreateFoldersTab(
                self.mainwindow, self.project
            )
            yield transfer.TransferTab(self.mainwindow, self.project)
            with TabPane("Configs", id="tabscreen_configs_tab"):
                yield configs.ConfigsContent(self, self.project)

   # def on_mount(self):
    #    self.start_watchdog()

    def start_watchdog(self):
        self.event_handler = watchdog.events.PatternMatchingEventHandler(
            patterns=["*"],
            ignore_patterns=[],
            ignore_directories=False)

        self.event_handler.on_moved = self.handle_local_filesystem_change
        self.event_handler.on_created = self.handle_local_filesystem_change
        self.event_handler.on_deleted = self.handle_local_filesystem_change

        self.observer = Observer()
        self.observer.schedule(self.event_handler, self.project.cfg["local_path"].as_posix(),  # TODO: centralise this.
                          recursive=True)
        self.observer.start()
        import time
        try:
            while True:
                time.sleep(1)
        finally:
            self.observer.stop()
            self.observer.join()

    def handle_local_filesystem_change(self, event):
        assert False

    def on_button_pressed(self, event: Button.Pressed):
        """
        Dismisses the TabScreen (and returns to the main menu) once
        the 'Main Menu' button is pressed.
        """

        if event.button.id == "all_main_menu_buttons":
            self.dismiss()

    def on_key(self):
        self.start_watchdog()