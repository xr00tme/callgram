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

        res_limit = min(video_parameters.width, video_parameters.height) if video_parameters else 360

        user_agent = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
    
        cookies_path = "/root/cookies/youtube/cookies.txt"
    
        commands = [
            'yt-dlp',
            '-g',
            '-f', "bestvideo[vcodec~='(vp09|avc1)']+m4a/bestaudio[ext=m4a]/bestaudio/best",
            '-S', f'res:{res_limit}',
            '--no-warnings',
            '--no-check-certificate',
            '--socket-timeout', '15',
            '--retries', '3',
            '--user-agent', user_agent,
            '--cookies', cookies_path,
            '--geo-bypass',
            '--geo-bypass-country', 'ID',
            '--remote-components', 'ejs:github',
            '--extractor-args', 'youtube:skip=dash,hls;youtubetab:skip=authcheck',
            '--limit-rate', '5M'
        ]

        if add_commands:
            try:
                additional_args = shlex.split(add_commands)
                skip_next = False
                for arg in additional_args:
                    if skip_next:
                        skip_next = False
                        continue
                    if arg in ["--cookies", "-f", "-g", "--no-warnings"]:
                        skip_next = True
                        continue
                    if arg not in commands:
                        commands.append(arg)
            except Exception:
                pass

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
                    timeout=35,
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
