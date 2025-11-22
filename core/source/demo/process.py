import json
import os
import subprocess

from PIL import Image
from django.conf import settings

from core.models import Task


def execute(task: Task):
    task.logging(f"{__name__}", "execute")

    dir = task.context.get("tmp_dir")
    preview_audio = ""

    with open(f"{dir}/audio.json", "r") as f:
        try:
            audio = json.load(f)
        except:
            with open(f"{dir}/audio.json", "rb") as fb:
                audio_data = fb.read()
                audio = json.loads(audio_data.decode('cp1251'))

    task.set_context({"optimized_cover": optimize_image_field(f"{dir}/cover.png")})

    topic_pos = 0
    preview_audio_found = False

    for topic in audio:
        if len(topic["file_name"]) > 0:
            topic["file_name_hls"] = process_audio_file(f"{dir}/audio/{topic['file_name']}")
            # preview track check
            if not preview_audio_found:
                preview_audio = topic["file_name_hls"]
                preview_audio_found = True

        topic_pos += 1

        subtopic_pos = 0
        for subtopic in topic["subtracks"]:
            for i in subtopic:
                if len(i["file_name"]) > 0:
                    i["file_name_hls"] = process_audio_file(f"{dir}/audio/{i['file_name']}")

                subtopic_pos += 1

    task.set_context({"audio": audio})
    task.set_context({"preview_audio": preview_audio})


def get_proportional_height(width, initial_size):
    initial_width = initial_size[0]
    initial_height = initial_size[1]
    koeff = float(initial_width/initial_height)
    return int(width/koeff)


def optimize_image_field(image_file):
    img = Image.open(image_file)

    if img.width > settings.COVER_WIDTH:
        img = img.resize((settings.COVER_WIDTH,
                          get_proportional_height(settings.COVER_WIDTH, img.size)),
                          Image.LANCZOS)

    file_name = image_file.split('/')[-1]
    ext = file_name.split('.')[-1]

    if ext == "png":
        img = img.convert('RGB')

    file_dir = "/".join(image_file.split('/')[:-1])
    optimized_file_name = os.path.join(file_dir, "optimized_cover.jpg")
    img.save(optimized_file_name, optimize=True, quality=95)

    return optimized_file_name


def process_audio_file(audio_file):
    dest_dir = os.path.dirname(audio_file)
    file_name = audio_file.split("/")[-1].split(".")[0]
    file_name_m3u8 = f"{dest_dir}/{file_name}.m3u8"
    cmd = f"ffmpeg -y -i {audio_file} -c:a libmp3lame -q:a 0 -map 0:0 -f segment -segment_time 10 -segment_list {file_name_m3u8} -segment_format mpegts {dest_dir}/{file_name}_chunk%03d.ts"
    subprocess.check_output(cmd.split(' '))
    return file_name_m3u8
