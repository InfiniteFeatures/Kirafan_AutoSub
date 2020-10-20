# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

def get_opencv_path():
    import cv2
    opencv_path = cv2.__path__[0]
    return opencv_path

a = Analysis(['AutoSub.py'],
             pathex=['.'],
             binaries=[
                (get_opencv_path() + '/opencv*_ffmpeg*.dll','.')
			 ],
             datas=[
                ('./usr/nmtg.png', './usr'),
                ('./usr/nmtgex.png', './usr'),
                ('./usr/jpfont.ttf', './usr'),
                ('./usr/cnfont.ttf', './usr'),
                ('./usr/kofont.ttf', './usr'),
                ('./usr/pattern0.png', './usr'),
                ('./usr/pattern1.png', './usr'),
                ('./usr/ffmpeg.exe', '.')
             ],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
             
dict_tree = Tree(get_opencv_path(), prefix='cv2', excludes=["*.pyc"])
a.datas += dict_tree
a.binaries = filter(lambda x: 'cv2' not in x[0], a.binaries)

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [],
          name='Kirafan_AutoSub_v11.0.',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=True )
