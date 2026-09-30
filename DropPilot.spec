# Build from the source directory with env/Scripts/pyinstaller.exe DropPilot.spec
from PyInstaller.utils.hooks import collect_data_files

datas = [('web', 'web'), ('lang', 'lang'), ('icons', 'icons'), ('LICENSE', '.')]
datas += collect_data_files('webview')
a = Analysis(['modern_main.py'], datas=datas,
             excludes=['gui', 'main', 'cache', 'tkinter', 'PIL.ImageTk'],
             hiddenimports=['webview.platforms.winforms', 'webview.platforms.edgechromium',
                            'logging.handlers'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name='DropPilot', debug=False,
          console=False, upx=False, icon='icons/droppilot.ico', version='version_info.txt')
