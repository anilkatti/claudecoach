"""Tests for the ClaudeCoach editorial-product component kit. Pure strings, no I/O."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import coach_theme as ct  # noqa: E402


def test_esc_coerces_none_and_escapes():
    assert ct.esc(None) == ""
    assert ct.esc("<b>&") == "&lt;b&gt;&amp;"


def test_page_shell_carries_tokens_and_fonts():
    html = ct.page("T", "<header>m</header>", "<p>b</p>", "<footer>f</footer>")
    assert html.startswith("<!DOCTYPE html>")
    assert "<title>T</title>" in html and "</html>" in html
    assert "--accent:#bd4d2a" in html          # new token
    assert "Inter" in html and "Fraunces" in html
    assert '<div class="wrap"><p>b</p></div>' in html
    assert "<header>m</header>" in html and "<footer>f</footer>" in html


def test_masthead_has_wordmark_and_crumb():
    m = ct.masthead("profile", "-Volumes-x")
    assert "ClaudeCoach" in m and "/ profile" in m
    assert "Profile" in m                        # label.title() in the crumb
    assert "<code>-Volumes-x</code>" in m


def test_hero_structure_and_escaping():
    h = ct.hero("KICK", "Title <x>", "Lead.", ct.chip("c", strong="9"))
    assert 'class="kicker">KICK<' in h
    assert "<h1>Title &lt;x&gt;</h1>" in h
    assert "Lead." in h and 'class="chiprow">' in h and "<b>9</b>" in h


def test_section_empty_body_returns_blank():
    assert ct.section("01", "X", "") == ""
    s = ct.section("01", "How you work", "<p>x</p>", eyebrow="signals")
    assert '<span class="num">01</span>' in s and "<h2>How you work</h2>" in s
    assert "signals" in s and "<p>x</p>" in s


def test_signal_grid_renders_rows():
    g = ct.signal_grid([{"k": "Prompting", "v": "Directive and clear", "q": "do X"}])
    assert 'class="sigs"' in g and 'class="k">Prompting<' in g
    assert "Directive and clear" in g and 'class="q">do X<' in g


def test_weight_bars_clamp_and_label():
    b = ct.weight_bars([{"label": "Bugs", "weight": 0.93},
                        {"label": "Over", "weight": 2.0},
                        {"label": "Under", "weight": -1}])
    assert "width:93%" in b and "Bugs" in b
    assert "width:100%" in b                      # clamped high
    assert "width:0%" in b                        # clamped low
    assert ">.93<" in b                           # ".NN" label


def test_stat_grid():
    s = ct.stat_grid([("6,764", "tokens"), ("8", "hooks")])
    assert 'class="n">6,764<' in s and "tokens" in s and 'class="n">8<' in s


def test_evidence_and_impact_figure():
    assert 'class="who">session:a<' in ct.evidence("session:a", "hi")
    fig = ct.impact_figure("2", "re-explains avoided")
    assert "<b>2</b>" in fig and "re-explains avoided" in fig


def test_callout_holds_trusted_html():
    c = ct.callout("<b>review</b> then <code>/perform-actions</code>")
    assert 'class="callout"' in c and "/perform-actions" in c


def test_priority_lane_kind_classes():
    assert 'class="pri now"' in ct.priority_lane("Do now", "now", "3 actions")
    assert 'class="pri consider"' in ct.priority_lane("Consider", "consider", "")
    assert 'class="pri fyi"' in ct.priority_lane("FYI", "fyi", "1 action")


def test_action_card_family_color_and_drawer():
    a = ct.action_card("Install X", "acquire", "low",
                       "Because reasons.",
                       impact_html=ct.impact_figure("2", "avoided"),
                       source_html='verified · <a href="https://ex.com">src</a>',
                       evidence_html=ct.evidence("sig", "q"),
                       apply_kind="run_command", apply_preview="/plugin install x")
    assert 'class="acard"' in a and "<h3>Install X</h3>" in a
    assert "var(--c-acquire)" in a                 # family dot color
    assert "low effort" in a
    assert "Apply — run_command" in a and "/plugin install x" in a


def test_footer():
    f = ct.footer("Read by Haiku. ", "nondeterministic.")
    assert "ClaudeCoach" in f and "nondeterministic." in f
