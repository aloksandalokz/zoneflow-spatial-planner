/*
    Alok VP Isolate - floating palette launcher
    Autodesk 3ds Max 2026

    Keep this file beside Alok_Viewport_Isolate.py and AlokViewportIsolate.dll.
*/
(
    local thisFile = getSourceFileName()
    local thisDir = getFilenamePath thisFile
    local pyFile = thisDir + "Alok_Viewport_Isolate.py"

    if doesFileExist pyFile then
    (
        python.ExecuteFile pyFile
    )
    else
    (
        messageBox ("Cannot find:\n" + pyFile) title:"VP ISOLATE"
    )
)
