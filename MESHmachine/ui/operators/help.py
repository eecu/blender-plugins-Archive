import bpy
import os
import sys
import socket
from ... utils.registration import get_path, get_prefs
from ... utils.system import makedir, open_folder
from ... import bl_info

enc = sys.getdefaultencoding()

class GetSupport(bpy.types.Operator):
    bl_idname = "machin3.get_meshmachine_support"
    bl_label = "MACHIN3: Get MESHmachine Support"
    bl_description = "Generate Log Files and Instructions for a Support Request."
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        logpath = makedir(os.path.join(get_path(), "logs"))
        resourcespath = makedir(os.path.join(get_path(), "resources"))
        assetspath = get_prefs().assetspath

        is_url_open = bpy.app.version >= (4, 1, 0) or bpy.app.version < (3, 6, 0)

        sysinfopath = os.path.join(logpath, "system_info.txt")
        bpy.ops.wm.sysinfo(filepath=sysinfopath)

        self.extend_system_info(context, sysinfopath, assetspath)

        src = os.path.join(resourcespath, "readme.html")
        readmepath = os.path.join(logpath, "readme.html")

        with open(src, "r") as f:
            html = f.read()

        html = html.replace("VERSION", ".".join((str(v) for v in bl_info['version'])))

        if is_url_open:
            folderurl = "file://" + logpath
            html = html.replace("FOLDER", f'<a href="{folderurl}">MESHmachine/logs</a>')

        else:
            html = html.replace("FOLDER", "MESHmachine/logs")

        with open(readmepath, "w") as f:
            f.write(html)

        if is_url_open:
            readmeurl = "file://" + readmepath
            bpy.ops.wm.url_open(url=readmeurl)

        open_folder(logpath)

        return {'FINISHED'}

    def extend_system_info(self, context, sysinfopath, assetspath):
        if os.path.exists(sysinfopath):
            with open(sysinfopath, 'r+', encoding=enc) as f:
                lines = f.readlines()
                newlines = lines.copy()

                for line in lines:
                    if all(string in line for string in ['version:', 'branch:', 'hash:']):
                        idx = newlines.index(line)
                        newlines.pop(idx)

                        newlines.insert(idx, line.replace(', type:', f", revision: {bl_info['revision']}, type:"))

                    elif line.startswith('MESHmachine'):
                        idx = newlines.index(line)

                        new = ['Assets:']
                        libs = [f for f in sorted(os.listdir(assetspath)) if os.path.isdir(os.path.join(assetspath, f))]

                        for lib in libs:
                            new.append(f"    {lib}")

                        for n in new:
                            idx += 1
                            newlines.insert(idx, f"  {n}\n")

                f.seek(0)
                f.writelines(newlines)
