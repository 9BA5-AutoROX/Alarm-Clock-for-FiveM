from controller.controller import Controller
from ui.overlay_window import OverlayWindow

def main():
    controller = Controller()
    window = OverlayWindow(controller)
    window.run()

if __name__ == "__main__":
    main()
