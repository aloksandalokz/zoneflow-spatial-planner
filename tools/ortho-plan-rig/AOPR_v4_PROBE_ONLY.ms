/* AOPR v4 standalone Corona probe. No rig/UI dependency. */

global AOPR_VERSION = "4.0-codex"
global AOPR_GREEN = color 0 255 0
global AOPR_LOG_LINES = #()

fn AOPR_Log_Reset = (AOPR_LOG_LINES = #())
fn AOPR_Log msg = (local s = msg as string; append AOPR_LOG_LINES s; format "%\n" s; s)
fn AOPR_IsValidNode n = ((n != undefined) and (isValidNode n))
fn AOPR_SafeGet obj propName = (local out = undefined; if obj != undefined do try(if isProperty obj propName do out = getProperty obj propName)catch(); out)
fn AOPR_WriteLog path = (local f = createFile path; if f == undefined then false else (for line in AOPR_LOG_LINES do format "%\n" line to:f; close f; true))

fn AOPR_CreateCoronaCamera camName =
(
    local cam = undefined
    try (cam = CoronaCam()) catch()
    if cam != undefined do
    (
        try (cam.targeted = false) catch()
        try (cam.name = camName) catch()
        try (cam.wirecolor = AOPR_GREEN) catch()
    )
    cam
)

fn AOPR_ProjectionStateFromViewport cam =
(
    if not (AOPR_IsValidNode cam) then #unknown
    else
    (
        local oldType = undefined
        local oldCam = undefined
        local result = #unknown
        try (oldType = viewport.getType()) catch()
        try (oldCam = viewport.getCamera()) catch()
        try
        (
            viewport.setCamera cam
            redrawViews()
            if viewport.isPerspView() then result = #perspective else result = #orthographic
        )
        catch()
        try
        (
            if AOPR_IsValidNode oldCam then viewport.setCamera oldCam
            else if oldType != undefined do viewport.setType oldType
            redrawViews()
        )
        catch()
        result
    )
)

fn AOPR_DumpCoronaProbe path =
(
    AOPR_Log_Reset()
    AOPR_Log ("AOPR Corona Probe - " + AOPR_VERSION)
    AOPR_Log ("3ds Max version: " + (maxVersion() as string))
    local cam = AOPR_CreateCoronaCamera "AOPR_PROBE_TEMP"
    if cam == undefined then
    (
        AOPR_Log "FAIL: CoronaCam() constructor unavailable."
        AOPR_WriteLog path
        false
    )
    else
    (
        AOPR_Log ("classOf: " + ((classOf cam) as string))
        AOPR_Log ("superClassOf: " + ((superClassOf cam) as string))
        AOPR_Log ("viewport projection initially: " + ((AOPR_ProjectionStateFromViewport cam) as string))
        local props = #()
        try (props = getPropNames cam) catch()
        AOPR_Log ("property count: " + (props.count as string))
        for p in props do
        (
            local value = AOPR_SafeGet cam p
            local cls = if value == undefined then "undefined" else ((classOf value) as string)
            AOPR_Log ((p as string) + " | " + cls + " | " + (value as string))
        )
        try (delete cam) catch()
        AOPR_WriteLog path
    )
)

local probePath = (getDir #userScripts) + "\\AOPR_CoronaProbe.txt"
local probeOK = AOPR_DumpCoronaProbe probePath
if probeOK then messageBox ("Corona probe completed.\n\n" + probePath) title:"AOPR Corona Probe"
else messageBox ("Corona probe FAILED.\n\nLog: " + probePath) title:"AOPR Corona Probe"
