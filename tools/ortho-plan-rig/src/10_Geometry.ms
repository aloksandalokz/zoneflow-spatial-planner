/* AOPR 10_Geometry.ms */

fn AOPR_BBoxWorld obj =
(
    local bb = undefined
    if AOPR_IsValidNode obj do try (bb = nodeGetBoundingBox obj (matrix3 1)) catch()
    bb
)

fn AOPR_BBoxInCamera obj cam =
(
    local bb = undefined
    if (AOPR_IsValidNode obj) and (AOPR_IsValidNode cam) do
        try (bb = nodeGetBoundingBox obj cam.transform) catch()
    bb
)

fn AOPR_WorldCenter obj =
(
    local bb = AOPR_BBoxWorld obj
    if bb == undefined then undefined else (bb[1] + bb[2]) / 2.0
)

fn AOPR_WorldMaxDimension obj =
(
    local bb = AOPR_BBoxWorld obj
    if bb == undefined then undefined
    else
    (
        local e = bb[2] - bb[1]
        max (abs e.x) (max (abs e.y) (abs e.z))
    )
)

fn AOPR_ViewAxes viewName =
(
    case viewName of
    (
        #front: #([0,1,0],  [0,0,1])
        #back:  #([0,-1,0], [0,0,1])
        #left:  #([1,0,0],  [0,0,1])
        #right: #([-1,0,0], [0,0,1])
        #top:   #([0,0,-1], [0,1,0])
        default: undefined
    )
)

fn AOPR_MakeCameraTM center viewDir upDir distance =
(
    local forward = normalize viewDir
    local zAxis = normalize (-forward)
    local xAxis = normalize (cross upDir zAxis)
    local yAxis = normalize (cross zAxis xAxis)
    local pos = center - (forward * distance)
    matrix3 xAxis yAxis zAxis pos
)

fn AOPR_SetCameraDirection cam obj viewName =
(
    if not (AOPR_IsValidNode cam) then #(false,"invalid camera")
    else if not (AOPR_IsValidNode obj) then #(false,"invalid grid")
    else
    (
        local axes = AOPR_ViewAxes viewName
        if axes == undefined then #(false,"unknown view")
        else
        (
            local center = AOPR_WorldCenter obj
            local d = AOPR_WorldMaxDimension obj
            if center == undefined then #(false,"cannot read grid bounds")
            else
            (
                if (d == undefined) or (d < 1.0) do d = 100.0
                local distance = (d * 2.0) + 100.0
                try (cam.targeted = false) catch()
                cam.transform = AOPR_MakeCameraTM center axes[1] axes[2] distance
                #(true,"camera transform set")
            )
        )
    )
)

fn AOPR_CenterCameraOnObject cam obj =
(
    local bb = AOPR_BBoxInCamera obj cam
    if bb == undefined then #(false,"camera-space bounds failed")
    else
    (
        local cx = (bb[1].x + bb[2].x) / 2.0
        local cy = (bb[1].y + bb[2].y) / 2.0
        local tm = cam.transform
        cam.pos = cam.pos + (tm.row1 * cx) + (tm.row2 * cy)
        #(true,"camera centered")
    )
)

fn AOPR_ProjectedWidth cam obj =
(
    local bb = AOPR_BBoxInCamera obj cam
    if bb == undefined then undefined else abs (bb[2].x - bb[1].x)
)

fn AOPR_ProjectedHeight cam obj =
(
    local bb = AOPR_BBoxInCamera obj cam
    if bb == undefined then undefined else abs (bb[2].y - bb[1].y)
)
