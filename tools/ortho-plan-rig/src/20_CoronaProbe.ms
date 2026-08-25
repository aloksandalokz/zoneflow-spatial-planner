/* AOPR 20_CoronaProbe.ms - deliberately independent of rig logic */

global AOPR_CORONA_CAMERA_CLASS = undefined

fn AOPR_FindCoronaCameraClass =
(
    if AOPR_CORONA_CAMERA_CLASS != undefined then AOPR_CORONA_CAMERA_CLASS
    else
    (
        local classes = #()
        local exactMatch = undefined
        local fallbackMatch = undefined

        try (classes = camera.classes) catch (classes = #())

        for cls in classes do
        (
            local n = toLower (cls as string)

            if n == "coronacam" do exactMatch = cls

            if fallbackMatch == undefined do
            (
                local hasCorona = (findString n "corona") != undefined
                local looksCamera = ((findString n "cam") != undefined) or ((findString n "camera") != undefined)
                if hasCorona and looksCamera do fallbackMatch = cls
            )
        )

        local found = if exactMatch != undefined then exactMatch else fallbackMatch

        if found != undefined do
        (
            try (pluginManager.loadClass found) catch()
            AOPR_CORONA_CAMERA_CLASS = found
        )

        found
    )
)

fn AOPR_CreateCoronaCamera camName =
(
    local cam = undefined
    local cls = AOPR_FindCoronaCameraClass()

    if cls != undefined do
    (
        try (pluginManager.loadClass cls) catch()
        try (cam = cls()) catch (cam = undefined)
    )

    if AOPR_IsValidNode cam do
    (
        try (cam.targeted = false) catch()
        try (cam.name = camName) catch()
        try (cam.wirecolor = AOPR_GREEN) catch()
    )
    cam
)

fn AOPR_CoronaAvailable =
(
    local c = AOPR_CreateCoronaCamera "AOPR_CORONA_AVAILABILITY_TEST"
    local ok = AOPR_IsValidNode c
    if ok do try (delete c) catch()
    ok
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

    local cls = AOPR_FindCoronaCameraClass()
    AOPR_Log ("Corona camera MAXClass: " + (cls as string))

    if cls == undefined do
    (
        AOPR_Log "FAIL: No Corona camera class found in camera.classes."
        AOPR_Log "--- REGISTERED CAMERA CLASSES ---"
        local allClasses = #()
        try (allClasses = camera.classes) catch()
        for c in allClasses do AOPR_Log (c as string)
        AOPR_WriteLog path
        return false
    )

    local cam = AOPR_CreateCoronaCamera "AOPR_PROBE_TEMP"
    if not (AOPR_IsValidNode cam) then
    (
        AOPR_Log "FAIL: Corona camera MAXClass was found, but instantiation failed."
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
            local clsValue = if value == undefined then "undefined" else ((classOf value) as string)
            AOPR_Log ((p as string) + " | " + clsValue + " | " + (value as string))
        )

        AOPR_Log "--- PROJECTION CANDIDATES ---"
        for p in (AOPR_CoronaCandidateProjectionProps cam) do AOPR_Log (p as string)
        AOPR_Log "--- ORTHO SIZE CANDIDATES ---"
        for p in (AOPR_CoronaCandidateOrthoSizeProps cam) do AOPR_Log (p as string)

        try (delete cam) catch()
        AOPR_WriteLog path
        true
    )
)
