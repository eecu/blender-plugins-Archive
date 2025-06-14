#

# 1.12
> 2025-05-07

## DeusEx

* Assetbrowser tools
	- add EditAssembly and FinishAssemblyEdit tools
		- access assembly's instance collection objects and manipulate them, then return to the previous outside-of-the-assembly state again
		- indicate AssemblyEdit mode via red region border, and red FinishAssembly button in top bar
		- transform the cursor relatively into the assembly edit mode, and back out again
		- fully support groups and wire objects within the assembly and adjusting their visibility accordingly to avoid outside-of-the-assembly clutter
		
		- support user made instance collections too
		- support linked assemblies or instance collections
			- NOTE: you can peak inside, but can't change anything permanently, until you make it local
			- distinguish linked and unlinked ones with a red vs green Edit icon
	
	- add CreateAssemblyVariant tool
		- creates an independent duplicate
		- optionally with linked object data via `ALT` mod key
		
	- add TurnAssemblyIntoAsset tool
		- turn any Assembly or user made Instance Collection into an Asset with Thumbnail
		- be default with catalog, tags and meta data, but can be skipped/postponed via `ALT` mod key

	- SetAssemblyOrigin tool (previously SetInstanceCollectionOffset)
		- support setting assembly origin rotation now
			- by default both - location and rotation - are set now, either from the cursor or another object
				- use `ALT` or `CTR` mod keys, or redo panel to set only rotation, or only location
			- NOTE: since Blender only supports a translation offset for instance collections, assembly origin orientation is changed, by manipulating instance collection root object locations and rotations within the collection
			
	- UpdateThumbnail tool
		- add Thumbnail Helper Gizmo to fine-tune automatic framing
			- NOTE: framing of the thumbnail is internally based on bbox(es)
				- but they may not represent the ideal or desired space the asset should occupy within a thumbnail
				- so the helper gizmo will overwrite the asset's bbox

* Group tools 
	- Group Mode (Outliner)
		- disable group gizmos when entering Group Mode  in the outliner
		- expose group gizmo toggle in outliner header
		
	- Group Origin Adjustment Mode
		- when entering disable potential axes locks (set up by the SetupGroupGizmos tool) and disable group gizmos too
		- when finishing re-enable axes locks and gizmos, and update the Inception pose if present
			- NOTE: it's still highly recommend to finalize the group origin BEFORE your create any group poses
			
	- SetupGroupGizmos tool 
		- actually disable group empty's axes locks, when finishing the op with locks turned off

* Modes Pie
	- group empties
		- expose Group Poses
			- adding, setting and updating of group poses, including batch poses
		- expose Setup Gizmos tool
		- expose Group Gizmo axes and toggles
		
* Save Pie
	- add FinishAssemblyEdit button, replacing the CreateAssembly button, when in EditAssembly mode
	
* Cursor and Origin Pie
	- support changing Assembly/Instance Collection origins, including *only location* or *only rotation* via `ALT` and `CTRL` mod keys
	
* TransformGroup, SetupGroupGizmos, TransformEdgeConstrained Transform and PunchIt tools
	- update status bars of all modal tools, support 4.3's extra wide even key icons
	
* TransformGroup, SetupGroupGizmos, TransformEdgeConstrained Transform tools
	- support apple magic mouse *scrolling*
	
* TransformEdgeConstrained and PunchIt tools
  - flesh out and modernize HUD
  - draw HUD and 3D view elements on active 3D view only

* TransformEdgeConstrained tool
	- add missing tooltip
	- expose at bottom of native `CTRL + E` *Edge Context menu*
	
* sidebar
	- Group tools
	 	- move active object's group gizmo settings and poses into sub-panels
			
	- Assetbrowser tools
		- expose EditAssembly and FinishAssemblyEdit buttons
			
* addon preferences
	- activate Group tools and Assetbrowser tools by default (DeusEx only)
  

## Prime

* Assetbrowser tools
	- CreateAssemblyAsset tool
		- support assembly/asset creation of objects with *severely hidden* children (in excluded or hidden collections)
		- support and default to keeping decal backups and stash objects again
			- and only expose the option if any are present at all
		- indicate entire assembly asset object count
		- support assembly/asset creation from selection only (and so for a part of a hierarchy only)
			- previously - for selection convenience - the entire object hierarchy determined and used for assembly/asset creation
			- now you can optionally create assemblies/assets from parts only, for instance, only the thigh of a robot leg
		- support assembly/asset creation without duplication (enable in addon prefs)
		- support adding tags and meta data
		- base average assembly origin location on non-wire objects preferably
		- improve main *_Assembly* collection creation (previously called *_Assets*), and support multiple (per-scene) across a single blend file
		- rename and invert behavior of previous *Unlink Asset* prop to *Drop Asset into Scene*
		- set collection colors, green for the main *_Assemblies* collection, orange for actual assembly asset collections
		- with a single asset browser open at time of asset creation select 'All' pseudo catalog in 'Current File' library
		
	- add ResetAssemblyOrigin tool 
		- zero out collection's 'instance_offset' and compensate collection objects accordingly
		 	- this ensures the assembly's origin is exactly in the world origin within the instance collection
		- support user made instance collections too
		
	- add CleanNonAssets tool 
		- used to prepare a file for saving in an asset library, avoiding file bloat
		- removes everything in a blend file that is not an asset or related to one
			- also keeps fake user data, that can optionally be removed manually
		- lays out all object and collection assets and fake users on the view layer
			- Assemblies get sorted by size, and are distributed on thew X axis
		- organizes objects and collections into three main collections: _Assemblies, _Assets, _FakeUsers
			- sort DECALmachine backups and MESHmachine stash objects into dedicated sub-collections
			
	- SetAssemblyOrigin tool (previously SetInstanceCollectionOffset)
		- default to work relatively to the active assembly/instance collection empty
			- legacy behavior (relative to original objects) can be enabled from redo panel or via 'SHIFT' mod key
		- support user made instance collections too
	
	- UpdateThumbnail tool
		- support NODETREE assets
	
	- DisassembleAssembly tool 
		- support disassembling instance collections with child collections and their contained objects
			- NOTE: assembly assets so far only ever contain on collection, due to [this Blender bug](https://projects.blender.org/blender/blender/issues/136100) 
		- sort disassembled decals (from DECALmachine) into decal collections, depending on DM's collection settings
	
	- assetbrowser bookmarks bar
		- avoid unnecessary changes to capitalization of user library names
		- fix exception when Filebrowser tools are not active also
		
* Group tools
	- support drawing group relationships
		- draw group origins and distinguish between active and other groups by color
		- draw lines visualising parenting hierarchies
		- optionally draw lines to group objects
		- optionally draw the active group, useful for massive scenes with thousands of objects, that would otherwise slow things down
	
	- Outliner
		- expose parenting button to visually indicate if object parenting is shown or not
		- significantly flesh out Group Mode (toggled via `1` key by default)
			- indicate if you are in group mode via red label in outliner header
			- automatically toggle group relationship drawing
			- improve outliner layout changes and restoration of initial state when entering/leaving group mode
			- by default - when entering group mode - disable auto select, recursive select and group empty hiding
				- disabling auto select in particular, helps manually changing group hierarchies by dragging group empties around in the outliner, and avoids unindented hierarchy changes
				- automatically respond to those changes and update internal group properties accordingly, so there is no more need to run the Group Select tool afterwards
			- avoid applying outliner *filter_text*, when there are no other empties but group empties or when group prefixes or suffixes are not actually used
			
	- flesh out Group Origin Adjustment mode
		- automatically toggle group relationship drawing
			- and use different colors than when turning it on manually or via Outliner Group mode
		- disable auto select, recursive select and group empty hiding
		- prevent running most group tools in this mode
		- prevent toggling auto select and recursive select
		
	- Ungroup tool
		- draw red fading wires to highlight the now ungrouped objects
		- draw fading labels to summarize the operation and affected objects
	
	- SelectGroup tool 
		- change behavior when in local view
			- always bring the group empty and other group objects into local view now
			- ignore recursive select setting, and instead support forcing recursive group selection via CTRL key
				- update tool tip accordingly
				
	- addon prefs
		- control what Outliner Group Mode toggles, and what buttons are shown in the Outliner header

	- fix issue with group auto naming to ensure the group suffix is always added after any potential potential index added by Blender
	- avoid group creation in linked collection, and pop a fading label about it
	
* SelectHierarchy tool 
	- completely rewrite and support *severely hidden* objects (those in excluded or hidden collections)
		- in HUD and redo panel indicate how many objects are still hidden, and how to reveal them
		- in redo panel offer quick way to reveal and select everything in the hierarchy
	
* Extrude tools 
	- expose Blender native Extrude **menu** keymap (in addon pref's Extrude tool settings section)
		- deal with case where it can't be found
		  - because it was removed
		  - because of the Industry Compatible keymap (which doesn't set it)
	- expose Cursor Spin and Punch It (a little) tools at bottom of `CTRL + F` *Face Context menu*
	
* SmartVert tool
	- SlideExtend
		- add HUD
		- support HyperCursor 0.9.18 changes
	- make merging UVs optional when merging LAST or CENTER
		- toggle in redo panel
	
* SmartFace tool 
	- add *topo mode*
		- launches modal to immediately position the new face's vert
		- preview next vert selection and apply it when finishing or aborting vert translation
		- supports Blender's auto merge setting
		- optionally disable in addon prefs for legacy behavior, and optionally only enable it when
			- face snapping is used
			- when retopology overlay is enabled

* CleanUp tool 
	- fix rare exception, when trying to remove redundant verts
	
* ApplyTransformations tool
	- when applying Scale in addition to compensating Bevel mods, also compensate the following mod types now:
		- Solidify
		- Displace
		- Welds
		- Linear and Linear Hyper Arrays
		- Helix Offset in Radial Hyper Arrays
	- when applying rotation rotate the Linear and Linear Hyper Array offset vectors accordingly to compensate
	- support applying transform on parented objects
	- in addition to comensating DECALmachine backups, also compensate MESHmachine's stashes now
	- improve applying scale/rotation on multiple objects of the same hierarchy
	- expose at bottom of the native `CTRL + A` *Apply menu* with direct *Rotation*, *Scale* and *Rotation & Scale* buttons
		
* MaterialPicker tool
  - improve raycasting internals
	 	- avoid hitting undesired objects when in local view
		- avoid hitting wire objects
  - fix exception picking a material in edit mode
  - fix exception picking *None* material from Assembly/Instance Collection object
  - fix material appended from asset browser not being cleared as an asset
  - fix import method LINK being used when asset browser is set to FOLLOW_PREFS
	
* Thread tool 
	- add missing tooltip
	- draw fading message for illegal selections

* AlignRelative tool 
  - add `D` key as primary instance/duplicate toggle (scrolling still works however)
  - flesh out HUD a little more
  - draw HUD and 3D view elements on active 3D view only
	- add missing tooltip
  
* Annotate, AlignRelative and Mirror tools
	- support apple magic mouse *scrolling*
	
* Mirror tool 
  - fix mirror object being recognized as misaligned, just because it's scaled differently
  - draw HUD and only on active 3D view
		
* Filebrowser tools 
	- AdjustThumbnailSize tool 
		- fix thumbnail size not being drawn in some 3d views when dragging size in asset shelf
		
* Toggle Region tool 
	- asset shelf toggling is enabled by default now (addon prefs)
		- when asset shelf is present, the shelf will be toggled instead of the asset browser
	- always restore 'All' pseudo library when either 'All' or 'Unassigned' was set at time of closing asset browser split
	
* Filebrowser tools
	- when cycling asset libraries via `1` key select 'All' pseudo catalog too

* Customize tool 
	- keymaps
		- change native size 'radial_control' keymaps to use *release_confirm*
			- Sculpt Mode
			- Grease Pencil Sculpt Mode
			- Grease Pencil Brush Stroke
			- Image Paint Brush
		 - re-enable 'mesh.loop_multi_select' keymap
			- now using 'ALT + SHIFT + CLICK_DRAG SOUTH' for loop selection, which conflict with MESHmachine's 'ALT + LMB' select wrapper
		- disable all hide_collection keymaps
	- start up file
		- disable showing object content in Outliner
	- in 4.4 input prefs
		- disable NDOF (Show) Orbit Center
	
- AlignRelative, MaterialPick, Mirror, Annotate, SmartVert/Slide Extend tools
	- update status bars, support 4.3's extra wide even key icons

* Modes pie
	- support adjustable top button (in addon prefs)
		- previously it always was the *Edit* button, which is now disabled by default
		- support *Sculpt* button, enabled by default
		- with Group tools active, support *Group*, *Group Select* and *Ungroup* at the top, depending on active object/selection
		- support showing a stack multiple buttons on top, combining any of the previous
			- NOTE: won't allow quick swiping motion
			
	- support EditAssembly Button at the bottom and Finish AssemblyEdit button at the top
		- optionally disable in addon prefs, and access from the sidebar, topbar or Save pie
		
	- flesh out empty object support
		- regular empties
			- expose empty's display type and display size
			- add Groupify tool, when groups tools are enabled, and the active empty has children
		- image empties
			- expose side, depth, opacity and gizmo properties
		- group empties
			- expose auto select, recursive select and hide empties settings
			- expose group name and size
			- expose Origin Adjustment mode toggle
			- expose Draw Group Relations toggles
			- expose Ungroup tool (optionally)
			
	- in SCULPT mode expose Symmetry, Dyntopo and Remesh options
			
	- add library reload button, if active object is linked or has linked data
	- for both *Library Reload* and *MakeLocal* buttons, preview EXACTLY what is linked in the tooltip
			
* Save pie
	- in Image/UV Editor expose
		- save image, save image as, open image, close image, pick image, new image, pack/unpack image and edit image externally
	- add OpenCurrentDir tool 
		- opens current folder in system's file browsers
		- when current file is startup file, open Blender's config folder
	- show * indicators in pie buttons, if blend file or image is unsaved
	- expose FBX *apply scale all* prefs directly in the pie
		- use the unity icon for it
	- expose CleanNonAssets tool 
		- and remove previous 'CTRL' mode of the *Save As* tool, which could be used for the same purpose (but did it worse)
	- ScreenCast
		- improve synergy with Screencast Keys extension
		- support disabling Screencast Keys, even when MACHIN3tools operator casting is itself no longer active
			- this happens when you start a new file while Screencasting is enabled
			
* Shading pie
	- Shade Smooth/Flat
		- support recursive shading of *severely hidden* objects (in excluded or hidden collections)
		- fix exception when 'boolean_auto_smooth' is disabled
		- fix issues with linked objects/data or partial selections, that include linked objects/data
		- ALT Smooth mode
			- skip sharpening HyperCursor's edge weight based edge bevels and HyperBevel objects
	- expose *Retopology Overlay* toggle
	- expose Mist Settings when *Mist Pass* is enabled, and `scene.world` is set
	- optimize when *Backface Culling* and *Face Orientation* toggles are shown
	- in 4.4, update Bloom Threshold and Size props for new Input types

* Cursor and Origin pie
	- support changing Assembly/Instance Collection origins from here
		- support to Cursor and to Object
	- support resetting the origin

* Snapping pie
	- expose global `use_snap` toggle
	- expose Snap Preset Targets in addon prefs
	- support alternating between SURFACE and FACE_NEAREST snapping toggling the Surface preset button a second time
		- optionally disable in addon prefs
	- optionally disable fading HUD in addon prefs
	- use non-alphabetic sorting order for multiple-snap-element indications at the top of the pie, and in the HUD
		- always sort it VERTEX > EDGE > FACE etc.

* Workspace pie
	- remember if `.alt` workspace was last used, and then switch back to it directly the next time

* Views pie
	- Smart Cam
		- if *Mist Pass' is enabled, enable `use_mist` Camera Viewport Display option

* Transform pie
	- avoid showing empty 3rd box on top for modes other than EDIT_MESH and OBJECT
	
* Quad Sphere object
	- expose default settings in addon prefs
	- support Unwrapping: None, Cross, Cubic, Cylindrical or Spherical
	
* sidebar
	- modernize using new `layout.panel` elements
	- add Get Support and Documentation panels,
		-both enabled by default, but can be disabled from the Help button in the header or the addon prefs
		
	- Assetbrowser tools
		- indicate if assembly or instance collection is linked, including for potential child assemblies
		- for instance collections that aren't local assembly assets, expose the collection selector, instead of just the collection name
		- fix exception when drawing 'instance_offset' of nested assemblies/instance collections
		
* addon preferences
	- modernize using new `layout.panel` elements
	- expose HUD shadow prefs
	- keep track of and display registered operator and keymaps counts
	- fix issue where some tools caused an empty Tool Settings box to appear, or where it would be missing
	- disable Toggle Region tool by default
	
* remove DECALmachine and MESHmachine post-asset drop cleanups
	- done by each addon separately by now


# 1.11.1

> 2024-11-25

* Assetbrowser tools
	- when changing asset origin, prevent asset from jumping around by compensating for new translation offset

* MaterialPicker
	- fix Windows only issue when assigning materials from asset browser due undocumented API change affecting how paths within blend files are represented

* Modes pie
	- without an active object, draw a message about it in the pie

* Customize tool
	- prevent exception in 4.3 due to API change, when customizing startup file shading
	
* Group tools
	- handle occasional "restricted context" exceptions


# 1.11

> 2024-11-09

* bump minimum Blender version to 4.2 LTS

* Align tool
	- support aligning selection to active's local axes
	- support aligning selection to cursor's local axes
	- rework the redo panel, and in particular the *align in between* and *align to bone* modes
		- for both add a distance slider, allowing you to tweak how an object is positioned

- AssetBrowser tools
	- CreateAssemblyAsset tool
		- set asset empty size based on asset object dimensions
		- fix issue where asset empty was not positioned properly, when disabling the unlink option
		- expose instance collection offset in Assetbrowser tools sidebar panel, including *from Cursor* and *from Object* ops

	- UpdateAssetThumbnail tool
		- support creating COLLECTION, MATERIAL and POSE/ACTION asset thumbnails
			- NOTE: all still require an OBJECT selection in the 3D view
		- support 'ALT' mod key to ensure overlays are rendered too, useful if you want armatures to show up in the thumbnail for instance

	- fix exception in asset browser, when active asset is not of type OBJECT

* FileBrowser tools
	- in AssetBrowser
		- turn import method selection into a modal tool
			- hold '4' key and move mouse horizontally
		- support modal preview sizes adjustment in asset shelfs tool
			- like in the FileBrowser, hold '3' key and move mouse horizontally
		- drop legacy non-modal behavior and remove option to disable it in addon prefs accordingly

* MaterialPicker tool
	- support picking materials from objects within instance collection assets

* SmartVert tool
	- use uvs=True arg when center- or last-merging

* SmartEdge tool
	- support creasing, when invoked via 'SHIFT + 2'

* SmartFace tool
	- when multiple objects are in edit mesh mode, support creating multiple new objects from face selections
	- by default clear mods on separated objects now
	- optionally support joining multiple separated objects into one

* Focus tool
	- in View Selected mode, ignore arrays by default now too, unless disabled in redo panel
		- just as already done with mirror mods, focus on the original, not the evaluated results of these modifiers

* Mirror tool
	- support mirroring Grease Pencil v3 objects in Blender 4.3

* Customize tool
	- disable 'F' keymap in grease pencil edit mode
		- you can still toggle cyclicity using 'ALT + C'
		- but with 'F' freed, *view_selected* can take over now

	- M3 theme
		- set asset shelf colors

* Tools pie
	- like the SurfaceDraw tool before, move grease pencil options from Modes pie to here as well now
		- ShrinkWrapGreasePencil tool, surface distance prop, Thickness and Opacity modifier access, when present

	- add Annotation Note tool
		- point the cursor at part of an object, call the pie, pick the Note tool, start typing
			- finish via 'LEFTMOUSE' or 'CTRL + RETURN'

			- see statusbar for options
				- screen X aligned by default, toggle Cursor X align via 'CTRL + S' or 'CTRL + C'
				- size is determined automatically, but can be changed by scrolling mouse
				- remove words via 'CTRL + W', remove all via 'CTRL + U' or 'CTRL + BACKSPACE'

			- in 4.2 Notes are Annotation based
			- in 4.3 due to API changes, Grease Pencil objects will be created instead
				- pro
					- parented to object
				- contra
					- pollutes scene
					- in solid shading has solid color, not annotation color
					- may require multiply blend to be legible
					- minimum stroke thickness hard cap, limiting small notes

	- ToggleAnnotation tool
		- update to fully support annotation note gpv3 objects in 4.3
			- it toggles both, regular annotation and the layers on the GP note objects

	- SurfaceDraw tool
		- update for 4.3's v3 Grease Pencils
		- when invoking LINE tool using SHIFT mod key, ensure sufficient subdivision count when subdivisions are currently < 10
    	- NOTE: you can always simplify later again, but you want to avoid having not enough subdivisions when drawing on curved surfaces

	- ShrinkwrapGreasePencil tool
		- update to work with GP's new attribute based data representation in 4.3

	- with an active GP object, expose it's layers and some layer props now too

  - when in Grease Pencil PAINT mode, expose Draw, Line and Erase tools
  	- with Line tool selected, expose line subdivisions prop
  - when in Grease Pencil EDIT mode, expose *Stroke Simplify* tool

	- fix HOps menu not appearing when installed as extension

* Save pie
	- avoid exposing fbx export when default fbx addon is disabled
	- add glTF import/export support
	- add Better FBX import/export support

	- Load Next/Previous tools
		- pop confirmation dialog when file has unsaved changes, to avoid accidental data loss

	- Clean out scene tool
		- support 4.3 annotations removal and empty annotion layer re-creation

* Modes pie
	- suport Blender 4.3 Grease Pencil rewrite
	- move grease pencil options from here to Tools pie
		- Shrinkwarp tool, Surface distance prop, Tickness and Opacity modifier access, when present
	- add VERTEX_GPENCIL / VERTEX_GREASE_PENCIL modes to tiny modes bar when active object is GP
	- in grease pencil paint mode, expose stroke placement popup
	- flesh out SCULPT, PAINT_TEXTURE, PAINT_WEIGHT, PAINT_VERTEX and PARTICLE modes
		- in each expose object, vert, edge and face mode toggles now

* Snapping pie
	- support setting snap element additively using 'ALT' mod key
	- indicate snap element(s) at the top of the pie
	- draw fading label when setting one of the presets indicating the curretn snap target and snap element(s)
	- use CLOSEST target for absolute grid snapping
	- enable snap_show_absolute_grid prefs by default now

* Shading pie
  - expose rotation, if mapping node is connected to image node, which in turn is connected to the background node

	- fix exception for world setup using background node with connected image texture

	- when detecting a trace_max_roughness of 0 while raytracing is enabled, reset it to its default of 0.5
     - opening up pre-4.2 files seems to set this value to 0, but with it at 0, all metals will look like plastic
 	 	 - print warning message to terminal when doing this

	- fix angle prop not being in degrees when replacing invalid auto smooth
		- also recreate show_expanded and use_pin_to_last props

	- when adding auto smooth mod via the toggle (not via the presets), ensure an angle of 20° is used, not the default 30°

* Transform pie
	- indicate current choice of pivot and orientation by drepressing buttons accordingly
 
* Cursor Pie
	- fix "Origin to Cursor" button width when multiple mesh modes are selected at the same time

* indicate if a MACHIN3tools update is available in 3D view's sidebar

* addon preferences
	- be more verbose in filebrowser/assetbrowser keymap labels in keymaps tab
	- indicate if a MACHIN3tools update is available

	- GetSupport tool
		- check for and list workspaces that have addon filtering enabled

	- fix assetbrowser tool prefs not showing up
  - remove some legacy prefs that are no longer used


# 1.10.1
> 2024-08-05

* AssetBrowser tools
	- rework MakeLocal tool completely
		- fix issues on more complex linked assets of assets, and sometimes even on simple linked assets
		- making objects (instance collection or not) is tiered
			- by default, if the selected object is linked, only the object itself will be made local
				- this allows you to position, scale, and rotate the object, while its data or linked instance collection remain linked, and so only exist in an external file)
			- only on the second run, or when holding down `SHIFT`, or when the object itself is not linked and only its data or instance collection be made local too
		- instance collections are only ever made local one level down
			- so for recursive linked instance collections, you could keep the lower level linked while making the upper level local or disassemble it
		
	- CreateAssemblyAsset tool
		- fix occasional black thumbnails
		- fix exception, when not unlinking empty

	- DisassembleAssembly tool
		- use new logic from MakeLocal to ensure linked assemblies are made local properly

* Save pie
	- add ReloadLibraries tool, when linked data blocks are used

* Modes pie
	- improve handling of linked or partially linked objects by detecting if object data or instance collection is linked, even if object itself is not linked (anymore)

* Group tool
	- add workaround for Blender 4.2 "object loses transform bug on redo" bug

* Cursor and Origin pie
	- OriginToBottomBounds tool
		- add workaround for Blender 4.2 "object loses transform bug on redo" bug

* CreateDoFEmpty (Prime only)
	- fix exception when drawing fading label

* SmartEdge tool
	- fix issue in Korean Bevel mode

* remove unnecessary imports all over


# 1.10
> 2024-08-01

* AssetBrowser tools
  - CreateAssemblyAsset tool
    - rework completely and massively simplify the UX and exposed options
      - always duplicate the original objects for use in the instance collection
        - and always removed MM stashes and DM backups on those duplicates
      - avoid moving instance collection objects into world origin, make use of `instance_offset` instead
      - always add asset collection to the viewlayer in the main *_Assets* collection, which itself is on, but excluded from the view layer
        - this aims to make things more transparent, and so you now can easily see which asset collections exist in the file
      - by default, unlink the asset empty, so the asset only appears in the AssetBrowser's LOCAL/Current File library
        - if disabled bring back an instance of it, offset in front of the original object(s)
    - redo thumbnail rendering too
      - perfectly frame the asset automatically, incl. recursive assets of assets
      - support camera view (incl. Depth of Field) and cycles rendering
    - support placing asset empty in Cursor location
  
  - add Disassemble tool
    - replaces previously awkwardly named AssembleInstanceCollection
    - make assembly asset/instance collection objects accessible
    - when assembly is linked, make it local
    - support Rigid Body setup if assembly objects are using it

  - add MakeLocal tool
    - makes assembly local without disassembling
    - unlike the native op it properly deals with only the selection, but also goes recursively over it to deal with linked assets of assets
      - whereas the native `make_local` would have to be run with the ALL argument, which would then affect ALL linked id types in the entire blend file

  - add RemoveAssemblyAsset tool
    - by default it removes the assembly empty + instance collection, if it no longer has any other users (such as other assemblies using the same instance collection) 
    - for local assets, it can optionalyl completely remove the entire asset and all instances of it from the file
      - naturally, this then removes it from the asset browser too
    - for legacy assets (those created with prior versions, that didn't duplicate the original objects yet) just disassemble the asset/assembly and let the user decide if the collection objects should be removed

  - add UpdateAssetThumbnail tool
    - can be called from the 3D view's sidebar simply by selecting any local assembly asset
    - or alternatively from thee asset browser's sidebar
      - here it requires selecting the asset itself, and any object in the 3D view
 
  - expose assembly asset collection name in asset browser's sidebar

  - AssetBrowser Bookmarks
    - add pseudo-bookmark for LOCAL (Current File) library
      - keymapped to `ALT + ^` by default
      - when using this, MACHIN3tools will auto size thumbnails based on asset browser dimensions
      - NOTE: it's not possible to set All or Unassigned catalogs from the API
        - so instead MACHIN3tools will select the most used catalog in the file to ensure something is shown at all
        - also note, that Blender doesn't even list catalogs that exist in a file, if that file is not stored in an asset library location

    - fix some issues where the wrong library and catalog where displayed in the header

* Material Picker tool
  - support multiple 3d views and asset browsers open at the same time
    - pick/assign from any 3d view or asset browser on the workspace
  - support picking from and assigning to FONT, SURFACE and META objects

* Filebrowser tools
  - fix opening active folder in system's file browser via `O`
  - support modal thumbnail size adjustment
    - just hold down the `3` and move the mouse horizontally
    - feel free to remap to `CTRL + MIDDLEMOUSÈ` click-drag, to mirror Blender native panel scaling
    - you can disable this in addon preferences for legacy-style thumbnail size cycling using `3` and `ALT + 3` accordingly

* Group tools
  - Outliner Group mode toggle (via `1` key)
    - when group auto-naming is enabled in addon preferences, further filter the outliner to consider the group prefix and/or suffix
       - this way you can truly only have group empties show up, instead of all empties

  - CreateGroup tool
    - when un-groupable (already parented) objects are among the selection, indicate that they weren't added to the group
       - also increase fading label time when there are un-groupable objects
  - redo/simplify group naming
  
  - Groupify tool
    - stop adding _GROUP to the empty names
    - support auto-naming addon pref
      - and with it disabled keep the original empty names accordingly

* Smart Edge tool
  - support connecting lose/non-manifold verts, thanks Artem!

* Align tool
  - add workaround in 4.2 for "object loses transform on redo" [bug](https://projects.blender.org/blender/blender/issues/125335)

* Customize tool
  - in Blender 4.2, support addon installation from from extensions repo installation
     - Icon Viewer
     - LoopTools
     - Screencast Keys
  - preferences
     - enable GPU compositing
  - keymaps
    - change `curve.select_more` and `curve.select_less` keymaps to `SHIFT` + `WHEEL UP/DOWN', inline with mesh and UV selections
    - change outliner `CTFL + F` search keymap to `/`
    - in Blender 4.2 remap new Sculpt mode visibility filtering keymaps to use SHIFT mod key, thereby avoiding conflicts wth Shading and Views pies

* Modes pie
  - add Guide mesh < > Final Mesh Editor support for quick access to the addon's *Dual Mesh Edit* mode

* Snapping pie
  - fix absolute snapping exception in 4.2

* Shading pie
  - update for Eevee Next in Blender 4.2
    - None, Low, High and Ultra Presets, check tooltips for details
    - support finding and applying user-created raytrace presets
    - expose passes incl. quick access to Shadow and Ambient Occlusion
    - expose fast GI related props
    - introduce *multi props* for resolution, thickness and quality(precision)
      - these set screen-trace and fast GI props at the same time
    - add bloom and dispersion toggles
      - both are setup and then toggled via realtime compositing
    - add Volume rendering toggle
      - with volume objects present, toggle volume object filtering in the viewport
      - without volume objects the world volume (node) is toggled, or created when there is none yet
      - force world volume creation via `SHIFT` when volume objects are present, but you want to setup a world volume too
      - when enabled, expose main world volume node props
     - in MATERIAL or RENDERED Eevee shading expose new *World Shadow* and "Sun Angle" props for adjustment of HDRI based shadows
  - Cycles
     - expose bloom and dispersion toggles here too
     - same for Volume rendering
  - expose world environment props, if found
    - generic support for props named: 'Power', 'Multiply', 'Rotate Z', 'Rotation', 'Blur'
    - Easy HDRI support for props: 'Sun Strength', 'Sky Strength', 'Custom Background', 'Solid Color', 'Rotation'
  - Shade Smooth and Toggle Auto Smooth
    - in Blender 4.2 prevent unintended removal of an existing auto smooth mod caused by native Smooth operator
  - Shade Flat
      - fix fading HUD instance counter in 4.1, and ensure auto smooth removals are counted properly in 4.2
  - Shader Smooth, Shade Flat and Toggle Auto Smooth
    - fix rare exception when encountering object without active modifier
  - Blender 4.1+
    - unmark the Smooth by Angle node group asset when bringing it in from the ESSENTIALS lib
  - Bevel Shader
    - exclude CURVES, VOLUME, ARMATURE, LATTICE and META object types from bevel shader setup attempts

* Views pie
  - Smart Cam
    - by default, support perfect viewport matching
      - adjusts scene resolution ratio to match viewport region
      - matches viewport FoV
      - sets camera's *sensor width* to 72
    - can be disabled in addon preferences
    - add fading HUD
  - Next/Prev Camera tools
    - add fading HUD
  - when in camera view
    - support naming the camera
    - expose camera sensor width
    - add Depth of Field utilities
      - add CreateDoFEmpty tool
        - quickly sets up an empty as the DoF focus object and invokes translate tool, ready to snap the empty to a surface
      - add Select DoF object tool
         - select (and reveal if hidden) currently used DoF focus object

* Save pie
  - in Blender 4.2
    - ScreenCasting
      - default to ScreenCast Keys extension over SKRIBE
      - make Toggle Region op show up in screencasted operator list
    - Purge Orphans
      - preview purging, by invoking the tool with `SHIFT` key pressed
    - fix .stl import/export due to API change
  - Export
    - expose custom export folders per-export type in addon preferences
      - if set, the exporter will open in theses folders, instead of in the home dir
  - Purge
    - remove empty collections, which native Blender doesn't do as long as they are on the viewlayer
  - Clean out .blend file  
    - remove node groups explicitly now, otherwise there may be left over ones, IF they are still marked as asset or fake user
    - update custom brush removal in Blender 4.2
     - remove libraries too
    - disable `use_scene_world` and `use_scene_lights`
    - update poll to reflect all the data types that are to be removed

* Tools pie
  - add annotate line tool
  - with active annotation tool
    - add Show/Hide Annotations tool
      - hides and reveals annotation layers
        - remembers previously hidden layers and only reveals those, that were previously visible
    - expose surface placement as buttons, not as list
  - bring back BoxCutter and HardOps support due to popular demand
   - bring back SurfaceDraw tool (previously in the Modes pie)
     - by default disabled in the addon preferences

* Workspace pie
  - in Blender 4.2, support Blender 'Icon Viewer' addon installation from extensions repo
    - it's exposed in the addon preferences
  - when syncing viewports from one workspace to another, sync `shading.use_compositor` and `shading.render_pass` too now

* Modes pie
  - prevent initiating Surface Slide, when mesh has shapekeys
  -  prevent rare exception when trying to sync tools

* addon preferences
  - Keymaps
    - in Blender 4.2, point out Shading pie and Views pie conflicts, due to new native Page Up/Down keymappings for Sculpt mode visibility filtering
      - expose these keymappins for easy remapping, if desired
    - Restore Missing Keymaps tool
      - add debug output and print to the system keymap which keymap items have been missing and now restored
    - fix potential exception 


# 1.9
> 2024-05-23

* MaterialPicker tool
  - add `RIGHTMOUSE` keymap
    - for now disabled by default, so please enable manually in addon prefs
    - if you use `RIGHTMOUSE` for the context menu, you can add a mod key in the MACHIN3tools keymap prefs for RMB-material-picking/assigning
    - I highly recommend you try this, IMO it's a game changer
  - the tool is only active on views that show materials: MATERIAL shading, RENDERED shading, and SOLID shading IF MATERIAL is chosen as the `color_type`
    - NOTE: in SOLID shading make use of the Colorize Materials tool in the Shading pie, if all your materials show as white
  - the tool existing in 3 *modes*: PICK, ASSIGN, ASSIGN_FROM_ASSETBROWSER
    - which one of these are available, depends on presence of material editor, asset browser, object or face selection
    - for instance, without a material editor or asset browser on the workspace, but with an object selection present, the tool will invoke into ASSIGN mode automatically
  - with an object or face selection present, support clearing materials using `X`
  - when appending material from assetbrowser attempt to set the material's viewport color
  - support assigning material from asset browser to entire object selection using `ALT`
    - as opposed to just the object the mouse is over via `LEFTMOUSE`
  - in the HUD
    - try to draw picked or to-be-assigned material's color under its name, fetched from the *Base Color* input of the last node
    - in object mode list objects that are to be assigned a material and lightly draw object wires
    - in edit mode indicate if material is to be assigned to face selection
  - fix button not appearing in RENDERED viewport (even though enabled in addon prefs)

* Filebrowser tools, Assetbrowser tools, AssetBrowser Bookmarks, Toggle Region tool
  - support asset browser `display_type` cycling + storage
    - NOTE: this is not natively exposed in the Blender UI, but internally the asset browser is still just a Filebrowser in Blender, and so the `display_type` can still be changed
    - cycle between display types:
      - THUMBNAIL
      - LIST_VERTICAL
      - LIST_HORIZONTAL
  - use the `2` key, just as in the Filebrowser (same keymap item in fact) for asset browser `display_type` cycling
  - use previously unused (in asset browser) `4` keymap to cycle asset import method now
  - also draw button to cycle through Assetbrowser `display_types` in asset browser header

* Shading pie
  - 4.1 Auto Smooth
    - expose and make the auto smooth angle accessible, even on meshes with custom normals
    - expose setting in addon prefs to keep Auto Smooth mod expanded in mod stack, not collapsed
    - if not found itn he file already, append *Smooth by Angle* nodegroup from ESSENTIALS lib, without relying native op
    - when opening the pie look for invalid auto smooth mod and remove it
      - Blender can *sometimes* create these, especially when pasting or appending objects from legacy files
      - terminal will complain about missing *Angle* or *Ignore Sharps* inputs in that case
  - in SOLID shading with MATERIAL `color_type` chosen, expose active object's active material's viewport color
   - support wireframe toggling and wireframe opacity adjustment in SCULPT mode
  - BevelShader setup
    - prevent exception when materials without node_tree are encounted, like Blender's Fur Material
  - Shade Smooth tool
    - update description to mention sharp edges are based on operator prop, not auto smooth angle any longer

* Modes pie
  - support EDIT_CURVES + SCULPT_CURVES modes
  - disable "SurfaceDraw"-pseudo-mode, use Annotate tools from tools pie instead!

* Tools pie
  - add annotate buttons at the bottom
  - remove out Hops/BC buttons, I don't think anybody uses the pie for these?
  - simplify HyperCursor / Select Box alternation
    - this now allows easy switching from HC to annotating, and back
    - avoid always force-enabling HC gizmos, when switching into HC tool too

* Workspace pie
  - add Geo Nodes workspace to bottom left

* SelectHierachy tool
  - support selecting geo nodes mod objects

* ToggleSmooth tool
  - use `SHIFT + TAB` as the default on Windows

* ApplyTransform tool
  - ensure object has data block, so transform can actually be applied

* addon preferences
  - mention Bevel Shader in Render tools description
    - it is exposed through the Shading pie, but enabled through the Render tools
  - add ResetKeymaps and RestoreKeymaps buttons in keymaps tab IF there are user modified keymaps or missingkeymaps (due to user removal, accidental or not)
  - improve how keymap items are drawn

* Customize tool
  - M3 theme
    - define compliant colors for Attribute Editor/Spreadsheet space
    - use fully transparent color for front-facing face orientation color
    - lower the alpha of the back-facing face orientation color (red)
  - overlays
    - when the M3 thme is being installed enable the face orientation overlays
  - startup file
    - set (annotate) stroke placement to SURFACE and set eraser size to 50px
  - keymaps
    - disable `node.select` keymappings in *Node Tool: Select Box* keymap
    - in 2.7x keymap
      - set `node.select` keymappings in *Node Editor* keymap from `RIGHTMOUSE` to `LEFGMOUSE` using `PRESS` events
      - this allows for additive and subtractive node selection using `SHIFT + LMB` without delay
  - system
    - enable experimental asset debug info


# 1.8
> 2024-03-22


## DeusEx

* SetupGroupGizmos tool
  - add option to lock axes, that don't carry a gizmo
    - this then allows for easy and lazy group rotation using the native op, without having to pick the right axis, and even with the rotation gizmo(s) disabled
    - disable locking via `R` or `L` keys


## Prime <sup>previously Standard</sup>

* Assetbrowser tools
  - add Assetbrowser Bookmarks
    - draw buttons for 10 bookmarks in the asset browser header
    - support jumping to library/catalog via click, saving via `SHIFT` click, and clearing bookmarks via `CTRL` click
      - see tooltips
    - support jumping to library/catalog via new `ALT + 0` to `ALT + 0` keymaps
    - bookmarks store and recall library, catalog and thumbnail size
    - bookmarks are stored on disk in `assetbrowser_bookmarks.json` in Blender's config folder
  - with the catalog sidebar closed, display the library and catalog in the asset browser header
  - support maintaining bookmarks, across Library renames (Blender restart required)
  - NOTE: you can't bookmark any catalog in the 'Current File' library
    - and you can't bookmark any library's 'Unassigned' catalog either

* Shading pie
  - BevelShader
    - support toggling it per-object
    - add arrow buttons to increase or decrease the global or per-object radius
      - halve and double the curretn value by default
      - with SHIFT held down, do -25% or +33% instead for smaller adjustments
  - Smooth, Flat, ToggleAutoSmooth tools
    - redo them completely, and maintain the same look and UX in 4.1 as before
    - in Blender 4.1
      - support auto smooth toggling by adding/removing geo node mod
        - sort it at the end of the stack, but before mirror and array mods
        - support intanced objects
      - support Auto Smooth for CURVE objects
    - support SURFACE objects in object mode (Blender does too, so why not)
    - properly deal with hidden children and mod objects when in local view and when either or both are included in a Smooth or Flat shading operation
    - when shading Smooth, optionally (but by default) enable Auto Smooth for objects carrying boolean mods
    - when shading Smooth with `ALT` pressed, sharpen edges via new operator angle property, not via a mesh's auto smooth angle prop as before
    - when Flat shading with `ALT` pressed to clear sharps, seams, etc, also disable Auto Smooth, if enabled, or present
    - limit options, that are exposed in redo panel, depending on context, hide what doesn't apply
    - when Flat shading and removing creases, make option, that avoids removal of creases while subd mods with `use_crease` are present, work per-object not globally or entire selection
    - add object mode fading HUD summarizing the shading changes
  - display Clear Custom Normals op, independently of Auto Smooth being enabled in 4.1
    - neither custom normals nor sharp edges require Auto Smooth anymore

* MaterialPicker tool
  - support fetching materials from and assigning them to CURVE objects

* SelectHierarchy tool
  - indicate number of hidden parents/children in fading HUD

* Group Add/Remove tools
  - add little fading HUD to visually confirm what happened

* ToggleRegion tool
  - avoid exception when library stored asset browser settings, is no longer registered

* Thread, ToggleSmooth and QuadSphere tools
  - deal with Auto Smooth changes in 4.1

* CreateAssemblyAsset tool
  - fix issues caused by 1.7's change to UUID based catalog storage

* Modes pie
  - Surface Slide tool
    - support instanced meshes
  - avoid exception when trying to mode change a linked object with library override

* addon preferences
  - add GetSupport tool, placed at the top of the addon prefs
  - add custom updater 
    - NOTE: since it's only introduced now in 1.8, it will only be of use for upcoming releases, so can't be used to install this very  1.8 update yet
    - allows for very easy addon update installation from .zip file, and from inside of Blender, instead of manually from the file browser
    - finds matching .zip file(s) in home and Downloads folder
    - allows selecting one of them them or manually selecting a file in any other location
    - extracts the file to a temporary location, and installs update when quitting Blender
    - like a manual update installation from the filebrowser, this maintains previous addon settings and custom keys
    - see installation instructions for details  

* Customize tool
  - tweak M3 theme
    - adjust to edit mode color changes in 4.1
    - make crease edges green
  - when customizing the startup file, while the Shading pie has been activated, disable native cursor display and activate custom cursor and object axes drawing instead
  - fix issues modifying keymap in 4.1
  - add hidden Toolbar Popup keymaps
    - set Annotate to D
    - set Annotate Erase to E
    - without deliberately creating these keymaps, the default keymaps will change depending on the active tool, now they are consistent
  - invert Transform Modal Map's proportional editing keymaps, so increasing the size is done by scrolling up and decreasing by scrolling down

------------------------------------------------------------------------------------------------------------------------------------------------
