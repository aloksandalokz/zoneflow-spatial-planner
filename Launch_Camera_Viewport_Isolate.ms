/*
    CAMERA VIEW ISOLATE
    3ds Max 2026

    Keep this file beside:
      Camera_Viewport_Isolate.py
      CameraViewportIsolate.dll
*/
(
    local thisFile = getSourceFileName()
    local thisDir = getFilenamePath thisFile
    local pyFile = thisDir + "Camera_Viewport_Isolate.py"

    if doesFileExist pyFile then
        python.ExecuteFile pyFile
    else
        messageBox ("Cannot find:\n" + pyFile) title:"CAMERA VIEW ISOLATE"
)
