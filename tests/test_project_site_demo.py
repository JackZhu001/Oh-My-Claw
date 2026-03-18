"""Tests for project-site demo."""
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_DIR = os.path.join(BASE_DIR, "demo", "project-site")


def test_index_html_exists():
    path = os.path.join(SITE_DIR, "index.html")
    assert os.path.exists(path)


def test_styles_css_exists():
    path = os.path.join(SITE_DIR, "styles.css")
    assert os.path.exists(path)


def test_app_js_exists():
    path = os.path.join(SITE_DIR, "app.js")
    assert os.path.exists(path)


def test_hero_section_exists():
    path = os.path.join(SITE_DIR, "index.html")
    with open(path) as f:
        assert 'id="hero"' in f.read()


def test_highlights_section_exists():
    path = os.path.join(SITE_DIR, "index.html")
    with open(path) as f:
        assert 'id="highlights"' in f.read()


def test_architecture_section_exists():
    path = os.path.join(SITE_DIR, "index.html")
    with open(path) as f:
        assert 'id="architecture"' in f.read()


def test_workflow_section_exists():
    path = os.path.join(SITE_DIR, "index.html")
    with open(path) as f:
        assert 'id="workflow"' in f.read()


def test_comparison_section_exists():
    path = os.path.join(SITE_DIR, "index.html")
    with open(path) as f:
        assert 'id="comparison"' in f.read()


def test_quickstart_section_exists():
    path = os.path.join(SITE_DIR, "index.html")
    with open(path) as f:
        assert 'id="quickstart"' in f.read()


def test_faq_section_exists():
    path = os.path.join(SITE_DIR, "index.html")
    with open(path) as f:
        assert 'id="faq"' in f.read()


def test_theme_toggle_button_exists():
    path = os.path.join(SITE_DIR, "index.html")
    with open(path) as f:
        assert 'id="themeToggle"' in f.read()


def test_js_has_localstorage_theme_logic():
    path = os.path.join(SITE_DIR, "app.js")
    with open(path) as f:
        content = f.read()
    assert "localStorage" in content
    assert "theme" in content


def test_faq_interaction_keywords():
    path = os.path.join(SITE_DIR, "app.js")
    with open(path) as f:
        assert "faq-question" in f.read()


def test_nav_anchor_links():
    path = os.path.join(SITE_DIR, "index.html")
    with open(path) as f:
        content = f.read()
    assert 'href="#hero"' in content
    assert 'href="#highlights"' in content