# -*- coding: utf-8 -*-
"""
Local yt-dlp resolver pentru Kodi.

Rezolvă URL-uri YouTube/Twitch/etc. direct pe mașina clientului —
URL-urile generate de YouTube sunt bound la IP-ul conexiunii,
deci clientul obține URL-uri valide pentru propriul IP (fără proxy server).

Returnează unul din:
  {"url": str, "headers": dict}
      — live stream sau format combinat (HLS etc.)
  {"url": None, "mpd": str, "headers": dict}
      — DASH: video+audio separate; MPD generat local cu URL-uri directe
"""

from __future__ import annotations

_FORMAT = (
    "bestvideo[ext=mp4]+bestaudio[ext=m4a]"
    "/bestvideo+bestaudio"
    "/best[protocol~='m3u8']"
    "/best"
)


def _build_mpd(video_url: str, audio_url: str, video_meta: dict, audio_meta: dict, duration: int) -> str:
    """Generează un MPEG-DASH MPD minimal cu URL-uri directe (fără proxy server)."""
    vm = video_meta or {}
    am = audio_meta or {}

    pt_dur = "PT%dS" % int(duration) if duration else "PT0S"

    vcodec = vm.get("codec") or "avc1.640028"
    width  = vm.get("width") or 1920
    height = vm.get("height") or 1080
    fps    = vm.get("fps") or 25
    vbr    = vm.get("bitrate") or 4000000
    vext   = vm.get("ext") or "mp4"

    acodec = am.get("codec") or "mp4a.40.2"
    abr    = am.get("bitrate") or 128000
    asr    = am.get("asr") or 44100

    vmime = "video/webm" if vext == "webm" else "video/mp4"
    amime = "audio/webm" if am.get("ext") == "webm" else "audio/mp4"

    def _xe(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<MPD xmlns="urn:mpeg:dash:schema:mpd:2011"\n'
        '     profiles="urn:mpeg:dash:profile:isoff-on-demand:2011"\n'
        '     type="static"\n'
        '     mediaPresentationDuration="{pt_dur}"\n'
        '     minBufferTime="PT4S">\n'
        '  <Period>\n'
        '    <AdaptationSet id="1" contentType="video" mimeType="{vmime}"\n'
        '                   codecs="{vcodec}" frameRate="{fps}" sar="1:1"\n'
        '                   subsegmentAlignment="true" subsegmentStartsWithSAP="1">\n'
        '      <Representation id="v1" bandwidth="{vbr}" width="{width}" height="{height}">\n'
        '        <BaseURL>{vurl}</BaseURL>\n'
        '      </Representation>\n'
        '    </AdaptationSet>\n'
        '    <AdaptationSet id="2" contentType="audio" mimeType="{amime}"\n'
        '                   codecs="{acodec}"\n'
        '                   subsegmentAlignment="true" subsegmentStartsWithSAP="1">\n'
        '      <Representation id="a1" bandwidth="{abr}" audioSamplingRate="{asr}">\n'
        '        <BaseURL>{aurl}</BaseURL>\n'
        '      </Representation>\n'
        '    </AdaptationSet>\n'
        '  </Period>\n'
        '</MPD>'
    ).format(
        pt_dur=pt_dur,
        vmime=vmime, vcodec=vcodec, fps=fps, vbr=vbr, width=width, height=height,
        vurl=_xe(video_url),
        amime=amime, acodec=acodec, abr=abr, asr=asr,
        aurl=_xe(audio_url),
    )


def resolve(url: str) -> dict:
    """
    Rezolvă url-ul local cu yt-dlp (script.module.yt-dlp).
    Aruncă excepție dacă rezolvarea eșuează.
    """
    import yt_dlp

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "format": _FORMAT,
        "noplaylist": True,
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    headers = dict(info.get("http_headers") or {})

    requested = info.get("requested_formats") or []
    if len(requested) >= 2:
        video = next(
            (f for f in requested
             if f.get("vcodec") not in (None, "none") and f.get("acodec") in (None, "none")),
            None,
        )
        audio = next(
            (f for f in requested
             if f.get("acodec") not in (None, "none") and f.get("vcodec") in (None, "none")),
            None,
        )
        if video and audio:
            video_meta = {
                "codec":   video.get("vcodec") or "",
                "width":   video.get("width") or 0,
                "height":  video.get("height") or 0,
                "fps":     video.get("fps") or 25,
                "bitrate": int((video.get("tbr") or 0) * 1000),
                "ext":     video.get("ext") or "mp4",
            }
            audio_meta = {
                "codec":   audio.get("acodec") or "",
                "bitrate": int((audio.get("tbr") or 0) * 1000),
                "ext":     audio.get("ext") or "m4a",
                "asr":     audio.get("asr") or 44100,
            }
            mpd = _build_mpd(
                video["url"], audio["url"],
                video_meta, audio_meta,
                info.get("duration") or 0,
            )
            return {"url": None, "mpd": mpd, "headers": headers}

    stream_url = info.get("url") or ""
    if not stream_url and info.get("formats"):
        stream_url = info["formats"][-1].get("url", "")

    if not stream_url:
        raise RuntimeError("yt-dlp local: niciun URL găsit pentru %s" % url)

    return {"url": stream_url, "headers": headers}
