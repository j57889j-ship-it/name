"""Convert only bold-heading text into Unicode display alphabets."""
from __future__ import annotations
import re

_LATIN = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
_MAPS = {
    "bold": "𝐀𝐁𝐂𝐃𝐄𝐅𝐆𝐇𝐈𝐉𝐊𝐋𝐌𝐍𝐎𝐏𝐐𝐑𝐒𝐓𝐔𝐕𝐖𝐗𝐘𝐙𝐚𝐛𝐜𝐝𝐞𝐟𝐠𝐡𝐢𝐣𝐤𝐥𝐦𝐧𝐨𝐩𝐪𝐫𝐬𝐭𝐮𝐯𝐰𝐱𝐲𝐳𝟎𝟏𝟐𝟑𝟒𝟓𝟔𝟕𝟖𝟗",
    "sans": "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵",
    "bolditalic": "𝑨𝑩𝑪𝑫𝑬𝑭𝑮𝑯𝑰𝑱𝑲𝑳𝑴𝑵𝑶𝑷𝑸𝑹𝑺𝑻𝑼𝑽𝑾𝑿𝒀𝒁𝒂𝒃𝒄𝒅𝒆𝒇𝒈𝒉𝒊𝒋𝒌𝒍𝒎𝒏𝒐𝒑𝒒𝒓𝒔𝒕𝒖𝒗𝒘𝒙𝒚𝒛0123456789",
    "script": "𝓐𝓑𝓒𝓓𝓔𝓕𝓖𝓗𝓘𝓙𝓚𝓛𝓜𝓝𝓞𝓟𝓠𝓡𝓢𝓣𝓤𝓥𝓦𝓧𝓨𝓩𝓪𝓫𝓬𝓭𝓮𝓯𝓰𝓱𝓲𝓳𝓴𝓵𝓶𝓷𝓸𝓹𝓺𝓻𝓼𝓽𝓾𝓿𝔀𝔁𝔂𝔃0123456789",
    "mono": "𝙰𝙱𝙲𝙳𝙴𝙵𝙶𝙷𝙸𝙹𝙺𝙻𝙼𝙽𝙾𝙿𝚀𝚁𝚂𝚃𝚄𝚅𝚆𝚇𝚈𝚉𝚊𝚋𝚌𝚍𝚎𝚏𝚐𝚑𝚒𝚓𝚔𝚕𝚖𝚗𝚘𝚙𝚚𝚛𝚜𝚝𝚞𝚟𝚠𝚡𝚢𝚣𝟶𝟷𝟸𝟹𝟺𝟻𝟼𝟽𝟾𝟿",
    "smallcaps": "ᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢᴀʙᴄᴅᴇꜰɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡxʏᴢ0123456789",
}


def _mapping(style: str) -> dict[str, str]:
    target = _MAPS.get(style, _MAPS["bold"])
    return {source: target[index] for index, source in enumerate(_LATIN) if index < len(target)}


def _convert_heading(text: str, style: str) -> str:
    mapping = _mapping(style)
    # Preserve HTML entities byte-for-byte; transform ordinary characters only.
    parts = re.split(r"(&[A-Za-z0-9#]+;)", text)
    for index in range(0, len(parts), 2):
        parts[index] = "".join(mapping.get(char, char) for char in parts[index])
    return "".join(parts)


def stylize(html_text: str, style: str = "bold") -> str:
    """Stylize content inside <b>...</b> only; leave body, entities and code intact."""
    if style not in _MAPS:
        style = "bold"
    pattern = re.compile(r"<b>(.*?)</b>", re.IGNORECASE | re.DOTALL)
    return pattern.sub(lambda match: "<b>" + _convert_heading(match.group(1), style) + "</b>", html_text)


def render_post(body_html: str, frame: str = "terminal", font: str = "bold") -> str:
    """Apply a channel frame and heading font; deterministic for preview and publish."""
    body = stylize(body_html, font)
    if frame == "terminal":
        return f"<code>root@dasturlash:~$ post</code>\n\n{body}"
    if frame == "card":
        return f"<b>━━━━━━━━━━━━━━━━</b>\n{body}\n<b>━━━━━━━━━━━━━━━━</b>"
    if frame == "script":
        return f"<i>✦ DASTURLASH &amp; AI ✦</i>\n\n{body}"
    return body


if __name__ == "__main__":
    assert stylize("<b>Hello</b> body", "bold").startswith("<b>𝐇𝐞𝐥𝐥𝐨</b>")
    assert stylize("<b>A&amp;B</b>", "mono") == "<b>𝙰&amp;𝙱</b>"
    assert "body" in stylize("<b>Title</b> body", "script")
    assert stylize("<b>o'g' g‘</b>", "sans").startswith("<b>𝗼'𝗴' 𝗴‘</b>")
