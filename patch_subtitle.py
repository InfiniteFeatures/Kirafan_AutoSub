# -*- coding: utf-8 -*-
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import cv2
import codecs
import subprocess
import os
import glob
import sys
import optparse
import re


def patch_subtitle():
    try:
        sys.setdefaultencoding('utf-8')
    except:
        pass

    python_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    currPath = sys.path[0]
    highPath = os.path.split(currPath)[0]
    env = os.environ.copy()
    spliter = ';' if os.name == 'nt' else ':'
    env["PATH"] = python_dir + spliter + highPath + spliter + env["PATH"]

    # Load Font
    fontDir = python_dir
    jpfontf = python_dir + "/jpfont.ttf"
    if (not os.path.isfile(jpfontf)):
        jpfontf = python_dir + "/usr/jpfont.ttf"
        fontDir = python_dir + "/usr"
    if (not os.path.isfile(jpfontf)):
        jpfontf = highPath + "/usr/jpfont.ttf"
        fontDir = highPath + "/usr"
    if (not os.path.isfile(jpfontf)):
        raise Exception("Can not find font")

    # Load Nmtg Black
    nmtg_blank_f = python_dir + "/usr/nmtg.png"
    if (not os.path.isfile(nmtg_blank_f)):
        nmtg_blank_f = highPath + "/usr/nmtg.png"
    nmtg_blank_ex_f = python_dir + "/usr/nmtgex.png"
    if (not os.path.isfile(nmtg_blank_ex_f)):
        nmtg_blank_ex_f = highPath + "/usr/nmtgex.png"

    parser = optparse.OptionParser()
    parser.add_option('--gray_threshold',
                      action="store", dest="gray_threshold",
                      help="gray_threshold of binarization", default=160)
    parser.add_option('--blank_extra_pre',
                      action="store", dest="blank_pre",
                      help="inpaint blank before textarea completely reach its position", default=3)
    parser.add_option('--nmtg_extra_pre',
                      action="store", dest="nmtg_pre",
                      help="inpaint nmtg before textarea completely reach its position", default=0)
    parser.add_option('--blank_extra_sub',
                      action="store", dest="blank_sub",
                      help="inpaint blank after textarea start to disappear", default=0)
    parser.add_option('--typed_speed',
                      action="store", dest="typed_speed",
                      help="typed effect(text rolling) speed, char per s", default=3)
    parser.add_option('--fontsize',
                      action="store", dest="fontsize",
                      help="font size of translated text", default=35)
    parser.add_option('--fontsize_title',
                      action="store", dest="fontsize_title",
                      help="fontsize of title", default=64)
    parser.add_option('--colorR',
                      action="store", dest="colorR",
                      help="color red", default=255)
    parser.add_option('--colorG',
                      action="store", dest="colorG",
                      help="color green", default=236)
    parser.add_option('--colorB',
                      action="store", dest="colorB",
                      help="color blue", default=211)
    parser.add_option('--positionY',
                      action="store", dest="positionY",
                      help="title position in Y axis", default=480)
    parser.add_option('--fontsize_nmtg',
                      action="store", dest="fontsize_nmtg",
                      help="font size of translated name tag", default=33)
    parser.add_option('--audio_bitrate',
                      action="store", dest="audio_bitrate",
                      help="ffmpeg acodec -ar", default="256k")
    parser.add_option('--overlap',
                      action="store_true", dest="overlap",
                      help="overlap text on japanese, for debugging")

    options, args = parser.parse_args()
    if (not len(args)):
        raise Exception("Missing input video.")
    arg0 = os.path.abspath(args[0])

    inputvideos = []
    single_file = True
    if (os.path.isfile(arg0)):
        if (arg0[-4:] == '.mp4'):
            inputvideos = [arg0]
    else:
        inputvideos = [arg0 + '/' + f for f in os.listdir(
            arg0) if re.search(r'^.*\d+\.mp4$', f)]
        print(inputvideos)
        if (len(inputvideos) == 0):
            raise Exception("Can not open " + arg0)
        outputfile = arg0 + '/videolist.txt'
        single_file = False
        ofp = open(outputfile, mode='w')

    inputvideos.sort()
    num_videos = len(inputvideos)
    video_index = 0
    for inputvideo in inputvideos:
        video_index += 1
        print("Progress: " + ("%04d" % video_index) +
              " / " + ("%04d" % num_videos))

        # output dir
        basename = os.path.basename(inputvideo)
        dirname = os.path.dirname(inputvideo)

        script_dir = dirname + ('/' if dirname else '') + 'autosub'
        script_fn = script_dir + '/' + basename + '.krfss'
        print("  Reading script file: " + script_fn)
        if (not os.path.isfile(script_fn)):
            raise Exception("Can not open script file " + script_fn)

        frame_cmds = {}
        frame_subindex = {}
        frame_haveblank = {}
        frame_havenmtg = {}
        frame_nmtgtransition = {}
        frame_index_temp = 0
        frame_index_temp1 = 0

        # read script
        import json
        with open(script_fn, mode='r', encoding='utf-8') as fp:
            text = fp.read()
            if (text[0].encode('utf-8') == codecs.BOM_UTF8):
                text = text[1:]
            script = json.loads(text)

        # read language
        fontf = python_dir + "/font.ttf"
        if (os.path.isfile(fontf)):
            pass
        elif script["lang"] == 'cn':
            fontf = fontDir + '/cnfont.ttf'
        elif script["lang"] == 'jp':
            fontf = fontDir + '/jpfont.ttf'
        elif script["lang"] == 'en':
            fontf = fontDir + '/enfont.ttf'
        elif script["lang"] == 'ko':
            fontf = fontDir + '/kofont.ttf'
        else:
            fontf = fontDir + '/jpfont.ttf'

        for command in script["timestamp"]:
            last_frame = 0
            frame = int(command["at"])
            action = command["action"]
            if (action == 'S' or action == 'E' or action == 'C'):
                frame_cmds[frame] = action
            if (action == 'S'):
                subindex = int(command["sub"])
                frame_subindex[frame] = subindex
            if (action == 'T'):
                for i in range(frame_index_temp, frame - int(options.blank_pre)):
                    frame_haveblank[i] = False
                frame_index_temp = frame - int(options.blank_pre)
                for i in range(frame_index_temp1, frame - int(options.nmtg_pre)):
                    frame_havenmtg[i] = False
                frame_index_temp1 = frame - int(options.nmtg_pre)
            if (action == 'X'):
                for i in range(frame_index_temp, frame + int(options.blank_sub)):
                    frame_haveblank[i] = True
                frame_index_temp = frame + int(options.blank_sub)
                for i in range(frame_index_temp1, frame):
                    frame_havenmtg[i] = True
                frame_index_temp1 = frame
            if (action == 'O'):
                for i in range(frame_index_temp, frame + 1):
                    frame_haveblank[i] = False
                frame_index_temp = frame
                for i in range(frame_index_temp1, frame + 1):
                    frame_havenmtg[i] = False
                frame_index_temp1 = frame
                last_frame = frame
            if (action == 'N'):
                nmtg_y = int(command["y"])
                nmtg_x = int(command["ex"])
                frame_nmtgtransition[frame] = (nmtg_y, nmtg_x)

        # print(script["trans"])
        # print(script["nmtgs"])

        # POSITION DEFINITION
        W = 1280
        ROI = (slice(500, 710), slice(70, 1140))
        ROI_NMTG_X0 = 15
        ROI_NMTG_Y0 = 7
        ROI_NMTG = (slice(ROI_NMTG_Y0, 50), slice(ROI_NMTG_X0, 395))
        NM_NMTG_X_CENTER = 189
        NM_NMTG_Y_CENTER = 22
        LINE_START = 169
        LINE_LENGTH = 800
        LINE_HEIGHT = 36
        ROI_LINE0_Y = 84
        ROI_LINE1_Y = 136
        ROI_LINE0_Y_CENTER = ROI_LINE0_Y + LINE_HEIGHT / 2
        ROI_LINE1_Y_CENTER = ROI_LINE1_Y + LINE_HEIGHT / 2
        ROI_LINE0 = (slice(ROI_LINE0_Y, ROI_LINE0_Y + LINE_HEIGHT),
                     slice(LINE_START, LINE_START + LINE_LENGTH))
        ROI_LINE1 = (slice(ROI_LINE1_Y, ROI_LINE1_Y + LINE_HEIGHT),
                     slice(LINE_START, LINE_START + LINE_LENGTH))
        ROI_LINE0_Y_CENTER_3LINES = 72 + LINE_HEIGHT / 2
        ROI_LINE1_Y_CENTER_3LINES = 110 + LINE_HEIGHT / 2
        ROI_LINE2_Y_CENTER_3LINES = 148 + LINE_HEIGHT / 2
        ROI_LINE_Y_CENTER_3LINES_MAP = [
            ROI_LINE0_Y_CENTER_3LINES, ROI_LINE1_Y_CENTER_3LINES, ROI_LINE2_Y_CENTER_3LINES]

        # COLOR
        TEXT_COLOR = (60, 66, 111)
        BOLD_COLOR = (0x8e, 0x66, 0xea)
        NMTG_COLOR = (255, 255, 255)

        video = cv2.VideoCapture(inputvideo)
        fps = video.get(cv2.CAP_PROP_FPS)
        # Iphone's video is rotated
        width = max(video.get(cv2.CAP_PROP_FRAME_HEIGHT),
                    video.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = min(video.get(cv2.CAP_PROP_FRAME_HEIGHT),
                     video.get(cv2.CAP_PROP_FRAME_WIDTH))
        # temp output without audio track
        out_name = "auto_sub_temp_file.m4v"
        fourcc = cv2.VideoWriter_fourcc('m', 'p', '4', 'v')
        out_video = cv2.VideoWriter(out_name, int(
            fourcc), fps, (int(width), int(height)))

        frame = 0
        font_text = ImageFont.truetype(fontf, int(options.fontsize))
        font_nmtg = ImageFont.truetype(fontf, int(options.fontsize_nmtg))
        font_title = ImageFont.truetype(fontf, int(options.fontsize_title))
        font_size_max = 1 * max(int(options.fontsize),
                                int(options.fontsize_nmtg)) + 20
        img_draw_temp = Image.new("RGB", (font_size_max * 20, font_size_max))
        draw_temp = ImageDraw.Draw(img_draw_temp)
        font_w_text, font_h_text = draw_temp.textsize(
            "LIPFgYTjyXSq|^#%", font=font_text)
        font_w_nmtg, font_h_nmtg = draw_temp.textsize(
            "LIPFgYTjyXSq|^#%", font=font_nmtg)
        img_nmtg_blank = cv2.imread(nmtg_blank_f)
        img_nmtg_blank_ex = cv2.imread(nmtg_blank_ex_f)

        # static string
        str_todraw = ''
        # a 'typed' effect
        str_typed_cache = ''
        str_typed_render = ''
        last_typed_start = 0
        index_sub = -1
        while(video.isOpened()):
            ret, img = video.read()
            if not ret:
                break
            time = frame / fps
            frame += 1

            # Iphone's video is rotated
            if (video.get(cv2.CAP_PROP_FRAME_HEIGHT) > video.get(cv2.CAP_PROP_FRAME_WIDTH)):
                img_rot = np.rot90(img)
            else:
                img_rot = img
            # ROI of TextArea and NameTag
            img_crop = img_rot[ROI]

            if (frame in frame_cmds):
                cmd = frame_cmds[frame]
                if (cmd == 'C'):
                    str_todraw = ''
                    #print(frame, "C")
                if (cmd == 'S'):
                    last_typed_start = frame
                    index_sub = frame_subindex[frame]
                    str_typed_cache = script["trans"][index_sub]
                    #print(frame, "S")
                    # print(str_typed_cache)
                if (cmd == 'E'):
                    str_todraw += str_typed_cache
                    str_typed_cache = ''
                    #print(frame, "E")
                    # print(str_todraw)

            is_blank = frame_haveblank[frame]
            is_nmtg = frame_havenmtg[frame]

            if (is_blank and not options.overlap):
                # binarization
                img_gray = cv2.cvtColor(img_crop, cv2.COLOR_BGR2GRAY)
                retval, img_bin = cv2.threshold(img_gray, int(
                    options.gray_threshold), 255, cv2.THRESH_BINARY)
                img_mask = cv2.bitwise_not(img_bin)
                img_mask[:ROI_LINE0_Y, :] = 0
                img_mask[ROI_LINE1_Y + LINE_HEIGHT:, :] = 0
                img_mask[:, :LINE_START] = 0
                img_mask[:, LINE_START + LINE_LENGTH:] = 0
                neiborhood8 = np.array([[1, 1, 1],
                                        [1, 1, 1],
                                        [1, 1, 1]],
                                       np.uint8)
                img_mask = cv2.dilate(img_mask, neiborhood8, iterations=2)
                # Inpaint to repair?
                img_inpaint = cv2.inpaint(
                    img_crop, img_mask, 3, cv2.INPAINT_TELEA)
            else:
                img_inpaint = img_crop

            nmtg_index = script["nmtg_map"][index_sub]
            nmtg = script["nmtgs"][nmtg_index]
            nmtg_x = script["nmtg_ex"][nmtg_index]
            if (is_nmtg and len(nmtg) and not options.overlap):
                img_inpaint[ROI_NMTG] = img_nmtg_blank
                for nmtg_ex_i in range(nmtg_x):
                    ROI_TEMP = (slice(ROI_NMTG_Y0, 50),
                                slice(395 + nmtg_ex_i, 395 + nmtg_ex_i + 1))
                    img_inpaint[ROI_TEMP] = img_nmtg_blank_ex

            if (frame in frame_nmtgtransition):
                nmtg_y, nmtg_x = frame_nmtgtransition[frame]
                img_inpaint[(slice(ROI_NMTG_Y0 + nmtg_y, 50 + nmtg_y),
                             slice(ROI_NMTG_X0, 395))] = img_nmtg_blank
                for nmtg_ex_i in range(nmtg_x):
                    ROI_TEMP = (slice(ROI_NMTG_Y0 + nmtg_y, 50 + nmtg_y),
                                slice(395 + nmtg_ex_i, 395 + nmtg_ex_i + 1))
                    img_inpaint[ROI_TEMP] = img_nmtg_blank_ex

            if (is_blank):
                img_pil = Image.fromarray(img_inpaint)
                draw = ImageDraw.Draw(img_pil)
                str_typed_render = str_typed_cache[:min(len(str_typed_cache), int(
                    float(options.typed_speed) * (frame - last_typed_start + 1)))]
                str_splited = (str_todraw + str_typed_render).split('\n')
                num_of_lines = len(str_splited)
                for (lineindex, text_line) in enumerate(str_splited):
                    draw_x = LINE_START
                    draw_y0 = ROI_LINE1_Y_CENTER if (
                        lineindex > 0) else ROI_LINE0_Y_CENTER
                    if (num_of_lines == 3):
                        draw_y0 = ROI_LINE_Y_CENTER_3LINES_MAP[lineindex]
                    for (spanindex, text_span) in enumerate(text_line.split('$')):
                        color = TEXT_COLOR if (
                            spanindex % 2 == 0) else BOLD_COLOR
                        span_w, span_h = draw.textsize(
                            text_span, font=font_text)
                        draw_y = draw_y0 - font_h_text / 2
                        draw.text((draw_x, draw_y), text_span,
                                  fill=color, font=font_text)
                        draw_x += span_w

            if (is_nmtg and len(nmtg)):
                (shape_h, shape_w) = img_nmtg_blank.shape[:2]
                shape_w = shape_w + nmtg_x
                img_draw_nmtg = Image.new("RGB", (shape_h, shape_w))
                draw_nmtg = ImageDraw.Draw(img_draw_nmtg)
                w_nmtg, h_nmtg = draw.textsize(nmtg, font=font_nmtg)
                draw.text(
                    (ROI_NMTG_X0 + NM_NMTG_X_CENTER - w_nmtg / 2 + nmtg_x / 2,
                     ROI_NMTG_Y0 + NM_NMTG_Y_CENTER - font_h_nmtg / 2),
                    nmtg, fill=NMTG_COLOR, font=font_nmtg
                )

            if (is_blank):
                img_drawed = np.array(img_pil)
                img_rot[ROI] = img_drawed

            # Print Title
            def mytext(draw, pos, text, font, fill, border='black', bp=2):
                x, y = pos
                shadowcolor = border
                draw.text((x-bp, y), text, font=font, fill=shadowcolor)
                draw.text((x+bp, y), text, font=font, fill=shadowcolor)
                draw.text((x, y-bp), text, font=font, fill=shadowcolor)
                draw.text((x, y+bp), text, font=font, fill=shadowcolor)
                # thicker border
                draw.text((x-bp, y-bp), text, font=font, fill=shadowcolor)
                draw.text((x+bp, y-bp), text, font=font, fill=shadowcolor)
                draw.text((x-bp, y+bp), text, font=font, fill=shadowcolor)
                draw.text((x+bp, y+bp), text, font=font, fill=shadowcolor)
                # now draw the text over it
                draw.text((x, y), text, font=font, fill=fill)

            TITLE_DISAPPEAR = 55
            TITLE_OUT = 45
            if (frame < TITLE_DISAPPEAR and ("title" in script) and len(script["title"])):
                title = script["title"].replace('\\n', '\n')
                Img_rot = Image.fromarray(img_rot)
                draw = ImageDraw.Draw(Img_rot)
                w, h = draw.textsize(title, font=font_title)
                mytext(draw, ((W-w)/2, int(options.positionY) - h/2), title, font=font_title,
                       fill=(int(options.colorB), int(options.colorG), int(options.colorR)))

                if (frame < TITLE_OUT and False):
                    img_merged = np.array(Img_rot)
                else:
                    alpha = (frame - TITLE_OUT) / (TITLE_DISAPPEAR - TITLE_OUT)
                    img_drawed = np.array(Img_rot)
                    img_merged = cv2.addWeighted(
                        img_drawed, 1 - alpha, img_rot, alpha, 0)
            else:
                img_merged = img_rot

            cv2.imshow("img_merged", img_merged)
            cv2.waitKey(1)
            out_video.write(img_merged)

            progress = int(frame / last_frame * 100)
            prog_char = int(progress / 4)
            print("  >" + "*" * prog_char +
                  "." * (25 - prog_char) + ("%03d" % progress) + "%",
                  end='\r')

        video.release()
        out_video.release()
        cv2.destroyAllWindows()
        print("\n")

        ffcmd = 'ffmpeg -y -hide_banner -loglevel error -vn -i "' + inputvideo + '"' + \
            " -acodec copy " + 'autosubed_tmp.aac'
        print("  Invoking " + ffcmd)
        subprocess.call(ffcmd, shell=True, env=env)
        ffcmd = 'ffmpeg -y -hide_banner -loglevel error -vn -i "' + out_name + '"' + \
            " -i " + 'autosubed_tmp.aac' + " -bsf:a aac_adtstoasc" \
            " -codec copy " + '"' + inputvideo + ".autosubed.mp4" + '"'
        print("  Invoking " + ffcmd)
        subprocess.call(ffcmd, shell=True, env=env)

        if not single_file:
            ofp.write("file " + "'" + os.path.basename(inputvideo) +
                      ".autosubed.mp4" + "'" + '\n')

        os.remove(out_name)
        os.remove('autosubed_tmp.aac')

    if not single_file:
        ofp.close()


if __name__ == '__main__':
    patch_subtitle()
