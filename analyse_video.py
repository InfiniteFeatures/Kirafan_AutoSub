# -*- coding: utf-8 -*-
import numpy as np
import cv2
import subprocess
import os
import glob
import sys
import re
import optparse


def analyse_video():
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

    pattern0_f = python_dir + "/usr/pattern0.png"
    if (not os.path.isfile(pattern0_f)):
        pattern0_f = highPath + "/usr/pattern0.png"
    if (not os.path.isfile(pattern0_f)):
        print("Can not load nmtg pattern0" + pattern0_f)
    img_pattern0 = cv2.imread(pattern0_f)

    pattern1_f = python_dir + "/usr/pattern1.png"
    if (not os.path.isfile(pattern1_f)):
        pattern1_f = highPath + "/usr/pattern1.png"
    if (not os.path.isfile(pattern1_f)):
        print("Can not load nmtg pattern1" + pattern1_f)
    img_pattern1 = cv2.imread(pattern1_f)

    def imwrite(filename, img, params=None):
        try:
            ext = os.path.splitext(filename)[1]
            result, n = cv2.imencode(ext, img, params)
            if result:
                with open(filename, mode='w+b') as f:
                    n.tofile(f)
                return True
            else:
                return False
        except Exception as e:
            print(e)
            return False

    # Parse options
    parser = optparse.OptionParser()
    parser.add_option('--gray_threshold',
                      action="store", dest="gray_threshold",
                      help="gray_threshold of binarization", default=160)
    parser.add_option('--textpos_threshold',
                      action="store", dest="textpos_threshold",
                      help="text position detection threshold", default=5)
    parser.add_option('--wait_frame_threshold',
                      action="store", dest="wait_frame_threshold",
                      help="text pause detection threshold in frame", default=2)
    parser.add_option('--nmtg_tm_threshold',
                      action="store", dest="nmtg_tm_threshold",
                      help="nmtg box template matching threshold", default=0.12)
    parser.add_option('--nmtg_extra_length_threshold',
                      action="store", dest="nmtg_extra_length_threshold",
                      help="nmtg box template extra_length threshold", default=4)

    options, args = parser.parse_args()
    if (not len(args)):
        print("Missing input video.")
        input()
        exit(-1)
    arg0 = os.path.abspath(args[0])
    inputvideos = []
    if (os.path.isfile(arg0)):
        if (arg0[-4:] == '.mp4'):
            inputvideos = [arg0]
    else:
        inputvideos = [arg0 + '/' + f for f in os.listdir(
            arg0) if re.search(r'^.*\d+\.mp4$', f)]
        print(inputvideos)
        if (len(inputvideos) == 0):
            raise Exception("Can not open " + arg0)

    # Ask Language
    currentlang = "cn"
    lang_config_f = python_dir + '/lang.config'
    if (os.path.isfile(lang_config_f)):
        with open(lang_config_f, mode='r', encoding='utf-8') as fp:
            currentlang = fp.read()
        print("lang.config exists using " +
              currentlang + " as target language")
    else:
        print("PLEASE SPECIFY YOUR TARGET LANGUAGE!")
        print("FROM THE FOLLOWING LIST")
        print("For Chinese,  input cn")
        print("For English,  input en")
        print("For Korean,   input ko")
        print("For Japanese, input jp")
        print("For Others,   keep empty")
        currentlang = input("input >")
        with open(lang_config_f, mode='w', encoding='utf-8') as fp:
            fp.write(currentlang)

    inputvideos.sort()
    num_videos = len(inputvideos)
    video_index = 0
    for inputvideo in inputvideos:
        video_index += 1
        print("Progress: " + ("%04d" % video_index) +
              " / " + ("%04d" % num_videos))

        # output dir
        print("  Inputvideo: " + inputvideo)
        basename = os.path.basename(inputvideo)
        dirname = os.path.dirname(inputvideo)
        output_dir = dirname + ('/' if dirname else '') + 'autosub'

        script_output = output_dir + '/' + basename + '.krfss'
        img_output_dir = output_dir + '/' + basename + '_img'
        print("  Script output: " + script_output)
        print("  Image output directory: " + img_output_dir)

        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(img_output_dir, exist_ok=True)

        # timestamp array
        timestamp_data = []
        # nmtg_db (array of image)
        g_nmtg_img_db = []
        g_nmtg_ex_db = []
        # raw_nmtg_index -> db_index
        nmtg_map = []

        # COLOR DEFINITION
        BLANK_COLOR_MAX = (250, 256, 256)
        BLANK_COLOR_MIN = (190, 190, 210)

        # blank color of textarea?

        def is_blank_p(p):
            return \
                (BLANK_COLOR_MAX[0] > p[0] > BLANK_COLOR_MIN[0]) and \
                (BLANK_COLOR_MAX[1] > p[1] > BLANK_COLOR_MIN[1]) and \
                (BLANK_COLOR_MAX[2] > p[2] > BLANK_COLOR_MIN[2])

        def is_blank_func(im0, im1):
            i0 = np.asarray(im0)
            i1 = np.asarray(im1)
            for ln in i0:
                for p in ln:
                    if not is_blank_p(p):
                        return False
            for ln in i1:
                for p in ln:
                    if not is_blank_p(p):
                        return False
            return True

        # judge if two nmtg_img are same

        def is_same_name(img0, img1):
            (h, w0) = img0.shape
            (h, w1) = img1.shape
            if (abs(w1 - w0) > int(options.nmtg_extra_length_threshold)):
                return False
            if (not w1 == w0):
                if (w1 > w0):
                    img1 = img1[:, 0:w0]
                if (w1 < w0):
                    img0 = img0[:, 0:w1]
            kernel = np.ones((3, 3), np.uint8)
            img0_dil_inv = cv2.bitwise_not(
                cv2.dilate(img0, kernel, iterations=1))
            img1_dil_inv = cv2.bitwise_not(
                cv2.dilate(img1, kernel, iterations=1))
            img_judge0 = cv2.bitwise_and(img0, img1_dil_inv)
            img_judge1 = cv2.bitwise_and(img1, img0_dil_inv)
            return 0 == np.sum(img_judge0) + np.sum(img_judge1)

        # get_index in nmtg db
        # if no same name in the db
        # then append

        def get_nmtg_index(img1, ex):
            for (i, img0) in enumerate(g_nmtg_img_db):
                if is_same_name(img0, img1):
                    return i
            g_nmtg_img_db.append(img1.copy())
            g_nmtg_ex_db.append(ex)
            i = len(g_nmtg_img_db) - 1
            imwrite(img_output_dir + '/' + "/nmtg_" +
                    ("%04d" % i)+".png", img1)
            return i

        # POSITION DEFINITION
        ROI = (slice(500, 710), slice(70, 1140))
        ROI_JUDGE0 = (slice(70, 72), slice(130, 1000))
        ROI_JUDGE1 = (slice(178, 180), slice(130, 1000))
        ROI_NMTG_SEARCH = (slice(0, 140), slice(13, 13 + 382))
        LINE_START = 169
        LINE_LENGTH = 800
        LINE_HEIGHT = 36
        ROI_LINE0_Y = 84
        ROI_LINE1_Y = 136
        ROI_LINE0 = (slice(ROI_LINE0_Y, ROI_LINE0_Y + LINE_HEIGHT),
                     slice(LINE_START, LINE_START + LINE_LENGTH))
        ROI_LINE1 = (slice(ROI_LINE1_Y, ROI_LINE1_Y + LINE_HEIGHT),
                     slice(LINE_START, LINE_START + LINE_LENGTH))

        # input video
        video_name = inputvideo
        video = cv2.VideoCapture(video_name)
        fps = video.get(cv2.CAP_PROP_FPS)
        last_frame = int(video.get(cv2.CAP_PROP_FRAME_COUNT))
        frame = 0

        # last character position of textarea
        last_textpos = 0
        last_change = 0
        last_textpos_store = 0

        # Status
        # 0: No text in textarea, waiting for text
        # 1:
        status = 0

        # Storing
        # 0: waiting for a start point of rolling text
        # 1: waiting for a end point of rolling text
        storing = 0

        # index of subtitle
        index_sub = 0

        # blank in last frame
        is_blank_last = -1

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
            # Judge ROI of TextArea
            img_judge0 = img_crop[ROI_JUDGE0]
            img_judge1 = img_crop[ROI_JUDGE1]
            # TextArea exist?
            is_blank = is_blank_func(img_judge0, img_judge1)

            # binarization
            img_gray = cv2.cvtColor(img_crop, cv2.COLOR_BGR2GRAY)
            retval, img_bin = cv2.threshold(img_gray, int(
                options.gray_threshold), 255, cv2.THRESH_BINARY)

            # The fisrt line of TextArea
            img_line0 = img_bin[ROI_LINE0]
            # The second line of TextArea
            img_line1 = img_bin[ROI_LINE1]
            # Concat 2 lines horizontally
            img_line = np.concatenate((img_line0, img_line1), axis=1)

            img_line0_color = img_crop[ROI_LINE0]
            img_line1_color = img_crop[ROI_LINE1]
            img_line0_color = cv2.bitwise_or(
                img_line0_color, cv2.cvtColor(img_line0, cv2.COLOR_GRAY2BGR))
            img_line1_color = cv2.bitwise_or(
                img_line1_color, cv2.cvtColor(img_line1, cv2.COLOR_GRAY2BGR))
            if (frame == 1):
                img_line_color = np.concatenate(
                    (img_line0_color, img_line1_color), axis=0)

            # Template Matching for NMTG
            img_nmtg_1_tomatch = img_crop[ROI_NMTG_SEARCH]
            kernel = np.ones((7, 7), np.uint8)
            img_nmtg_1_tomatch = cv2.erode(img_nmtg_1_tomatch, kernel)

            img_tm = cv2.matchTemplate(
                img_nmtg_1_tomatch, img_pattern0, cv2.TM_SQDIFF_NORMED)
            min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(img_tm)

            nmtg_x = 0
            if (min_val < float(options.nmtg_tm_threshold)):
                nmtg_y = min_loc[1] - 2
                if (nmtg_y < 0):
                    nmtg_y = 0
                # Search NameTag Length
                img_nmtg_2_tomatch = img_crop[nmtg_y:nmtg_y + 56, 390: 600]

                img_tm_2 = cv2.matchTemplate(
                    img_nmtg_2_tomatch, img_pattern1, cv2.TM_SQDIFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(img_tm_2)
                nmtg_x = min_loc[0]
                if (nmtg_x < int(options.nmtg_extra_length_threshold)):
                    nmtg_x = 0

                cv2.line(img_nmtg_2_tomatch, (nmtg_x, nmtg_y),
                         (nmtg_x, nmtg_y + 56), (255, 255, 0), 3)

                # Write Nmtg Y
                if (nmtg_y > 1):
                    #print("Nmtg Transition", frame, nmtg_y, nmtg_x)
                    timestamp_data.append(
                        {"at": frame, "action": "N", "y": nmtg_y, "ex": nmtg_x}
                    )

            # If TextArea does not exits
            # clear the textarealine
            if (not is_blank):
                img_line[:] = 255

            # Rotated textarea line 90 deg
            arr_line_rot = np.array(np.rot90(img_line))
            # Scan the 'x position' of last character => textpos
            textpos = arr_line_rot.shape[0]
            for col in arr_line_rot:
                textpos -= 1
                if (not np.all(col)):
                    break

            # detect change of textpos
            is_textpos_changed = 0
            # avoid jittering of textpos
            if (abs(textpos - last_textpos) > int(options.textpos_threshold)):
                is_textpos_changed = 1 if (textpos - last_textpos) > 0 else -1

            if (not is_blank_last == int(is_blank)):
                if (is_blank):
                    #print("TextArea In", frame)
                    timestamp_data.append({"at": frame, "action": "T"})
                else:
                    #print("TextArea Out", frame)
                    timestamp_data.append({"at": frame, "action": "X"})
                is_blank_last = int(is_blank)

            # NO TEXT, waiting for a new line
            if (status == 0):
                # Start of a Line
                if (textpos > 0):
                    #print("LN", frame)
                    #timestamp_data.append({"at": frame, "action": "L"}) <= unused
                    # Status -> 1
                    status = 1
                    # mark frame change
                    last_change = frame
                    last_textpos_store = 0
                    if (storing == 0):
                        #print("Start", frame)
                        timestamp_data.append(
                            {"at": frame, "action": "S", "sub": index_sub})
                        storing = 1

            # Monitoring change of textarea
            elif (status == 1):
                # new text +
                if (is_textpos_changed > 0):
                    last_change = frame
                    if (storing == 0):
                        #print("Start", frame)
                        timestamp_data.append(
                            {"at": frame, "action": "S", "sub": index_sub})
                        storing = 1
                # Keep
                if (is_textpos_changed == 0):
                    # wait <wait_frame_threshold> and then store.
                    if (frame - last_change > int(options.wait_frame_threshold) and abs(last_textpos_store - textpos) > int(options.textpos_threshold)):
                        frame_real = frame - int(options.wait_frame_threshold)
                        #print("End", frame_real)
                        timestamp_data.append(
                            {"at": frame_real, "action": "E"}) #, "sub": index_sub}) <= unused
                        storing = 0
                        # Store TextArea
                        img_line0_color_c = img_line0_color.copy()
                        img_line1_color_c = img_line1_color.copy()
                        cv2.line(img_line0_color_c,
                                 (last_textpos_store + 10, 30), (textpos, 30),
                                 (127, 255, 0), 20)
                        cv2.line(img_line1_color_c,
                                 (last_textpos_store + 10 - LINE_LENGTH,
                                  30), (textpos - LINE_LENGTH, 30),
                                 (127, 255, 0), 20)
                        img_line_color_o = np.concatenate(
                            (img_line0_color, img_line1_color), axis=0)
                        img_line_color_c = np.concatenate(
                            (img_line0_color_c, img_line1_color_c), axis=0)
                        img_line_color = cv2.addWeighted(
                            img_line_color_o, 0.85, img_line_color_c, 0.15, 1)
                        imwrite(img_output_dir + '/' + "text_" +
                                ("%04d" % index_sub)+".png", img_line_color)
                        #print("index_sub: " + str(index_sub))

                        # Get NameTag Area
                        ROI_NMTG = (slice(7, 50), slice(15, 390 + nmtg_x))
                        img_nmtg = cv2.bitwise_not(img_bin[ROI_NMTG])
                        cv2.imshow("img_nmtg", img_nmtg)
                        # Store NameTag
                        nmtg_index = get_nmtg_index(img_nmtg, nmtg_x)
                        nmtg_map.append(nmtg_index)
                        #print("nmtg_index: " + str(nmtg_index))

                        index_sub += 1
                        last_textpos_store = textpos

                # Carriage return
                if (is_textpos_changed < 0):
                    #print("CR", frame)
                    timestamp_data.append({"at": frame, "action": "C"})
                    status = 0

            cv2.imshow("img_crop", img_crop)
            cv2.imshow("img_sub", img_line_color)
            cv2.waitKey(1)
            last_textpos = textpos

            progress = int(frame / last_frame * 100)
            prog_char = int(progress / 4)
            print("  >" + "*" * prog_char +
                  "." * (25 - prog_char) + ("%03d" % progress) + "%",
                  end='\r')

        #print("All End", frame)
        video.release()
        cv2.destroyAllWindows()
        print("\n")
        timestamp_data.append({"at": frame, "action": "O"})

        # Write to json file
        import json
        script_fp = open(script_output, mode='w', encoding='utf-8')
        json_nmtgs = [''] * len(g_nmtg_img_db)
        json_trans = [''] * len(nmtg_map)
        json_data = {
            "video": basename,
            "version": '11.0.0',
            "total": len(nmtg_map),
            "lang": currentlang,
            "title": "",
            "nmtgs": json_nmtgs,
            "trans": json_trans,
            "nmtg_map": nmtg_map,
            "nmtg_ex": g_nmtg_ex_db,
            "timestamp": timestamp_data
        }
        json_text = json.dumps(json_data, indent=2)
        script_fp.write(json_text)


if __name__ == '__main__':
    analyse_video()
