import bpy
import os
import sys
from ... utils.registration import get_path, get_prefs
from ... utils.system import makedir, open_folder
from ... import bl_info

enc = sys.getdefaultencoding()

class GetSupport(bpy.types.Operator):
    bl_idname = "machin3.get_machin3tools_support"
    bl_label = "MACHIN3: Get MACHIN3tools Support"
    bl_description = "Generate Log Files and Instructions for a Support Request."
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        logpath = makedir(os.path.join(get_path(), "logs"))
        resourcespath = makedir(os.path.join(get_path(), "resources"))

        sysinfopath = os.path.join(logpath, "system_info.txt")
        bpy.ops.wm.sysinfo(filepath=sysinfopath)

        self.extend_system_info(context, sysinfopath)

        src = os.path.join(resourcespath, "readme.html")
        readmepath = os.path.join(logpath, "readme.html")

        with open(src, "r") as f:
            html = f.read()

        html = html.replace("VERSION", ".".join((str(v) for v in bl_info['version'])))

        folderurl = "file://" + logpath
        html = html.replace("FOLDER", f'<a href="{folderurl}">MACHIN3tools/logs</a>')

        with open(readmepath, "w") as f:
            f.write(html)

        readmeurl = "file://" + readmepath
        bpy.ops.wm.url_open(url=readmeurl)

        open_folder(logpath)

        return {'FINISHED'}

    def extend_system_info(self, context, sysinfopath):
        if os.path.exists(sysinfopath):
            with open(sysinfopath, 'r+', encoding=enc) as f:
                lines = f.readlines()
                newlines = lines.copy()

                for line in lines:
                    if all(string in line for string in ['version:', 'branch:', 'hash:']):
                        idx = newlines.index(line)
                        newlines.pop(idx)
                        newlines.insert(idx, line.replace(', type:', f", revision: {bl_info['revision']}, type:"))

                    elif line.startswith('MACHIN3tools'):
                        idx = newlines.index(line)

                        new = []

                        filters = [ws for ws in bpy.data.workspaces if ws.use_filter_by_owner]

                        if filters:
                            new.append("")
                            new.append("Workspace Addon Filters")

                            for ws in filters:
                                new.append(f"  {'🚫'} Addon Filtering enabled on '{ws.name}' Workspace")

                        prefs = get_prefs()

                        tools = []
                        pies = []

                        for p in dir(prefs):
                            if p.startswith('activate_'):
                                status = getattr(prefs, p, None)

                                if p.endswith('_pie'):
                                    name = p.replace('activate_', '').replace('_pie', '').title() + " Pie"
                                    pies.append((name, status))

                                else:
                                    name = p.replace('activate_', '').replace('_', ' ').title()

                                    if 'Tools' not in name:
                                        name += " Tool"

                                    tools.append((name, status))

                        new.append("")
                        new.append("Tools")

                        for tool, status in tools:
                            icon = "✔ " if status else "❌"

                            new.append(f"  {icon} {tool}")

                        new.append("")
                        new.append("Pies")

                        for pie, status in pies:
                            icon = "✔ " if status else "❌"

                            new.append(f"  {icon} {pie}")

                        new.append("")

                        for n in new:
                            idx += 1
                            newlines.insert(idx, f"  {n}\n")

                f.seek(0)
                f.writelines(newlines)
