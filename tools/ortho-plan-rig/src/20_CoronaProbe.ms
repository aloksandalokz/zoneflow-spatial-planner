/* AOPR 20_CoronaProbe.ms - deliberately independent of rig logic */

fn AOPR_CoronaAvailable =
(
    local ok = false
    try
    (
        local c = CoronaCam()
        ok = (c != undefined)
        if c != undefined do delete c
    )
    catch()
    ok
)

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

fn AOPR_CoronaCandidateProjectionProps cam =
(
    local out = #()
    local props = #()
    try (props = getPropNames cam) catch()
    for p in props do
    (
        local s = toLower (p as string)
        if ((findString s "projection") != undefined) or ((findString s "proj") != undefined) or ((findString s "ortho") != undefined) do
            append out p
    )
    out
)

fn AOPR_CoronaCandidateOrthoSizeProps cam =
(
    local out = #()
    local props = #()
    try (props = getPropNames cam) catch()
    for p in props do
    (
        local s = toLower (p as string)
        local ortho = (findString s "ortho") != undefined
        local sizeish = ((findString s "size") != undefined) or ((findString s "width") != undefined) or ((findString s "view") != undefined)
        if ortho and sizeish do append out p
    )
    out
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
        AOPR_Log "--- PROPERTIES ---"
        for p in props do
        (
            local value = AOPR_SafeGet cam p
            local cls = if value == undefined then "undefined" else ((classOf value) as string)
            AOPR_Log ((p as string) + " | " + cls + " | " + (value as string))
        )

        AOPR_Log "--- PROJECTION CANDIDATES ---"
        for p in (AOPR_CoronaCandidateProjectionProps cam) do AOPR_Log (p as string)
        AOPR_Log "--- ORTHO SIZE CANDIDATES ---"
        for p in (AOPR_CoronaCandidateOrthoSizeProps cam) do AOPR_Log (p as string)

        try (delete cam) catch()
        AOPR_WriteLog path
    )
)
