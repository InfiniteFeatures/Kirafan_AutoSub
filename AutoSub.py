# -*- coding: utf-8 -*-
import os
import sys
import traceback

import sequence_crop
import analyse_video
import patch_subtitle
import concat
import convert

try:
    sys.setdefaultencoding('utf-8')
except:
    pass

args = ' '.join(sys.argv[1:])

print('''
Kirara Fantasia Auto Subtitle Patcher v10
Powered by Ayaya (twitter: @kirafan_autodec)
''')
print("Your args is: " + args)
print('''
Please select function from below:
1. Crop and Reencode Raw Movie
2. Analysis and Auto-Label to krfss Files
3. Auto-Patch Subtitle from krfss Files
4. Concat Videos into A Single File
5. Convert OP/ED/CM into mpeg4 Format
''')

try:
    user_select = 0
    while (not user_select in {1, 2, 3, 4, 5}):
        try:
            user_select = int(input("Input from (1, 2, 3, 4, 5) >> "))
        except ValueError:
            pass

    if user_select == 1:
        sequence_crop.sequence_crop()
    elif user_select == 2:
        analyse_video.analyse_video()
    elif user_select == 3:
        patch_subtitle.patch_subtitle()
    elif user_select == 4:
        concat.concat()
    elif user_select == 5:
        convert.convert()
    else:
        raise Exception("Unknown Selection")
    print("Done")
    input("Press enter to exit...")

except Exception as e:
    traceback.print_exception(type(e), e, e.__traceback__, file=sys.stderr)
    print("ERROR: " + str(e))
    print("Aborting")
    input("Press enter to exit...")
