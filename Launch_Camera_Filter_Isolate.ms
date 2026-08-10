/* Camera Filter Isolate - 3ds Max 2026 */
(
    local thisFile = getSourceFileName()
    local thisDir = getFilenamePath thisFile
    local pyFile = thisDir + "Camera_Filter_Isolate.py"

    if doesFileExist pyFile then
        python.ExecuteFile pyFile
    else
        messageBox ("Cannot find:\n" + pyFile) title:"CAMERA FILTER"
)
