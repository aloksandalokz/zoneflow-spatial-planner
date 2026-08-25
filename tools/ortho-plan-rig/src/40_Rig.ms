/* AOPR 40_Rig.ms */

fn AOPR_GetOrCreateCamera camName viewName =
(
    local cam = getNodeByName camName exact:true
    if (AOPR_IsValidNode cam) and (AOPR_IsRigNode cam) then
    (
        try (cam.targeted = false) catch()
        cam.wirecolor = AOPR_GREEN
        cam
    )
    else
    (
        if AOPR_IsValidNode cam do camName = uniqueName (camName + "_RIG")
        cam = AOPR_CreateCoronaCamera camName
        if AOPR_IsValidNode cam do AOPR_TagNode cam viewName:(viewName as string)
        cam
    )
)

fn AOPR_FitCamera cam gridObj viewName =
(
    local r = AOPR_SetCameraDirection cam gridObj viewName
    if not r[1] then r
    else
    (
        r = AOPR_CenterCameraOnObject cam gridObj
        if not r[1] then r
        else
        (
            local width = AOPR_ProjectedWidth cam gridObj
            if (width == undefined) or (width <= 0.0) then #(false,"projected width invalid")
            else if not (AOPR_SetCoronaOrthographic cam) then #(false,"Corona orthographic mode failed")
            else if not (AOPR_SetCoronaOrthoWidth cam width) then #(false,"Corona Ortho View Size failed")
            else
            (
                cam.wirecolor = AOPR_GREEN
                redrawViews()
                #(true,("fit width = " + (width as string)))
            )
        )
    )
)

fn AOPR_BuildOrFit camName gridObj viewName =
(
    if not (AOPR_IsValidNode gridObj) then #(false,"pick a grid object")
    else
    (
        local cam = AOPR_GetOrCreateCamera camName viewName
        if not (AOPR_IsValidNode cam) then #(false,"CoronaCam() creation failed")
        else AOPR_FitCamera cam gridObj viewName
    )
)

fn AOPR_MakeTopDuplicates topCam =
(
    if not (AOPR_IsValidNode topCam) then #(false,"top camera does not exist")
    else
    (
        local names = #(
            "1. clip hanging structure",
            "2. clipp ceiling 1",
            "3. clipp ceiling 2",
            "4. clip ceiling 3"
        )
        local made = 0
        for nm in names do
        (
            local old = getNodeByName nm exact:true
            if (AOPR_IsValidNode old) and (AOPR_IsRigNode old) do delete old
            local c = copy topCam
            c.name = if getNodeByName nm exact:true == undefined then nm else uniqueName nm
            c.wirecolor = AOPR_GREEN
            AOPR_TagNode c viewName:"topClip"
            made += 1
        )
        #(true,("created " + (made as string) + " top duplicates"))
    )
)
