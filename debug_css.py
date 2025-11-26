from textual.css.stylesheet import Stylesheet
from textual.dom import DOMNode
import os

css_path = "tui/terminal_app.css"

try:
    with open(css_path, "r") as f:
        css = f.read()
    
    stylesheet = Stylesheet()
    stylesheet.add_source(css, css_path)
    stylesheet.parse()
    print("CSS parsed successfully")
except Exception as e:
    print(f"CSS parse error: {e}")
