"""HTML templates for web UI."""

from .templates_body import INDEX_BODY
from .templates_script import INDEX_SCRIPT
from .templates_style import INDEX_STYLE

INDEX_HTML = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TTS Adapter</title>
    <style>
{INDEX_STYLE}
    </style>
</head>
<body>
{INDEX_BODY}
<script>
{INDEX_SCRIPT}
</script>
</body>
</html>
"""
