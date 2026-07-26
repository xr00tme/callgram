import asyncio
import logging
import re
import shlex
import subprocess
from typing import Optional, Tuple

from .exceptions import YtDlpError
from .ffmpeg import cleanup_commands
from .types.raw import VideoParameters

py_logger = logging.getLogger("pytgcalls")


class YtDlp:
    YOUTUBE_REGX = re.compile(
        r"^((?:https?:)?//)?((?:www|m)\.)?"
        r"(youtube(-nocookie)?\.com|youtu.be)"
        r"(/(?:[\w\-]+\?v=|embed/|live/|v/)?)"
        r"([\w\-]+)(\S+)?$",
    )

    @staticmethod
    def is_valid(link: str) -> bool:
        return bool(YtDlp.YOUTUBE_REGX.match(link))

    @staticmethod
    async def extract(
        link: Optional[str],
        video_parameters: VideoParameters,
        add_commands: Optional[str],
    ) -> Tuple[Optional[str], Optional[str]]:
        if not link:
            return None, None

        commands = [
            "yt-dlp",
            "-g",
            "-f",
            "bestvideo[vcodec~='(vp09|avc1)']+m4a/best",
            "-S",
            f"res:{min(video_parameters.width, video_parameters.height)}",
            "--no-warnings",
            "--cookies",
            "/root/cookies/youtube/cookies.txt",
            "--geo-bypass",
            "--geo-bypass-country",
            "ID",
            "--no-check-certificate",
        ]

        if add_commands:
            commands += await cleanup_commands(
                shlex.split(add_commands),
                "yt-dlp",
                [
                    "-f",
                    "-g",
                    "--no-warnings",
                    "--cookies",
                ],
            )

        commands.append(link)

        py_logger.debug(f'Running yt-dlp: {" ".join(commands)}')

        loop = asyncio.get_running_loop()
        try:
            proc_res = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    commands,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=30,
                ),
            )

            if proc_res.returncode != 0:
                raise YtDlpError(proc_res.stderr.strip())

            data = proc_res.stdout.strip().split("\n")

            if not data:
                raise YtDlpError("No stream URLs found")

            video_url = data[0]
            audio_url = data[1] if len(data) > 1 else data[0]

            return video_url, audio_url

        except FileNotFoundError:
            raise YtDlpError("yt-dlp is not installed")
        except subprocess.TimeoutExpired:
            raise YtDlpError("yt-dlp timeout")
