from watchdog.observers import Observer
import watchdog.events

if False:
    def print_me(event):
        print("HW")

    event_handler = watchdog.events.PatternMatchingEventHandler(
                patterns=["*"],
                ignore_patterns=[],
                ignore_directories=False)
    event_handler.on_moved = print_me
    event_handler.on_created = print_me
    event_handler.on_deleted = print_me

    observer = Observer()
    observer.schedule(event_handler, r"C:\fMRIData\git-repo\easy_electrophysiology", recursive=False)
    observer.start()


from watchdog.observers import Observer
import watchdog.events

class MyTestClass():
    def __init__(self):

        self.start_watchdog()

    def start_watchdog(self):
        self.event_handler = watchdog.events.PatternMatchingEventHandler(
            patterns=["*"],
            ignore_patterns=[],
            ignore_directories=False)

        self.event_handler.on_moved = self.handle_local_filesystem_change
        self.event_handler.on_created = self.handle_local_filesystem_change
        self.event_handler.on_deleted = self.handle_local_filesystem_change

        self.observer = Observer()
        self.observer.schedule(self.event_handler, r"C:\data\datashuttle\local\my_first_project",  # TODO: try as path
                          recursive=True)
        self.observer.start()

    def handle_local_filesystem_change(self, event):
        assert False

my_test_class = MyTestClass()
