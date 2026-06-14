import sys

from sound_mixer.app import SoundMixerApp


def main() -> int:
    app = SoundMixerApp()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
