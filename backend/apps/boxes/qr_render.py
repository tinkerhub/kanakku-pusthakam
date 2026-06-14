import segno
from django.utils.html import escape


def render_qr_label_svg(payload: str, label: str | None = None) -> str:
    png_data_uri = segno.make(payload).png_data_uri(scale=5)
    if label is None:
        return (
            '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="300" viewBox="0 0 300 300">'
            '<rect width="300" height="300" fill="#ffffff"/>'
            f'<image href="{png_data_uri}" x="10" y="10" width="280" height="280"/>'
            "</svg>"
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="320" height="360" viewBox="0 0 320 360">'
        '<rect width="320" height="360" fill="#ffffff"/>'
        f'<image href="{png_data_uri}" x="20" y="10" width="280" height="280"/>'
        f'<text x="160" y="330" text-anchor="middle" font-family="Arial,sans-serif" font-size="18" fill="#111827">{escape(label)}</text>'
        "</svg>"
    )
