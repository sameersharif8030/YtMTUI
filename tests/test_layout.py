from ytmtui.layout import LayoutEngine


def main() -> None:
    engine = LayoutEngine()

    wide = engine.plan(120, 40, mini=False)
    assert not wide.mini and not wide.compact
    assert wide.show_header and wide.show_sidebar and wide.show_hero and wide.show_library and wide.show_queue and wide.show_footer

    narrow = engine.plan(60, 40, mini=False)
    assert not narrow.mini
    assert narrow.compact

    medium = engine.plan(100, 40, mini=False)
    assert medium.compact  # 100 >= 96 = tablet breakpoint (compact)

    short = engine.plan(120, 5, mini=False)
    assert short.mini and not short.show_sidebar and not short.show_header

    tiny_footer = engine.plan(120, 13, mini=False)
    assert tiny_footer.show_footer  # footer always shown except in mini mode

    mini = engine.plan(120, 40, mini=True)
    assert mini.mini and not mini.show_sidebar and not mini.show_library and not mini.show_queue
    assert mini.compact  # mini mode is always compact

    mini_narrow = engine.plan(60, 40, mini=True)
    assert mini_narrow.mini and mini_narrow.compact

    print("layout tests OK")


if __name__ == "__main__":
    main()
