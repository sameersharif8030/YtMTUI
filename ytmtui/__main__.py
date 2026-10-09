from .app import YtMTUI


def main() -> None:
    app = YtMTUI()
    try:
        app.run()
    finally:
        app.shutdown_player()


if __name__ == "__main__":
    main()
