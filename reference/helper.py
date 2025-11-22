import json
from pygments import highlight
from pygments.lexers import JsonLexer
from pygments.formatters import HtmlFormatter
from django.utils.safestring import mark_safe


def pretty_json(field):
    """Function to display pretty version of our data"""
    if type(field) is str:
        field = json.loads(field)
    response = json.dumps(field, sort_keys=True, indent=2, ensure_ascii=False)
    formatter = HtmlFormatter(style='colorful', nobackground=True)
    response = highlight(response, JsonLexer(), formatter)
    style = "<style>" + formatter.get_style_defs() + ".s2{background-color:transparent!important;} .nt{color:#aeffae!important;}</style><br>"
    return mark_safe(style + response)
