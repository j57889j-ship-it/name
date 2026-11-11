from bot.ui.stylizer import stylize, render_post


def test_bold_heading_only_changes():
    result = stylize("<b>Hello</b> normal body", "bold")
    assert result == "<b>𝐇𝐞𝐥𝐥𝐨</b> normal body"


def test_entities_are_preserved():
    assert stylize("<b>A&amp;B</b>", "mono") == "<b>𝙰&amp;𝙱</b>"


def test_code_and_pre_are_not_changed():
    text = "<b>Title</b> <code>print('ok')</code> <pre>ABC</pre>"
    result = stylize(text, "script")
    assert "<code>print('ok')</code>" in result
    assert "<pre>ABC</pre>" in result


def test_post_frame():
    assert render_post("<b>Hi</b>", "terminal", "bold").startswith("<code>root@dasturlash:~$ post</code>")


def test_apostrophes_are_untouched():
    result = stylize("<b>o'g' g‘</b>", "sans")
    assert "'" in result and "‘" in result
