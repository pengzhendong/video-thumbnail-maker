# Copyright (c) 2023, Zhendong Peng (pzd17@tsinghua.org.cn)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import os
from pathlib import Path
import random

import av
from PIL import Image, ImageFont, ImageDraw, ImageEnhance
from tqdm import tqdm
import yaml


def get_metadata(filename, container, comment):
    duration = container.duration // 1000000
    video = container.streams.video[0]
    video_codec = video.codec_context.codec.name.upper()
    video_profile = video.codec_context.profile
    video_bit_rate = video.bit_rate // 1000
    video_frame = float(video.average_rate)
    audio = container.streams.audio[0]
    audio_codec = audio.codec_context.codec.name.upper()
    audio_profile = audio.codec_context.profile
    audio_bit_rate = audio.bit_rate // 1000
    audio_lang = audio.metadata.get("language", "und").title()
    return {
        "File Name": f": {os.path.basename(filename)}",
        "File Size": f": {container.size / 1024 / 1024:.2f} MB",
        "Resolution":
        f": {video.width}x{video.height} / {video_frame:.2f} fps",
        "Duration":
        f": {duration // 3600:02}:{duration % 3600 // 60:02}:{duration % 60:02}",
        "Video":
        f": {video_codec} ({video_profile}) :: {video_bit_rate} kb/s, {video_frame:.2f} fps",
        "Audio":
        f": {audio_codec} ({audio_profile}) :: {audio_bit_rate} kbps, {audio.rate} Hz, {audio.channels} channels :: {audio_lang}",
        "Comment": f": {comment}",
    }


def get_textbox_size(text, font):
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    left, top, right, bottom = draw.textbbox((10, 10), text, font=font)
    width = right - left + 15
    height = bottom - top + 30
    return width, height


def draw_logo(image, config, width):
    logo = Image.open(config["path"]).convert("RGBA")
    logo = logo.resize((width, int(logo.size[1] / logo.size[0] * width)))
    alpha = logo.split()[-1]
    alpha = ImageEnhance.Brightness(alpha).enhance(config["transparency"])
    logo.putalpha(alpha)
    image.paste(logo, box=(image.size[0] - logo.size[0], 0), mask=logo)


def create_thumbnail(filename, config, output_folder):
    container = av.open(filename)
    metadata = get_metadata(filename, container, config["comment"])
    font = ImageFont.truetype(config["font"], size=config["font_size"])

    text = "\n".join(metadata.keys())
    textbox_width, textbox_height = get_textbox_size(text, font)

    row = config["matrix"]["row"]
    col = config["matrix"]["col"]
    padding = config["matrix"]["padding"]
    background_color = config["background_color"]
    block_width = config["matrix"]["block_width"]
    video = container.streams.video[0]
    block_height = int(block_width / video.width * video.height)
    width = (block_width + padding) * col + padding
    height = textbox_height + (block_height + padding) * row
    img = Image.new("RGB", (width, height), background_color)

    text_color = config["text_color"]
    ImageDraw.Draw(img).text((10, 10), text, text_color, font=font)
    text = "\n".join(list(metadata.values()))
    ImageDraw.Draw(img).text((textbox_width, 10), text, text_color, font=font)
    draw_logo(img, config["logo"], int(block_width / 4))

    if not config["shuffle"]:
        random.seed(23)
    frames = sorted(random.sample(range(723, video.frames - 723), row * col))
    for idx, frame in enumerate(frames):
        container.seek(int(frame / video.average_rate) * 1000000)
        screenshot = next(container.decode(video=0)).to_image()
        x = padding + (padding + block_width) * (idx % col)
        y = textbox_height + (padding + block_height) * (idx // col)
        screenshot = screenshot.resize((block_width, block_height),
                                       resample=Image.BILINEAR)
        img.paste(screenshot, box=(x, y))
        yield (idx + 1) / (row * col)
    img.save(f"{output_folder}/{Path(filename).stem}.png")


def main():
    parser = argparse.ArgumentParser(
        description="Make thumbnails (caps, previews) of video file.")
    parser.add_argument("--video", required=True, help="video file")
    parser.add_argument("--config",
                        default="config.yml",
                        help="config yaml file")
    parser.add_argument("--output_folder",
                        default=".",
                        help="thumbnail output folder")
    args = parser.parse_args()

    config = yaml.safe_load(open(args.config, encoding="utf-8"))
    with tqdm(total=100) as pbar:
        for progress in create_thumbnail(args.video, config,
                                         args.output_folder):
            pbar.update(int(progress * 100) - pbar.n)


if __name__ == "__main__":
    main()
